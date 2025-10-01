import os
import sys
import subprocess
import glob
from datetime import datetime, timezone

def run_command(command, cwd=None, check=True):
    """Führt einen Shell-Befehl aus und gibt bei Fehlern eine detaillierte Ausgabe."""
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"🔥 Fehler beim Ausführen von: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return Code: {e.returncode}", file=sys.stderr)
        print(f"STDOUT: {e.stdout}", file=sys.stderr)
        print(f"STDERR: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def main():
    """
    Hauptlogik zum Veröffentlichen der Dokumentation.
    1. Sucht nach Markdown-Dateien.
    2. Klont das Doku-Repository.
    3. Generiert für jede Datei einen Hugo-Header und fügt den Inhalt an.
    4. Committet und pusht die Änderungen.
    """
    # --- 1. Umgebungsvariablen und Konfiguration abrufen ---
    doc_source_dir = os.environ.get("DOC_SOURCE_DIR", "deployments/documentation")
    docs_repo_url = os.environ.get("DOCS_REPO_URL")
    docs_repo_token = os.environ.get("DOCS_REPO_TOKEN")
    ci_project_name = os.environ.get("CI_PROJECT_NAME")
    ci_server_host = os.environ.get("CI_SERVER_HOST")

    if not all([docs_repo_url, docs_repo_token, ci_project_name, ci_server_host]):
        print("🔥 Fehler: Eine oder mehrere erforderliche Umgebungsvariablen fehlen.", file=sys.stderr)
        print("(DOCS_REPO_URL, DOCS_REPO_TOKEN, CI_PROJECT_NAME, CI_SERVER_HOST)", file=sys.stderr)
        sys.exit(1)

    clone_dir = "docs_repo"

    # --- 2. Überprüfung der Quelldateien ---
    source_files = glob.glob(os.path.join(doc_source_dir, "*.md"))
    if not source_files:
        print(f"ℹ️ Keine .md-Dateien in '{doc_source_dir}' gefunden. Überspringe Dokumentations-Update.")
        sys.exit(0)

    print(f"✔️ {len(source_files)} Markdown-Datei(en) gefunden, die verarbeitet werden.")

    # --- 3. Git-Setup und Klonen ---
    print("Richte Git ein und klone das Dokumentations-Repository...")
    clean_repo_url = docs_repo_url.replace("https://", "")
    clone_url_with_token = f"https://gitlab-ci-token:{docs_repo_token}@{clean_repo_url}"

    run_command(["git", "config", "--global", "user.email", f"ci-bot@{ci_server_host}"])
    run_command(["git", "config", "--global", "user.name", "GitLab CI Documentation Bot"])
    run_command(["git", "clone", clone_url_with_token, clone_dir])

    # --- 4. Markdown-Dateien verarbeiten ---
    target_doc_dir = os.path.join(clone_dir, "site", "content", "aac-services", ci_project_name)
    os.makedirs(target_doc_dir, exist_ok=True)

    print(f"Verarbeite alle .md-Dateien und schreibe sie nach '{target_doc_dir}'...")
    for source_file_path in source_files:
        source_basename = os.path.basename(source_file_path)
        file_title = os.path.splitext(source_basename)[0].replace('-', ' ').capitalize()
        target_file_path = os.path.join(target_doc_dir, source_basename)

        print(f"  -> Erstelle '{target_file_path}' mit Hugo-Header...")

        # Zeitstempel für den Header
        now_utc = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Hugo Front Matter (Header) erstellen
        hugo_header = f"""---
title: "{ci_project_name}: {file_title}"
date: {now_utc}
lastmod: {now_utc}
draft: false
description: "Automatisch generierte Dokumentation für {ci_project_name} - {file_title}."
---

"""
        # Originalinhalt lesen
        with open(source_file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Header und Inhalt in die Zieldatei schreiben
        with open(target_file_path, 'w', encoding='utf-8') as f:
            f.write(hugo_header)
            f.write(original_content)

        # Datei zum Git-Staging hinzufügen
        run_command(["git", "add", target_file_path], cwd=clone_dir)

    # --- 5. Änderungen committen und pushen ---
    print("Überprüfe auf Änderungen...")
    # Prüfen, ob es gestagete Änderungen gibt
    diff_check = run_command(["git", "diff", "--staged", "--quiet"], cwd=clone_dir, check=False)

    if diff_check.returncode != 0:
        print("Änderungen gefunden. Erstelle Commit und pushe...")
        commit_message = f"docs: Aktualisiere Service-Dokumentation für {ci_project_name}"
        run_command(["git", "commit", "-m", commit_message], cwd=clone_dir)
        run_command(["git", "push", "origin", "main"], cwd=clone_dir)
        print("✔️ Dokumentation erfolgreich aktualisiert.")
    else:
        print("ℹ️ Keine Änderungen an der Dokumentation festgestellt.")

if __name__ == "__main__":
    main()
import os
import sys
import subprocess
import glob
from datetime import datetime, timezone

def run_command(command, cwd=None, check=True):
    """Führt einen Shell-Befehl aus und gibt bei Fehlern eine detaillierte Ausgabe."""
    print(f"Executing: {' '.join(command)}")
    # Wenn ein Arbeitsverzeichnis (cwd) angegeben ist, wird es im Log angezeigt
    if cwd:
        print(f"  (in directory: {cwd})")
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
        print(f"STDOUT:\n{e.stdout}", file=sys.stderr)
        print(f"STDERR:\n{e.stderr}", file=sys.stderr)
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
    docs_repo_url_full = os.environ.get("DOCS_REPO_URL")
    docs_repo_token = os.environ.get("CI_GITLAB_TOKEN_GLOBAL_FESER") # Beispiel, anpassen falls nötig
    ci_project_name = os.environ.get("CI_PROJECT_NAME", "Unbekanntes Projekt")
    ci_server_host = os.environ.get("CI_SERVER_HOST")

    if not docs_repo_url_full or not docs_repo_token:
        print("🔥 Fehler: DOCS_REPO_URL oder der Token sind nicht gesetzt.", file=sys.stderr)
        sys.exit(1)

    # Authentifizierte URL zusammenbauen
    # Beispiel: https://gitlab.int.fam-feser.de/documentation/aac-iac-documentation.git
    # wird zu: https://gitlab-ci-token:TOKEN@gitlab.int.fam-feser.de/...
    auth_repo_url = docs_repo_url_full.replace("https://", f"https://gitlab-ci-token:{docs_repo_token}@")

    # Verzeichnis, in das geklont wird
    docs_repo_dir = 'docs_repo'

    # --- 2. Markdown-Dateien im Quellverzeichnis finden ---
    source_files = glob.glob(os.path.join(doc_source_dir, '*.md'))
    if not source_files:
        print("Keine .md-Dateien im Verzeichnis gefunden. Beende den Vorgang.")
        sys.exit(0)
    print(f"✔️ {len(source_files)} Markdown-Datei(en) gefunden, die verarbeitet werden.")

    # --- 3. Git einrichten und das Dokumentations-Repository klonen ---
    print("Richte Git ein und klone das Dokumentations-Repository...")
    run_command(["git", "config", "--global", "user.email", f"ci-bot@{ci_server_host}"])
    run_command(["git", "config", "--global", "user.name", "GitLab CI Documentation Bot"])
    run_command(["git", "clone", auth_repo_url, docs_repo_dir])

    # --- 4. Dateien verarbeiten und in das geklonte Repository schreiben ---
    # Zielverzeichnis im Doku-Repo
    # Passe 'aac-services/{{service_name}}' bei Bedarf an
    target_content_dir = os.path.join(docs_repo_dir, 'site', 'content', 'aac-services', ci_project_name)
    os.makedirs(target_content_dir, exist_ok=True)
    
    files_to_add = []

    print(f"Verarbeite alle .md-Dateien und schreibe sie nach '{target_content_dir}'...")
    for source_file_path in source_files:
        file_name = os.path.basename(source_file_path)
        file_title = os.path.splitext(file_name)[0].replace('_', ' ').title()
        
        # Zielpfad für die neue Datei
        destination_file_path = os.path.join(target_content_dir, file_name)
        
        # Hugo-Header erstellen
        now_utc = datetime.now(timezone.utc).isoformat()
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

        # Neue Datei mit Header und Inhalt schreiben
        print(f"-> Erstelle '{destination_file_path}' mit Hugo-Header...")
        with open(destination_file_path, 'w', encoding='utf-8') as f:
            f.write(hugo_header + original_content)
        
        # Pfad für 'git add' relativ zum Repo-Verzeichnis merken
        relative_path_for_git = os.path.relpath(destination_file_path, docs_repo_dir)
        files_to_add.append(relative_path_for_git)

    # --- 5. Änderungen committen und pushen (WICHTIG: im richtigen Verzeichnis!) ---
    if not files_to_add:
        print("Keine neuen oder geänderten Dateien zum Committen vorhanden.")
        sys.exit(0)

    print("Füge Änderungen zum Git-Index hinzu...")
    # Alle neuen/geänderten Dateien auf einmal hinzufügen
    run_command(["git", "add"] + files_to_add, cwd=docs_repo_dir)

    print("Erstelle Commit...")
    commit_message = f"docs: Aktualisiere Dokumentation für {ci_project_name}"
    # Prüfen, ob es überhaupt Änderungen gibt, um einen leeren Commit zu vermeiden
    status_result = run_command(["git", "status", "--porcelain"], cwd=docs_repo_dir)
    if not status_result.stdout:
        print("Keine Änderungen zum Committen erkannt. Überspringe Commit und Push.")
    else:
        run_command(["git", "commit", "-m", commit_message], cwd=docs_repo_dir)
        print("Pushe Änderungen zum Repository...")
        run_command(["git", "push"], cwd=docs_repo_dir)
        print("✔️ Dokumentation erfolgreich veröffentlicht!")


if __name__ == "__main__":
    main()
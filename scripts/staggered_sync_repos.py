import os
import sys
import subprocess
import time

# --- Konfiguration ---

# Passe diesen Pfad an, falls deine Repositories woanders liegen
ROOT_DIR = r'c:\Workdirektory\Sync\Coding\GitLab\aac-application-defenitions\applications'

# Die Commit-Nachricht, die für die automatischen Updates verwendet wird
COMMIT_MESSAGE = "chore: Automated sync to trigger CI pipeline"

# Die Verzögerung in Sekunden zwischen den einzelnen Pushes (3 Minuten = 180 Sekunden)
DELAY_SECONDS = 60

# --- Skriptlogik ---

def run_command(command, cwd):
    """Führt einen Shell-Befehl im angegebenen Verzeichnis aus und gibt den Return-Code zurück."""
    try:
        # Führe den Befehl aus und unterdrücke die Ausgabe, es sei denn, es gibt einen Fehler
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return result.returncode
    except subprocess.CalledProcessError as e:
        # Gib nur dann eine Fehlermeldung aus, wenn es ein echter Fehler ist
        # (z.B. kein "nothing to commit")
        if "nothing to commit" not in e.stderr and "up-to-date" not in e.stdout:
            print(f"  -> ⚠️  Befehl '{' '.join(command)}' fehlgeschlagen:", file=sys.stderr)
            print(f"  -> STDERR: {e.stderr.strip()}", file=sys.stderr)
        return e.returncode

def get_git_branch(cwd):
    """Ermittelt den aktuellen Git-Branch im Repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def main():
    """Findet alle Git-Repositories, committet und pusht Änderungen gestaffelt."""
    
    if not os.path.isdir(ROOT_DIR):
        print(f"❌ FEHLER: Das Hauptverzeichnis wurde nicht gefunden: {ROOT_DIR}", file=sys.stderr)
        return
        
    print(f"🚀 Starte den gestaffelten Sync für Repositories in: {ROOT_DIR}\n")

    # Sammle alle gültigen Git-Repositories
    repos_to_process = []
    for repo_name in os.listdir(ROOT_DIR):
        repo_path = os.path.join(ROOT_DIR, repo_name)
        if os.path.isdir(repo_path) and os.path.isdir(os.path.join(repo_path, '.git')):
            repos_to_process.append(repo_path)
    
    total_repos = len(repos_to_process)
    print(f"🔎 {total_repos} Git-Repositories gefunden, die verarbeitet werden.\n")

    for i, repo_path in enumerate(repos_to_process):
        repo_name = os.path.basename(repo_path)
        print("-" * 60)
        print(f"⚙️  Verarbeite Repository {i+1}/{total_repos}: {repo_name}")

        # 1. Prüfen, ob es überhaupt uncommittete Änderungen gibt
        if run_command(["git", "diff", "--quiet"], cwd=repo_path) == 0 and run_command(["git", "diff", "--staged", "--quiet"], cwd=repo_path) == 0:
            print("  -> ✅ Keine Änderungen gefunden. Überspringe.")
            continue

        # 2. Änderungen hinzufügen (adden)
        print("  -> Staging aller Änderungen...")
        run_command(["git", "add", "."], cwd=repo_path)

        # 3. Committen (nur wenn es etwas zu committen gibt)
        print("  -> Erstelle Commit...")
        commit_rc = run_command(["git", "commit", "-m", COMMIT_MESSAGE], cwd=repo_path)
        if commit_rc != 0:
            print("  -> ℹ️ Nichts zu committen (wahrscheinlich nur Whitespace-Änderungen oder bereits committet). Fahre fort.")

        # 4. Aktuellen Branch ermitteln
        branch = get_git_branch(repo_path)
        if not branch:
            print("  -> ❌ Konnte den aktuellen Branch nicht ermitteln. Überspringe Push.")
            continue
        
        print(f"  -> Aktueller Branch ist '{branch}'.")

        # 5. Pull mit Rebase, um Konflikte zu vermeiden
        print("  -> Führe 'git pull --rebase' aus...")
        if run_command(["git", "pull", "--rebase", "origin", branch], cwd=repo_path) != 0:
            print(f"  -> ❌ 'git pull' ist fehlgeschlagen. Bitte manuell prüfen: {repo_path}")
            continue # Zum nächsten Repo springen

        # 6. Pushen der Änderungen
        print(f"  -> Pushe Änderungen zu 'origin/{branch}'...")
        if run_command(["git", "push", "origin", branch], cwd=repo_path) == 0:
            print(f"  -> ✅ Erfolgreich gepusht!")
        else:
            print(f"  -> ❌ Push fehlgeschlagen. Bitte manuell prüfen: {repo_path}")
            continue

        # 7. Warten, außer es ist das letzte Repository
        if i < total_repos - 1:
            print(f"\n  -> 🕒 Warte {DELAY_SECONDS} Sekunden bis zum nächsten Repository...")
            time.sleep(DELAY_SECONDS)
            print("\n")

    print("-" * 60)
    print("\n✨ Alle Repositories wurden verarbeitet.")

if __name__ == "__main__":
    print("====================================================================")
    print("Dieses Skript committet und pusht Änderungen in allen Sub-Repositories")
    print("mit einer Verzögerung, um CI-Runner nicht zu überlasten.")
    print(f"Verzögerung ist auf {DELAY_SECONDS} Sekunden eingestellt.")
    print("====================================================================")
    
    response = input("\nMöchtest du mit dem Sync-Vorgang fortfahren? (ja/nein): ")
    if response.lower() in ['ja', 'j', 'yes', 'y']:
        main()
    else:
        print("Vorgang vom Benutzer abgebrochen.")

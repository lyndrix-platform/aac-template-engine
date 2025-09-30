import os
import subprocess
import gitlab
import sys

"""
.SYNOPSIS
  Klont oder aktualisiert alle Repositories aus einer bestimmten GitLab-Gruppe.
.DESCRIPTION
  Dieses Skript verbindet sich mit einer GitLab-Instanz, listet alle Projekte
  innerhalb einer definierten Gruppe auf und klont jedes Projekt in ein
  lokales Zielverzeichnis. Wenn ein Projektverzeichnis bereits existiert,
  wird stattdessen 'git pull' ausgeführt, um es zu aktualisieren.

  Die Konfiguration (GitLab-URL, Token) wird aus Umgebungsvariablen gelesen,
  um die Sicherheit zu erhöhen.
.PREREQUISITES
  - Python 3.x
  - Git muss im System-PATH installiert und verfügbar sein.
  - Die Python-Bibliothek 'python-gitlab' muss installiert sein:
    pip install python-gitlab
.SETUP
  Setze die folgenden Umgebungsvariablen vor der Ausführung:
  - GITLAB_URL: Die URL deiner GitLab-Instanz (z.B. "https://gitlab.int.fam-feser.de")
  - GITLAB_PRIVATE_TOKEN: Dein persönlicher GitLab Access Token mit 'read_repository'-Rechten.
"""

# --- Konfiguration ---
# Passe diese Werte bei Bedarf an.

# Der Pfad zur GitLab-Gruppe, aus der die Repositories geklont werden sollen.
GROUP_PATH = "aac-application-definitions"

# Das lokale Verzeichnis, in das die Repositories geklont werden sollen.
TARGET_CLONE_DIR = r"C:\Workdirektory\Sync\Coding\GitLab\aac-application-defenitions\applications"

# Gib einen spezifischen Branch an, der geklont werden soll.
# Wenn der Wert leer ist (z.B. ""), wird der Default-Branch des Repositories verwendet.
BRANCH_TO_CLONE = ""  # Z.B. "dev", "test" oder "main"

# Soll das Skript bereits existierende Repositories aktualisieren (`git pull`)?
# Wenn False, werden existierende Repositories komplett übersprungen.
UPDATE_EXISTING_REPOS = False

# --- Skriptlogik ---

def main():
    """Hauptfunktion des Skripts."""
    gitlab_url = os.getenv("GITLAB_URL")
    private_token = os.getenv("GITLAB_PRIVATE_TOKEN")

    if not all([gitlab_url, private_token]):
        print("🔥 Fehler: Die Umgebungsvariablen GITLAB_URL und GITLAB_PRIVATE_TOKEN müssen gesetzt sein.")
        sys.exit(1)

    # Stelle sicher, dass das Zielverzeichnis existiert.
    if not os.path.exists(TARGET_CLONE_DIR):
        print(f"📂 Erstelle Zielverzeichnis: {TARGET_CLONE_DIR}")
        os.makedirs(TARGET_CLONE_DIR)

    # --- Verbindung zu GitLab herstellen ---
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        gl.auth()
        print("✅ Erfolgreich bei GitLab authentifiziert.")
    except Exception as e:
        print(f"🔥 Fehler bei der GitLab-Authentifizierung: {e}")
        sys.exit(1)

    try:
        # --- Gruppe und Projekte abrufen ---
        print(f"🔍 Suche nach Gruppe '{GROUP_PATH}'...")
        group = gl.groups.get(GROUP_PATH)
        projects = group.projects.list(all=True, include_subgroups=True)
        print(f"✔️ {len(projects)} Projekte in der Gruppe (inkl. Untergruppen) gefunden.")

        # --- Projekte klonen oder aktualisieren ---
        for project in projects:
            project_path = os.path.join(TARGET_CLONE_DIR, project.path)
            print("-" * 50)

            if os.path.isdir(os.path.join(project_path, '.git')):
                if UPDATE_EXISTING_REPOS:
                    print(f"🔄 Aktualisiere '{project.name}' in '{project_path}'...")
                    try:
                        subprocess.run(["git", "pull"], cwd=project_path, check=True, capture_output=True, text=True)
                        print(f"✔️ '{project.name}' erfolgreich aktualisiert.")
                    except subprocess.CalledProcessError as e:
                        print(f"⚠️ Fehler beim Aktualisieren von '{project.name}': {e.stderr}")
                else:
                    print(f"✅ '{project.name}' existiert bereits. Überspringe.")
                    continue
            else:
                # --- KORREKTUR: HTTPS-URL mit Token verwenden statt SSH ---
                # Erstellt eine URL im Format: https://oauth2:DEIN_TOKEN@gitlab.example.com/gruppe/projekt.git
                # Dies ermöglicht das Klonen ohne SSH-Schlüssel.
                clone_url = project.http_url_to_repo.replace("https://", f"https://oauth2:{private_token}@")

                # Baue den Klon-Befehl zusammen
                clone_command = ["git", "clone"]
                if BRANCH_TO_CLONE:
                    clone_command.extend(["--branch", BRANCH_TO_CLONE])
                    print(f"⬇️ Klone Branch '{BRANCH_TO_CLONE}' von '{project.name}' nach '{project_path}'...")
                else:
                    print(f"⬇️ Klone Default-Branch von '{project.name}' nach '{project_path}'...")
                
                clone_command.extend([clone_url, project_path])

                try:
                    # Führe den zusammengesetzten Befehl aus
                    subprocess.run(clone_command, check=True, capture_output=True, text=True)
                    print(f"✔️ '{project.name}' erfolgreich geklont.")
                except subprocess.CalledProcessError as e:
                    print(f"🔥 Fehler beim Klonen von '{project.name}': {e.stderr}")

    except Exception as e:
        print(f"🔥 Ein unerwarteter Fehler ist aufgetreten: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
    print("\n✨ Skript abgeschlossen.")
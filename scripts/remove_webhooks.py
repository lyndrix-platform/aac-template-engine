import gitlab
import os

# --- Konfiguration ---
# Setze deine GitLab-URL und deinen Token als Umgebungsvariablen
# oder trage sie direkt hier ein.
# Beispiel für direkte Eingabe: GITLAB_URL = "https://gitlab.int.fam-feser.de"
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.int.fam-feser.de")
PRIVATE_TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN", "DEIN_PERSOENLICHER_ACCESS_TOKEN")

# Der Pfad zu deinem Repository
PROJECT_PATH = "aac-application-definitions/aac-template-engine"

# --- Initialisierung der GitLab-Verbindung ---
try:
    gl = gitlab.Gitlab(GITLAB_URL, private_token=PRIVATE_TOKEN)
    gl.auth()
    print("✅ Erfolgreich bei GitLab authentifiziert.")
except Exception as e:
    print(f"❌ Fehler bei der Authentifizierung: {e}")
    exit()

try:
    # --- Projekt finden ---
    project = gl.projects.get(PROJECT_PATH)
    print(f"⚙️  Arbeite mit Projekt: '{project.name_with_namespace}' (ID: {project.id})")

    # --- Alle Webhooks (Hooks) des Projekts abrufen ---
    hooks = project.hooks.list()

    if not hooks:
        print("\nℹ️  Keine Webhooks in diesem Repository gefunden.")
    else:
        print("\n🔎 Folgende Webhooks wurden gefunden:")
        for hook in hooks:
            print(f"  - ID: {hook.id}, URL: {hook.url}")

        # --- Sicherheitsabfrage vor dem Löschen ---
        # Um die Webhooks zu löschen, musst du die nächste Zeile auskommentieren,
        # indem du das '#' am Anfang entfernst.
        confirmation = input("\nMöchtest du alle oben gelisteten Webhooks wirklich löschen? (ja/nein): ")
        #confirmation = "nein" # Standardmäßig auf 'nein' gesetzt zur Sicherheit

        if confirmation.lower() == 'ja':
            print("\n🗑️  Lösche Webhooks...")
            for hook in hooks:
                try:
                    hook.delete()
                    print(f"  - ✅ Webhook mit ID {hook.id} ({hook.url}) gelöscht.")
                except gitlab.exceptions.GitlabError as e:
                    print(f"  - ❌ Fehler beim Löschen von Webhook ID {hook.id}: {e}")
            print("\n✨ Alle Webhooks wurden verarbeitet.")
        else:
            print("\n🛑 Löschvorgang abgebrochen.")

except gitlab.exceptions.GitlabError as e:
    print(f"\n❌ Ein Fehler ist aufgetreten: {e}")
    print("   Stelle sicher, dass der Projektpfad korrekt ist und dein Token die nötigen Rechte hat.")
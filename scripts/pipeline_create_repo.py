import gitlab
import os
import sys
import argparse
import time

def run_creation_logic(gitlab_url, private_token, target_group_path, template_project_path, new_repo_name, branch_list_str, template_trigger_branch, target_trigger_branch):
    """
    Diese Funktion enthält die eigentliche Logik zur Erstellung des Repositories und der Trigger-Konfiguration.
    Sie ist idempotent und kann mehrfach ausgeführt werden.
    """
    # --- Konfiguration ---
    branches_to_create = [b.strip() for b in branch_list_str.split(',')]
    project_path_slug = new_repo_name.lower().replace(' ', '-')
    
    if gitlab_url.startswith("https://"):
        clean_gitlab_url = gitlab_url[8:]
    else:
        clean_gitlab_url = gitlab_url

    print("--- Konfiguration ---")
    print(f"GitLab URL: {gitlab_url}")
    print(f"Zielgruppe: {target_group_path}")
    print(f"Template Projekt: {template_project_path}")
    print(f"Neues Repository: {new_repo_name}")
    print("---------------------\n")

    # --- Verbindung zu GitLab herstellen ---
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        gl.auth()
        print("✅ Erfolgreich bei GitLab authentifiziert.")
    except Exception as e:
        print(f"🔥 Fehler bei der Authentifizierung: {e}")
        sys.exit(1)

    try:
        # --- Projekte und Gruppen abrufen ---
        print("🔍 Suche nach Zielgruppe...")
        target_group = gl.groups.list(search=target_group_path)[0]
        print(f"✔️ Zielgruppe '{target_group.full_path}' gefunden (ID: {target_group.id}).")

        print("🔍 Suche nach Template-Projekt...")
        template_project = gl.projects.get(template_project_path)
        print(f"✔️ Template-Projekt '{template_project.path_with_namespace}' gefunden (ID: {template_project.id}).")

        # --- 1. Prüfen, ob das Projekt bereits existiert ---
        full_project_path = f"{target_group.path}/{project_path_slug}"
        try:
            project = gl.projects.get(full_project_path)
            print(f"✔️ Projekt '{project.name_with_namespace}' existiert bereits. Überspringe Erstellung.")
        except gitlab.exceptions.GitlabGetError:
            print(f"\n🚀 Projekt '{full_project_path}' nicht gefunden. Erstelle es via Fork-Methode...")
            fork_data = {'namespace_id': target_group.id, 'name': new_repo_name, 'path': project_path_slug}
            fork_job = template_project.forks.create(fork_data)
            project = gl.projects.get(fork_job.id)
            print("  - Warte auf Abschluss des Kopiervorgangs...")
            while project.import_status == 'started':
                time.sleep(2)
                project.reload()
            if project.import_status == 'failed':
                raise Exception(f"Der Import-Prozess (Fork) ist fehlgeschlagen: {project.import_error}")
            project.unfork()
            print(f"🎉 Projekt '{project.name_with_namespace}' erfolgreich und unabhängig erstellt.")
        
        # --- 2. Branches erstellen (idempotent) ---
        source_branch = project.default_branch
        print(f"\n🌿 Prüfe und erstelle Branches aus dem Source-Branch '{source_branch}'...")
        for branch_name in branches_to_create:
            try:
                project.branches.get(branch_name)
                print(f"  - Branch '{branch_name}' existiert bereits.")
            except gitlab.exceptions.GitlabGetError:
                project.branches.create({'branch': branch_name, 'ref': source_branch})
                print(f"  - Branch '{branch_name}' neu erstellt.")

        # --- 3. Prüfen, ob Webhook/Trigger bereits konfiguriert ist ---
        print(f"\n🔗 Prüfe und konfiguriere Cross-Projekt-Trigger...")
        
        # Wir identifizieren den Webhook anhand seiner Basis-URL, da der Token nicht auslesbar ist.
        webhook_url_base = f"https://{clean_gitlab_url}/api/v4/projects/{project.id}/ref/{target_trigger_branch}/trigger/pipeline"
        existing_hooks = template_project.hooks.list(all=True)
        found_hook = next((h for h in existing_hooks if h.url.startswith(webhook_url_base)), None)

        if found_hook:
            print("✔️ Passender Webhook/Trigger existiert bereits.")
        else:
            print("  - Konfiguriere neuen Trigger und Webhook...")
            trigger = project.triggers.create({'description': f'Triggered by updates in {template_project.path_with_namespace}'})
            trigger_token = trigger.token
            
            webhook_url = f"{webhook_url_base}?token={trigger_token}"
            hook_data = { 'url': webhook_url, 'push_events': True, 'push_events_branch_filter': template_trigger_branch, 'enable_ssl_verification': True }
            template_project.hooks.create(hook_data)
            print("  - Trigger und Webhook erfolgreich erstellt.")

        print("\n✨ Alle Operationen erfolgreich abgeschlossen!")

    except gitlab.exceptions.GitlabError as e:
        print(f"🔥 Ein GitLab-API-Fehler ist aufgetreten: {e.error_message}")
        sys.exit(1)
    except Exception as e:
        print(f"🔥 Ein unerwarteter Fehler ist aufgetreten: {e}")
        sys.exit(1)
def main():
    """
    Parst Argumente und holt Fallback-Werte aus Umgebungsvariablen.
    """
    parser = argparse.ArgumentParser(description="Erstellt ein GitLab Repository inkl. Cross-Projekt-Trigger.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--repo-name', help="Name des neuen Repositories.")
    parser.add_argument('--group-path', help="Pfad der Zielgruppe.")
    parser.add_argument('--template-path', help="Pfad des Template-Projekts.")
    parser.add_argument('--branches', help="Komma-getrennte Liste der Branches.")
    parser.add_argument('--gitlab-url', help="URL Ihrer GitLab-Instanz.")
    parser.add_argument('--template-trigger-branch', help="Branch im Template, der den Trigger auslöst (Default: main).")
    parser.add_argument('--target-trigger-branch', help="Branch im neuen Repo, auf dem die Pipeline laufen soll (Default: main).")
    args = parser.parse_args()

    # Logik: Argument nutzen, ansonsten Umgebungsvariable als Fallback
    config = {
        "new_repo_name": args.repo_name or os.environ.get('NEW_REPO_NAME'),
        "target_group_path": args.group_path or os.environ.get('TARGET_GROUP_PATH'),
        "template_project_path": args.template_path or os.environ.get('TEMPLATE_PROJECT_PATH'),
        "branch_list_str": args.branches or os.environ.get('BRANCH_LIST', 'dev,test,main,prod'),
        "gitlab_url": args.gitlab_url or os.environ.get('GITLAB_URL'),
        "private_token": os.environ.get('GITLAB_PRIVATE_TOKEN'), # Token NUR aus Umgebungsvariable
        "template_trigger_branch": args.template_trigger_branch or os.environ.get('TEMPLATE_TRIGGER_BRANCH', 'main'),
        "target_trigger_branch": args.target_trigger_branch or os.environ.get('TARGET_TRIGGER_BRANCH', 'main')
    }

    # Überprüfen, ob die minimal notwendigen Variablen gesetzt sind
    if not all([config["gitlab_url"], config["private_token"], config["target_group_path"], config["template_project_path"], config["new_repo_name"]]):
        print("🔥 Fehler: Nicht alle erforderlichen Konfigurationswerte konnten ermittelt werden.")
        print("Stellen Sie sicher, dass GITLAB_URL, GITLAB_PRIVATE_TOKEN, TARGET_GROUP_PATH, TEMPLATE_PROJECT_PATH und NEW_REPO_NAME gesetzt sind.")
        sys.exit(1)
    
    run_creation_logic(**config)

if __name__ == '__main__':
    main()
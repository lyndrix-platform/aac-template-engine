import gitlab
import os
import sys
import argparse
import time


# HINWEIS: Für die SVG-zu-PNG-Konvertierung wird skia-python benötigt.
# Bitte installieren mit: pip install skia-python
try:
    import skia
except ImportError:
    print("🔥 Fehler: Das Paket 'skia-python' fehlt.")
    print("   Bitte installieren Sie es mit: pip install skia-python")
    sys.exit(1)

def convert_svg_to_png(svg_path, png_path):
    """
    Konvertiert eine SVG-Datei in eine PNG-Datei.
    Verwendet eine Standardgröße von 500x500, falls die SVG keine eigenen Abmessungen hat.
    """
    # Erstelle einen Datenstrom (Stream) aus der Datei
    stream = skia.MemoryStream.MakeFromFile(svg_path)
    svg_dom = skia.SVGDOM.MakeFromStream(stream)

    # Prüfe, ob die SVG eine Größe hat
    if svg_dom.containerSize().isEmpty():
        print(f"   - SVG '{os.path.basename(svg_path)}' hat keine Größe. Verwende Standard 500x500px.")
        width, height = 500, 500
    else:
        width = int(svg_dom.containerSize().width())
        height = int(svg_dom.containerSize().height())

    # Skaliere die SVG, damit sie die gesamte Fläche ausfüllt
    svg_dom.setContainerSize(skia.Size(width, height))

    # Erstelle eine Zeichenfläche in der Zielgröße
    surface = skia.Surface(width, height)
    
    # Zeichne die SVG auf die Fläche
    with surface as canvas:
        svg_dom.render(canvas)
    
    # Speichere das Ergebnis als PNG-Datei
    image = surface.makeImageSnapshot()
    image.save(png_path, skia.kPNG)

def set_project_avatar(project, project_path_slug):
    """Setzt den Avatar für ein gegebenes Projekt, falls eine Icon-Datei existiert."""
    service_name = project_path_slug
    if service_name.startswith('aac-'):
        service_name = service_name[4:]  # "aac-" vom Anfang entfernen
    
    icon_path = os.path.join("service-icons", f"{service_name}.png")
    svg_icon_path = os.path.join("service-icons", f"{service_name}.svg")
    
    avatar_to_upload = None
    
    if os.path.exists(icon_path):
        avatar_to_upload = icon_path
    elif os.path.exists(svg_icon_path):
        print(f"ℹ️  Konvertiere '{svg_icon_path}' zu '{icon_path}'...")
        try:
            convert_svg_to_png(svg_icon_path, icon_path)
            avatar_to_upload = icon_path
            print("✔️ Konvertierung erfolgreich.")
        except Exception as e:
            print(f"⚠️ Warnung: SVG-Konvertierung fehlgeschlagen: {e}")
            return # Breche ab, wenn Konvertierung fehlschlägt
    
    if avatar_to_upload:
        try:
            print(f"\n🖼️  Setze Repository-Avatar von '{avatar_to_upload}'...")
            with open(avatar_to_upload, 'rb') as avatar_file:
                project.avatar = avatar_file
                project.save()
            print("✔️ Avatar erfolgreich gesetzt.")
        except Exception as e:
            print(f"⚠️ Warnung: Avatar konnte nicht gesetzt werden: {e}")
    else:
        print(f"ℹ️ Kein Icon für '{service_name}' im service-icons Verzeichnis gefunden.")
def run_creation_logic(gitlab_url, private_token, target_group_path, template_project_path, webhook_source_path, new_repo_name, branch_list_str, template_trigger_branch, target_trigger_branch):
    """
    Diese Funktion enthält die eigentliche Logik zur Erstellung des Repositories und der Trigger-Konfiguration.
    Sie ist idempotent und kann mehrfach ausgeführt werden.
    """
    # --- Konfiguration ---
    branches_to_create = [b.strip() for b in branch_list_str.split(',')]
    project_path_slug = new_repo_name.lower().replace(' ', '-')

    # Anzeigenamen im Format "AaC-Wort1-Wort2" erstellen
    if new_repo_name.startswith('aac-'):
        base_name = new_repo_name[4:]
    else:
        base_name = new_repo_name
    capitalized_parts = [part.capitalize() for part in base_name.split('-')]
    display_name = f"AaC-{'-'.join(capitalized_parts)}"
    
    if gitlab_url.startswith("https://"):
        clean_gitlab_url = gitlab_url[8:]
    else:
        clean_gitlab_url = gitlab_url

    print("--- Konfiguration ---")
    print(f"GitLab URL: {gitlab_url}")
    print(f"Zielgruppe: {target_group_path}")
    print(f"Template Projekt: {template_project_path}")
    print(f"Webhook Quelle: {webhook_source_path}")
    print(f"Repository (Pfad): {project_path_slug}")
    print(f"Repository (Anzeigename): {display_name}")
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

        print("🔍 Suche nach Webhook-Quellprojekt...")
        webhook_source_project = gl.projects.get(webhook_source_path)
        print(f"✔️ Webhook-Quellprojekt '{webhook_source_project.path_with_namespace}' gefunden (ID: {webhook_source_project.id}).")

        # --- 1. Prüfen, ob das Projekt bereits existiert ---
        full_project_path = f"{target_group.path}/{project_path_slug}"
        try:
            project = gl.projects.get(full_project_path)
            print(f"✔️ Projekt '{project.name_with_namespace}' existiert bereits.")
            
            # --- HIER IST DER FIX ---
            # Prüfen und aktualisieren des Anzeigenamens, falls er nicht übereinstimmt
            if project.name != display_name:
                print(f"   - Anzeigename wird aktualisiert von '{project.name}' zu '{display_name}'...")
                project.name = display_name
                project.save()
                print("   - ✔️ Name erfolgreich aktualisiert.")

        except gitlab.exceptions.GitlabGetError:
            print(f"\n🚀 Projekt '{full_project_path}' nicht gefunden. Erstelle es via Fork-Methode...")
            
            fork_data = {'namespace_id': target_group.id, 'name': display_name, 'path': project_path_slug}
            
            fork_job = template_project.forks.create(fork_data)
            project = gl.projects.get(fork_job.id)
            print("  - Warte auf Abschluss des Kopiervorgangs...")
            
            while project.attributes.get('import_status') == 'started':
                time.sleep(2)
                project = gl.projects.get(project.id)

            if project.attributes.get('import_status') == 'failed':
                import_error = project.attributes.get('import_error', 'Unbekannter Fehler')
                raise Exception(f"Der Import-Prozess (Fork) ist fehlgeschlagen: {import_error}")

            print(f"🎉 Projekt '{project.name_with_namespace}' erfolgreich erstellt. Entferne Fork-Beziehung...")
            project.delete_fork_relation()
            print("✔️ Fork-Beziehung erfolgreich entfernt.")
            # --- 1.1 Avatar setzen (falls vorhanden) ---
            set_project_avatar(project, project_path_slug)

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

        # --- 3. Avatar für bestehende Projekte setzen/aktualisieren ---
        set_project_avatar(project, project_path_slug)

        # --- 4. Webhook/Trigger bereinigen und neu erstellen ---
        print(f"\n🔗 Prüfe und konfiguriere Cross-Projekt-Trigger im Projekt '{webhook_source_project.name}'...")
        
        webhook_url_base = f"https://{clean_gitlab_url}/api/v4/projects/{project.id}/ref/{target_trigger_branch}/trigger/pipeline"
        existing_hooks = webhook_source_project.hooks.list(all=True)
        
        # Finde und lösche alle existierenden Webhooks für dieses Zielprojekt
        hooks_to_delete = [h for h in existing_hooks if h.url.startswith(webhook_url_base.split('?')[0])]
        if hooks_to_delete:
            print(f"  - {len(hooks_to_delete)} existierende Webhook(s) für dieses Projekt gefunden. Werden gelöscht...")
            for hook in hooks_to_delete:
                hook.delete()
            print("  - ✔️ Alte Webhooks erfolgreich gelöscht.")

        print("  - Erstelle neuen Trigger und Webhook...")
        trigger = project.triggers.create({'description': f'Trigger for {project.path_with_namespace}'})
        hook_data = { 'url': f"{webhook_url_base}?token={trigger.token}", 'push_events': True, 'push_events_branch_filter': template_trigger_branch, 'enable_ssl_verification': True }
        webhook_source_project.hooks.create(hook_data)
        print("  - ✔️ Neuer Trigger und Webhook erfolgreich erstellt.")

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
    parser.add_argument('--repo-name', help="Name des neuen Repositories.", required=True)
    parser.add_argument('--group-path', help="Pfad der Zielgruppe.", required=True)
    parser.add_argument('--template-path', help="Pfad des Template-Projekts.", required=True)
    ## NEU: Neuer, erforderlicher Parameter ##
    parser.add_argument('--webhook-source-path', help="Pfad des Projekts, das den Webhook erhalten soll.", required=True)
    parser.add_argument('--branches', help="Komma-getrennte Liste der Branches.")
    parser.add_argument('--gitlab-url', help="URL Ihrer GitLab-Instanz.")
    parser.add_argument('--template-trigger-branch', help="Branch im Webhook-Quellprojekt, der den Trigger auslöst (Default: main).")
    parser.add_argument('--target-trigger-branch', help="Branch im neuen Repo, auf dem die Pipeline laufen soll (Default: main).")
    args = parser.parse_args()

    # Logik: Argument nutzen, ansonsten Umgebungsvariable als Fallback
    config = {
        "new_repo_name": args.repo_name or os.environ.get('NEW_REPO_NAME'),
        "target_group_path": args.group_path or os.environ.get('TARGET_GROUP_PATH'),
        "template_project_path": args.template_path or os.environ.get('TEMPLATE_PROJECT_PATH'),
        ## NEU ##
        "webhook_source_path": args.webhook_source_path or os.environ.get('WEBHOOK_SOURCE_PATH'),
        "branch_list_str": args.branches or os.environ.get('BRANCH_LIST', 'dev,test,main,prod'),
        "gitlab_url": args.gitlab_url or os.environ.get('GITLAB_URL'),
        "private_token": os.environ.get('GITLAB_PRIVATE_TOKEN'), # Token NUR aus Umgebungsvariable
        "template_trigger_branch": args.template_trigger_branch or os.environ.get('TEMPLATE_TRIGGER_BRANCH', 'main'),
        "target_trigger_branch": args.target_trigger_branch or os.environ.get('TARGET_TRIGGER_BRANCH', 'main')
    }

    # Überprüfen, ob die minimal notwendigen Variablen gesetzt sind
    # (required=True in argparse übernimmt die Prüfung für Kommandozeilenargumente)
    if not all([config["gitlab_url"], config["private_token"]]):
         print("🔥 Fehler: Die Umgebungsvariablen GITLAB_URL und/oder GITLAB_PRIVATE_TOKEN sind nicht gesetzt.")
         sys.exit(1)
    
    run_creation_logic(**config)

if __name__ == '__main__':
    main()
import argparse
import os
import sys
import shutil
import yaml
from jinja2 import Environment, FileSystemLoader

# The complex load_and_prerender_ssot function has been completely removed.

def process_deployment_templates(deployment_type, data, env):
    """
    Handles generation for a specific deployment type.
    """
    print(f"\n--- Processing Templates for Deployment-Type: {deployment_type} ---")
    
    custom_template_dir = f"custom_templates/{deployment_type}"
    if os.path.isdir(custom_template_dir):
        print(f"Benutzerdefiniertes Template-Verzeichnis gefunden: '{custom_template_dir}'")
        template_dir = custom_template_dir
    else:
        print(f"Kein benutzerdefiniertes Verzeichnis gefunden. Verwende Standard-Templates.")
        template_dir = f"templates/{deployment_type}"

    output_dir = f"deployments/{deployment_type}"

    if not os.path.isdir(template_dir):
        print(f"Template-Verzeichnis '{template_dir}' nicht gefunden. Überspringe Generierung.", file=sys.stderr)
        return

    os.makedirs(output_dir, exist_ok=True)
    
    for root, _, files in os.walk(template_dir):
        for file in files:
            if file.endswith(".j2"):
                template_path = os.path.join(root, file)
                template = env.get_template(template_path)
                rendered_content = template.render(data)
                output_filename = os.path.basename(template_path)[:-3]
                output_filepath = os.path.join(output_dir, output_filename)
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                print(f"Erfolgreich generiert: {output_filepath}")

def process_custom_files(data, env):
    """
    Processes the custom_templates/files directory.
    """
    print("\n--- Processing Custom Files ---")
    custom_files_dir = "custom_templates/files"
    output_base_dir = "deployments/files"

    if not os.path.isdir(custom_files_dir):
        print(f"Verzeichnis für benutzerdefinierte Dateien '{custom_files_dir}' nicht gefunden. Überspringe.")
        return

    for root, _, files in os.walk(custom_files_dir):
        for filename in files:
            source_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_path, custom_files_dir)
            dest_path_with_ext = os.path.join(output_base_dir, relative_path)
            os.makedirs(os.path.dirname(dest_path_with_ext), exist_ok=True)

            if filename.endswith(".j2"):
                dest_path = dest_path_with_ext[:-3]
                print(f"Rendere '{source_path}' -> '{dest_path}'")
                template = env.get_template(source_path)
                rendered_content = template.render(data)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
            else:
                print(f"Kopiere '{source_path}' -> '{dest_path_with_ext}'")
                shutil.copy2(source_path, dest_path_with_ext)

def main():
    """
    Generates deployment manifests from a fully-rendered SSoT file.
    """
    parser = argparse.ArgumentParser(description="Generiert Deployment-Manifeste aus einer SSoT-Datei.")
    parser.add_argument('--ssot-file', required=True, help="Pfad zur zentralen, bereits gerenderten SSoT YAML-Datei.")
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="Der zu generierende Deployment-Typ.")
    action_group.add_argument('--process-files', action='store_true', help="Nur benutzerdefinierte Dateien verarbeiten.")

    args = parser.parse_args()

    try:
        # The pre-render logic is gone. We simply load the file.
        print(f"Lade finale SSoT-Daten aus: {args.ssot_file}")
        with open(args.ssot_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
        
        if args.deployment_type:
            process_deployment_templates(args.deployment_type, data, env)
        
        if args.process_files:
            process_custom_files(data, env)

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
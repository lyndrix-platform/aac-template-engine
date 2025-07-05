import argparse
import os
import sys
import shutil
import yaml
from jinja2 import Environment, FileSystemLoader, BaseLoader

def load_and_prerender_ssot(ssot_file_path):
    """
    Loads the SSoT file and pre-renders it multiple times to resolve nested variables.
    """
    print(f"Lade SSoT-Daten aus: {ssot_file_path}")
    with open(ssot_file_path, 'r', encoding='utf-8') as f:
        raw_ssot_content = f.read()

    # Render the SSoT file multiple times to resolve nested variables.
    env = Environment(loader=BaseLoader())
    rendered_ssot_content = raw_ssot_content
    for i in range(5):  # Max 5 passes to avoid infinite loops
        previous_content = rendered_ssot_content
        template = env.from_string(previous_content)
        data_for_render = yaml.safe_load(previous_content)
        rendered_ssot_content = template.render(data_for_render)
        if previous_content == rendered_ssot_content:
            print(f"SSoT-Variablen nach {i+1} Durchlauf(en) stabil.")
            break
    else:
        print("WARNUNG: SSoT-Variablen wurden nach 5 Durchläufen nicht stabil.", file=sys.stderr)

    return yaml.safe_load(rendered_ssot_content)

def process_deployment_templates(deployment_type, data, env):
    """
    Handles generation for a specific deployment type, using custom templates if they exist.
    """
    print(f"\n--- Processing Templates for Deployment-Type: {deployment_type} ---")
    
    # Check for a custom template directory and prioritize it
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
    
    template_files = []
    for root, _, files in os.walk(template_dir):
        for file in files:
            if file.endswith(".j2"):
                template_files.append(os.path.join(root, file))
    
    print(f"Gefundene Templates zum Generieren: {[os.path.basename(f) for f in template_files]}")

    if not template_files:
        print(f"Keine .j2-Templates im Verzeichnis gefunden: {template_dir}")
        return
    
    for template_path in template_files:
        template = env.get_template(template_path)
        rendered_content = template.render(data)
        output_filename = os.path.basename(template_path)[:-3]  # Remove .j2
        output_filepath = os.path.join(output_dir, output_filename)
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(rendered_content)
        print(f"Erfolgreich generiert: {output_filepath}")

def process_custom_files(data, env):
    """
    Processes the custom_templates/files directory.
    Renders .j2 files and copies all other files, preserving structure.
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
            
            # Calculate the relative path to preserve the directory structure
            relative_path = os.path.relpath(source_path, custom_files_dir)
            dest_path_with_ext = os.path.join(output_base_dir, relative_path)

            # Ensure the destination directory exists
            os.makedirs(os.path.dirname(dest_path_with_ext), exist_ok=True)

            if filename.endswith(".j2"):
                # Render Jinja2 template
                dest_path = dest_path_with_ext[:-3] # Remove .j2 extension
                print(f"Rendere '{source_path}' -> '{dest_path}'")
                template = env.get_template(source_path)
                rendered_content = template.render(data)
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
            else:
                # Copy any other file
                print(f"Kopiere '{source_path}' -> '{dest_path_with_ext}'")
                shutil.copy2(source_path, dest_path_with_ext)

def main():
    """
    Generates deployment manifests and files from a central SSoT file.
    """
    parser = argparse.ArgumentParser(description="Generiert Deployment-Manifeste und Dateien aus einer SSoT-Datei.")
    parser.add_argument('--ssot-file', required=True, help="Pfad zur zentralen SSoT YAML-Datei.")
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="Der zu generierende Deployment-Typ (z.B. docker_compose).")
    action_group.add_argument('--process-files', action='store_true', help="Nur benutzerdefinierte Dateien aus 'custom_templates/files' verarbeiten.")

    args = parser.parse_args()

    try:
        data = load_and_prerender_ssot(args.ssot_file)
        # The FileSystemLoader should look from the root of the project
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
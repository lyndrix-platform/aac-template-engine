import argparse
import os
import sys
import shutil
import yaml
import json
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# DEBUG-HELFERFUNKTION
# ==============================================================================
def print_debug_header(title):
    """Druckt eine gut sichtbare Überschrift für Debug-Abschnitte."""
    print("\n" + "="*80)
    print(f"DEBUG: {title.upper()}")
    print("="*80)

def print_debug_data(variable_name, data):
    """Druckt den Inhalt einer Variablen formatiert als JSON."""
    print(f"\n--- Inhalt von: {variable_name} ---")
    try:
        # JSON ist oft besser lesbar für komplexe, verschachtelte Strukturen
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except TypeError:
        # Fallback, falls die Daten nicht JSON-serialisierbar sind
        print(data)
    print("--- Ende des Inhalts ---\n")

# ==============================================================================
# HAUPTFUNKTIONEN
# ==============================================================================

def process_deployment_templates(deployment_type, data, env):
    """
    Verarbeitet Templates für einen bestimmten Deployment-Typ und gibt Debug-Infos aus.
    """
    print_debug_header(f"Verarbeite Templates für Deployment-Typ: {deployment_type}")
    
    custom_template_dir = f"custom_templates/{deployment_type}"
    if os.path.isdir(custom_template_dir):
        print(f"INFO: Benutzerdefiniertes Template-Verzeichnis gefunden: '{custom_template_dir}'")
        template_dir = custom_template_dir
    else:
        print(f"INFO: Kein benutzerdefiniertes Verzeichnis gefunden. Verwende Standard-Templates aus 'templates/{deployment_type}'.")
        template_dir = f"templates/{deployment_type}"

    output_dir = f"deployments/{deployment_type}"

    if not os.path.isdir(template_dir):
        print(f"FEHLER: Template-Verzeichnis '{template_dir}' nicht gefunden. Überspringe Generierung.", file=sys.stderr)
        return

    print(f"INFO: Zielverzeichnis für generierte Dateien: '{output_dir}'")
    os.makedirs(output_dir, exist_ok=True)
    
    for root, _, files in os.walk(template_dir):
        for file in files:
            if file.endswith(".j2"):
                template_path = os.path.join(root, file)
                output_filename = os.path.basename(template_path)[:-3]
                output_filepath = os.path.join(output_dir, output_filename)

                print_debug_header(f"Rendere Template: {template_path}")
                
                try:
                    template = env.get_template(template_path)
                    rendered_content = template.render(data)
                    
                    # Debug-Ausgabe des gerenderten Inhalts
                    print(f"DEBUG: Ziel-Datei: {output_filepath}")
                    print("--- Gerenderter Inhalt (vor dem Schreiben) ---")
                    print(rendered_content)
                    print("--- Ende des gerenderten Inhalts ---\n")

                    # Schreiben der Datei
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                    print(f"INFO: Erfolgreich generiert: {output_filepath}")

                except Exception as e:
                    print(f"FEHLER beim Rendern von '{template_path}': {e}", file=sys.stderr)


def process_custom_files(data, env):
    """
    Verarbeitet benutzerdefinierte Dateien und gibt Debug-Infos aus.
    """
    print_debug_header("Verarbeite benutzerdefinierte Dateien")
    custom_files_dir = "custom_templates/files"
    output_base_dir = "deployments/files"

    if not os.path.isdir(custom_files_dir):
        print(f"INFO: Verzeichnis für benutzerdefinierte Dateien '{custom_files_dir}' nicht gefunden. Überspringe.")
        return

    for root, _, files in os.walk(custom_files_dir):
        for filename in files:
            source_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_path, custom_files_dir)
            dest_path_with_ext = os.path.join(output_base_dir, relative_path)
            os.makedirs(os.path.dirname(dest_path_with_ext), exist_ok=True)

            if filename.endswith(".j2"):
                dest_path = dest_path_with_ext[:-3]
                print_debug_header(f"Rendere benutzerdefiniertes Template: {source_path}")
                print(f"DEBUG: Ziel-Datei: {dest_path}")

                try:
                    template = env.get_template(source_path)
                    rendered_content = template.render(data)
                    
                    print("--- Gerenderter Inhalt (vor dem Schreiben) ---")
                    print(rendered_content)
                    print("--- Ende des gerenderten Inhalts ---\n")
                    
                    with open(dest_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                    print(f"INFO: Erfolgreich generiert: {dest_path}")
                except Exception as e:
                    print(f"FEHLER beim Rendern von '{source_path}': {e}", file=sys.stderr)
            else:
                print_debug_header(f"Kopiere benutzerdefinierte Datei: {source_path}")
                print(f"DEBUG: Ziel-Datei: {dest_path_with_ext}")
                shutil.copy2(source_path, dest_path_with_ext)
                print(f"INFO: Erfolgreich kopiert: {dest_path_with_ext}")


def main():
    """
    Generiert Deployment-Manifeste aus einer SSoT-Datei und gibt umfassende Debug-Infos aus.
    """
    parser = argparse.ArgumentParser(description="Generiert Deployment-Manifeste aus einer SSoT-Datei.")
    parser.add_argument('--ssot-file', required=True, help="Pfad zur zentralen, bereits gerenderten SSoT YAML-Datei.")
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="Der zu generierende Deployment-Typ.")
    action_group.add_argument('--process-files', action='store_true', help="Nur benutzerdefinierte Dateien verarbeiten.")

    args = parser.parse_args()

    print_debug_header("Skriptstart und Argumente")
    print(f"Argumente: {vars(args)}")

    try:
        print(f"\nINFO: Lade finale SSoT-Daten aus: {args.ssot_file}")
        with open(args.ssot_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Dies ist der wichtigste Debug-Schritt:
        # Zeigt den exakten Datenstand, den das Skript von Ansible erhalten hat.
        print_debug_header("Vollständige SSoT-Daten nach dem Laden aus der YAML-Datei")
        print_debug_data("data", data)

        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
        
        if args.deployment_type:
            process_deployment_templates(args.deployment_type, data, env)
        
        if args.process_files:
            process_custom_files(data, env)
        
        print_debug_header("Skript erfolgreich beendet")

    except Exception as e:
        print(f"FATALER FEHLER: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

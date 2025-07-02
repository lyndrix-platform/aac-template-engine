import argparse
import os
import sys
import yaml
from jinja2 import Environment, FileSystemLoader, BaseLoader

def main():
    """
    Generiert Deployment-Manifeste aus einer zentralen SSoT-Datei.
    Das Skript nimmt einen Deployment-Typ entgegen, findet alle zugehörigen .j2-Templates,
    rendert sie mit den Daten aus der SSoT-Datei und speichert das Ergebnis.
    """
    parser = argparse.ArgumentParser(description="Generiert Deployment-Manifeste aus einer SSoT-Datei.")
    parser.add_argument('--ssot-file', required=True, help="Pfad zur zentralen SSoT YAML-Datei.")
    parser.add_argument('--deployment-type', required=True, help="Der zu generierende Deployment-Typ (z.B. docker_compose).")
    args = parser.parse_args()

    try:
        # --- 1. Lade die SSoT-Daten und rendere sie in mehreren Durchläufen vor ---
        print(f"Lade SSoT-Daten aus: {args.ssot_file}")
        with open(args.ssot_file, 'r', encoding='utf-8') as f:
            raw_ssot_content = f.read()

        # Rendere die SSoT-Datei mehrmals, um verschachtelte Variablen aufzulösen.
        # Dies ist notwendig, wenn Variablen von anderen gerenderten Variablen abhängen.
        env = Environment(loader=BaseLoader())
        rendered_ssot_content = raw_ssot_content
        for i in range(5):  # Maximal 5 Durchläufe, um Endlosschleifen zu vermeiden
            previous_content = rendered_ssot_content
            template = env.from_string(previous_content)
            data_for_render = yaml.safe_load(previous_content)
            rendered_ssot_content = template.render(data_for_render)
            if previous_content == rendered_ssot_content:
                print(f"SSoT-Variablen nach {i+1} Durchlauf(en) stabil.")
                break
        else:
            print("WARNUNG: SSoT-Variablen wurden nach 5 Durchläufen nicht stabil.", file=sys.stderr)

        data = yaml.safe_load(rendered_ssot_content)

        # --- 2. Richte die Jinja2-Umgebung für die finalen Templates ein ---
        template_env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)

        # --- 3. Finde und verarbeite alle Templates für den angegebenen Deployment-Typ ---
        template_dir = f"templates/{args.deployment_type}"
        output_dir = f"deployments/{args.deployment_type}"

        if not os.path.isdir(template_dir):
            print(f"Template-Verzeichnis '{template_dir}' nicht gefunden. Überspringe Generierung.", file=sys.stderr)
            return # Beende den Job für diesen Typ, aber nicht die ganze Pipeline

        os.makedirs(output_dir, exist_ok=True)
        
        # Verwende os.walk statt glob, um auch "dotfiles" (z.B. .env.j2) zuverlässig zu finden.
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
            template = template_env.get_template(template_path)
            rendered_content = template.render(data)
            output_filename = os.path.basename(template_path)[:-3]  # Entferne .j2
            output_filepath = os.path.join(output_dir, output_filename)
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
            print(f"Erfolgreich generiert: {output_filepath}")

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
import yaml

def validate_service_stage(service_file: Path, stage: str, template_engine_path: Path):
    """
    Generiert die docker-compose.yml für einen Service und eine Stage, indem es
    das 'generate_manifest.py'-Skript aufruft und das Ergebnis validiert.
    """
    service_name = service_file.parent.name
    print(f"  -> Validating stage: [{stage}]...", end="", flush=True)

    # Erstellt ein temporäeres Verzeichnis, das nach Gebrauch automatisch bereinigt wird.
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        try:
            # 1. Lade service.yml und konvertiere es in einen JSON-String für das Generator-Skript.
            with open(service_file, 'r', encoding='utf-8') as f:
                ssot_data = yaml.safe_load(f)
            ssot_json_string = json.dumps(ssot_data)

            # 2. Rufe generate_manifest.py als Subprozess auf.
            generator_script_path = template_engine_path / 'scripts' / 'generate_manifest.py'

            # Das Generator-Skript benötigt möglicherweise die service.yml im Arbeitsverzeichnis,
            # um z.B. custom_templates zu finden. Wir kopieren sie dorthin.
            shutil.copy(service_file, temp_path / 'service.yml')

            subprocess.run(
                [
                    sys.executable,  # Stellt sicher, dass der gleiche Python-Interpreter verwendet wird
                    str(generator_script_path),
                    '--ssot-json', ssot_json_string,
                    '--template-path', str(template_engine_path.resolve()),
                    '--stage', stage,
                    '--deployment-type', 'docker_compose'
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=temp_path  # Führe das Skript im temporären Verzeichnis aus
            )

            # 3. Führe 'docker-compose config' für die generierte Datei aus.
            compose_file_path = temp_path / 'deployments' / 'docker_compose' / 'docker-compose.yml'
            if not compose_file_path.exists():
                raise FileNotFoundError("docker-compose.yml wurde vom Generator-Skript nicht erstellt.")

            subprocess.run(
                ['docker-compose', '-f', str(compose_file_path), 'config'],
                check=True,
                capture_output=True,
                text=True
            )

            print(" ✅ SUCCESS")
            return True

        except subprocess.CalledProcessError as e:
            print(" ❌ FAILED")
            # Unterscheide zwischen Fehlern vom Generator-Skript und von Docker Compose.
            if "generate_manifest.py" in str(e.cmd):
                print("\n--- Generator Script Error ---")
            else:
                print("\n--- Docker Compose Error ---")
            print(e.stderr)
            print("--------------------------\n")
            return False
        except Exception as e:
            print(" ❌ FAILED")
            print(f"\n--- Script Error ---\n{type(e).__name__}: {e}\n--------------------\n")
            return False


def main():
    """Hauptfunktion des Skripts."""
    parser = argparse.ArgumentParser(
        description="Validiert die generierten Docker Compose Konfigurationen für alle Services und Stages."
    )
    parser.add_argument("apps_path", help="Der Pfad zum Verzeichnis, das die Service-Repository-Klone enthält (z.B. 'applications').")
    parser.add_argument("--templates", default=".", help="Der Pfad zum 'aac-template-engine' Verzeichnis.")
    args = parser.parse_args()

    applications_dir = Path(args.apps_path)
    template_engine_dir = Path(args.templates).resolve()

    if not applications_dir.is_dir():
        print(f"FEHLER: Das Anwendungsverzeichnis wurde nicht gefunden: {applications_dir}", file=sys.stderr)
        sys.exit(1)
    if not (template_engine_dir / 'scripts' / 'generate_manifest.py').is_file():
        print(f"FEHLER: Das Generator-Skript wurde nicht gefunden: {template_engine_dir / 'scripts' / 'generate_manifest.py'}", file=sys.stderr)
        sys.exit(1)

    service_files = sorted(list(applications_dir.glob('**/service.yml')))

    if not service_files:
        print(f"Keine 'service.yml'-Dateien im Verzeichnis '{applications_dir}' gefunden.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(service_files)} services to validate.\n")

    total_checks = 0
    failed_checks = 0

    for file in service_files:
        service_name = file.parent.name
        print(f"=========================================")
        print(f"Validating Service: {service_name}")
        print(f"=========================================")

        # Annahme: 'dev', 'test', 'prod' sind die relevanten Stages.
        # Dies könnte dynamisch aus der service.yml gelesen werden, falls nötig.
        for stage in ["dev", "test", "prod"]:
            total_checks += 1
            if not validate_service_stage(file, stage, template_engine_dir):
                failed_checks += 1
        print("")

    print("=========================================")
    print("Validation Summary")
    print("=========================================")
    print(f"Total checks performed: {total_checks}")
    print(f"Successful checks: {total_checks - failed_checks}")
    print(f"Failed checks: {failed_checks}")
    print("=========================================\n")

    if failed_checks > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
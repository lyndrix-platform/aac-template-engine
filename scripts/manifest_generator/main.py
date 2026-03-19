# scripts/manifest_generator/main.py
import argparse
import sys
import os
import traceback
import yaml 
import json

from .context import ContextBuilder
from .engine import ManifestEngine

# 1. Import ALL Processors
from .processors.imports import ImportProcessor
from .processors.metadata import MetadataProcessor
from .processors.environment import EnvironmentProcessor
from .processors.networks import NetworkProcessor
from .processors.ingress import IngressProcessor
from .processors.specs import SpecProcessor
from .processors.volumes import VolumeProcessor

def main():
    parser = argparse.ArgumentParser(description="Modular Manifest Generator")
    parser.add_argument('--ssot-json', required=True, help="JSON string OR path to a JSON file")
    parser.add_argument('--template-path', required=True, help="Path to template engine repo")
    parser.add_argument('--stage', required=True, help="Deployment stage (dev, prod)")
    parser.add_argument('--deployment-type', default='docker_compose')
    
    # HIER IST DER FIX: Die CI-Pipeline schickt diese Argumente mit!
    parser.add_argument('--process-documentation', action='store_true', help="Generate documentation")
    parser.add_argument('--process-files', action='store_true', help="Process custom files")
    
    args = parser.parse_args()

    # --- Robust Input Handling ---
    ssot_input = args.ssot_json
    if os.path.isfile(ssot_input):
        print(f"  [I] Reading SSoT from file: {ssot_input}")
        with open(ssot_input, 'r', encoding='utf-8') as f:
            if ssot_input.endswith(('.yml', '.yaml')):
                parsed_yaml = yaml.safe_load(f)
                ssot_input = json.dumps(parsed_yaml)
            else:
                ssot_input = f.read()

    try:
        # 1. Build Data Context
        builder = ContextBuilder(ssot_input, args.stage)
        context = builder.build()

        # 2. Run Logic Processors (Strict Order Required)
        processors = [
            ImportProcessor(args.template_path),
            MetadataProcessor(),
            EnvironmentProcessor(),
            NetworkProcessor(),
            IngressProcessor(),
            SpecProcessor(),
            VolumeProcessor()
        ]

        for proc in processors:
            context = proc.process(context)

        # 3. Render Manifests
        engine = ManifestEngine(args.template_path, os.getcwd())
        
        # 4. Weiche für die CI-Jobs
        if args.process_documentation:
            print("  [I] Processing Documentation...")
            if hasattr(engine, 'render_documentation'):
                engine.render_documentation(context)
            else:
                # Fallback, falls die Methode im neuen Engine-Code fehlt
                engine.render_all(context, args.deployment_type)
                
        elif args.process_files:
            print("  [I] Processing Custom Files...")
            if hasattr(engine, 'render_files'):
                engine.render_files(context)
            else:
                engine.render_all(context, args.deployment_type)
                
        else:
            print("  [I] Processing Docker Compose...")
            engine.render_all(context, args.deployment_type)
        
        print("\nSuccess: Manifest generation complete.")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
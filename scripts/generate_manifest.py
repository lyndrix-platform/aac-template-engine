#!/usr/bin/env python3
"""
Deployment Manifest Generator - v2 (Simplified)

This script takes a fully-rendered JSON data structure and uses it to
render final deployment template files (e.g., docker-compose.yml).
It does not perform any data merging or multi-pass rendering itself.
"""
import os
import sys
import json
import argparse
import shutil
from jinja2 import Environment, FileSystemLoader

def process_templates(directory, output_base, context, env):
    """Generic function to find and render .j2 templates."""
    if not os.path.isdir(directory):
        print(f"INFO: Template directory not found, skipping: {directory}", file=sys.stderr)
        return

    for root, _, files in os.walk(directory):
        for file in files:
            source_path = os.path.join(root, file)
            relative_path = os.path.relpath(source_path, directory)
            output_path_raw = os.path.join(output_base, relative_path)
            os.makedirs(os.path.dirname(output_path_raw), exist_ok=True)
            
            if file.endswith(".j2"):
                output_path = output_path_raw[:-3]
                print(f"INFO: Rendering template '{source_path}' to '{output_path}'")
                try:
                    template = env.get_template(source_path)
                    rendered_content = template.render(context)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                except Exception as e:
                    print(f"ERROR: Failed to render {source_path}: {e}", file=sys.stderr)
            else:
                # Copy non-template files directly
                print(f"INFO: Copying file '{source_path}' to '{output_path_raw}'")
                shutil.copy2(source_path, output_path_raw)

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generates deployment manifests from a JSON SSoT string.")
    parser.add_argument('--ssot-json', required=True, help="The complete, pre-rendered SSoT as a JSON string.")
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="The deployment type to generate (e.g., 'docker_compose').")
    action_group.add_argument('--process-files', action='store_true', help="Process 'custom_templates/files' only.")
    
    args = parser.parse_args()

    try:
        # Load the complete, static data from the JSON argument
        data = json.loads(args.ssot_json)
        
        # The Jinja environment can be simple, as it just needs to find the template files.
        # The rendering context is passed directly to the render() call.
        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)

        if args.deployment_type:
            deployment_type = args.deployment_type
            # Check for a custom template directory first, otherwise use the default
            custom_dir = f"custom_templates/{deployment_type}"
            default_dir = f"templates/{deployment_type}"
            template_dir = custom_dir if os.path.isdir(custom_dir) else default_dir
            
            process_templates(template_dir, f"deployments/{deployment_type}", data, env)

        if args.process_files:
            process_templates("custom_templates/files", "deployments/files", data, env)

        print("INFO: Script finished successfully.")

    except json.JSONDecodeError as e:
        print(f"FATAL: Invalid JSON provided to --ssot-json. Error: {e}", file=sys.stderr)
        print("--- Received JSON String ---", file=sys.stderr)
        print(args.ssot_json, file=sys.stderr)
        print("----------------------------", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
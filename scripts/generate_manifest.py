#!/usr/bin/env python3
"""
Deployment Manifest Generator - v4 (Simple Renderer)

This script's only job is to render Jinja2 templates. It takes a
fully-rendered SSoT file (in YAML format) and uses it as the context
to generate deployment files. It performs NO data merging or recursive rendering.
"""
import os
import sys
import yaml
import argparse
import shutil
from jinja2 import Environment, FileSystemLoader

def process_templates(directory: str, output_base: str, context: dict, env: Environment):
    """Generic function to find and render .j2 templates or copy other files."""
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
                    # The loader path is relative to the script's execution directory
                    template = env.get_template(source_path)
                    rendered_content = template.render(context)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                except Exception as e:
                    print(f"ERROR: Failed to render {source_path}: {e}", file=sys.stderr)
            else:
                print(f"INFO: Copying file '{source_path}' to '{output_path_raw}'")
                shutil.copy2(source_path, output_path_raw)

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generates deployment manifests from a final SSoT file.")
    parser.add_argument('--ssot-file', required=True, help="Path to the final, pre-rendered SSoT YAML file.")
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="The deployment type to generate (e.g., 'docker_compose').")
    action_group.add_argument('--process-files', action='store_true', help="Process 'custom_templates/files' only.")
    
    args = parser.parse_args()

    try:
        # --- Step 1: Load the final SSoT data directly ---
        print(f"INFO: Loading final SSoT from file: {args.ssot_file}", file=sys.stderr)
        with open(args.ssot_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("SSoT data is empty after loading.")

        # --- Step 2: Process templates ---
        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)

        if args.deployment_type:
            deployment_type = args.deployment_type
            template_dir = f"templates/{deployment_type}"
            output_dir = f"deployments/{deployment_type}"
            print(f"INFO: Generating for deployment type '{deployment_type}'...", file=sys.stderr)
            process_templates(template_dir, output_dir, data, env)

        if args.process_files:
            files_dir = "custom_templates/files"
            output_dir = "deployments/files"
            print("INFO: Processing custom files...", file=sys.stderr)
            process_templates(files_dir, output_dir, data, env)

        print("INFO: Script finished successfully.")

    except Exception as e:
        print(f"FATAL: An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

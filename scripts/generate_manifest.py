#!/usr/bin/env python3
"""
Deployment Manifest Generator - v3 (Robust)

This script generates deployment configurations from a Single Source of Truth (SSoT).
It can accept the SSoT data from either a JSON string or a YAML file, ensuring
consistent behavior across different execution environments (like local, CI, and Ansible).

Key Features:
- Handles data input from both --ssot-json (for Ansible) and --ssot-file (for CI).
- Performs a multi-pass rendering of the SSoT file to resolve nested Jinja2 templates.
- Renders template files (.j2) into final deployment manifests.
- Copies non-template files directly to the output directory.
"""
import os
import sys
import json
import argparse
import shutil
import yaml
from jinja2 import Environment, FileSystemLoader, meta

def render_ssot_recursively(sot_content_str: str, max_passes: int = 5) -> dict:
    """
    Renders a string containing Jinja2 templates against its own data,
    recursively, until no more templates can be resolved.

    Args:
        sot_content_str: The string content of the SSoT file.
        max_passes: The maximum number of rendering passes to prevent infinite loops.

    Returns:
        A fully rendered Python dictionary.
    """
    env = Environment()
    rendered_text = sot_content_str
    
    for i in range(max_passes):
        print(f"INFO: SSoT Rendering Pass {i + 1}...", file=sys.stderr)
        template = env.from_string(rendered_text)
        
        # Find undefined variables to see if we need another pass
        undefined_vars = meta.find_undeclared_variables(env.parse(rendered_text))
        
        # Load the current text as YAML to use as the rendering context
        current_context = yaml.safe_load(rendered_text)
        rendered_text = template.render(current_context)
        
        # If there are no more undefined variables, we are done.
        if not undefined_vars:
            print("INFO: SSoT rendering complete.", file=sys.stderr)
            break
    else:
        print("WARNING: Max rendering passes reached. There might be unresolved templates.", file=sys.stderr)

    return yaml.safe_load(rendered_text)

def process_templates(directory: str, output_base: str, context: dict, env: Environment):
    """
    Generic function to find and render .j2 templates or copy other files.
    """
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
                    # Use a file-based loader for the template environment
                    template_env = Environment(loader=FileSystemLoader(os.path.dirname(source_path)), trim_blocks=True, lstrip_blocks=True)
                    template = template_env.get_template(os.path.basename(source_path))
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
    parser = argparse.ArgumentParser(description="Generates deployment manifests from an SSoT.")
    
    # --- Input Arguments ---
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--ssot-json', help="The SSoT as a JSON string (for Ansible).")
    input_group.add_argument('--ssot-file', help="Path to the SSoT YAML file (for CI/local runs).")

    # --- Action Arguments ---
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="The deployment type to generate (e.g., 'docker_compose').")
    action_group.add_argument('--process-files', action='store_true', help="Process 'custom_templates/files' only.")
    
    args = parser.parse_args()

    data = {}
    try:
        # --- Step 1: Load SSoT data from either JSON or File ---
        if args.ssot_json:
            print("INFO: Loading SSoT from JSON string.", file=sys.stderr)
            # Ansible has already done the recursive rendering, so we just load it.
            data = json.loads(args.ssot_json)
        elif args.ssot_file:
            print(f"INFO: Loading SSoT from file: {args.ssot_file}", file=sys.stderr)
            with open(args.ssot_file, 'r', encoding='utf-8') as f:
                sot_content = f.read()
            # For file-based input (CI), we need to do the recursive rendering here.
            data = render_ssot_recursively(sot_content)

        if not data:
            raise ValueError("SSoT data is empty after loading.")

        # --- Step 2: Process templates based on the loaded data ---
        # The Jinja environment for rendering templates from the filesystem.
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

#!/usr/bin/env python3
"""
Deployment Manifest Generator - v7 (Override-Aware Renderer)

This script generates deployment configurations from a Single Source of Truth (SSoT).
It intelligently uses templates from the service's own 'custom_templates' directory
if they exist, otherwise it falls back to the default templates provided by the
'--template-path' argument.
"""
import os
import sys
import json
import argparse
import shutil
from copy import deepcopy
from jinja2 import Environment, FileSystemLoader, ChoiceLoader

def render_ssot_recursively(data: dict) -> dict:
    """
    Recursively renders Jinja2 templates within the SSoT data structure.
    This mimics Ansible's `lookup('template', ...)` behavior, ensuring that
    data passed from any source is fully resolved before being used.
    """
    # Create a Jinja2 environment.
    env = Environment(trim_blocks=True, lstrip_blocks=True)

    # Convert the initial dict to a JSON string.
    previous_render = ""
    current_render = json.dumps(data)

    # Loop to allow for multi-pass rendering, e.g., {{ a }} -> {{ b }} -> c.
    # This is necessary for nested templates like `{{ dependencies.database.name }}`
    # which itself contains `{{ service.name }}`.
    # We'll loop up to 10 times or until the output stabilizes.
    for _ in range(10):
        if previous_render == current_render:
            # No more changes, rendering is stable.
            break

        previous_render = current_render

        # The context for rendering is the last rendered version of the data.
        context = json.loads(previous_render)
        template = env.from_string(previous_render)
        current_render = template.render(context)
    else:
        # This 'else' belongs to the 'for' loop. It runs if the loop finished without a `break`.
        print("WARNING: Recursive rendering did not stabilize after 10 passes. Check for circular references in service.yml.", file=sys.stderr)

    # Convert the final rendered JSON string back to a Python dict.
    return json.loads(current_render)

def process_templates(template_paths: list, output_base: str, context: dict):
    """
    Finds all unique .j2 templates across a list of directories,
    and renders them using a loader that respects override priority.
    """
    # Create a loader that checks for templates in the provided paths, in order.
    # e.g., it will look in the service repo's custom path first, then the engine path.
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(path) for path in template_paths if os.path.isdir(path)]),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Gather all unique template filenames from all template paths.
    all_templates = set()
    for path in template_paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".j2"):
                        # Store the path relative to its template directory
                        all_templates.add(os.path.relpath(os.path.join(root, file), path))

    if not all_templates:
        print(f"INFO: No templates found in any of the paths: {template_paths}", file=sys.stderr)
        return

    # Render each unique template. The ChoiceLoader will find the correct one.
    for template_file in all_templates:
        output_path_raw = os.path.join(output_base, template_file)
        output_path = output_path_raw[:-3] # Remove .j2 extension
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        print(f"INFO: Rendering '{template_file}' to '{output_path}'")
        try:
            template = env.get_template(template_file)
            rendered_content = template.render(context)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
        except Exception as e:
            print(f"ERROR: Failed to render {template_file}: {e}", file=sys.stderr)
            sys.exit(1)

def deep_merge(source, destination):
    """
    Recursively merge source dict into destination dict.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            destination[key] = value
    return destination

def get_current_stage(data: dict) -> str:
    """Determines the current deployment stage from the SSoT data."""
    # The git_version (dev, test, main) directly corresponds to the stage.
    return data.get("git_version", "dev").replace("main", "prod")

def process_network_logic(data: dict) -> dict:
    """
    Applies default network configurations for Docker Compose deployments.
    """
    service_name = data.get("service", {}).get("name", "unknown-service")

    # 1. Define default network structures
    default_network_definitions = {
        "secured": {"name": "services-secured", "external": True},
        "exposed": {"name": "services-exposed", "external": True},
        "interconnect": {"name": "docker-default", "external": True},
        "stack_internal": {"name": f"{service_name}_stack_internal", "driver": "bridge"}
    }
    default_networks_to_join = ["secured", "exposed", "stack_internal", "interconnect"]

    # Get the docker_compose section, creating it if it doesn't exist
    dc_deployments = data.setdefault('deployments', {}).setdefault('docker_compose', {})

    # 2. Merge network_definitions
    custom_network_definitions = dc_deployments.get('network_definitions', {})
    # The custom definitions from service.yml override the defaults
    merged_network_definitions = {**default_network_definitions, **custom_network_definitions}
    dc_deployments['network_definitions'] = merged_network_definitions

    # 3. Merge networks_to_join for the main service
    custom_networks_to_join = dc_deployments.get('networks_to_join', [])
    # Combine lists and remove duplicates, preserving order
    merged_networks_to_join = list(dict.fromkeys(default_networks_to_join + custom_networks_to_join))
    dc_deployments['networks_to_join'] = merged_networks_to_join

    # 4. Ensure dependencies join the stack_internal network
    for dep_name, dep_config in data.get('dependencies', {}).items():
        dep_networks = dep_config.setdefault('networks_to_join', [])
        if 'stack_internal' not in dep_networks:
            dep_networks.append('stack_internal')

    return data

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generates deployment manifests from a JSON SSoT string.")
    parser.add_argument('--ssot-json', required=True, help="The complete, pre-rendered SSoT as a JSON string.")
    parser.add_argument('--template-path', required=True, help="The absolute path to the main template engine directory.")
    
    parser.add_argument('--stage', required=True, help="The deployment stage (e.g., dev, test, prod) to apply overrides for.")
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--deployment-type', help="The deployment type to generate (e.g., 'docker_compose').")
    action_group.add_argument('--process-files', action='store_true', help="Process 'custom_templates/files' only.")
    
    args = parser.parse_args()

    try:
        initial_data = json.loads(args.ssot_json)

        # Ensure 'dependencies' key exists to prevent rendering errors
        initial_data.setdefault('dependencies', {})

        # Inject the current stage into the data
        initial_data.setdefault('service', {})['stage'] = args.stage

        # Apply Stage-Specific Overrides
        current_stage = args.stage
        print(f"INFO: Generating manifests for stage: '{current_stage}'", file=sys.stderr)

        data_with_overrides = deepcopy(initial_data)
        stage_overrides = data_with_overrides.pop("stage_overrides", {})
        if current_stage in stage_overrides:
            print(f"INFO: Applying overrides for stage '{current_stage}'", file=sys.stderr)
            override_data = stage_overrides[current_stage]
            data_with_overrides = deep_merge(override_data, data_with_overrides)

        # --- Apply Default Docker Compose Network Logic (BEFORE recursive rendering) ---
        if args.deployment_type == 'docker_compose':
            print("INFO: Pre-processing and applying default Docker Compose network logic.", file=sys.stderr)
            data_with_overrides = process_network_logic(data_with_overrides)

        # Resolve Jinja2 templates within the SSoT data
        data = render_ssot_recursively(data_with_overrides)

        # --- DEBUG: Print the exact data being used for rendering ---
        print("--- SCRIPT: Using the following data for rendering ---", file=sys.stderr)
        print(json.dumps({"service": data.get("service"), "config": data.get("config"), "deployments": data.get("deployments")}, indent=2), file=sys.stderr)
        print("----------------------------------------------------", file=sys.stderr)

        if not data:
            raise ValueError("SSoT data is empty after loading from JSON.")

        # --- Define template paths with override priority ---
        service_repo_path = os.getcwd() 
        template_engine_path = args.template_path

        if args.deployment_type:
            deployment_type = args.deployment_type
            template_paths = [
                os.path.join(service_repo_path, 'custom_templates', deployment_type),
                os.path.join(template_engine_path, 'templates', deployment_type)
            ]
            output_dir = os.path.join("deployments", deployment_type)
            process_templates(template_paths, output_dir, data)

        if args.process_files:
            template_paths = [
                os.path.join(service_repo_path, 'custom_templates', 'files'),
                os.path.join(template_engine_path, 'templates', 'files')
            ]
            output_dir = os.path.join("deployments", "files")
            process_templates(template_paths, output_dir, data)

        print("INFO: Script finished successfully.")

    except Exception as e:
        print(f"FATAL: An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

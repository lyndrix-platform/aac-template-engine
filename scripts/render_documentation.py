#!/usr/bin/env python3
"""
Renders the final documentation.md by embedding generated artifact content.

This script treats the service's documentation.md as a Jinja2 template and
injects the content of the generated docker-compose.yml, .env, and stack.env
files into their respective placeholders.
"""
import os
import sys
import argparse
import json
from copy import deepcopy
from jinja2 import Environment, FileSystemLoader


def read_file_content(path: str) -> str:
    """Reads the content of a file, returns a placeholder if not found."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"File not found at: {path}"
    except Exception as e:
        return f"Error reading file {path}: {e}"

def deep_merge(source, destination):
    """Recursively merge source dict into destination dict."""
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            destination[key] = value
    return destination

def render_ssot_recursively(data: dict) -> dict:
    """Recursively renders Jinja2 templates within the SSoT data structure."""
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    previous_render = ""
    current_render = json.dumps(data)
    for _ in range(10):
        if previous_render == current_render:
            break
        previous_render = current_render
        context = json.loads(previous_render)
        template = env.from_string(previous_render)
        current_render = template.render(context)
    else:
        print("WARNING: Recursive rendering did not stabilize after 10 passes.", file=sys.stderr)
    return json.loads(current_render)

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Renders a documentation.md file with embedded artifacts.")
    parser.add_argument('--ssot-json', required=True, help="The complete SSoT as a JSON string from service.yml.")
    parser.add_argument('--stage', required=True, help="The deployment stage (e.g., dev, test, prod).")
    parser.add_argument('--template-file', default='documentation.md', help="Path to the documentation template file.")
    parser.add_argument('--compose-file', default='deployments/docker_compose/docker-compose.yml', help="Path to the Docker Compose file.")
    parser.add_argument('--dotenv-file', default='deployments/docker_compose/.env', help="Path to the .env file.")
    parser.add_argument('--stackenv-file', default='deployments/docker_compose/stack.env', help="Path to the stack.env file.")
    parser.add_argument('--output-file', default='documentation.md', help="Path to write the final output file.")
    args = parser.parse_args()
    
    if not os.path.exists(args.template_file):
        print(f"INFO: Template file '{args.template_file}' not found. Skipping documentation rendering.", file=sys.stderr)
        sys.exit(0)

    print("INFO: Rendering documentation with embedded artifacts...", file=sys.stderr)

    # 1. Load initial data and apply stage-specific overrides
    initial_data = json.loads(args.ssot_json)
    initial_data.setdefault('service', {})['stage'] = args.stage

    data_with_overrides = deepcopy(initial_data)
    stage_overrides = data_with_overrides.pop("stage_overrides", {})
    if args.stage in stage_overrides:
        print(f"INFO: Applying overrides for stage '{args.stage}' to documentation context.", file=sys.stderr)
        override_data = stage_overrides[args.stage]
        data_with_overrides = deep_merge(override_data, data_with_overrides)

    # 2. Recursively render the SSoT data itself to resolve internal templates
    context = render_ssot_recursively(data_with_overrides)

    # 3. Add the content of the generated files to the context
    # This makes them available for embedding in the documentation.
    context.update({
        'DOCKER_COMPOSE_CONTENT': read_file_content(args.compose_file),
        'DOT_ENV_CONTENT': read_file_content(args.dotenv_file),
        'STACK_ENV_CONTENT': read_file_content(args.stackenv_file)
    })

    # Ensure keys used by the template exist to prevent errors, even if empty
    context.setdefault('service', {})
    context.setdefault('config', {})
    context.setdefault('deployments', {}).setdefault('docker_compose', {})
    context.setdefault('volumes', [])
    context.setdefault('ports', [])
    context.setdefault('dependencies', {})

    # 4. Use Jinja2 to render the final documentation file
    env = Environment(loader=FileSystemLoader(os.path.dirname(args.template_file) or '.'), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(os.path.basename(args.template_file))
    try:
        rendered_content = template.render(context)
    except Exception as e:
        print(f"ERROR: Failed to render documentation template: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output_file, 'w', encoding='utf-8') as f:
        f.write(rendered_content)

    print(f"INFO: Successfully rendered and updated '{args.output_file}'.", file=sys.stderr)

if __name__ == "__main__":
    main()
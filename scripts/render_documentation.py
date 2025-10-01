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

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Renders a documentation.md file with embedded artifacts.")
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

    # The context for rendering is the content of the generated files
    context = {
        'DOCKER_COMPOSE_CONTENT': read_file_content(args.compose_file),
        'DOT_ENV_CONTENT': read_file_content(args.dotenv_file),
        'STACK_ENV_CONTENT': read_file_content(args.stackenv_file)
    }

    # Use Jinja2 to render the documentation file itself
    env = Environment(loader=FileSystemLoader(os.path.dirname(args.template_file) or '.'), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(os.path.basename(args.template_file))
    rendered_content = template.render(context)

    with open(args.output_file, 'w', encoding='utf-8') as f:
        f.write(rendered_content)

    print(f"INFO: Successfully rendered and updated '{args.output_file}'.", file=sys.stderr)

if __name__ == "__main__":
    main()
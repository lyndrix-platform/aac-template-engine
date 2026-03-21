# scripts/manifest_generator/engine.py
import os
import yaml
from jinja2 import Environment, FileSystemLoader, ChoiceLoader

class ManifestEngine:
    def __init__(self, template_base_path: str, service_repo_path: str):
        self.template_base = template_base_path
        self.service_path = service_repo_path

    def _to_yaml_filter(self, data, indent=2):
        return yaml.dump(data, indent=indent, default_flow_style=False, sort_keys=False)

    def render_all(self, context: dict, deployment_type: str):
        # Setup loader: Look in Service Custom Templates FIRST, then Global Engine
        loader = ChoiceLoader([
            FileSystemLoader(os.path.join(self.service_path, 'custom_templates', deployment_type)),
            FileSystemLoader(os.path.join(self.template_base, 'templates', deployment_type))
        ])

        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        env.filters['to_yaml'] = self._to_yaml_filter

        output_dir = os.path.join("deployments", deployment_type)
        os.makedirs(output_dir, exist_ok=True)

        # Render every template found in the directory
        for template_name in env.list_templates():
            if not template_name.endswith('.j2'): continue
            
            print(f"  [>] Rendering: {template_name}")
            template = env.get_template(template_name)
            output_file = os.path.join(output_dir, template_name.replace('.j2', ''))
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(template.render(context))
                
                
                
    def render_documentation(self, context: dict):
        # Lade Templates aus dem 'documentation' Ordner
        loader = ChoiceLoader([
            FileSystemLoader(os.path.join(self.service_path, 'custom_templates', 'documentation')),
            FileSystemLoader(os.path.join(self.template_base, 'templates', 'documentation'))
        ])
        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        env.filters['to_yaml'] = self._to_yaml_filter

        # MkDocs Struktur vorbereiten
        base_output_dir = os.path.join("deployments", "documentation")
        docs_output_dir = os.path.join(base_output_dir, "docs")
        os.makedirs(docs_output_dir, exist_ok=True)

        for template_name in env.list_templates():
            if not template_name.endswith('.j2'): continue
            
            print(f"  [>] Rendering Documentation: {template_name}")
            template = env.get_template(template_name)
            
            # Dateinamen für MkDocs anpassen
            if template_name == 'mkdocs.yml.j2':
                output_file = os.path.join(base_output_dir, 'mkdocs.yml')
            elif template_name == 'documentation.md.j2':
                output_file = os.path.join(docs_output_dir, 'index.md')
            else:
                output_file = os.path.join(docs_output_dir, template_name.replace('.j2', ''))
                
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(template.render(context))
                
    def render_files(self, context: dict):
        base_src_dir = os.path.join(self.service_path, 'custom_templates', 'files')
        if not os.path.exists(base_src_dir):
            print("  [>] No custom files directory found. Skipping.")
            return

        # Load templates directly from the custom files directory
        loader = FileSystemLoader(base_src_dir)
        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        env.filters['to_yaml'] = self._to_yaml_filter

        output_base_dir = os.path.join("deployments", "files")

        for template_name in env.list_templates():
            if not template_name.endswith('.j2'): 
                continue
                
            print(f"  [>] Rendering Custom File: {template_name}")
            template = env.get_template(template_name)
            
            # This preserves subdirectory structures (e.g. data/seatcupra.netrc.j2 -> data/seatcupra.netrc)
            relative_out_path = template_name.replace('.j2', '')
            output_file = os.path.join(output_base_dir, relative_out_path)
            
            # Ensure the target subdirectories exist
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(template.render(context))
                
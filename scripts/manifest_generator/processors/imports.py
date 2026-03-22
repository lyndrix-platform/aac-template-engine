# scripts/manifest_generator/processors/imports.py
import os
import yaml
from copy import deepcopy
from .base import BaseProcessor

class ImportProcessor(BaseProcessor):
    def __init__(self, template_base_path: str):
        # Normalize the path to handle relative/absolute inputs correctly
        self.template_path = os.path.abspath(template_base_path)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merges the override dictionary heavily onto the base dictionary."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)
        return base

    def process(self, context: dict) -> dict:
        # 1. Process Main Service Import
        if 'import' in context:
            # Ensure we strip any leading slashes from the 'import' string 
            # so os.path.join doesn't treat it as a root path
            clean_import = context['import'].lstrip('/')
            import_path = os.path.join(self.template_path, clean_import)
            
            if os.path.isfile(import_path):
                print(f"  [I] Importing base template: {import_path}")
                with open(import_path, 'r', encoding='utf-8') as f:
                    base_def = yaml.safe_load(f) or {}
                
                overrides = context.get('overrides', {})
                context = self._deep_merge(base_def, overrides)
                
                # Ensure service identity is strictly maintained from overrides
                if 'service' in overrides:
                    context['service'] = overrides['service']
            else:
                print(f"  [X] FATAL: Main import path not found: {import_path}")
                raise FileNotFoundError(f"Missing catalog file: {import_path}")

        # 2. Process Dependency Imports (Sidecar deployment mode)
        deps = context.get('dependencies', {})
        for dep_name, dep_cfg in deps.items():
            if 'import' in dep_cfg:
                import_path = os.path.join(self.template_path, dep_cfg['import'])
                if os.path.isfile(import_path):
                    print(f"  [I] Importing base template for Dependency '{dep_name}': {dep_cfg['import']}")
                    with open(import_path, 'r', encoding='utf-8') as f:
                        base_def = yaml.safe_load(f) or {}
                    
                    overrides = dep_cfg.get('overrides', {})
                    merged = self._deep_merge(base_def, overrides)
                    
                    # Replace the dependency config with the fully merged object
                    deps[dep_name] = merged
                else:
                    print(f"  [X] FATAL: Dependency import path not found: {import_path}")
                    raise FileNotFoundError(f"Missing catalog file: {import_path}")

        return context
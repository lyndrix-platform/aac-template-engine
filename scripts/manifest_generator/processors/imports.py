# scripts/manifest_generator/processors/imports.py
import os
import yaml
from copy import deepcopy
from .base import BaseProcessor

class ImportProcessor(BaseProcessor):
    def __init__(self, template_base_path: str):
        # This requires the base path of the engine to find the 'catalog' folder
        self.template_path = template_base_path

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merges the override dictionary heavily onto the base dictionary."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)
        return base

    def process(self, context: dict) -> dict:
        # 1. Process Main Service Import (Standalone deployment mode)
        if 'import' in context:
            import_path = os.path.join(self.template_path, context['import'])
            if os.path.isfile(import_path):
                print(f"  [I] Importing base template for Main Service: {context['import']}")
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
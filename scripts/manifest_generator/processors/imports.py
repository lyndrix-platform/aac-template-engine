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

    def _split_image(self, image_ref: str):
        """Split Docker image ref into repo/tag with safe defaults."""
        if not isinstance(image_ref, str) or not image_ref:
            return None, None

        # Keep digest refs stable and default tag handling in the template pipeline.
        if '@' in image_ref:
            repo = image_ref.split('@', 1)[0]
            return repo, 'latest'

        if ':' not in image_ref:
            return image_ref, 'latest'

        repo, tail = image_ref.rsplit(':', 1)
        # If the tail still contains a slash, we likely split on registry port, not tag.
        if '/' in tail:
            return image_ref, 'latest'

        return repo, tail or 'latest'

    def _normalize_environment(self, dep_cfg: dict):
        env = dep_cfg.get('environment')
        if not isinstance(env, list):
            return

        env_dict = {}
        for item in env:
            if isinstance(item, str) and '=' in item:
                key, value = item.split('=', 1)
                env_dict[key] = value
        if env_dict:
            dep_cfg['environment'] = env_dict

    def _normalize_ports(self, dep_cfg: dict):
        ports = dep_cfg.get('ports')
        if not isinstance(ports, list):
            return

        normalized = []
        for p in ports:
            if isinstance(p, dict):
                normalized.append(p)
                continue
            if not isinstance(p, str):
                continue

            raw = p.strip()
            if not raw:
                continue

            protocol = 'TCP'
            if '/' in raw:
                raw, proto = raw.split('/', 1)
                if proto:
                    protocol = proto.upper()

            if ':' in raw:
                external, internal = raw.split(':', 1)
            else:
                external, internal = raw, raw

            try:
                normalized.append({
                    'name': 'web',
                    'external_port': int(external),
                    'port': int(internal),
                    'protocol': protocol
                })
            except ValueError:
                continue

        dep_cfg['ports'] = normalized

    def _normalize_dependency_schema(self, context: dict):
        main_svc = context.get('service', {}).get('name', 'app')
        deps = context.get('dependencies', {})
        if not isinstance(deps, dict):
            return

        for dep_name, dep_cfg in deps.items():
            if not isinstance(dep_cfg, dict):
                continue

            # Accept compose-style keys as fallback.
            if not dep_cfg.get('name'):
                dep_cfg['name'] = dep_cfg.get('container_name') or f"{main_svc}-{dep_name}"

            if dep_cfg.get('restart') and not dep_cfg.get('restart_policy'):
                dep_cfg['restart_policy'] = dep_cfg['restart']

            if dep_cfg.get('image') and not dep_cfg.get('image_repo'):
                repo, tag = self._split_image(dep_cfg.get('image'))
                if repo:
                    dep_cfg['image_repo'] = repo
                if tag and not dep_cfg.get('image_tag'):
                    dep_cfg['image_tag'] = tag

            dep_cfg.setdefault('image_tag', 'latest')

            self._normalize_environment(dep_cfg)
            self._normalize_ports(dep_cfg)

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

            # 3. Normalize dependency entries to accept compose-like shorthand blocks.
            self._normalize_dependency_schema(context)

        return context
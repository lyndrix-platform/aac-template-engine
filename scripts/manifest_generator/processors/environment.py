# scripts/manifest_generator/processors/environment.py
from .base import BaseProcessor

class EnvironmentProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        """
        Forcefully migrates legacy env/secret blocks to root level 
        and prepares them for the rendering engine.
        """
        # 1. Initialize root-level containers if missing
        context.setdefault('environment', {})
        context.setdefault('secrets', {})
        
        dc = context.get('deployments', {}).get('docker_compose', {})

        # --- PART A: INTERNAL LIFTING (Source Logic) ---

        # Lift legacy 'dot_env' to root 'environment'
        legacy_env = dc.pop('dot_env', {}) # .pop() removes it from the old location
        if legacy_env:
            print(f"  [!] Lifting legacy 'dot_env' to root 'environment' for {context['service']['name']}")
            for k, v in legacy_env.items():
                # Root level wins if there is a conflict
                if k not in context['environment']:
                    context['environment'][k] = v

        # Lift legacy 'stack_env' to root 'secrets'
        legacy_secrets = dc.pop('stack_env', {})
        if legacy_secrets:
            print(f"  [!] Lifting legacy 'stack_env' to root 'secrets' for {context['service']['name']}")
            for k, v in legacy_secrets.items():
                if k not in context['secrets']:
                    context['secrets'][k] = v

        # --- PART B: PREPARATION (Rendering Logic) ---

        # These are the variables the 'Dumb View' (.env.j2) will actually loop over
        context['processed_env'] = {}
        context['processed_secrets'] = {}

        # 1. Process Main Service Environment
        for k, v in context['environment'].items():
            context['processed_env'][k] = str(v)

        # 2. Process Main Service Secrets
        for k, v in context['secrets'].items():
            context['processed_secrets'][k] = str(v)

        # 3. Handle Dependencies (Sidecars)
        # We also standardize dependency env vars here
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_env = dep_cfg.get('environment', {})
            # We don't lift these to root (they belong to the dep), but we do split them
            for k, v in dep_env.items():
                if any(x in k.lower() for x in ['pass', 'secret', 'token', 'key']):
                    context['processed_secrets'][k] = str(v)
                else:
                    context['processed_env'][k] = str(v)

        return context
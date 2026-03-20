from .base import BaseProcessor

class EnvironmentProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        # 1. Initialize root containers
        context.setdefault('environment', {})
        context.setdefault('secrets', {})
        
        dc = context.get('deployments', {}).get('docker_compose', {})

        # --- PART A: ROBUST LIFTING ---
        # Look for env vars in both the root 'dc' and 'dc.environment' (if it exists)
        legacy_env = dc.pop('dot_env', {}) 
        if legacy_env:
            for k, v in legacy_env.items():
                context['environment'][k] = v
                
        # Also grab anything already sitting in dc['environment']
        dc_env = dc.pop('environment', {})
        if dc_env:
            for k, v in dc_env.items():
                context['environment'][k] = v

        legacy_secrets = dc.pop('stack_env', {})
        if legacy_secrets:
            for k, v in legacy_secrets.items():
                context['secrets'][k] = v

        # --- PART B: PREPARATION ---
        context['processed_env'] = {}
        context['processed_secrets'] = {}

        # 1. Process Main Service
        for k, v in context['environment'].items():
            context['processed_env'][k] = str(v)

        for k, v in context['secrets'].items():
            context['processed_secrets'][k] = str(v)

        # 2. Process Dependencies
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_env = dep_cfg.get('environment', {})
            for k, v in dep_env.items():
                if any(x in k.lower() for x in ['pass', 'secret', 'token', 'key']):
                    context['processed_secrets'][k] = str(v)
                else:
                    context['processed_env'][k] = str(v)

        return context
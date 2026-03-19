from .base import BaseProcessor

class SpecProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        """Extracts and sanitizes advanced Docker Compose hardware and privilege specifications."""
        dc = context.get('deployments', {}).get('docker_compose', {})
        
        # HIER IST DER FIX: 'security_opt' ist jetzt einfach Teil der Whitelist
        advanced_keys = [
            'network_mode', 'user', 'privileged', 'runtime', 
            'cap_add', 'cap_drop', 'devices', 'deploy', 'security_opt' 
        ]
        
        # 1. Process Main Service Specs
        processed_specs = {}
        for key in advanced_keys:
            if key in dc:
                processed_specs[key] = dc[key]
                
        context['processed_specs'] = processed_specs
        
        # 2. Process Dependency Specs (Sidecars)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_specs = {}
            for key in advanced_keys:
                if key in dep_cfg:
                    dep_specs[key] = dep_cfg[key]
            dep_cfg['processed_specs'] = dep_specs

        return context
# scripts/manifest_generator/processors/specs.py
from .base import BaseProcessor

class SpecProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        
        # Keys handled explicitly by the .j2 template (the "Dumb" parts)
        template_keys = [
            'command', 'restart_policy', 'host_base_path', 'networks_to_join', 
            'network_definitions', 'volumes', 'healthcheck', 'depends_on', 
            'environment', 'secrets'
        ]

        def get_clean_specs(data):
            # Capture everything else: deploy, privileged, runtime, network_mode, etc.
            return {k: v for k, v in data.items() if k not in template_keys and v is not None}

        # 1. Process Main Service
        processed_specs = get_clean_specs(dc)

        # 2. Process Dependencies & Host-Gateway Injection
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_specs = get_clean_specs(dep_cfg)
            
            # Connectivity Logic: If sidecar is host mode, main app needs a DNS hint
            if dep_cfg.get('network_mode') == 'host':
                extra_hosts = processed_specs.setdefault('extra_hosts', [])
                mapping = f"{dep_cfg.get('name')}:host-gateway"
                if mapping not in extra_hosts:
                    extra_hosts.append(mapping)
            
            dep_cfg['processed_specs'] = dep_specs

        context['processed_specs'] = processed_specs
        return context
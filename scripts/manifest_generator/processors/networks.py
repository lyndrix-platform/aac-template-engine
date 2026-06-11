# scripts/manifest_generator/processors/networks.py
from .base import BaseProcessor

class NetworkProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc_name = context.get('service', {}).get('name', 'app')
        dc = context.setdefault('deployments', {}).setdefault('docker_compose', {})
        cfg = context.get('config', {})
        ports = context.get('ports', [])
        
        # 1. Infrastructure Definitions
        context['network_definitions'] = {
            "secured": {"name": "services-secured", "external": True},
            "exposed": {"name": "services-exposed", "external": True},
            "interconnect": {"name": "docker-default", "external": True},
            "stack_internal": {"name": f"{svc_name}_stack_internal", "driver": "bridge"}
        }

        # 2. Main Service Logic
        if dc.get('network_mode'):
            context['processed_networks'] = []
        else:
            assigned = ["interconnect", "stack_internal"]
            if cfg.get('integrations', {}).get('traefik', {}).get('enabled', False):
                assigned.append("secured")
            
            if any(isinstance(p, dict) and p.get('external_port') is not None for p in ports):
                assigned.append("exposed")

            context['processed_networks'] = sorted(list(set(assigned + dc.get('networks_to_join', []))))
        
        # 3. Dependency Logic
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            if dep_cfg.get('network_mode'):
                dep_cfg['processed_networks'] = []
                continue

            assigned = ["stack_internal"]
            dep_cfg['processed_networks'] = sorted(
                list(set(assigned + dep_cfg.get('networks_to_join', [])))
            )

        return context
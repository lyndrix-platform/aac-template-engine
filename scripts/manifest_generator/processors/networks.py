# scripts/manifest_generator/processors/networks.py
from .base import BaseProcessor

class NetworkProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc_name = context.get('service', {}).get('name', 'app')
        dc = context.setdefault('deployments', {}).setdefault('docker_compose', {})
        cfg = context.get('config', {})
        ports = context.get('ports', [])
        
        # 1. Infrastructure Definitions (The "What")
        # These are the actual network configs rendered at the bottom of the file
        default_defs = {
            "secured": {"name": "services-secured", "external": True},
            "exposed": {"name": "services-exposed", "external": True},
            "interconnect": {"name": "docker-default", "external": True},
            "stack_internal": {"name": f"{svc_name}_stack_internal", "driver": "bridge"}
        }
        custom_defs = dc.get('network_definitions', {})
        context['network_definitions'] = {**default_defs, **custom_defs}

        # 2. Logic Switches (The "Who joins what")
        if dc.get('network_mode') == 'host':
            context['processed_networks'] = []
            return context

        # Backbone networks always joined
        assigned = ["interconnect", "stack_internal"]
        
        # SWITCH: Secured (Traefik)
        traefik_enabled = cfg.get('integrations', {}).get('traefik', {}).get('enabled', False)
        if traefik_enabled:
            assigned.append("secured")
        
        # SWITCH: Exposed (Host Ports)
        # Check if any port entry has an external_port set
        has_external_port = any(
            isinstance(p, dict) and p.get('external_port') is not None 
            for p in ports
        )
        if has_external_port:
            assigned.append("exposed")

        # 3. Manual Overrides (For edge cases)
        custom_join = dc.get('networks_to_join', [])
        
        # Final deduplication and sorting
        context['processed_networks'] = sorted(list(set(assigned + custom_join)))
        
        # Ensure dependencies also join the internal hallway
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_nets = dep_cfg.setdefault('processed_networks', [])
            if "stack_internal" not in dep_nets:
                dep_nets.append("stack_internal")

        return context
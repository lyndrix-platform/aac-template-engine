# scripts/manifest_generator/processors/networks.py

class NetworkProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc_name = context.get('service', {}).get('name', 'app')
        dc = context.setdefault('deployments', {}).setdefault('docker_compose', {})
        cfg = context.get('config', {})
        ports = context.get('ports', [])
        
        # 1. Infrastructure Definitions
        default_defs = {
            "secured": {"name": "services-secured", "external": True},
            "exposed": {"name": "services-exposed", "external": True},
            "interconnect": {"name": "docker-default", "external": True},
            "stack_internal": {"name": f"{svc_name}_stack_internal", "driver": "bridge"}
        }
        custom_defs = dc.get('network_definitions', {})
        context['network_definitions'] = {**default_defs, **custom_defs}

        # 2. Main Service Logic
        # If main service is host mode, it gets NO networks.
        if dc.get('network_mode') == 'host':
            context['processed_networks'] = []
        else:
            assigned = ["interconnect", "stack_internal"]
            
            if cfg.get('integrations', {}).get('traefik', {}).get('enabled', False):
                assigned.append("secured")
            
            has_external_port = any(
                isinstance(p, dict) and p.get('external_port') is not None 
                for p in ports
            )
            if has_external_port:
                assigned.append("exposed")

            custom_join = dc.get('networks_to_join', [])
            context['processed_networks'] = sorted(list(set(assigned + custom_join)))
        
        # 3. Dependency Logic (CRITICAL FIX HERE)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            # If the dependency is using host network mode, 
            # we MUST NOT assign it to the internal hallway.
            if dep_cfg.get('network_mode') == 'host':
                dep_cfg['processed_networks'] = []
                continue

            dep_nets = dep_cfg.setdefault('processed_networks', [])
            if "stack_internal" not in dep_nets:
                dep_nets.append("stack_internal")

        return context
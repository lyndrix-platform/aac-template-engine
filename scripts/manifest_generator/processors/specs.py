# scripts/manifest_generator/processors/specs.py
from .base import BaseProcessor

class SpecProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        
        # A comprehensive blacklist to prevent internal or explicitly handled keys 
        # from leaking into the 'catch-all' processed_specs block.
        blacklist = {
            # Standard explicitly handled Docker Compose keys
            'image', 'container_name', 'hostname', 'restart', 'restart_policy',
            'env_file', 'ports', 'volumes', 'networks', 'labels', 'healthcheck',
            'command', 'depends_on', 'environment', 'secrets',
            
            # SSoT / Template Engine internal keys
            'name', 'image_repo', 'image_tag', 'category', 'description', 
            'friendly_name', 'icon', 'stage', 'host_base_path', 
            'routing_host_network', 'networks_to_join', 'network_definitions',
            'dot_env', 'stack_env'
        }

        def get_clean_specs(data):
            # Keep ONLY valid advanced Docker Compose keys (deploy, extra_hosts, logging, etc.)
            return {
                k: v for k, v in data.items() 
                if k not in blacklist 
                and not str(k).startswith('processed_') 
                and v is not None
            }

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
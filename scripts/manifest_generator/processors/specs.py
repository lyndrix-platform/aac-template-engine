from .base import BaseProcessor

class SpecProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        main_svc = context.get('service', {}).get('name', 'app')
        
        blacklist = {
            'image', 'container_name', 'hostname', 'restart', 'restart_policy',
            'env_file', 'ports', 'volumes', 'networks', 'labels', 'healthcheck',
            'command', 'depends_on', 'environment', 'secrets',
            'name', 'image_repo', 'image_tag', 'category', 'description', 
            'friendly_name', 'icon', 'stage', 'host_base_path', 
            'routing_host_network', 'networks_to_join', 'network_definitions',
            'dot_env', 'stack_env'
        }

        def get_clean_specs(data):
            return {
                k: v for k, v in data.items() 
                if k not in blacklist 
                and not str(k).startswith('processed_') 
                and v is not None
            }

        # 1. Process Main Service
        processed_specs = get_clean_specs(dc)
        depends_on_block = {}

        # 2. Process Dependencies
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_specs = get_clean_specs(dep_cfg)
            dep_svc_name = dep_cfg.get('name', f"{main_svc}-{dep_name}")
            
            if dep_cfg.get('network_mode') == 'host':
                extra_hosts = processed_specs.setdefault('extra_hosts', [])
                mapping = f"{dep_svc_name}:host-gateway"
                if mapping not in extra_hosts:
                    extra_hosts.append(mapping)
            
            # INJECT DEPENDS_ON LOGIC
            if 'healthcheck' in dep_cfg:
                depends_on_block[dep_svc_name] = {"condition": "service_healthy"}
            else:
                depends_on_block[dep_svc_name] = {"condition": "service_started"}

            dep_cfg['processed_specs'] = dep_specs

        if depends_on_block:
            processed_specs['depends_on'] = depends_on_block

        context['processed_specs'] = processed_specs
        return context
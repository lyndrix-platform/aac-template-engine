# scripts/manifest_generator/processors/volumes.py
from .base import BaseProcessor

class VolumeProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        base_path = dc.get('host_base_path', '/export/docker')
        main_svc = context.get('service', {}).get('name', 'app')
        vol_defs = context.get('volumes', {}) # Global definitions from SSoT

        context['processed_volumes'] = []
        context['named_volumes'] = {}

        # 1. Main Service Volumes (Only mount what is explicitly requested in deployments.docker_compose.volumes)
        for mount_str in dc.get('volumes', []):
            parts = mount_str.split(':')
            v_id = parts[0]
            target = parts[1] if len(parts) > 1 else f"/{v_id}"

            v_def = vol_defs.get(v_id, {})
            v_type = v_def.get('type', 'bind')

            if v_type == 'bind':
                source = v_def.get('source', f"{base_path}/{main_svc}/{v_id}")
            elif v_def.get('driver'):
                source = v_id
                context['named_volumes'][v_id] = v_def
            else:
                source = f"{base_path}/{main_svc}/{v_id}"

            context['processed_volumes'].append(f"{source}:{target}")

        # 2. Dependency Volumes (Mount based on the component catalog definition)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_svc_name = dep_cfg.get('name', f"{main_svc}-{dep_name}")
            dep_cfg['processed_volumes'] = []
            
            dep_vols = dep_cfg.get('volumes', {})
            for v_id, v_def in dep_vols.items():
                target = v_def.get('target', f"/{v_id}")
                v_type = v_def.get('type', 'bind')

                if v_type == 'bind':
                    source = v_def.get('source', f"{base_path}/{dep_svc_name}/{v_id}")
                elif v_def.get('driver'):
                    source = v_id
                    context['named_volumes'][v_id] = v_def
                else:
                    source = f"{base_path}/{dep_svc_name}/{v_id}"

                dep_cfg['processed_volumes'].append(f"{source}:{target}")

        return context
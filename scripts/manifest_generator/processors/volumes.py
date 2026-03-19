# scripts/manifest_generator/processors/volumes.py
from .base import BaseProcessor

class VolumeProcessor(BaseProcessor):
    def _generate_volume_string(self, v_id, v_def, svc_name, base_path, context):
        """Helper to generate the final source:target string and register named volumes."""
        target = v_def.get('target', f"/{v_id}")
        v_type = v_def.get('type', 'bind')

        if v_type == 'bind':
            # Use explicit source if provided, otherwise follow standard path convention
            source = v_def.get('source', f"{base_path}/{svc_name}/{v_id}")
        elif v_def.get('driver'):
            # It's a Docker named volume (e.g., using longhorn or local driver)
            source = v_id
            context['named_volumes'][v_id] = v_def
        else:
            # Fallback to standard bind path
            source = f"{base_path}/{svc_name}/{v_id}"

        return f"{source}:{target}"

    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        base_path = dc.get('host_base_path', '/export/docker')
        main_svc = context.get('service', {}).get('name', 'app')
        vol_defs = context.get('volumes', {}) # Global definitions from SSoT

        context['processed_volumes'] = []
        context['named_volumes'] = {}

        # 1. Process Main Service Volumes
        # These come from the 'deployments.docker_compose.volumes' list
        for mount_str in dc.get('volumes', []):
            if not isinstance(mount_str, str):
                continue
                
            parts = mount_str.split(':')
            v_id = parts[0]
            
            # Fetch definition from the global volumes block if it exists
            v_def = vol_defs.get(v_id, {})
            # If the mount_str had a specific target (e.g. "db:/var/lib/mysql"), use it
            if len(parts) > 1:
                v_def['target'] = parts[1]

            vol_string = self._generate_volume_string(v_id, v_def, main_svc, base_path, context)
            context['processed_volumes'].append(vol_string)

        # 2. Process Dependency Volumes (Sidecars)
        # These come from the catalog/blueprint 'volumes' dictionary
        deps = context.get('dependencies', {})
        if isinstance(deps, dict):
            for dep_name, dep_cfg in deps.items():
                dep_svc_name = dep_cfg.get('name', f"{main_svc}-{dep_name}")
                dep_cfg['processed_volumes'] = []
                
                dep_vols = dep_cfg.get('volumes', {})
                
                # CRITICAL FIX: Ensure dep_vols is a dictionary before calling .items()
                if not isinstance(dep_vols, dict):
                    print(f"  [!] WARNING: volumes for dependency '{dep_name}' is not a dictionary. Skipping.")
                    continue

                for v_id, v_def in dep_vols.items():
                    if not isinstance(v_def, dict):
                        continue
                        
                    vol_string = self._generate_volume_string(v_id, v_def, dep_svc_name, base_path, context)
                    dep_cfg['processed_volumes'].append(vol_string)

        return context
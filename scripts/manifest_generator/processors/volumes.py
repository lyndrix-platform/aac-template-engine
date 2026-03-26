# scripts/manifest_generator/processors/volumes.py
from .base import BaseProcessor

class VolumeProcessor(BaseProcessor):
    def _generate_volume_string(self, v_id, v_def, svc_name, base_path, context, mount_str):
        """Helper to generate the final source:target string and register named volumes."""
        parts = mount_str.split(':')
        target = v_def.get('target', f"/{v_id}")
        flags = ""
        
        if len(parts) >= 2:
            target = parts[1]
        if len(parts) >= 3:
            flags = f":{parts[2]}"

        # FIX: Explicitly evaluate 'driver' first. 
        # Any definition with a custom driver belongs in named_volumes.
        if v_def.get('driver'):
            source = v_id
            context['named_volumes'][v_id] = v_def
        else:
            # Fallback for standard bind mounts or other un-driven types
            v_type = v_def.get('type', 'bind')
            
            if v_type == 'bind':
                # Native support for single-file mounts without Jinja-variables
                if 'file' in v_def:
                    source = f"{base_path}/{svc_name}/{v_def['file']}"
                else:
                    # Standard behavior for folders or explicit 'source' strings
                    source = v_def.get('source', f"{base_path}/{svc_name}/{v_id}")
            else:
                source = f"{base_path}/{svc_name}/{v_id}"

        return f"{source}:{target}{flags}"

    def process(self, context: dict) -> dict:
        dc = context.get('deployments', {}).get('docker_compose', {})
        base_path = dc.get('host_base_path', '/export/docker')
        main_svc = context.get('service', {}).get('name', 'app')
        vol_defs = context.get('volumes', {}) 

        context['processed_volumes'] = []
        context['named_volumes'] = {}
        
        # 1. Process Main Service Volumes
        for mount_str in dc.get('volumes', []):
            if not isinstance(mount_str, str):
                continue
                
            v_id = mount_str.split(':')[0]
            v_def = vol_defs.get(v_id, {})

            vol_string = self._generate_volume_string(v_id, v_def, main_svc, base_path, context, mount_str)
            context['processed_volumes'].append(vol_string)
            
        # 2. Automatically lift any lingering 'raw_volumes'
        for raw_vol in dc.get('raw_volumes', []):
            if raw_vol not in context['processed_volumes']:
                context['processed_volumes'].append(raw_vol)

        # 3. Process Dependency Volumes (Sidecars)
        deps = context.get('dependencies', {})
        if isinstance(deps, dict):
            for dep_name, dep_cfg in deps.items():
                dep_svc_name = dep_cfg.get('name', f"{main_svc}-{dep_name}")
                dep_cfg['processed_volumes'] = []
                
                dep_vols = dep_cfg.get('volumes', {})
                if not isinstance(dep_vols, dict):
                    continue

                for v_id, v_def in dep_vols.items():
                    if not isinstance(v_def, dict):
                        continue
                        
                    target = v_def.get('target', f"/{v_id}")
                    flags = v_def.get('flags', '')
                    mock_mount_str = f"{v_id}:{target}"
                    if flags:
                        mock_mount_str += f":{flags}"
                        
                    vol_string = self._generate_volume_string(v_id, v_def, main_svc, base_path, context, mock_mount_str)
                    dep_cfg['processed_volumes'].append(vol_string)

        return context
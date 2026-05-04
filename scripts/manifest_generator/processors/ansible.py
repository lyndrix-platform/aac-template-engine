from .base import BaseProcessor

class AnsibleProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        """
        Pre-calculates all host directories and their required ownership 
        so Ansible can just execute a flat list without complex Jinja logic.
        """
        ansible_dirs = []
        dc = context.get('deployments', {}).get('docker_compose', {})
        base_path = dc.get('host_base_path', '/export/docker')
        main_svc = context.get('service', {}).get('name', 'app')

        # 1. Get default IDs from the root environment block
        env = context.get('environment', {})
        default_puid = str(env.get('PUID', '1000'))
        default_pgid = str(env.get('PGID', '1000'))

        def add_dir(path, is_db, override_uid=None, override_gid=None):
            ansible_dirs.append({
                'path': path,
                'owner': override_uid if override_uid else ('999' if is_db else default_puid),
                'group': override_gid if override_gid else ('999' if is_db else default_pgid),
                'mode': '0700' if is_db else '0755'
            })

        # Helper function to evaluate if a mount is likely a file
        def is_file_mount(source_path):
            # If the source string has an extension, it's a file mount.
            # Example: /export/docker/app/config.json
            return '.' in source_path.split('/')[-1]

        # Helper to resolve the host source path from a volume definition,
        # mirroring VolumeProcessor logic. Returns None for named volumes.
        def resolve_source(v_id, v_def, svc_name):
            if v_def.get('driver'):
                return None
            v_type = v_def.get('type', 'bind')
            if v_type == 'bind':
                if 'file' in v_def:
                    return f"{base_path}/{svc_name}/{v_def['file']}"
                return v_def.get('source', f"{base_path}/{svc_name}/{v_id}")
            return f"{base_path}/{svc_name}/{v_id}"

        # 2. Build a source-path → (uid, gid) map for main service volumes
        #    that carry explicit uid/gid overrides in their volume definition.
        vol_defs = context.get('volumes', {})
        uid_gid_map = {}
        for mount_str in dc.get('volumes', []):
            if not isinstance(mount_str, str):
                continue
            v_id = mount_str.split(':')[0]
            v_def = vol_defs.get(v_id, {})
            if v_def.get('uid') or v_def.get('gid'):
                source = resolve_source(v_id, v_def, main_svc.lower())
                if source:
                    uid_gid_map[source] = (
                        str(v_def['uid']) if v_def.get('uid') else None,
                        str(v_def['gid']) if v_def.get('gid') else None,
                    )

        # 3. Add the main service base directory
        service_target_dir = f"{base_path}/{main_svc.lower()}"
        add_dir(service_target_dir, is_db=False)

        # 4. Process Main Service Volumes
        for vol_str in context.get('processed_volumes', []):
            source = vol_str.split(':')[0]
            # Only track absolute paths (bind mounts), not Docker named volumes OR files
            if source.startswith('/') and not is_file_mount(source):
                override = uid_gid_map.get(source, (None, None))
                add_dir(source, is_db=False, override_uid=override[0], override_gid=override[1])

        # 5. Process Dependency Volumes (Sidecars)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            image_repo = dep_cfg.get('image_repo', '').lower()

            # THE FIX 2: Added 'redis' to the database check list
            is_db = any(db in image_repo for db in ['mariadb', 'mysql', 'postgres', 'redis'])

            # Build uid/gid override map for this dependency's volumes
            dep_uid_gid_map = {}
            for v_id, v_def in dep_cfg.get('volumes', {}).items():
                if not isinstance(v_def, dict):
                    continue
                if v_def.get('uid') or v_def.get('gid'):
                    # Dependency volumes are stored under the main service path
                    source = resolve_source(v_id, v_def, main_svc.lower())
                    if source:
                        dep_uid_gid_map[source] = (
                            str(v_def['uid']) if v_def.get('uid') else None,
                            str(v_def['gid']) if v_def.get('gid') else None,
                        )

            for vol_str in dep_cfg.get('processed_volumes', []):
                source = vol_str.split(':')[0]
                if source.startswith('/') and not is_file_mount(source):
                    override = dep_uid_gid_map.get(source, (None, None))
                    add_dir(source, is_db=is_db, override_uid=override[0], override_gid=override[1])

        # 6. Deduplicate (in case paths overlap) while preserving the first assignment
        unique_dirs = {}
        for d in ansible_dirs:
            if d['path'] not in unique_dirs:
                unique_dirs[d['path']] = d

        # Export to context
        context['ansible_directories'] = list(unique_dirs.values())
        return context
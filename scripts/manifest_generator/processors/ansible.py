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

        def add_dir(path: str, is_db: bool):
            ansible_dirs.append({
                'path': path,
                'owner': '999' if is_db else default_puid,
                'group': '999' if is_db else default_pgid
            })

        # 2. Add the main service base directory
        service_target_dir = f"{base_path}/{main_svc.lower()}"
        add_dir(service_target_dir, is_db=False)

        # 3. Process Main Service Volumes
        for vol_str in context.get('processed_volumes', []):
            source = vol_str.split(':')[0]
            # Only track absolute paths (bind mounts), not Docker named volumes
            if source.startswith('/'):
                add_dir(source, is_db=False)

        # 4. Process Dependency Volumes (Sidecars)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            image_repo = dep_cfg.get('image_repo', '').lower()
            # Flag if this specific sidecar is a database
            is_db = any(db in image_repo for db in ['mariadb', 'mysql', 'postgres'])

            for vol_str in dep_cfg.get('processed_volumes', []):
                source = vol_str.split(':')[0]
                if source.startswith('/'):
                    add_dir(source, is_db=is_db)

        # 5. Deduplicate (in case paths overlap) while preserving the first assignment
        unique_dirs = {}
        for d in ansible_dirs:
            if d['path'] not in unique_dirs:
                unique_dirs[d['path']] = d

        # Export to context
        context['ansible_directories'] = list(unique_dirs.values())
        return context
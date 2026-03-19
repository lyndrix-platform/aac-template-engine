# scripts/butcher.py
import os
import yaml
import copy
import subprocess
import sys
from pathlib import Path

# Mapping of known legacy image_repos to their new catalog blueprints
CATALOG_MAP = {
    "mariadb": "catalog/mariadb.yml",
    "redis": "catalog/redis.yml",
    "postgres": "catalog/postgres.yml"
}

# Secrets that should ALWAYS be at the root for stack.env inheritance
GLOBAL_SECRETS = [
    # PostgreSQL
    "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB",
    
    # MariaDB / MySQL
    "MARIADB_PASSWORD", "MARIADB_ROOT_PASSWORD", "MARIADB_USER", "MARIADB_DATABASE",
    "MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD", "MYSQL_USER", "MYSQL_DATABASE",
    
    # Redis
    "REDIS_PASSWORD",
    
    # MongoDB
    "MONGO_INITDB_ROOT_USERNAME", "MONGO_INITDB_ROOT_PASSWORD",
    
    # InfluxDB
    "DOCKER_INFLUXDB_INIT_PASSWORD", "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN",
    
    # Meilisearch / Search
    "MEILI_MASTER_KEY", "TYPESENSE_API_KEY",
    
    # MQTT
    "MQTT_PASSWORD", "MQTT_USER",
    
    # General / Common
    "DB_PASSWORD", "DATABASE_URL", "JWT_SECRET"
]

# Legacy Jinja variables that the new engine handles natively (we delete these)
REDUNDANT_VARS = [
    "SERVICE_NAME", "SERVICE_HOSTNAME", "SERVICE_DOMAIN_NAME", 
    "SERVICE_IMAGE_NAME", "SERVICE_IMAGE_TAG"
]

def normalize_volumes(vol_data):
    """Converts legacy ["source:target"] lists into agnostic {"id": {"target": "..."}} dicts."""
    if isinstance(vol_data, dict):
        return vol_data
    if not isinstance(vol_data, list):
        return {}

    normalized = {}
    for entry in vol_data:
        if not isinstance(entry, str):
            continue
        
        parts = entry.split(':')
        v_id = parts[0]
        target = parts[1] if len(parts) > 1 else f"/{v_id}"
        
        # Determine if it's a path (bind) or a name (volume)
        normalized[v_id] = {"target": target}
        if v_id.startswith('/') or v_id.startswith('.'):
            normalized[v_id]["type"] = "bind"
        else:
            normalized[v_id]["description"] = f"Persistent storage for {v_id}"
            
    return normalized

def clean_environment(env_dict, target_secrets=None):
    """
    1. Removes redundant Jinja variables.
    2. Siphons 'Global Secrets' to the root secrets dictionary.
    3. Strips legacy Jinja interpolation strings.
    """
    if not isinstance(env_dict, dict):
        return {}
    
    cleaned = {}
    for k, v in env_dict.items():
        # Rule 1: Delete redundant engine variables
        if k in REDUNDANT_VARS:
            continue
        
        # Rule 2: Siphon secrets to the root level
        if target_secrets is not None:
            if k in GLOBAL_SECRETS or "PASSWORD" in k or "SECRET" in k or "TOKEN" in k:
                target_secrets[k] = str(v)
                continue

        # Rule 3: Strip legacy Jinja strings
        if isinstance(v, str) and '{{' in v:
            # If the variable was just a pointer to another env var, we drop it
            # because the new engine handles inheritance natively.
            if 'stack_env' in v or 'dot_env' in v or 'service.name' in v:
                continue
            
        cleaned[k] = str(v)
    return cleaned

def clean_volumes(volume_dict):
    """Purges hardcoded Jinja paths from volume sources."""
    if not isinstance(volume_dict, dict):
        return volume_dict
    
    for v_id, v_def in volume_dict.items():
        if isinstance(v_def, dict) and 'source' in v_def:
            if isinstance(v_def['source'], str) and '{{' in v_def['source'] and 'host_base_path' in v_def['source']:
                print(f"  [>] Cleaning Jinja path from volume source: {v_id}")
                del v_def['source']
    return volume_dict

def butcher_manifest(legacy_path):
    print(f"\n🔪 Butchering: {legacy_path}")
    
    with open(legacy_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data:
        return False

    new_data = copy.deepcopy(data)
    dc = new_data.get('deployments', {}).get('docker_compose', {})

    if 'secrets' not in new_data:
        new_data['secrets'] = {}

    # 1. Hoist Environments & Secrets
    old_dot_env = dc.pop('dot_env', {})
    old_stack_env = dc.pop('stack_env', {})
    new_data['environment'] = clean_environment(old_dot_env)
    new_data['secrets'].update(clean_environment(old_stack_env))

    # 2. Normalize and Clean Volumes
    if 'volumes' in new_data:
        new_data['volumes'] = normalize_volumes(new_data['volumes'])
        new_data['volumes'] = clean_volumes(new_data['volumes'])

    # 3. Refactor Dependencies
    deps = new_data.get('dependencies', {})
    for dep_name, dep_cfg in list(deps.items()):
        # Pre-normalize dependency volumes to prevent Engine crashes
        if 'volumes' in dep_cfg:
            dep_cfg['volumes'] = normalize_volumes(dep_cfg['volumes'])

        repo = dep_cfg.get('image_repo')
        if repo in CATALOG_MAP:
            print(f"  [>] Refactoring '{dep_name}' to {CATALOG_MAP[repo]}")
            
            old_dep_env = dep_cfg.pop('environment', {})
            clean_dep_env = clean_environment(old_dep_env, target_secrets=new_data['secrets'])

            overrides = {
                "name": dep_cfg.pop('name', f"{data['service']['name']}-{dep_name}"),
                "image_tag": str(dep_cfg.pop('image_tag', 'latest'))
            }
            if clean_dep_env:
                overrides['environment'] = clean_dep_env
            if 'volumes' in dep_cfg:
                overrides['volumes'] = dep_cfg.pop('volumes')

            new_data['dependencies'][dep_name] = {
                "import": CATALOG_MAP[repo],
                "overrides": overrides
            }
            new_data['dependencies'][dep_name]['overrides']['_renovate_hint'] = f"datasource=docker depName={repo}"

            if repo == "postgres" and 'db' in new_data.get('volumes', {}):
                print("  [>] Aligning Postgres volume key: db -> db_data")
                new_data['volumes']['db_data'] = new_data['volumes'].pop('db')

    # 4. Final Cleanup
    for key in ['environment', 'secrets', 'dependencies']:
        if not new_data.get(key): new_data.pop(key, None)

    with open(legacy_path, 'w', encoding='utf-8') as f:
        yaml.dump(new_data, f, sort_keys=False, default_flow_style=False)
    
    with open(legacy_path, 'r', encoding='utf-8') as f:
        raw_text = f.read().replace("_renovate_hint:", "# renovate:")
    with open(legacy_path, 'w', encoding='utf-8') as f:
        f.write(raw_text)

    return True

def validate_with_engine(engine_root, target_yml):
    """Runs the template engine against the mutated file."""
    print("  [>] Validating with Manifest Engine...")
    scripts_dir = os.path.join(os.path.abspath(engine_root), "scripts")
    cmd = [
        sys.executable, "-m", "manifest_generator.main",
        "--ssot-json", os.path.abspath(target_yml),
        "--template-path", os.path.abspath(engine_root),
        "--stage", "dev", "--deployment-type", "docker_compose"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=scripts_dir)
    if result.returncode == 0 and "Success: Manifest generation complete." in result.stdout:
        print("  [SUCCESS] Engine successfully compiled the manifest.")
        return True
    else:
        print(f"  [FATAL] Engine validation failed!\n--- STDERR ---\n{result.stderr}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python butcher.py <path_to_engine_root> <path_to_target>")
        sys.exit(1)

    engine_root, target_path = sys.argv[1], sys.argv[2]
    targets = [str(p) for p in Path(target_path).rglob('service.yml')] if os.path.isdir(target_path) else [target_path]

    failed = 0
    for yml_file in targets:
        if butcher_manifest(yml_file):
            if not validate_with_engine(engine_root, yml_file):
                failed += 1
    
    print(f"\n========================================\nMigration Complete. Failed: {failed} / {len(targets)}")
    if failed > 0: sys.exit(1)

if __name__ == "__main__":
    main()
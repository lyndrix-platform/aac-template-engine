# scripts/butcher.py
import os
import yaml
import copy
import subprocess
import sys
import re
from pathlib import Path

CATALOG_MAP = {
    "mariadb": "catalog/mariadb.yml",
    "mysql": "catalog/mysql.yml",
    "postgres": "catalog/postgres.yml",
    "postgresql": "catalog/postgres.yml",
    "redis": "catalog/redis.yml"
}

GLOBAL_SECRETS = [
    "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB",
    "MARIADB_PASSWORD", "MARIADB_ROOT_PASSWORD", "MARIADB_USER", "MARIADB_DATABASE",
    "MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD", "MYSQL_USER", "MYSQL_DATABASE",
    "REDIS_PASSWORD", "JWT_SECRET", "ADMIN_PASSWORD"
]

REDUNDANT_VARS = ["SERVICE_NAME", "SERVICE_HOSTNAME", "SERVICE_DOMAIN_NAME"]

def migrate_jinja_expressions(text):
    """Fixes internal Jinja pointers in the YAML text to match the new structure."""
    # deployments.docker_compose.stack_env.KEY -> secrets.KEY
    text = text.replace('deployments.docker_compose.stack_env', 'secrets')
    # deployments.docker_compose.dot_env.KEY -> environment.KEY
    text = text.replace('deployments.docker_compose.dot_env', 'environment')
    # deployments.docker_compose.network_definitions -> network_definitions
    text = text.replace('deployments.docker_compose.network_definitions', 'network_definitions')
    return text

def clean_environment(env_dict, target_secrets=None):
    if not isinstance(env_dict, dict): return {}
    cleaned = {}
    for k, v in env_dict.items():
        if k in REDUNDANT_VARS: continue
        if target_secrets is not None and (k in GLOBAL_SECRETS or "PASSWORD" in k or "SECRET" in k):
            target_secrets[k] = str(v)
            continue
        if isinstance(v, str) and '{{' in v and ('stack_env' in v or 'dot_env' in v):
            continue
        cleaned[k] = str(v)
    return cleaned

def butcher_manifest(legacy_path):
    print(f"\n🔪 Butchering: {legacy_path}")
    with open(legacy_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not data: return False

    new_data = copy.deepcopy(data)
    dc = new_data.get('deployments', {}).get('docker_compose', {})
    if 'secrets' not in new_data: new_data['secrets'] = {}

    # 1. Hoist Environment, Secrets, and Networks
    old_dot_env = dc.pop('dot_env', {})
    old_stack_env = dc.pop('stack_env', {})
    new_data['environment'] = clean_environment(old_dot_env)
    new_data['secrets'].update(clean_environment(old_stack_env))
    
    # 2. Hoist Network Definitions to root
    if 'network_definitions' in dc:
        new_data['network_definitions'] = dc.pop('network_definitions')

    # 3. Refactor Dependencies
    deps = new_data.get('dependencies', {})
    for dep_name, dep_cfg in list(deps.items()):
        repo = dep_cfg.get('image_repo')
        if repo in CATALOG_MAP:
            old_dep_env = dep_cfg.pop('environment', {})
            clean_dep_env = clean_environment(old_dep_env, target_secrets=new_data['secrets'])
            overrides = {
                "name": dep_cfg.pop('name', f"{data['service']['name']}-{dep_name}"),
                "image_tag": str(dep_cfg.pop('image_tag', 'latest'))
            }
            if clean_dep_env: overrides['environment'] = clean_dep_env
            new_data['dependencies'][dep_name] = {"import": CATALOG_MAP[repo], "overrides": overrides}
            new_data['dependencies'][dep_name]['overrides']['_renovate_hint'] = f"datasource=docker depName={repo}"

    # 4. Final Cleanup
    for key in ['environment', 'secrets', 'dependencies']:
        if not new_data.get(key): new_data.pop(key, None)

    # 5. Write and Migrate Jinja Text
    with open(legacy_path, 'w', encoding='utf-8') as f:
        yaml.dump(new_data, f, sort_keys=False, default_flow_style=False)
    
    with open(legacy_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    raw_text = migrate_jinja_expressions(raw_text) # THE FIX
    raw_text = raw_text.replace("_renovate_hint:", "# renovate:")
    
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
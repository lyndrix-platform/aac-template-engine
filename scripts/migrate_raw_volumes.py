import os
import sys
from ruamel.yaml import YAML

def generate_volume_id(target_path):
    """Converts a path like /var/run/docker.sock to a clean YAML key: var_run_docker_sock"""
    clean_name = target_path.strip('/').replace('/', '_').replace('.', '_')
    return clean_name if clean_name else "root_mount"

def migrate_repo(yaml_path, yaml_parser):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml_parser.load(f)
        except Exception as e:
            print(f"  [!] Error parsing YAML: {e}")
            return False

    if not data or 'deployments' not in data or 'docker_compose' not in data['deployments']:
        return False

    dc = data['deployments']['docker_compose']
    
    # Check if raw_volumes exists
    if 'raw_volumes' not in dc:
        return False

    raw_volumes = dc['raw_volumes']
    
    # 1. Handle Empty Arrays
    if not raw_volumes:
        print(f"  [-] Deleting empty raw_volumes array.")
        del dc['raw_volumes']
        write_yaml(yaml_path, yaml_parser, data)
        return True

    # 2. Handle Populated Arrays
    print(f"  [!] Migrating {len(raw_volumes)} raw volume(s)...")
    
    if 'volumes' not in dc:
        dc['volumes'] = []
        
    if 'volumes' not in data:
        data['volumes'] = {}
    elif data['volumes'] is None:
        data['volumes'] = {}

    for raw_vol in raw_volumes:
        # Parse: source:target:flags
        parts = raw_vol.split(':')
        source = parts[0]
        target = parts[1] if len(parts) > 1 else parts[0]
        flags = f":{parts[2]}" if len(parts) > 2 else ""
        
        # Generate an ID
        vol_id = generate_volume_id(target)
        
        # Create standard mount string (id:target:flags)
        standard_mount = f"{vol_id}:{target}{flags}"
        
        # Append to deployment volumes if not already there
        if standard_mount not in dc['volumes']:
            dc['volumes'].append(standard_mount)
            
        # Add the explicit source definition to the root volumes block
        if vol_id not in data['volumes']:
            data['volumes'][vol_id] = {
                'description': f"Auto-migrated raw volume for {target}",
                'type': 'bind',
                'source': source
            }
            print(f"      -> Mapped: {standard_mount} (Source: {source})")

    # Delete the legacy key
    del dc['raw_volumes']
    write_yaml(yaml_path, yaml_parser, data)
    return True

def write_yaml(yaml_path, yaml_parser, data):
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml_parser.dump(data, f)

def main():
    # Set this to your exact applications directory
    base_dir = r"C:\Users\Shared\Workdirektory\Code-Infra\GitLab\aac-application-defenitions\applications"
    
    yaml_parser = YAML()
    yaml_parser.preserve_quotes = True
    yaml_parser.indent(mapping=2, sequence=4, offset=2)

    print("======================================================")
    print("🧹 STARTING SURGICAL YAML MIGRATION (RAW_VOLUMES)")
    print("======================================================")

    if not os.path.exists(base_dir):
        print(f"FATAL: Directory not found: {base_dir}")
        sys.exit(1)

    migrated_count = 0
    for entry in os.listdir(base_dir):
        repo_path = os.path.join(base_dir, entry)
        if os.path.isdir(repo_path):
            yaml_path = os.path.join(repo_path, 'service.yml')
            if os.path.exists(yaml_path):
                if migrate_repo(yaml_path, yaml_parser):
                    print(f"✅ Successfully updated: {entry}")
                    migrated_count += 1

    print("======================================================")
    print(f"🏁 MIGRATION COMPLETE. {migrated_count} repositories updated.")
    print("======================================================")

if __name__ == "__main__":
    main()
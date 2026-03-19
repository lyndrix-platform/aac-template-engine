import os
import sys
from ruamel.yaml import YAML

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
    
    # Check if raw_options exists
    if 'raw_options' not in dc:
        return False

    raw_options = dc['raw_options']
    
    # 1. Handle Empty Arrays/Dicts
    if not raw_options:
        print(f"  [-] Deleting empty raw_options block.")
        del dc['raw_options']
        write_yaml(yaml_path, yaml_parser, data)
        return True

    # 2. Lift Populated Options
    print(f"  [!] Migrating raw_options...")
    
    if isinstance(raw_options, dict):
        for key, value in raw_options.items():
            dc[key] = value
            print(f"      -> Lifted '{key}' directly into docker_compose")

    # Delete the legacy key
    del dc['raw_options']
    write_yaml(yaml_path, yaml_parser, data)
    return True

def write_yaml(yaml_path, yaml_parser, data):
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml_parser.dump(data, f)

def main():
    base_dir = r"C:\Users\Shared\Workdirektory\Code-Infra\GitLab\aac-application-defenitions\applications"
    
    yaml_parser = YAML()
    yaml_parser.preserve_quotes = True
    yaml_parser.indent(mapping=2, sequence=4, offset=2)

    print("======================================================")
    print("🧹 STARTING SURGICAL YAML MIGRATION (RAW_OPTIONS)")
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
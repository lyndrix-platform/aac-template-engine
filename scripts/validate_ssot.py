import os
import sys
import yaml

def validate_ssot(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except Exception as e:
            return [f"FATAL YAML Parse Error: {e}"]

    if not data:
        return ["File is completely empty."]

    errors = []

    # 1. Mandatory Service Keys
    svc = data.get('service', {})
    if not svc:
        errors.append("Missing root block: 'service'")
    else:
        for req in ['name', 'image_repo', 'image_tag', 'stage']:
            if req not in svc:
                errors.append(f"Missing mandatory key: 'service.{req}'")

    # 2. Deployment Block Exists
    dc = data.get('deployments', {}).get('docker_compose', {})
    if not dc:
        errors.append("Missing block: 'deployments.docker_compose'")

    # 3. Dangling Volumes (Mounted but not defined)
    defined_volumes = data.get('volumes', {}) or {}
    for vol_str in dc.get('volumes', []):
        if not isinstance(vol_str, str):
            continue
            
        v_id = vol_str.split(':')[0]
        
        # Ignore direct host mounts (start with / or .) and Jinja variables (start with {{)
        if not v_id.startswith('/') and not v_id.startswith('.') and not v_id.startswith('{{'):
            if v_id not in defined_volumes:
                errors.append(f"Dangling Volume: '{v_id}' is mounted in docker_compose, but missing from root 'volumes:' block.")

    # 4. Common Typos and Misplaced Keys
    if 'environments' in dc:
        errors.append("Typo: Found 'environments' in docker_compose. It must be 'environment'.")
    if 'security_opts' in dc:
        errors.append("Typo: Found 'security_opts'. It must be 'security_opt'.")
    if 'raw_volumes' in dc:
        errors.append("Legacy Code: 'raw_volumes' still exists.")
    if 'ports' in dc:
        errors.append("Misplaced Key: 'ports' should be at the root level, not inside 'deployments.docker_compose'.")

    # 5. Traefik Domain Validation
    cfg = data.get('config', {})
    traefik_enabled = cfg.get('integrations', {}).get('traefik', {}).get('enabled', False)
    if traefik_enabled:
        if not cfg.get('domain_name') and not cfg.get('public_domain_name'):
            errors.append("Traefik enabled, but no 'domain_name' found in 'config:' block.")

    return errors

def main():
    base_dir = r"C:\Users\Shared\Workdirektory\Code-Infra\GitLab\aac-application-defenitions\applications"
    
    print("======================================================")
    print("🔎 RUNNING SSOT LINTER (STRICT MODE)")
    print("======================================================")

    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        sys.exit(1)

    total_repos = 0
    failed_repos = 0

    for entry in os.listdir(base_dir):
        repo_path = os.path.join(base_dir, entry)
        if os.path.isdir(repo_path):
            yaml_path = os.path.join(repo_path, 'service.yml')
            if os.path.exists(yaml_path):
                total_repos += 1
                errors = validate_ssot(yaml_path)
                
                if errors:
                    failed_repos += 1
                    print(f"\n❌ {entry}")
                    for err in errors:
                        print(f"   - {err}")

    print("\n======================================================")
    if failed_repos == 0:
        print(f"✅ ALL {total_repos} REPOSITORIES PASSED VALIDATION.")
    else:
        print(f"⚠️  {failed_repos} out of {total_repos} repositories have errors.")
    print("======================================================")

if __name__ == "__main__":
    main()
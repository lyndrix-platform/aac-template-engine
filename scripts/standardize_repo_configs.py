import os
import yaml

# CONFIG: The root folder containing all your service repository clones
SERVICES_ROOT = "C:/Users/Shared/Workdirektory/Code-Infra/GitLab/aac-application-defenitions/applications" 

# 1. The Full Deployment Strategy (Including Infra-Testing Branches)
STRATEGY = {
    'main': {'enabled': True, 'target_stage': 'prod'},
    'dev': {'enabled': True, 'target_stage': 'dev'},
    'test': {'enabled': False, 'target_stage': 'test'},
    'ansible-dev': {'enabled': True, 'target_stage': 'dev'},
    'iac-dev': {'enabled': True, 'target_stage': 'dev'},
    'template-dev': {'enabled': True, 'target_stage': 'dev'}
}

# 2. The Strict CI/CD Switchboard Template
# We use a raw string to ensure perfect formatting and no loss of GitLab syntax.
STANDARD_CI_CONTENT = """variables:
  # DEFAULTS: Use Stable Infrastructure for everything
  ENGINE_BRANCH: "main"
  ANSIBLE_BRANCH: "main"
  INVENTORY_BRANCH: "main"
  SKIP_DEPLOYMENT: "false"

workflow:
  rules:
    # 1. Infra Testing: Template Engine Dev
    - if: '$CI_COMMIT_BRANCH =~ /^template-dev/'
      variables:
        ENGINE_BRANCH: "dev"
    # 2. Infra Testing: IAC / Inventory Dev
    - if: '$CI_COMMIT_BRANCH =~ /^iac-dev/'
      variables:
        INVENTORY_BRANCH: "dev"
    # 3. Infra Testing: Ansible Controller Dev
    - if: '$CI_COMMIT_BRANCH =~ /^ansible-dev/'
      variables:
        ANSIBLE_BRANCH: "dev"
    # 4. Standard Flow (App Dev/Main)
    - when: always

include:
  - project: 'aac-application-definitions/aac-template-engine'
    ref: $ENGINE_BRANCH
    file: '/templates/cicd/service-pipeline.yml'
"""

def update_service_yaml(file_path):
    """Injects the deployment strategy into the service.yml without destroying other data."""
    try:
        with open(file_path, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader) or {}

        # Overwrite or inject the strategy
        data['deployment_strategy'] = STRATEGY

        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False, indent=2)
        
        print(f"  [OK] service.yml updated.")
    except Exception as e:
        print(f"  [ERROR] Failed to update service.yml: {e}")

def overwrite_ci_file(file_path):
    """Completely replaces the .gitlab-ci.yml with the Titanium Switchboard standard."""
    try:
        with open(file_path, 'w', newline='\n') as f:
            f.write(STANDARD_CI_CONTENT)
        print(f"  [OK] .gitlab-ci.yml overwritten with Switchboard logic.")
    except Exception as e:
        print(f"  [ERROR] Failed to update .gitlab-ci.yml: {e}")

if __name__ == "__main__":
    print(f"Starting mass rollout in: {SERVICES_ROOT}\n")
    
    if not os.path.exists(SERVICES_ROOT):
        print("CRITICAL: The specified directory does not exist. Check your path.")
        exit(1)

    for root, dirs, files in os.walk(SERVICES_ROOT):
        # We only care about directories that actually look like service repositories
        if 'service.yml' in files:
            print(f"Processing repository: {os.path.basename(root)}")
            
            # Process service.yml
            service_path = os.path.join(root, 'service.yml')
            update_service_yaml(service_path)
            
            # Process .gitlab-ci.yml
            ci_path = os.path.join(root, '.gitlab-ci.yml')
            overwrite_ci_file(ci_path)
            
            print("-" * 40)
            
    print("\nMigration complete. Review your git diffs before committing.")
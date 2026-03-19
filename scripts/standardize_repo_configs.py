import os
import yaml

# CONFIG: The root folder containing all your service repository clones
SERVICES_ROOT = "C:/Users/Shared/Workdirektory/Code-Infra/GitLab/aac-application-defenitions/applications" 

STRATEGY = {
    'main': {'enabled': True, 'target_stage': 'prod'},
    'dev': {'enabled': True, 'target_stage': 'dev'},
    'test': {'enabled': False, 'target_stage': 'test'},
    'ansible-dev': {'enabled': True, 'target_stage': 'dev'},
    'iac-dev': {'enabled': True, 'target_stage': 'dev'},
    'template-dev': {'enabled': True, 'target_stage': 'dev'}
}

# FIX: This is the correct, proven GitLab CI Switchboard using include:rules
STANDARD_CI_CONTENT = """variables:
  # DEFAULTS for downstream pipelines
  ANSIBLE_BRANCH: "main"
  INVENTORY_BRANCH: "main"
  SKIP_DEPLOYMENT: "false"

workflow:
  rules:
    # 1. Infra Testing: IAC / Inventory Dev
    - if: '$CI_COMMIT_BRANCH =~ /^iac-dev/'
      variables:
        INVENTORY_BRANCH: "dev"
    # 2. Infra Testing: Ansible Controller Dev
    - if: '$CI_COMMIT_BRANCH =~ /^ansible-dev/'
      variables:
        ANSIBLE_BRANCH: "dev"
    # 3. Standard Flow (App Dev/Main)
    - when: always

include:
  # ROUTE A: Experimental Template Engine
  - project: 'aac-application-definitions/aac-template-engine'
    ref: dev
    file: '/templates/cicd/service-pipeline.yml'
    rules:
      - if: '$CI_COMMIT_BRANCH =~ /^template-dev/'

  # ROUTE B: Stable Template Engine (Default)
  - project: 'aac-application-definitions/aac-template-engine'
    ref: main
    file: '/templates/cicd/service-pipeline.yml'
    rules:
      - if: '$CI_COMMIT_BRANCH !~ /^template-dev/'
"""

def update_service_yaml(file_path):
    try:
        with open(file_path, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader) or {}

        data['deployment_strategy'] = STRATEGY

        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False, indent=2)
        print(f"  [OK] service.yml updated.")
    except Exception as e:
        print(f"  [ERROR] Failed to update service.yml: {e}")

def overwrite_ci_file(file_path):
    try:
        with open(file_path, 'w', newline='\n') as f:
            f.write(STANDARD_CI_CONTENT)
        print(f"  [OK] .gitlab-ci.yml overwritten.")
    except Exception as e:
        print(f"  [ERROR] Failed to update .gitlab-ci.yml: {e}")

if __name__ == "__main__":
    print(f"Starting CI override rollout in: {SERVICES_ROOT}\n")
    
    if not os.path.exists(SERVICES_ROOT):
        print("CRITICAL: The specified directory does not exist. Check your path.")
        exit(1)

    for root, dirs, files in os.walk(SERVICES_ROOT):
        if 'service.yml' in files:
            print(f"Processing repository: {os.path.basename(root)}")
            
            # Update the CI file with the correct include:rules syntax
            ci_path = os.path.join(root, '.gitlab-ci.yml')
            overwrite_ci_file(ci_path)
            
            # Update the service.yml just to be safe
            service_path = os.path.join(root, 'service.yml')
            update_service_yaml(service_path)
            
            print("-" * 40)
            
    print("\nMigration complete. All CI files now use include:rules.")
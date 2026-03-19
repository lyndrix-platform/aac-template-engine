import os
import yaml
import subprocess

# CONFIG: The root folder containing all your service repository clones
SERVICES_ROOT = "C:/Users/Shared/Workdirektory/Code-Infra/GitLab/aac-application-defenitions/applications"

def scrub_healthcheck(file_path):
    changed = False
    try:
        with open(file_path, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader) or {}

        # Dig into the dictionary safely and delete the healthcheck if it exists
        if 'deployments' in data and 'docker_compose' in data['deployments']:
            if 'healthcheck' in data['deployments']['docker_compose']:
                del data['deployments']['docker_compose']['healthcheck']
                changed = True

        if changed:
            with open(file_path, 'w') as f:
                yaml.dump(data, f, sort_keys=False, default_flow_style=False, indent=2)
            print(f"  [CLEANED] Removed bad healthcheck from {file_path}")
            
        return changed
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

if __name__ == "__main__":
    print("Starting Healthcheck Scrub...")
    for root, dirs, files in os.walk(SERVICES_ROOT):
        if 'service.yml' in files:
            repo_name = os.path.basename(root)
            service_path = os.path.join(root, 'service.yml')
            
            if scrub_healthcheck(service_path):
                # Auto-commit and Push the fix using GitLab Push Options to create an MR
                os.chdir(root)
                subprocess.run("git checkout dev", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run("git pull origin dev", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                branch_name = "fix/remove-bad-healthcheck"
                subprocess.run(f"git branch -D {branch_name}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(f"git checkout -b {branch_name}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                subprocess.run("git add service.yml", shell=True)
                subprocess.run('git commit -m "fix: remove hardcoded node healthcheck"', shell=True, stdout=subprocess.DEVNULL)
                
                # Push and automatically create an MR targeting 'dev'
                subprocess.run(f'git push -o merge_request.create -o merge_request.target=dev -o merge_request.title="fix: remove hardcoded node healthcheck" origin {branch_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                print(f"  [MR CREATED] for {repo_name}")
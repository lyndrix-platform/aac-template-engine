#!/usr/bin/env python3
"""
Service Promotion and Inventory Management Script

This script automates the promotion of a service to a target environment (dev/test)
by updating a central Ansible inventory file in the 'iac-controller' repository.

Workflow:
1. Clones the iac-controller repository.
2. Loads the main inventory file (e.g., 'feser_homelab.yml').
3. Determines the target site for deployment:
   - It first looks for where the service is deployed in the 'prod' stage.
   - If found, it uses that same site (e.g., 'onprem' or 'hetzner') for the target stage.
   - If not found in 'prod', it defaults to a hardcoded site ('onprem').
4. Finds a suitable host within the target site and stage (e.g., a 'dev' host in 'onprem').
   - It picks the first available host in the specified stage that is part of the 'docker_hosts' group.
5. Constructs the service definition and injects/updates it in the host's service list.
6. Commits and pushes the updated inventory file back to the iac-controller repository.
"""
import os
import sys
import argparse
import subprocess
import yaml
from pathlib import Path


def run_command(command, cwd=None, check=True):
    """Executes a shell command and handles errors."""
    print(f"Executing: {' '.join(command)}", flush=True)
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        print(process.stdout)
        if process.stderr:
            print(f"STDERR: {process.stderr}", file=sys.stderr)
        return process.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}", file=sys.stderr)
        print(f"STDOUT: {e.stdout}", file=sys.stderr)
        print(f"STDERR: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def find_prod_site(inventory_data, service_name):
    """Finds which site a service is deployed to in production."""
    for site_name, site_data in inventory_data.get("sites", {}).items():
        prod_stage = site_data.get("stages", {}).get("prod", {})
        for host_data in prod_stage.get("hosts", {}).values():
            for service in host_data.get("services", []):
                if service.get("name") == service_name:
                    print(f"Found '{service_name}' in production on site '{site_name}'.")
                    return site_name
    return None


def find_target_host(inventory_data, site_name, target_stage):
    """Finds the first available docker host in a given site and stage."""
    site = inventory_data.get("sites", {}).get(site_name)
    if not site:
        print(f"ERROR: Site '{site_name}' not found in inventory.", file=sys.stderr)
        sys.exit(1)

    stage = site.get("stages", {}).get(target_stage)
    if not stage:
        print(f"ERROR: Stage '{target_stage}' not found in site '{site_name}'.", file=sys.stderr)
        sys.exit(1)

    for host_name, host_data in stage.get("hosts", {}).items():
        if "docker_hosts" in host_data.get("ansible_groups", []):
            print(f"Found target host '{host_name}' in site '{site_name}' and stage '{target_stage}'.")
            return host_name

    print(f"ERROR: No suitable 'docker_hosts' found in site '{site_name}', stage '{target_stage}'.", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Promote a service by updating the central IaC inventory.")
    parser.add_argument("--service-name", required=True, help="Name of the service (e.g., aac-firefly-iii).")
    parser.add_argument("--service-git-repo", required=True, help="Full Git URL of the service repository.")
    parser.add_argument("--target-stage", required=True, choices=['dev', 'test'], help="The stage to promote to (dev or test).")
    parser.add_argument("--iac-controller-repo-url", required=True, help="Git URL for the iac-controller repository.")
    parser.add_argument("--iac-controller-token", required=True, help="Access token for pushing to the iac-controller repo.")
    parser.add_argument("--inventory-file", default="environments/feser_homelab.yml", help="Relative path to the inventory file in the controller repo.")
    args = parser.parse_args()

    # --- 1. Setup Git and Clone Controller Repo ---
    controller_clone_dir = Path("/tmp/iac-controller")
    authed_controller_url = args.iac_controller_repo_url.replace("https://", f"https://gitlab-ci-token:{args.iac_controller_token}@")

    run_command(["git", "config", "--global", "user.email", f"ci-bot@{os.getenv('CI_SERVER_HOST', 'gitlab.com')}"])
    run_command(["git", "config", "--global", "user.name", "GitLab Service Promoter"])
    run_command(["rm", "-rf", str(controller_clone_dir)])
    run_command(["git", "clone", "--depth=1", authed_controller_url, str(controller_clone_dir)])

    # --- 2. Load and Analyze Inventory ---
    inventory_path = controller_clone_dir / args.inventory_file
    if not inventory_path.exists():
        print(f"ERROR: Inventory file not found at {inventory_path}", file=sys.stderr)
        sys.exit(1)

    with open(inventory_path, 'r') as f:
        # Use a loader that preserves comments and structure if possible in the future
        inventory = yaml.safe_load(f)

    prod_site = find_prod_site(inventory, args.service_name)
    target_site = prod_site if prod_site else "onprem"
    print(f"Determined target site: '{target_site}'")

    target_host_name = find_target_host(inventory, target_site, args.target_stage)

    # --- 3. Create/Update Service Definition ---
    service_definition = {
        "name": args.service_name,
        "state": "present",
        "git_repo": args.service_git_repo,
        "git_version": args.target_stage,
        "deploy_type": "docker_compose"
    }

    # Navigate to the target host's service list
    target_host = inventory["sites"][target_site]["stages"][args.target_stage]["hosts"][target_host_name]
    if "services" not in target_host:
        target_host["services"] = []

    # Check if service already exists and update it, otherwise append
    service_found = False
    for i, existing_service in enumerate(target_host["services"]):
        if existing_service.get("name") == args.service_name:
            print(f"Updating existing service '{args.service_name}' on host '{target_host_name}'.")
            target_host["services"][i] = service_definition
            service_found = True
            break

    if not service_found:
        print(f"Adding new service '{args.service_name}' to host '{target_host_name}'.")
        target_host["services"].append(service_definition)

    # --- 4. Write Changes and Push to Git ---
    with open(inventory_path, 'w') as f:
        yaml.dump(inventory, f, default_flow_style=False, sort_keys=False, indent=2)

    # Check for changes
    git_status = run_command(["git", "status", "--porcelain"], cwd=controller_clone_dir)
    if not git_status:
        print("✅ No changes to the inventory. Nothing to commit.")
        sys.exit(0)

    print("📝 Inventory has changed. Committing and pushing...")
    run_command(["git", "add", str(inventory_path)], cwd=controller_clone_dir)
    commit_message = f"ci: Promote service '{args.service_name}' to '{args.target_stage}' on host '{target_host_name}'"
    run_command(["git", "commit", "-m", commit_message], cwd=controller_clone_dir)
    run_command(["git", "push"], cwd=controller_clone_dir)

    print(f"✅ Successfully promoted service '{args.service_name}' to stage '{args.target_stage}'.")


if __name__ == "__main__":
    main()
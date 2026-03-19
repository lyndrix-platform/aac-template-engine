import argparse
import sys
import os
import traceback
import yaml 
import json

from .context import ContextBuilder
from .engine import ManifestEngine

# 1. Import ALL Processors
from .processors.imports import ImportProcessor
from .processors.metadata import MetadataProcessor
from .processors.environment import EnvironmentProcessor
from .processors.networks import NetworkProcessor
from .processors.ingress import IngressProcessor
from .processors.specs import SpecProcessor
from .processors.volumes import VolumeProcessor
from .processors.ansible import AnsibleProcessor

def get_strategy_for_branch(strategy_block, current_branch):
    """Determines the correct deployment strategy using exact or prefix matching."""
    if not strategy_block:
        # Failsafe default if block is completely missing
        return {'enabled': True, 'target_stage': 'dev'}

    # 1. Exact match (e.g., 'main', 'dev', 'test')
    if current_branch in strategy_block:
        return strategy_block[current_branch]

    # 2. Prefix match (e.g., 'ansible-dev-feature' matches 'ansible-dev')
    for key, strategy in strategy_block.items():
        if current_branch.startswith(key):
            return strategy

    # 3. Default fallback if branch is entirely unknown
    return {'enabled': False, 'target_stage': 'none'}

def main():
    parser = argparse.ArgumentParser(description="Modular Manifest Generator")
    parser.add_argument('--ssot-json', required=True, help="JSON string OR path to a JSON file")
    parser.add_argument('--template-path', required=True, help="Path to template engine repo")
    parser.add_argument('--stage', required=True, help="Deployment stage (dev, prod)")
    parser.add_argument('--deployment-type', default='docker_compose')
    
    parser.add_argument('--process-documentation', action='store_true', help="Generate documentation")
    parser.add_argument('--process-files', action='store_true', help="Process custom files")
    
    args = parser.parse_args()

    # --- Robust Input Handling ---
    ssot_input = args.ssot_json
    if os.path.isfile(ssot_input):
        print(f"  [I] Reading SSoT from file: {ssot_input}")
        with open(ssot_input, 'r', encoding='utf-8') as f:
            if ssot_input.endswith(('.yml', '.yaml')):
                parsed_yaml = yaml.safe_load(f)
                ssot_input = json.dumps(parsed_yaml)
            else:
                ssot_input = f.read()

    try:
        # --- STRATEGY & KILL-SWITCH LOGIC ---
        raw_ssot_dict = json.loads(ssot_input)
        strategy_block = raw_ssot_dict.get('deployment_strategy', {})
        current_branch = os.getenv('SERVICE_BRANCH', 'main')
        
        active_strategy = get_strategy_for_branch(strategy_block, current_branch)
        is_enabled = active_strategy.get('enabled', True)
        
        # Override the CLI stage arg with the strategy's target stage
        calculated_stage = active_strategy.get('target_stage', args.stage)

        # 1. Build Data Context using the correct calculated stage
        builder = ContextBuilder(ssot_input, calculated_stage)
        context = builder.build()

        # Inject the enabled flag into the context for Ansible to read later
        context['deployment_enabled'] = is_enabled

        # 2. Run Logic Processors (Strict Order Required)
        processors = [
            ImportProcessor(args.template_path),
            MetadataProcessor(),
            EnvironmentProcessor(),
            NetworkProcessor(),
            IngressProcessor(),
            SpecProcessor(),
            VolumeProcessor(),
            AnsibleProcessor() 
        ]

        for proc in processors:
            context = proc.process(context)

        # 3. Dump the fully rendered context for Ansible to consume
        output_dir = os.path.join(os.getcwd(), "deployments")
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "ansible_context.json"), "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)

        # --- THE ABORT GATE ---
        if not is_enabled:
            print(f"\n  [!] DEPLOYMENT SKIPPED: Branch '{current_branch}' is disabled by deployment_strategy.")
            print("  [I] Context written successfully for Ansible evaluation. Exiting cleanly.")
            sys.exit(0)

        # 4. Render Manifests
        engine = ManifestEngine(args.template_path, os.getcwd())
        
        # 5. Switch for the CI jobs
        if args.process_documentation:
            print("  [I] Processing Documentation...")
            if hasattr(engine, 'render_documentation'):
                engine.render_documentation(context)
            else:
                engine.render_all(context, args.deployment_type)
                
        elif args.process_files:
            print("  [I] Processing Custom Files...")
            if hasattr(engine, 'render_files'):
                engine.render_files(context)
            else:
                engine.render_all(context, args.deployment_type)
                
        else:
            print("  [I] Processing Docker Compose...")
            engine.render_all(context, args.deployment_type)
        
        print("\nSuccess: Manifest generation complete.")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
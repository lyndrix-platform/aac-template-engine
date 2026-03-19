# scripts/manifest_generator/context.py
import json
from copy import deepcopy
from jinja2 import Environment

class ContextBuilder:
    def __init__(self, ssot_json: str, stage: str):
        self.raw_data = json.loads(ssot_json)
        self.stage = stage

    def _deep_merge(self, source, destination):
        """Standard deep merge to ensure overrides don't wipe out existing blocks."""
        for key, value in source.items():
            if isinstance(value, dict):
                node = destination.setdefault(key, {})
                self._deep_merge(value, node)
            else:
                destination[key] = value
        return destination

    def _render_recursive(self, data: dict, passes=5) -> dict:
        """
        Resolves internal references (e.g., {{ secrets.DB_PASS }}).
        Uses string-serialization to allow cross-referencing anywhere in the tree.
        """
        env = Environment(trim_blocks=True, lstrip_blocks=True)
        current_render = json.dumps(data)
        
        for i in range(passes):
            previous_render = current_render
            context = json.loads(previous_render)
            template = env.from_string(previous_render)
            
            # This handles the actual 'Rendering' of the entire YAML structure
            current_render = template.render(context)
            
            if previous_render == current_render:
                break
        return json.loads(current_render)

    def build(self) -> dict:
        # 1. Start with the "Safety Net"
        # This ensures Jinja never sees an 'Undefined' error for standard keys
        context = {
            "service": {"name": "app", "stage": self.stage},
            "config": {},
            "environment": {},
            "secrets": {},
            "dependencies": {},
            "volumes": {},
            "network_definitions": {},
            "deployments": {
                "docker_compose": {
                    "volumes": [],
                    "networks_to_join": []
                }
            },
            "stage": self.stage
        }

        # 2. Merge the actual SSoT data into the safety net
        # We use deepcopy to avoid mutating the original raw_data
        data = deepcopy(self.raw_data)
        self._deep_merge(data, context)

        # 3. Apply Stage Overrides (e.g., prod changes hostname)
        # We look for overrides specific to the current stage (dev/test/prod)
        overrides = context.pop("stage_overrides", {}).get(self.stage, {})
        if overrides:
            self._deep_merge(overrides, context)
        
        # 4. Final Multi-pass rendering
        # This resolves all {{ }} brackets using the fully merged context
        return self._render_recursive(context)
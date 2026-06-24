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

    def _render_node(self, node, root, env):
        """Render a single node against the full `root` context.

        Renders structurally (per string scalar) instead of serializing the
        whole tree to a JSON string, so values that contain JSON-significant
        characters (quotes, braces) in resolved references can't corrupt the
        document.
        """
        if isinstance(node, dict):
            return {self._render_node(k, root, env): self._render_node(v, root, env)
                    for k, v in node.items()}
        if isinstance(node, list):
            return [self._render_node(item, root, env) for item in node]
        if isinstance(node, str) and ('{{' in node or '{%' in node):
            return env.from_string(node).render(root)
        return node

    def _render_recursive(self, data: dict, passes=5) -> dict:
        """
        Resolves internal references (e.g., {{ secrets.DB_PASS }}) anywhere in
        the tree, repeating until stable (handles references to references).
        """
        env = Environment(trim_blocks=True, lstrip_blocks=True)
        current = data
        for i in range(passes):
            rendered = self._render_node(current, current, env)
            if rendered == current:
                break
            current = rendered
        return current

    def build(self) -> dict:
        # 1. Start with the "Safety Net"
        # This ensures Jinja never sees an 'Undefined' error for standard keys
        context = {
            "service": {"name": "app", "stage": self.stage},
            "config": {},
            "environment": {},
            "secrets": {},
            # schema_version 2: reference-only definition values (never written to a
            # file, only resolved via {{ vars.X }} during _render_recursive).
            "vars": {},
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
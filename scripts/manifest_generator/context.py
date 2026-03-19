# scripts/manifest_generator/context.py
import json
from copy import deepcopy
from jinja2 import Environment

class ContextBuilder:
    def __init__(self, ssot_json: str, stage: str):
        self.raw_data = json.loads(ssot_json)
        self.stage = stage

    def _deep_merge(self, source, destination):
        for key, value in source.items():
            if isinstance(value, dict):
                node = destination.setdefault(key, {})
                self._deep_merge(value, node)
            else:
                destination[key] = value
        return destination

    def _render_recursive(self, data: dict, passes=5) -> dict:
        """Resolves internal Jinja references like {{ service.name }} within the YAML data."""
        env = Environment(trim_blocks=True, lstrip_blocks=True)
        current_render = json.dumps(data)
        
        for i in range(passes):
            previous_render = current_render
            context = json.loads(previous_render)
            template = env.from_string(previous_render)
            current_render = template.render(context)
            if previous_render == current_render:
                break
        return json.loads(current_render)

    def build(self) -> dict:
        data = deepcopy(self.raw_data)
        # 1. Force stage in service identity
        data.setdefault('service', {})['stage'] = self.stage
        
        # 2. Apply stage overrides
        overrides = data.pop("stage_overrides", {}).get(self.stage, {})
        if overrides:
            data = self._deep_merge(overrides, data)
        
        # 3. Stabilize variables
        return self._render_recursive(data)
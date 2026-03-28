from .base import BaseProcessor

class PortProcessor(BaseProcessor):
    def _format_ports(self, ports_data):
        """Helper to convert port dicts to strings."""
        processed = []
        if not isinstance(ports_data, list):
            return processed
            
        for p in ports_data:
            if not isinstance(p, dict):
                continue
            internal = p.get('port')
            external = p.get('external_port')
            protocol = p.get('protocol', 'TCP').lower()
            if internal and external:
                processed.append(f"{external}:{internal}/{protocol}")
        return processed

    def process(self, context: dict) -> dict:
        # 1. Process Main Service Ports
        context['processed_ports'] = self._format_ports(context.get('ports', []))

        # 2. Process Dependency Ports (The Fix)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            # Look for a 'ports' key inside each dependency configuration
            dep_ports = dep_cfg.get('ports', [])
            dep_cfg['processed_ports'] = self._format_ports(dep_ports)

        return context
from .base import BaseProcessor

class PortProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        """
        Converts the structured 'ports' list into the 'processed_ports' 
        format that Docker Compose expects.
        """
        ports_data = context.get('ports', [])
        processed_ports = []

        if not isinstance(ports_data, list):
            context['processed_ports'] = []
            return context

        for p in ports_data:
            if not isinstance(p, dict):
                continue
                
            internal = p.get('port')
            external = p.get('external_port')
            # Default to TCP if not specified
            protocol = p.get('protocol', 'TCP').lower()

            # We only generate a mapping if an external port is explicitly defined
            if internal and external:
                # Format: "9001:9001/tcp"
                processed_ports.append(f"{external}:{internal}/{protocol}")

        context['processed_ports'] = processed_ports
        return context
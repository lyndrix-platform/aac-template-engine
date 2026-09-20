from .base import BaseProcessor

class PortProcessor(BaseProcessor):
    def _format_ports(self, ports_data, host_ip=None):
        """Helper to convert port dicts to strings.

        Optional `bind` per port restricts the host-side listener:
          bind: host      -> the host's primary address (ansible_host_ip, injected
                             per host by the rollout) instead of 0.0.0.0
          bind: <address> -> a literal address
        Without `bind` docker publishes on all interfaces as before. Binding to
        the LAN address keeps services off secondary interfaces (e.g. the
        NetBird mesh IP, whose client grabs wt0:53 itself when it is free —
        a 0.0.0.0:53 publish then fails after every reboot).
        """
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
                bind = p.get('bind')
                prefix = ''
                if bind == 'host' and host_ip:
                    prefix = f"{host_ip}:"
                elif bind and bind != 'host':
                    prefix = f"{bind}:"
                processed.append(f"{prefix}{external}:{internal}/{protocol}")
        return processed

    def process(self, context: dict) -> dict:
        host_ip = context.get('ansible_host_ip')
        # 1. Process Main Service Ports
        context['processed_ports'] = self._format_ports(context.get('ports', []), host_ip)

        # 2. Process Dependency Ports (The Fix)
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            # Look for a 'ports' key inside each dependency configuration
            dep_ports = dep_cfg.get('ports', [])
            dep_cfg['processed_ports'] = self._format_ports(dep_ports, host_ip)

        return context
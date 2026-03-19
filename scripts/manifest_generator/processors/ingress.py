# scripts/manifest_generator/processors/ingress.py
from .base import BaseProcessor

class IngressProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc = context.get('service', {})
        cfg = context.get('config', {})
        ints = cfg.get('integrations', {})
        dc = context.get('deployments', {}).get('docker_compose', {})
        
        # 1. State & Identity Variables
        name = svc.get('name', 'unknown')
        stage = svc.get('stage', 'dev')
        domain = cfg.get('domain_name', 'local.lan')
        host = context.get('inventory_hostname', 'ci-host')
        inv_friendly = context.get('inventory_hostname_friendly', 'CI')
        
        # 2. FQDN Logic (The "Where")
        if not cfg.get('generate_hostname', False):
            fqdn = f"{svc.get('hostname', name)}.{domain}"
        else:
            fqdn = f"{stage}.{name}.{host}.{domain}"
            
        public_fqdn = None
        if ints.get('traefik', {}).get('internet_facing') and cfg.get('public_domain_name'):
            public_fqdn = f"{svc.get('hostname', name)}.{cfg['public_domain_name']}"

        labels = {}

        # 3. SWITCH: Traefik Automation
        if ints.get('traefik', {}).get('enabled'):
            t = ints['traefik']
            
            # Rule Building
            rule = f"Host(`{fqdn}`)"
            if public_fqdn:
                rule += f" || Host(`{public_fqdn}`)"
                
            # Network Logic
            net_name = dc.get('network_definitions', {}).get('secured', {}).get('name', 'services-secured')
            
            # Port Logic (Priority: Explicit > Ports List > Default 80)
            ports = context.get('ports', [])
            default_port = ports[0].get('port') if ports and isinstance(ports[0], dict) else 80
            svc_port = str(t.get('service_port', default_port))

            labels.update({
                "traefik.enable": "true",
                "traefik.docker.network": net_name,
                f"traefik.http.routers.{name}.rule": rule,
                f"traefik.http.routers.{name}.entrypoints": t.get('entrypoint', 'websecure'),
                f"traefik.http.routers.{name}.tls": "true",
                f"traefik.http.routers.{name}.tls.certresolver": t.get('cert_resolver', 'ionos')
            })

            # Host Network vs Container Network Routing
            if cfg.get('routing_host_network'):
                ansible_ip = context.get('ansible_host_ip', '10.111.111.111')
                labels[f"traefik.http.services.{name}.loadbalancer.server.url"] = f"http://{ansible_ip}:{svc_port}"
            else:
                labels[f"traefik.http.services.{name}.loadbalancer.server.port"] = svc_port
                labels[f"traefik.http.services.{name}.loadbalancer.server.scheme"] = t.get('service_scheme', 'http')
                
            if t.get('servers_transport'):
                labels[f"traefik.http.services.{name}.loadbalancer.serverstransport"] = t['servers_transport']

        # 4. SWITCH: AutoDNS Automation
        if ints.get('autodns', {}).get('enabled'):
            adns = ints['autodns']
            labels[f"auto-dns.createWildcard.{name}"] = str(adns.get('create_wildcard', False)).lower()
            
            if not cfg.get('generate_hostname', False):
                labels[f"auto-dns.customDNS.{name}"] = "true"
                labels[f"auto-dns.customDOMAIN.{name}"] = domain
                labels[f"auto-dns.customHost.{name}"] = svc.get('hostname', name)
            else:
                labels[f"auto-dns.customDNS.{name}"] = "false"
                labels[f"auto-dns.domain.{name}"] = domain
                labels[f"auto-dns.stage.{name}"] = stage
                labels[f"auto-dns.service.{name}"] = name
                labels[f"auto-dns.hostname.{name}"] = host

        # 5. SWITCH: Homepage Dashboard
        if ints.get('homepage', {}).get('enabled'):
            h = ints.get('homepage', {})
            href = f"https://{public_fqdn if public_fqdn else fqdn}"
            
            labels.update({
                "homepage.group": svc.get('category', 'Management'),
                "homepage.name": f"{svc.get('friendly_name', name)} - {inv_friendly}",
                "homepage.href": h.get('href', href),
                "homepage.icon": svc.get('icon', 'default.png'),
                "homepage.description": svc.get('description', '')
            })
            
            # Widget Support
            if h.get('widget'):
                w = h['widget']
                labels["homepage.widget.type"] = w.get('type')
                labels["homepage.widget.url"] = f"https://{fqdn}"
                if w.get('key'):
                    labels["homepage.widget.key"] = w['key']

        context['processed_labels'] = labels
        return context
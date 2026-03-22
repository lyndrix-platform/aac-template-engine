# scripts/manifest_generator/processors/ingress.py
from .base import BaseProcessor

class IngressProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc = context.get('service', {})
        cfg = context.get('config', {})
        ints = cfg.get('integrations', {})
        dc = context.get('deployments', {}).get('docker_compose', {})
        
        name = svc.get('name', 'unknown')
        stage = svc.get('stage', 'dev')
        domain = cfg.get('domain_name', 'local.lan')
        host = context.get('inventory_hostname', 'ci-host')
        inv_friendly = context.get('inventory_hostname_friendly', 'CI')
        
        # FQDN Logic
        if not cfg.get('generate_hostname', False):
            fqdn = f"{svc.get('hostname', name)}.{domain}"
        else:
            fqdn = f"{stage}.{name}.{host}.{domain}"
            
        # PUBLIC FQDN LOGIC (Updated to support custom public_hostname)
        public_fqdn = None
        if ints.get('traefik', {}).get('internet_facing') and cfg.get('public_domain_name'):
            # Grab the custom public hostname if it exists, otherwise fall back to the internal hostname
            pub_host = cfg.get('public_hostname', svc.get('hostname', name))
            public_fqdn = f"{pub_host}.{cfg['public_domain_name']}"

        labels = {}

        # Traefik Logic
        if ints.get('traefik', {}).get('enabled'):
            t = ints['traefik']
            rule = f"Host(`{fqdn}`)"
            
            if public_fqdn:
                rule += f" || Host(`{public_fqdn}`)"
                
            ports = context.get('ports', [])
            default_port = ports[0].get('port') if ports else 80
            svc_port = str(t.get('service_port', default_port))
            
            # Extract the new variables with safe defaults
            scheme = t.get('service_scheme', 'http')
            transport = t.get('servers_transport')

            labels.update({
                "traefik.enable": "true",
                f"traefik.http.routers.{name}.rule": rule,
                f"traefik.http.routers.{name}.entrypoints": t.get('entrypoint', 'websecure'),
                f"traefik.http.routers.{name}.tls": "true",
                f"traefik.http.routers.{name}.tls.certresolver": t.get('cert_resolver', 'ionos')
            })

            # Check if we route to Host or Container
            if dc.get('network_mode') == 'host' or cfg.get('routing_host_network'):
                ansible_ip = context.get('ansible_host_ip', '10.111.111.111')
                # Fixed: Use the dynamic scheme instead of hardcoded 'http'
                labels[f"traefik.http.services.{name}.loadbalancer.server.url"] = f"{scheme}://{ansible_ip}:{svc_port}"
            else:
                net_name = dc.get('network_definitions', {}).get('secured', {}).get('name', 'services-secured')
                labels["traefik.docker.network"] = net_name
                labels[f"traefik.http.services.{name}.loadbalancer.server.port"] = svc_port
                # Fixed: Tell Traefik to use https inside the docker network if requested
                labels[f"traefik.http.services.{name}.loadbalancer.server.scheme"] = scheme

            # Fixed: Apply the servers_transport if it was defined in the config
            if transport:
                labels[f"traefik.http.services.{name}.loadbalancer.serverstransport"] = transport

        # 3. AutoDNS Automation
        if ints.get('autodns', {}).get('enabled'):
            adns = ints['autodns']
            labels[f"auto-dns.createWildcard.{name}"] = str(adns.get('create_wildcard', False)).lower()
            if not cfg.get('generate_hostname', False):
                labels[f"auto-dns.customDNS.{name}"], labels[f"auto-dns.customDOMAIN.{name}"] = "true", domain
                labels[f"auto-dns.customHost.{name}"] = svc.get('hostname', name)
            else:
                labels.update({f"auto-dns.customDNS.{name}": "false", f"auto-dns.domain.{name}": domain,
                               f"auto-dns.stage.{name}": stage, f"auto-dns.service.{name}": name, f"auto-dns.hostname.{name}": host})

        # 4. Homepage Dashboard
        if ints.get('homepage', {}).get('enabled'):
            h = ints.get('homepage', {})
            labels.update({
                "homepage.group": svc.get('category', 'Management'),
                "homepage.name": f"{svc.get('friendly_name', name)} - {inv_friendly}",
                # Homepage will now correctly link to the public FQDN if it exists
                "homepage.href": h.get('href', f"https://{public_fqdn if public_fqdn else fqdn}"),
                "homepage.icon": svc.get('icon', 'default.png'),
                "homepage.description": svc.get('description', '')
            })
            if h.get('widget'):
                w = h['widget']
                labels.update({"homepage.widget.type": w.get('type'), "homepage.widget.url": f"https://{fqdn}"})
                if w.get('key'): labels["homepage.widget.key"] = w['key']

        context['processed_labels'] = labels
        return context
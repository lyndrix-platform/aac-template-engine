# scripts/manifest_generator/processors/metadata.py
from .base import BaseProcessor

class MetadataProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        svc = context.setdefault('service', {})
        name = svc.get('name', 'unknown-service')
        
        # 1. Ensure friendly_name exists for Homepage
        if not svc.get('friendly_name'):
            # Convert 'aac-traefik' to 'Traefik'
            svc['friendly_name'] = name.replace('aac-', '').replace('-', ' ').title().strip()
            
        # 2. Fix the inventory hostname for the " - Host" suffix
        inv_host = context.get('inventory_hostname', 'ci-validation-host')
        context['inventory_hostname_friendly'] = inv_host.replace('-', ' ').title()

        return context
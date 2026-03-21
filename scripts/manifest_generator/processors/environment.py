from .base import BaseProcessor

class EnvironmentProcessor(BaseProcessor):
    def process(self, context: dict) -> dict:
        # 1. Root-Container sicherstellen
        context.setdefault('environment', {})
        context.setdefault('secrets', {})
        
        dc = context.get('deployments', {}).get('docker_compose', {})

        # --- PART A: ROBUST LIFTING (Migration/Legacy) ---
        # Wir sammeln alles ein, was in alten oder tiefen Strukturen vergraben ist
        for key in ['dot_env', 'environment']:
            val = dc.pop(key, {})
            if isinstance(val, dict):
                context['environment'].update(val)

        legacy_secrets = dc.pop('stack_env', {})
        if isinstance(legacy_secrets, dict):
            context['secrets'].update(legacy_secrets)

        # --- PART B: PREPARATION ---
        # Wir initialisieren die finalen Dicts
        context['processed_env'] = {}
        context['processed_secrets'] = {}

        # 1. Hilfsfunktion für sauberes String-Casting und Sortierung
        def distribute_env(env_dict, is_secret_source=False):
            for k, v in env_dict.items():
                val_str = str(v)
                # Entscheidung: Wo landet die Variable?
                # A: Sie kommt aus einer Secret-Quelle
                # B: Sie triggert die Heuristik (als Sicherheitsnetz)
                is_likely_secret = any(x in k.lower() for x in ['pass', 'secret', 'token', 'key'])
                
                if is_secret_source or is_likely_secret:
                    context['processed_secrets'][k] = val_str
                else:
                    context['processed_env'][k] = val_str

        # 2. Main Service verarbeiten (Explizite Trennung)
        distribute_env(context['environment'], is_secret_source=False)
        distribute_env(context['secrets'], is_secret_source=True)

        # 3. Dependencies verarbeiten
        # HINWEIS: Sidecars sollten idealerweise ihre eigene Env-Datei haben. 
        # Wenn du sie in die globale mischen willst, ist dies der Weg:
        for dep_name, dep_cfg in context.get('dependencies', {}).items():
            dep_env = dep_cfg.get('environment', {})
            if isinstance(dep_env, dict):
                distribute_env(dep_env, is_secret_source=False)

        return context
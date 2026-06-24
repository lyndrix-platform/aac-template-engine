from .base import BaseProcessor


class EnvironmentProcessor(BaseProcessor):
    """Splits the central environment/secrets state into .env / stack.env.

    schema_version 1 (legacy, default): lifts legacy nested forms
    (deployments.docker_compose.{dot_env,environment,stack_env}) up to the root
    and classifies variables with a substring heuristic as a safety net.

    schema_version 2: the central ``environment:`` / ``secrets:`` blocks ARE the
    single state. Classification is explicit (environment -> .env, secrets ->
    stack.env, no heuristic) and ``deployments.docker_compose.environment`` is
    NOT lifted -- it is the main service's explicit inline env block, rendered
    straight into the compose file and resolved against ``vars:``/``secrets:``.
    """

    def process(self, context: dict) -> dict:
        context.setdefault('environment', {})
        context.setdefault('secrets', {})
        context.setdefault('vars', {})

        schema_version = self._schema_version(context)
        dc = context.get('deployments', {}).get('docker_compose', {})

        context['processed_env'] = {}
        context['processed_secrets'] = {}

        if schema_version >= 2:
            self._warn_legacy_blocks(dc)
            # No lifting: dc.environment stays in place for inline rendering.
            # Root environment/secrets feed .env/stack.env (dependency inheritance);
            # the main service references them explicitly under schema_version 2.
            for k, v in context['environment'].items():
                context['processed_env'][k] = str(v)
            for k, v in context['secrets'].items():
                context['processed_secrets'][k] = str(v)
            return context

        # --- Legacy (schema_version 1) ---
        # PART A: robust lifting of legacy nested forms into the root.
        for key in ['dot_env', 'environment']:
            val = dc.pop(key, {})
            if isinstance(val, dict):
                context['environment'].update(val)

        legacy_secrets = dc.pop('stack_env', {})
        if isinstance(legacy_secrets, dict):
            context['secrets'].update(legacy_secrets)

        # PART B: distribute with the substring heuristic as a safety net.
        def distribute_env(env_dict, is_secret_source=False):
            for k, v in env_dict.items():
                val_str = str(v)
                is_likely_secret = any(x in k.lower() for x in ['pass', 'secret', 'token', 'key'])
                if is_secret_source or is_likely_secret:
                    context['processed_secrets'][k] = val_str
                else:
                    context['processed_env'][k] = val_str

        distribute_env(context['environment'], is_secret_source=False)
        distribute_env(context['secrets'], is_secret_source=True)

        return context

    @staticmethod
    def _schema_version(context: dict) -> int:
        raw = context.get('config', {}).get('schema_version', 1)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _warn_legacy_blocks(dc: dict) -> None:
        # Under schema_version 2, dc.environment is expected (the main inline env
        # block); only the truly legacy nested forms are deprecated.
        for legacy_key in ('dot_env', 'stack_env'):
            if legacy_key in dc:
                print(f"  [DEPRECATION] 'deployments.docker_compose.{legacy_key}' is legacy; "
                      f"move values into the central 'secrets:'/'vars:' blocks (schema_version 2).")

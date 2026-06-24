#!/usr/bin/env python3
"""extract_overrides.py -- migrate a legacy service.yml to the schema_version 2
"single configuration state" and emit the iac-controller override block(s).

It NEVER writes in place. It prints (or writes to --out-dir) three kinds of
artifact:

  1. <service>.service.v2.yml      -- the publishable service.yml (placeholders)
  2. <service>.service.v2.real.yml -- the same v2 file with REAL values inlined
                                      (used by verify_parity.py as render A)
  3. <service>.override.<site>.<stage>.<host>.yml -- the host services[].config
                                      override block holding the REAL values,
                                      ready to paste into iac-controller.

Model (schema_version 2):
  * secrets:  central secret state -> stack.env (dependencies inherit)
  * vars:     central non-secret state, reference-only (never written to a file)
  * deployments.docker_compose.environment: the main service's EXPLICIT inline
              env, every key referencing {{ vars.X }} / {{ secrets.X }}
  * dependency inline env literals are rewritten to references (same key names)

Real (sensitive / environment-specific) values are replaced by placeholders in
the publishable file and moved into the override block.
"""
import argparse
import glob
import os
import re
import sys

import yaml

PLACEHOLDER = "CHANGE_ME"
DOMAIN_PLACEHOLDER = "example.com"

# --- classification helpers ------------------------------------------------

_SECRET_KEY_RE = re.compile(
    r"(pass|secret|token|api[_-]?key|private|credential|signing)", re.IGNORECASE
)
_SECRET_KEY_SUFFIX = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")
_ENV_SPECIFIC_SUFFIX = (
    "_URL", "_ISSUER", "_CLIENT_ID", "_HOST", "_NODE_IP", "_DOMAIN", "_TARGETS",
)
_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_FQDN_RE = re.compile(r"\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+\b", re.IGNORECASE)
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_OPAQUE_RE = re.compile(r"^[A-Za-z0-9+/=._~-]{24,}$")


def is_obvious_nonsecret(value) -> bool:
    """Values that are never sensitive regardless of key name."""
    raw = str(value).strip().strip('"').strip("'")
    if raw.lower() in ("true", "false", "yes", "no", "none", ""):
        return True
    if raw.isdigit():
        return True
    return False


def looks_secret(key: str, value) -> bool:
    if is_obvious_nonsecret(value):
        return False
    if _SECRET_KEY_RE.search(key) or key.upper().endswith(_SECRET_KEY_SUFFIX):
        return True
    sval = str(value)
    # URL carrying user:pass@host credentials
    if _URL_RE.search(sval) and re.search(r"://[^/\s:@]+:[^/\s:@]+@", sval):
        return True
    return False


def looks_env_specific(key: str, value) -> bool:
    if key.upper().endswith(_ENV_SPECIFIC_SUFFIX):
        return True
    sval = str(value)
    if _URL_RE.search(sval) or _IP_RE.search(sval):
        return True
    # bare FQDN (but not paths like Europe/Berlin or /data)
    if "/" not in sval and _FQDN_RE.search(sval) and "." in sval:
        return True
    # long opaque token (client ids, api keys hidden in env: block)
    if _OPAQUE_RE.match(sval) and not sval.isdigit():
        return True
    return False


def must_externalize(key: str, value, from_secret_block: bool) -> bool:
    """True if the value is sensitive/environment-specific and must move out."""
    if from_secret_block:
        return looks_secret(key, value) or looks_env_specific(key, value)
    return looks_secret(key, value) or looks_env_specific(key, value)


def placeholder_for(key: str, value) -> str:
    return PLACEHOLDER


def normalize_scalar(value):
    """Strip a single layer of surrounding matching quotes from malformed YAML
    scalars (e.g. '"6"' -> 6) when the inner content has no quote of its own."""
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'") and s[0] not in s[1:-1]:
            return s[1:-1]
    return value


# --- core ------------------------------------------------------------------

class Extraction:
    def __init__(self):
        self.vars = {}            # published vars: block (placeholders / literals)
        self.vars_real = {}       # real values for vars
        self.secrets = {}         # published secrets: block
        self.secrets_real = {}    # real values for secrets
        self.override_vars = {}   # values to externalize into iac-controller
        self.override_secrets = {}
        self.override_config = {}
        self.main_env_refs = {}   # deployments.docker_compose.environment mapping
        self.notes = []

    def add_var(self, key, value):
        value = normalize_scalar(value)
        self.vars_real[key] = value
        if must_externalize(key, value, from_secret_block=False):
            self.vars[key] = placeholder_for(key, value)
            self.override_vars[key] = value
        else:
            self.vars[key] = value
        self.main_env_refs[key] = "{{ vars.%s }}" % key

    def add_secret(self, key, value):
        value = normalize_scalar(value)
        self.secrets_real[key] = value
        if must_externalize(key, value, from_secret_block=True):
            self.secrets[key] = placeholder_for(key, value)
            self.override_secrets[key] = value
        else:
            self.secrets[key] = value
        self.main_env_refs[key] = "{{ secrets.%s }}" % key


def migrate_service(data: dict) -> Extraction:
    ex = Extraction()

    # 1. main-service environment: -> vars: (+ explicit inline refs)
    for key, value in (data.get("environment") or {}).items():
        # a clearly-secret key hiding in environment: is promoted to secrets:
        if looks_secret(key, value):
            ex.add_secret(key, value)
        else:
            ex.add_var(key, value)

    # 2. secrets: -> central secrets: (+ explicit inline refs)
    for key, value in (data.get("secrets") or {}).items():
        ex.add_secret(key, value)

    # 3. config.domain_name / public_domain_name -> externalize
    cfg = data.get("config") or {}
    for dkey in ("domain_name", "public_domain_name"):
        if dkey in cfg:
            ex.override_config[dkey] = cfg[dkey]

    return ex


def rewrite_dependency_env(dependencies: dict, ex: Extraction):
    """Rewrite inline dependency env literals into references to the central
    state, keeping identical key names. Mutates `dependencies` in place and
    records real values into the override."""
    for dep_name, dep in (dependencies or {}).items():
        for block_name in ("environment", "secrets"):
            block = dep.get(block_name)
            if block_name == "secrets" and isinstance(block, dict):
                # fold dependency secrets into the central secret state
                pass
            if not isinstance(block, dict):
                # also look inside overrides.<block>
                ov = dep.get("overrides", {})
                block = ov.get(block_name) if isinstance(ov, dict) else None
                target = ov if isinstance(block, dict) else None
            else:
                target = dep
            if not isinstance(block, dict):
                continue
            for key, value in list(block.items()):
                if "{{" in str(value):
                    continue  # already a reference
                if looks_secret(key, value):
                    if key not in ex.secrets_real:
                        ex.add_secret(key, value)
                        # add_secret also recorded a main_env_ref; drop it (dep-local)
                        ex.main_env_refs.pop(key, None)
                    block[key] = "{{ secrets.%s }}" % key
                elif looks_env_specific(key, value):
                    if key not in ex.vars_real:
                        ex.vars_real[key] = value
                        ex.vars[key] = PLACEHOLDER
                        ex.override_vars[key] = value
                    block[key] = "{{ vars.%s }}" % key
                # portable literal -> leave as-is (publishable)


def discover_placements(service_name: str, controller_root: str):
    """Find every host services[] entry matching service_name across the
    inventory. Returns list of (site, stage, host, source_file)."""
    placements = []
    pattern = os.path.join(controller_root, "sites", "*", "stages", "*", "hosts.yml")
    for path in sorted(glob.glob(pattern)):
        parts = path.split(os.sep)
        try:
            site = parts[parts.index("sites") + 1]
            stage = parts[parts.index("stages") + 1]
        except (ValueError, IndexError):
            site = stage = "?"
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] could not parse {path}: {e}", file=sys.stderr)
            continue
        for host_name, host in (doc.get("hosts") or {}).items():
            for svc in (host.get("services") or []):
                if isinstance(svc, dict) and svc.get("name") == service_name:
                    placements.append((site, stage, host_name, path))
    # profiles (global, no per-stage secrets possible)
    prof_path = os.path.join(controller_root, "global", "03_profiles.yml")
    if os.path.exists(prof_path):
        with open(prof_path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for prof_name, prof in (doc.get("profiles") or {}).items():
            for svc in (prof.get("services") or []):
                name = svc.get("name") if isinstance(svc, dict) else svc
                if name == service_name:
                    placements.append(("(profile)", prof_name, "(all hosts)", prof_path))
    return placements


def build_v2_service(data: dict, ex: Extraction, real: bool) -> dict:
    out = dict(data)  # shallow copy; we replace the relevant blocks
    cfg = dict(out.get("config") or {})
    cfg["schema_version"] = 2
    if not real:
        for dkey in ("domain_name", "public_domain_name"):
            if dkey in cfg:
                cfg[dkey] = DOMAIN_PLACEHOLDER
    out["config"] = cfg

    out.pop("environment", None)  # folded into vars: + dc.environment
    out["vars"] = ex.vars_real if real else ex.vars
    out["secrets"] = ex.secrets_real if real else ex.secrets

    deployments = dict(out.get("deployments") or {})
    dc = dict(deployments.get("docker_compose") or {})
    dc["environment"] = ex.main_env_refs
    deployments["docker_compose"] = dc
    out["deployments"] = deployments
    return out


_ENV_REF_RE = re.compile(r"\{\{\s*environment\.([A-Za-z0-9_]+)\s*\}\}")


def rewrite_env_refs(text: str, ex: "Extraction") -> str:
    """Rewrite {{ environment.KEY }} references to the namespace KEY now lives in
    under schema_version 2: {{ secrets.KEY }} if it was classified as a secret,
    else {{ vars.KEY }}. {{ secrets.* }} / {{ config.* }} are left untouched."""
    def repl(m):
        key = m.group(1)
        ns = "secrets" if key in ex.secrets_real else "vars"
        return "{{ %s.%s }}" % (ns, key)
    return _ENV_REF_RE.sub(repl, text)


def rewrite_node(node, ex: "Extraction"):
    """Recursively rewrite {{ environment.X }} refs in all string values."""
    if isinstance(node, dict):
        return {k: rewrite_node(v, ex) for k, v in node.items()}
    if isinstance(node, list):
        return [rewrite_node(v, ex) for v in node]
    if isinstance(node, str):
        return rewrite_env_refs(node, ex)
    return node


def rewrite_custom_templates(service_dir: str, ex: "Extraction") -> dict:
    """Return {relative_path: rewritten_content} for every custom_templates/*.j2
    whose {{ environment.X }} references changed."""
    out = {}
    ct_dir = os.path.join(service_dir, "custom_templates")
    if not os.path.isdir(ct_dir):
        return out
    for root, _dirs, files in os.walk(ct_dir):
        for fn in files:
            if not fn.endswith(".j2"):
                continue
            fpath = os.path.join(root, fn)
            rel = os.path.relpath(fpath, service_dir)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            new = rewrite_env_refs(content, ex)
            if new != content:
                out[rel] = new
    return out


def build_override(ex: Extraction) -> dict:
    cfg = {}
    if ex.override_vars:
        cfg["vars"] = ex.override_vars
    if ex.override_secrets:
        cfg["secrets"] = ex.override_secrets
    if ex.override_config:
        cfg["config"] = ex.override_config
    return cfg


def yaml_dump(data) -> str:
    return yaml.dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)


def main():
    p = argparse.ArgumentParser(description="Migrate a service.yml to schema_version 2 + emit overrides")
    p.add_argument("--service-yml", required=True)
    p.add_argument("--controller-root", help="iac-controller/environments dir (for placement discovery)")
    p.add_argument("--out-dir", help="write artifacts here instead of stdout")
    args = p.parse_args()

    with open(args.service_yml, "r", encoding="utf-8-sig") as f:
        data = yaml.safe_load(f)

    try:
        existing_sv = int((data.get("config") or {}).get("schema_version", 1))
    except (TypeError, ValueError):
        existing_sv = 1
    if existing_sv >= 2:
        sys.exit("ERROR: this service.yml is already schema_version 2 (migrated). "
                 "Run the extractor on the ORIGINAL legacy service.yml, not the migrated one.")

    service_name = (data.get("service") or {}).get("name", "unknown")

    ex = migrate_service(data)

    v2_placeholder = build_v2_service(data, ex, real=False)
    rewrite_dependency_env(v2_placeholder.get("dependencies"), ex)
    # rebuild after dependency rewrite may have added vars/secrets
    v2_placeholder["vars"] = ex.vars
    v2_placeholder["secrets"] = ex.secrets

    v2_real = build_v2_service(data, ex, real=True)
    # mirror dependency rewrites into the real file
    v2_real["dependencies"] = v2_placeholder.get("dependencies")
    v2_real["vars"] = ex.vars_real
    v2_real["secrets"] = ex.secrets_real

    # Rewrite {{ environment.X }} refs to {{ vars.X }}/{{ secrets.X }} everywhere
    # (in-tree string values + custom_templates files), since environment: is gone.
    v2_placeholder = rewrite_node(v2_placeholder, ex)
    v2_real = rewrite_node(v2_real, ex)
    service_dir = os.path.dirname(os.path.abspath(args.service_yml))
    ct_rewritten = rewrite_custom_templates(service_dir, ex)

    override = build_override(ex)
    placements = discover_placements(service_name, args.controller_root) if args.controller_root else []

    artifacts = {
        f"{service_name}.service.v2.yml": yaml_dump(v2_placeholder),
        f"{service_name}.service.v2.real.yml": yaml_dump(v2_real),
    }
    # rewritten custom_templates (relative paths preserved, e.g.
    # custom_templates/files/config/x.yml.j2) so they can be copied into the repo
    for rel, content in ct_rewritten.items():
        artifacts[rel] = content
    # one override doc per placement, with the service entry skeleton
    if placements:
        for site, stage, host, _src in placements:
            entry = {"name": service_name, "state": "present",
                     "deploy_type": "docker_compose", "config": override}
            artifacts[f"{service_name}.override.{site}.{stage}.{host}.yml"] = yaml_dump(entry)
    else:
        entry = {"name": service_name, "state": "present",
                 "deploy_type": "docker_compose", "config": override}
        artifacts[f"{service_name}.override.yml"] = yaml_dump(entry)

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for name, content in artifacts.items():
            dest = os.path.join(args.out_dir, name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [+] wrote {dest}")
    else:
        for name, content in artifacts.items():
            print(f"\n# ===== {name} =====")
            print(content)

    print(f"\n# placements for {service_name}:", file=sys.stderr)
    for site, stage, host, src in placements:
        print(f"#   {site}/{stage}/{host}  ({src})", file=sys.stderr)
    if not placements:
        print("#   (none found in controller inventory)", file=sys.stderr)


if __name__ == "__main__":
    main()

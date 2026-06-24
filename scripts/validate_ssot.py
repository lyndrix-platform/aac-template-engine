#!/usr/bin/env python3
"""SSoT linter for service.yml files.

Usage:
    python scripts/validate_ssot.py <path-or-glob> [<path-or-glob> ...]

A path may be a single service.yml, a service directory, or a parent directory
(scanned recursively for service.yml). Exits non-zero if any ERROR is found
(warnings do not fail the run).

On top of the structural checks it adds (for schema_version >= 2):
  * a publishability gate -- the published service.yml must NOT contain real
    secrets; secret values must be placeholders.
  * an inline-literal lint -- secrets/env-specific values should live in the
    central state and be referenced, not hardcoded in dependency/main env.
"""
import glob
import os
import re
import sys

import yaml

PLACEHOLDERS = {"CHANGE_ME", "example.com", "changeme", ""}
_OPAQUE_RE = re.compile(r"^[A-Za-z0-9+/=._~-]{24,}$")
_URL_CRED_RE = re.compile(r"://[^/\s:@]+:[^/\s:@]+@")
_SECRET_KEY_RE = re.compile(r"(pass|secret|token|api[_-]?key|private|credential|signing)", re.IGNORECASE)


def is_placeholder(value) -> bool:
    s = str(value).strip()
    return s in PLACEHOLDERS or "CHANGE_ME" in s


def looks_real_secret(value) -> bool:
    """A concrete, sensitive-looking literal (not a placeholder/reference)."""
    s = str(value).strip()
    if not s or is_placeholder(s) or "{{" in s:
        return False
    if _URL_CRED_RE.search(s):
        return True
    if _OPAQUE_RE.match(s) and not s.isdigit():
        return True
    return False


def schema_version(data: dict) -> int:
    try:
        return int((data.get("config") or {}).get("schema_version", 1))
    except (TypeError, ValueError):
        return 1


def validate_ssot(yaml_path):
    """Return (errors, warnings)."""
    errors, warnings = [], []
    try:
        with open(yaml_path, "r", encoding="utf-8-sig") as f:
            data = yaml.safe_load(f)
    except Exception as e:  # noqa: BLE001
        return [f"FATAL YAML Parse Error: {e}"], []

    if not data:
        return ["File is completely empty."], []

    sv = schema_version(data)

    # 1. Mandatory service keys
    svc = data.get("service", {})
    if not svc:
        errors.append("Missing root block: 'service'")
    else:
        for req in ["name", "image_repo", "image_tag", "stage"]:
            if req not in svc:
                errors.append(f"Missing mandatory key: 'service.{req}'")

    # 2. Deployment block exists
    dc = data.get("deployments", {}).get("docker_compose", {}) or {}
    if not dc:
        errors.append("Missing block: 'deployments.docker_compose'")

    # 3. Dangling volumes
    defined_volumes = data.get("volumes", {}) or {}
    for vol_str in dc.get("volumes", []) or []:
        if not isinstance(vol_str, str):
            continue
        v_id = vol_str.split(":")[0]
        if not v_id.startswith(("/", ".", "{{")) and v_id not in defined_volumes:
            errors.append(f"Dangling Volume: '{v_id}' is mounted but missing from root 'volumes:'.")

    # 4. Typos / misplaced keys
    if "environments" in dc:
        errors.append("Typo: 'environments' in docker_compose. It must be 'environment'.")
    if "security_opts" in dc:
        errors.append("Typo: 'security_opts'. It must be 'security_opt'.")
    if "ports" in dc:
        errors.append("Misplaced Key: 'ports' belongs at the root, not in 'deployments.docker_compose'.")

    # 5. Traefik domain validation
    cfg = data.get("config", {}) or {}
    if cfg.get("integrations", {}).get("traefik", {}).get("enabled", False):
        if not cfg.get("domain_name") and not cfg.get("public_domain_name"):
            errors.append("Traefik enabled, but no 'domain_name' in 'config:'.")

    # 6. Legacy-form deprecation
    for legacy in ("dot_env", "stack_env"):
        if legacy in dc:
            warnings.append(f"Deprecated: 'deployments.docker_compose.{legacy}' -> move to central 'secrets:'/'vars:' (schema_version 2).")
    if sv < 2:
        warnings.append("schema_version < 2: legacy env/secret heuristic in effect. Migrate to schema_version 2.")

    # 7a. Publishability: no real secrets in a committed service.yml. A migrated
    # (schema_version 2) file MUST be clean (ERROR); legacy files are flagged as
    # a migration-backlog WARNING so transition CI is not broken wholesale.
    sink = errors if sv >= 2 else warnings
    tag = "PUBLISHABILITY" if sv >= 2 else "publishability"
    for key, value in (data.get("secrets") or {}).items():
        if looks_real_secret(value):
            sink.append(f"{tag}: secrets.{key} looks like a real secret; placeholder it and move the value to iac-controller.")

    # 7b. schema_version 2 inline-literal lint
    if sv >= 2:
        # inline-literal lint across vars + main env + dependency env
        for key, value in (data.get("vars") or {}).items():
            if looks_real_secret(value):
                warnings.append(f"Inline literal: vars.{key} looks sensitive; consider moving to 'secrets:'.")
        main_env = (dc.get("environment") or {})
        for key, value in main_env.items():
            if "{{" not in str(value) and looks_real_secret(value):
                warnings.append(f"Inline literal: deployments.docker_compose.environment.{key} should reference {{{{ vars/secrets }}}}.")
        for dep_name, dep in (data.get("dependencies") or {}).items():
            blocks = [dep.get("environment"), dep.get("secrets"),
                      (dep.get("overrides") or {}).get("environment")]
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                for key, value in block.items():
                    if "{{" not in str(value) and looks_real_secret(value):
                        warnings.append(f"Inline literal: dependency '{dep_name}' env '{key}' should reference the central state.")

    return errors, warnings


def iter_service_files(targets):
    for t in targets:
        if os.path.isfile(t):
            yield t
        elif os.path.isdir(t):
            direct = os.path.join(t, "service.yml")
            if os.path.exists(direct):
                yield direct
            else:
                yield from sorted(glob.glob(os.path.join(t, "**", "service.yml"), recursive=True))
        else:
            yield from sorted(glob.glob(t, recursive=True))


def main():
    targets = sys.argv[1:] or ["."]
    files = list(dict.fromkeys(iter_service_files(targets)))

    print("=" * 54)
    print("RUNNING SSOT LINTER")
    print("=" * 54)

    if not files:
        print("No service.yml found for the given path(s).")
        sys.exit(1)

    total = failed = warned = 0
    for path in files:
        total += 1
        errors, warnings = validate_ssot(path)
        label = os.path.relpath(path)
        if errors:
            failed += 1
            print(f"\n[FAIL] {label}")
            for err in errors:
                print(f"   ERROR: {err}")
            for w in warnings:
                print(f"   warn:  {w}")
        elif warnings:
            warned += 1
            print(f"\n[WARN] {label}")
            for w in warnings:
                print(f"   warn:  {w}")

    print("\n" + "=" * 54)
    print(f"{total} checked | {failed} failed | {warned} with warnings")
    print("=" * 54)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

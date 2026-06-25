#!/usr/bin/env python3
"""check_placement_leaks.py <service> -- pre-cutover gate.

For the given migrated (v2) service, replicate the Ansible bridge merge
(service.yml | combine(host_service.config, recursive=True)) for EVERY committed
placement in iac-controller and fail if the merged config still contains a
publishable placeholder (example.com / CHANGE_ME). This catches the class of bug
where a service is placed on a host but its iac-controller override is missing or
incomplete, so it would deploy with the publishable default leaking through.

Reads service.yml from the service repo working tree (the about-to-be-pushed v2),
and host entries from iac-controller origin/main (the deployed truth).

Exit 0 = clean, 1 = leak found, 2 = usage/IO error.
"""
import os
import subprocess
import sys

import yaml

CTRL = os.environ.get("CTRL", "/home/marvin/gitlab/iac-environment/iac-controller")
APPS = os.environ.get(
    "APPS", "/home/marvin/gitlab/iac-environment/aac-application-defenitions/applications-repository")
PLACEHOLDERS = ("example.com", "CHANGE_ME")
HOSTS_FILES = ("sites/hetzner/stages/prod/hosts.yml", "sites/onprem/stages/prod/hosts.yml",
               "sites/onprem/stages/dev/hosts.yml", "sites/onprem/stages/test/hosts.yml",
               "sites/hetzner/stages/dev/hosts.yml", "sites/hetzner/stages/test/hosts.yml")


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def find_leaks(node, path=""):
    leaks = []
    if isinstance(node, dict):
        for k, v in node.items():
            leaks += find_leaks(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            leaks += find_leaks(v, f"{path}[{i}]")
    elif isinstance(node, str):
        if any(p in node for p in PLACEHOLDERS):
            leaks.append((path.lstrip("."), node))
        # wrapped ("...") or backslash-escaped values corrupt the legacy stack.env
        # render ("unexpected character in variable name") and break inline JSON.
        elif (len(node) >= 2 and node[0] == '"' and node[-1] == '"') or '\\"' in node:
            leaks.append((path.lstrip("."), node))
    return leaks


def main():
    if len(sys.argv) != 2:
        print("usage: check_placement_leaks.py <service>", file=sys.stderr); sys.exit(2)
    svc = sys.argv[1]
    sf = os.path.join(APPS, svc, "service.yml")
    if not os.path.exists(sf):
        print(f"{svc}: service.yml not found", file=sys.stderr); sys.exit(2)
    sy = yaml.safe_load(open(sf)) or {}
    if (sy.get("config") or {}).get("schema_version", 1) < 2:
        print(f"{svc}: not v2, skipping leak check"); sys.exit(0)

    placements = 0
    bad = []
    for rel in HOSTS_FILES:
        raw = subprocess.run(["git", "-C", CTRL, "show", f"origin/main:environments/{rel}"],
                             capture_output=True, text=True).stdout
        if not raw:
            continue
        doc = yaml.safe_load(raw) or {}
        for hn, host in (doc.get("hosts") or {}).items():
            if not isinstance(host, dict):
                continue
            for s in (host.get("services") or []):
                if not isinstance(s, dict) or s.get("name") != svc:
                    continue
                placements += 1
                merged = deep_merge(sy, s.get("config") or {})
                # only inspect config/secrets/vars (env/deployments may legitimately
                # carry CHANGE_ME placeholders intended to be set elsewhere)
                for blk in ("config", "secrets", "vars"):
                    for p, v in find_leaks(merged.get(blk), blk):
                        bad.append((rel.split("/", 1)[1].replace("/hosts.yml", ""), hn, p, v))

    if not placements:
        print(f"{svc}: no committed placement (nothing to leak-check)"); sys.exit(0)
    if bad:
        print(f"{svc}: LEAK -- {len(bad)} placeholder(s) survive the bridge merge:")
        for loc, hn, p, v in bad:
            print(f"    {loc}/{hn}  {p} = {v}")
        sys.exit(1)
    print(f"{svc}: clean ({placements} placement(s), no placeholders leak)")
    sys.exit(0)


if __name__ == "__main__":
    main()

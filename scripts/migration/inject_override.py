#!/usr/bin/env python3
"""inject_override.py -- insert a `config:` override block into a host service
entry in an iac-controller hosts.yml, preserving the rest of the file verbatim
(text insertion, not a full YAML re-dump, so comments/formatting survive).

Idempotent: if the target service entry already has a `config:` sub-key it is
left untouched (re-running is a no-op) unless --replace is given.

Usage:
  inject_override.py --hosts <hosts.yml> --override <override.yml> --service <name> [--replace]
"""
import argparse
import sys

import yaml


def indent_block(config_block: dict, spaces: int = 8) -> str:
    dumped = yaml.dump(config_block, sort_keys=False, default_flow_style=False, allow_unicode=True)
    pad = " " * spaces
    out = "".join(pad + line if line.strip() else line for line in dumped.splitlines(keepends=True))
    if not out.endswith("\n"):
        out += "\n"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts", required=True)
    ap.add_argument("--override", required=True)
    ap.add_argument("--service", required=True)
    ap.add_argument("--replace", action="store_true", help="replace an existing config: block")
    args = ap.parse_args()

    with open(args.override, "r", encoding="utf-8") as f:
        ov = yaml.safe_load(f)
    config_block = {"config": (ov.get("config", ov) if isinstance(ov, dict) else {})}
    indented = indent_block(config_block)

    with open(args.hosts, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out, i, injected = [], 0, False
    sub_keys = ("state:", "deploy_type:", "git_repo:", "git_version:")
    while i < len(lines):
        out.append(lines[i])
        if not injected and lines[i].strip() == f"- name: {args.service}":
            j = i + 1
            # copy the entry's scalar sub-keys
            while j < len(lines) and lines[j].lstrip().startswith(sub_keys):
                out.append(lines[j])
                j += 1
            # idempotency: existing config: block on this entry
            if j < len(lines) and lines[j].lstrip().startswith("config:"):
                if not args.replace:
                    print(f"  [=] {args.service}: config: already present in {args.hosts}; skipping")
                    return
                # skip the existing config block (deeper-indented lines)
                base_indent = len(lines[j]) - len(lines[j].lstrip())
                k = j + 1
                while k < len(lines) and (not lines[k].strip() or (len(lines[k]) - len(lines[k].lstrip())) > base_indent):
                    k += 1
                j = k  # drop old block
            out.append(indented)
            injected = True
            i = j
            continue
        i += 1

    if not injected:
        sys.exit(f"ERROR: service entry '{args.service}' not found in {args.hosts}")

    # sanity: result still parses
    yaml.safe_load("".join(out))
    with open(args.hosts, "w", encoding="utf-8") as f:
        f.writelines(out)
    print(f"  [+] injected config into {args.service} @ {args.hosts}")


if __name__ == "__main__":
    main()

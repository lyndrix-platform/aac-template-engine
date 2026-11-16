#!/usr/bin/env python3
"""Helpers for scripts/public_release.sh (public GitHub release sync).

Sub-commands:
  sanitize <service.yml>        blank all secret values (-> CHANGE_ME); rewrites file only if needed
  readme   <tree> <service.yml> create/extend README.md with a "Quick start (docker compose)" section
  notes    <CHANGELOG.md> <X.Y.Z>   print the changelog section of a release (empty if none)
"""
import os
import re
import sys

import yaml

SECRET_HINTS = ("pass", "secret", "token", "key")
BOILERPLATE_MARK = "get started with GitLab"


def cmd_sanitize(path):
    with open(path, encoding="utf-8-sig") as f:
        data = yaml.safe_load(f) or {}
    changed = 0

    def blank(block):
        nonlocal changed
        if not isinstance(block, dict):
            return
        for k, v in block.items():
            if isinstance(v, (dict, list)):
                continue
            if v not in ("CHANGE_ME", "", None):
                block[k] = "CHANGE_ME"
                changed += 1

    blank(data.get("secrets"))
    # secret-looking keys in the plain environment/vars blocks as well
    for name in ("environment", "vars"):
        blk = data.get(name)
        if isinstance(blk, dict):
            sub = {k: v for k, v in blk.items() if any(h in k.lower() for h in SECRET_HINTS)}
            blank(sub)
            blk.update(sub)
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    print(f"sanitize: {changed} secret value(s) replaced by CHANGE_ME")


def _external_networks(compose_path):
    try:
        with open(compose_path, encoding="utf-8") as f:
            c = yaml.safe_load(f) or {}
    except OSError:
        return []
    out = []
    for key, n in (c.get("networks") or {}).items():
        if isinstance(n, dict) and n.get("external"):
            out.append(n.get("name") or key)
    return out


def cmd_readme(tree, ssot):
    with open(ssot, encoding="utf-8-sig") as f:
        s = yaml.safe_load(f) or {}
    svc = s.get("service", {})
    name = svc.get("name", os.path.basename(os.path.abspath(tree)))
    desc = (svc.get("description") or "").strip()
    image = f"{svc.get('image_repo', '')}:{svc.get('image_tag', 'latest')}".strip(":")
    nets = _external_networks(os.path.join(tree, "deployments/docker_compose/docker-compose.yml"))
    qs = ["## Quick start (docker compose)", "",
          "Ready-to-use deployment files are in `deployments/docker_compose/`.", "",
          "1. Open `deployments/docker_compose/.env` and `stack.env` and replace every `CHANGE_ME`.",
          "2. Adapt hostnames / domain (`example.com`) to your environment."]
    if nets:
        qs += ["3. Make sure the external Docker networks exist (or adapt the `networks:` block):",
               "   ```bash", *[f"   docker network create {n}" for n in nets], "   ```"]
    qs += ["", "```bash", "cd deployments/docker_compose", "docker compose up -d", "```", ""]
    qs = "\n".join(qs)

    path = os.path.join(tree, "README.md")
    existing = ""
    if os.path.exists(path):
        existing = open(path, encoding="utf-8").read()
    if not existing.strip() or BOILERPLATE_MARK in existing:
        body = [f"# {name}", ""]
        if desc:
            body += [desc, ""]
        if image.strip():
            body += [f"Container image: `{image}`", ""]
        body += [qs,
                 "## About this repository", "",
                 "`service.yml` is the single source of truth of this service. The files in `deployments/` are",
                 "generated from it with the [aac-template-engine](https://github.com/lyndrix-platform/aac-template-engine)",
                 "using placeholder values only. This repository is a release snapshot (one commit per release).", ""]
        text = "\n".join(body)
        print("readme: generated (GitLab boilerplate or missing README replaced)")
    elif re.search(r"^#+\s*quick\s*-?start", existing, re.I | re.M):
        print("readme: kept (Quick start already present)")
        return
    else:
        text = existing.rstrip("\n") + "\n\n" + qs
        print("readme: Quick start section appended")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_notes(changelog, tag):
    try:
        lines = open(changelog, encoding="utf-8").read().splitlines()
    except OSError:
        return
    pat = re.compile(r"^#{1,3}\s*\[?v?" + re.escape(tag) + r"\]?(\s|$|\()")
    out, on = [], False
    for ln in lines:
        if on and re.match(r"^#{1,3}\s", ln):
            break
        if pat.match(ln):
            on = True
            continue
        if on:
            out.append(ln)
    print("\n".join(out).strip())


if __name__ == "__main__":
    c, a = sys.argv[1], sys.argv[2:]
    {"sanitize": cmd_sanitize, "readme": cmd_readme, "notes": cmd_notes}[c](*a)

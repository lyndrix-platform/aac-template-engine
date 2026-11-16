#!/usr/bin/env python3
"""Helpers for scripts/public_release.sh (public GitHub release sync).

Sub-commands:
  sanitize <service.yml>        blank all secret values (-> CHANGE_ME); rewrites file only if needed
  finalize <tree>                  inline CHANGE_ME -> \${KEY:?}, single .env.example
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

    def looks_secret(k, v):
        v = str(v)
        if any(h in k.lower() for h in SECRET_HINTS + ("credential", "auth", "_url", "dsn")):
            return True
        # long mixed-class token-like value without spaces
        return (len(v) >= 16 and " " not in v and re.search(r"[A-Za-z]", v) and re.search(r"[0-9]", v)
                and not v.startswith(("http://", "https://", "/")))

    def blank(block):
        nonlocal changed
        if not isinstance(block, dict):
            return
        for k, v in block.items():
            if isinstance(v, (dict, list)):
                continue
            # non-secret entries (e.g. POSTGRES_USER / POSTGRES_DB) keep their real default
            if v not in ("CHANGE_ME", "", None) and looks_secret(k, v):
                block[k] = "CHANGE_ME"
                changed += 1

    # neutral, non-secret defaults for platform-injected metadata (stay real values, not CHANGE_ME)
    svc = data.get("service", {}) or {}
    cfg = data.setdefault("config", {}) or {}
    host = svc.get("hostname") or svc.get("name", "app")
    defaults = {"SERVICE_IMAGE_TAG": svc.get("image_tag"), "SERVICE_IMAGE_NAME": svc.get("image_repo"),
                "SERVICE_ICON": svc.get("icon"), "SERVICE_DOMAIN_NAME": "example.com"}
    allv = [data.get("vars"), data.get("environment")]
    for blk in allv:
        if not isinstance(blk, dict):
            continue
        for k, v in list(blk.items()):
            if v != "CHANGE_ME":
                continue
            ku = k.upper()
            if defaults.get(k):
                blk[k] = defaults[k]; changed += 1
            elif re.search(r"URL|AUTHORITY|ISSUER|DOMAIN|HOST", ku) and not re.search(r"DATABASE|DSN|PASS|SECRET|TOKEN|KEY", ku):
                blk[k] = (f"https://{host}.example.com" if re.search(r"URL|AUTHORITY|ISSUER", ku) else f"{host}.example.com")
                changed += 1
    # hostnames: <hostname>.example.com (no <stage>.<service>.<host>.<domain> construct), neutral domain
    for c in [cfg] + [(o or {}).get("config") or {} for o in (data.get("stage_overrides") or {}).values()]:
        if "generate_hostname" in c:
            c["generate_hostname"] = False; changed += 1
        for dk in ("domain_name", "public_domain_name"):
            if c.get(dk) and c[dk] != "example.com":
                c[dk] = "example.com"; changed += 1
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
    print(f"sanitize: {changed} value(s) neutralised (defaults/hostnames/secrets)")


SECRET_RE = re.compile(r"pass|secret|token|key|credential|database|dsn", re.I)


def _read_envfile(path):
    out = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


def _external_networks(compose_path):
    try:
        c = yaml.safe_load(open(compose_path, encoding="utf-8")) or {}
    except OSError:
        return []
    return [(n.get("name") or k) for k, n in (c.get("networks") or {}).items() if isinstance(n, dict) and n.get("external")]


def cmd_finalize(tree):
    """Keep the compose exactly as rendered (platform networks, paths, labels). Only:
    - inline CHANGE_ME secrets -> ${KEY:?set in .env}
    - rendered .env/stack.env -> single .env.example (all vars commented, secrets CHANGE_ME)
    - env_file: [.env, stack.env] -> [.env]"""
    d = os.path.join(tree, "deployments/docker_compose")
    cpath = os.path.join(d, "docker-compose.yml")
    text = open(cpath, encoding="utf-8").read()
    env = {}
    env.update(_read_envfile(os.path.join(d, ".env")))
    env.update(_read_envfile(os.path.join(d, "stack.env")))

    def sub(m):
        env[m.group(2)] = "CHANGE_ME"
        return f'{m.group(1)}{m.group(2)}: "${{{m.group(2)}:?set {m.group(2)} in .env (see .env.example)}}"'
    text = re.sub(r'^(\s+)([A-Za-z_][A-Za-z0-9_]*): "CHANGE_ME"\s*$', sub, text, flags=re.M)
    text = re.sub(r"^\s+- stack\.env\s*\n", "", text, flags=re.M)
    open(cpath, "w", encoding="utf-8").write(text)

    lines = ["# Copy to .env and set every CHANGE_ME:  cp .env.example .env", ""]
    for k in sorted(env, key=lambda k: (env[k] != "CHANGE_ME", k)):
        v = env[k]
        if v == "CHANGE_ME" and not SECRET_RE.search(k):
            lines += ["# REQUIRED - set for your environment", f"{k}=CHANGE_ME", ""]
        elif v == "CHANGE_ME" or SECRET_RE.search(k) and v:
            lines += [f"# SECRET - set a strong value" + (" (must match the POSTGRES_* values)" if re.search("DATABASE|DSN", k, re.I) else ""),
                      f"{k}=CHANGE_ME", ""]
        else:
            lines += [f"# default: {v}", f"{k}={v}", ""]
    if env:
        open(os.path.join(d, ".env.example"), "w", encoding="utf-8").write("\n".join(lines))
    for fn in (".env", "stack.env"):
        try:
            os.remove(os.path.join(d, fn))
        except OSError:
            pass
    print(f"finalize: {len(env)} variable(s) in .env.example")


def cmd_readme(tree, ssot):
    with open(ssot, encoding="utf-8-sig") as f:
        s = yaml.safe_load(f) or {}
    svc = s.get("service", {})
    name = svc.get("name", os.path.basename(os.path.abspath(tree)))
    desc = (svc.get("description") or "").strip()
    image = f"{svc.get('image_repo', '')}:{svc.get('image_tag', 'latest')}".strip(":")
    nets = _external_networks(os.path.join(tree, "deployments/docker_compose/docker-compose.yml"))
    has_env = os.path.exists(os.path.join(tree, "deployments/docker_compose/.env.example"))
    qs = ["## Quick start (docker compose)", "",
          "```bash",
          "cd deployments/docker_compose",
          *(["cp .env.example .env      # set every CHANGE_ME"] if has_env else []),
          "docker compose up -d", "```", ""]
    if nets:
        qs += ["The compose file expects these external Docker networks (create them once, or adapt `networks:`):", "",
               "```bash", *[f"docker network create {n}" for n in nets], "```", ""]
    qs += ["Data is stored under `/export/docker/<service>/` on the host (see `volumes:`). Hostnames use `example.com`;",
           "the Traefik/auto-dns/homepage labels target the platform this was generated for - adjust or remove them.", ""]
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
    {"sanitize": cmd_sanitize, "finalize": cmd_finalize, "readme": cmd_readme, "notes": cmd_notes}[c](*a)

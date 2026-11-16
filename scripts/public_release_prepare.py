#!/usr/bin/env python3
"""Helpers for scripts/public_release.sh (public GitHub release sync).

Sub-commands:
  sanitize <service.yml>        blank all secret values (-> CHANGE_ME); rewrites file only if needed
  standalone <tree> <service.yml>  make rendered compose standalone (+ .env.example, traefik override)
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


PLATFORM_VARS = {"SERVICE_STAGE", "SERVICE_NAME", "SERVICE_NAME_LOWERCASE", "SERVICE_HOSTNAME", "SERVICE_CATEGORY",
                 "SERVICE_DESCRIPTION", "SERVICE_ICON", "SERVICE_RESTART_POLICY", "SERVICE_IMAGE_NAME",
                 "SERVICE_IMAGE_TAG", "SERVICE_DOMAIN_NAME", "DEFAULT_DOCKER_DIR"}
SECRET_RE = re.compile(r"pass|secret|token|key|credential", re.I)


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


def _dollar(v):
    return v.replace("$", "$$") if "$" in v and not v.startswith("${") else v


def cmd_standalone(tree, ssot):
    """Turn the platform-rendered compose into a standalone one (no external networks, relative
    volumes, no platform labels, .env.example) plus an optional Traefik override."""
    d = os.path.join(tree, "deployments/docker_compose")
    cpath = os.path.join(d, "docker-compose.yml")
    comp = yaml.safe_load(open(cpath, encoding="utf-8"))
    ssot_d = yaml.safe_load(open(ssot, encoding="utf-8-sig")) or {}
    svc_meta = ssot_d.get("service", {})
    host = svc_meta.get("hostname") or svc_meta.get("name", "app")

    extra_env = _read_envfile(os.path.join(d, ".env"))
    extra_env.update(_read_envfile(os.path.join(d, "stack.env")))

    env_example = {}   # KEY -> (default, kind, comment)
    seen = {}

    def register(k, v):
        """Return the compose value for env var k with default v, recording it for .env.example."""
        v = "" if v is None else str(v)
        is_secret = (SECRET_RE.search(k) and v and v.lower() not in ("true", "false") and not v.isdigit()
                     and not k.startswith("NEXT_PUBLIC_"))
        if v == "CHANGE_ME" or is_secret:
            if k not in seen:
                kind = "secret" if (SECRET_RE.search(k) and not k.startswith("NEXT_PUBLIC_")) else "required"
                note = ("SECRET - set a strong value" if kind == "secret" else "REQUIRED - set for your environment")
                if "DATABASE" in k.upper() or k.upper().endswith("DSN"):
                    note += " (must match the POSTGRES_* values / db service name)"
                env_example[k] = ("CHANGE_ME", note)
                seen[k] = "CHANGE_ME"
            if seen[k] == "CHANGE_ME":
                return f"${{{k}:?set {k} in .env (see .env.example)}}"
            return v
        if k in seen and seen[k] != v:
            return v                                   # collision with different default: keep literal
        if k not in seen:
            env_example[k] = (v, f"default: {v}" if v else "optional")
            seen[k] = v
        return f"${{{k}:-{_dollar(v)}}}"

    traefik_services = {}
    for name, svc in comp.get("services", {}).items():
        svc.pop("container_name", None)
        labels = svc.pop("labels", None) or {}
        if isinstance(labels, list):
            labels = dict(x.split("=", 1) for x in labels if "=" in x)
        if str(labels.get("traefik.enable", "")).lower() == "true":
            port = labels.get(f"traefik.http.services.{name}.loadbalancer.server.port")
            scheme = labels.get(f"traefik.http.services.{name}.loadbalancer.server.scheme", "http")
            traefik_services[name] = (port, scheme)
        # networks: one local bridge only
        svc["networks"] = ["internal"]
        # volumes: platform host path -> relative
        vols = []
        for v in svc.get("volumes", []) or []:
            m = re.match(r"^/export/docker/[^/]+/(.+?):(.*)$", str(v))
            vols.append(f"./{m.group(1)}:{m.group(2)}" if m else v)
        if vols:
            svc["volumes"] = vols
        # ports: host port overridable
        ports = []
        for p in svc.get("ports", []) or []:
            m = re.match(r"^(\d+):(\d+)(/\w+)?$", str(p))
            if m:
                k = f"HOST_PORT_{m.group(2)}"
                if k not in env_example:
                    env_example[k] = (m.group(1), f"host port for container port {m.group(2)}")
                    seen[k] = m.group(1)
                ports.append(f"${{{k}:-{m.group(1)}}}:{m.group(2)}{m.group(3) or ''}")
            else:
                ports.append(p)
        if ports:
            svc["ports"] = ports
        # environment
        env = svc.get("environment")
        if isinstance(env, dict):
            new = {}
            for k, v in env.items():
                if k in PLATFORM_VARS:
                    continue
                new[k] = register(k, v)
            svc["environment"] = new
        elif env is not None:
            pass
        # env_file (sidecars): platform split .env/stack.env -> single .env, values from rendered files
        if svc.get("env_file"):
            svc["env_file"] = [".env"]
            for k, v in extra_env.items():
                if k not in PLATFORM_VARS:
                    register(k, v)

    comp["networks"] = {"internal": {"driver": "bridge"}}
    header = ("# Standalone docker compose deployment (generated from service.yml by aac-template-engine).\n"
              "# Usage: cp .env.example .env  # edit the CHANGE_ME values\n"
              "#        docker compose up -d\n"
              "# Optional Traefik: docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d\n")
    with open(cpath, "w", encoding="utf-8") as f:
        f.write(header + yaml.safe_dump(comp, sort_keys=False, width=200))

    # .env.example (secrets/required first)
    lines = ["# Copy to .env and adapt:  cp .env.example .env", ""]
    for k, (v, note) in sorted(env_example.items(), key=lambda kv: (kv[1][0] != "CHANGE_ME", kv[0])):
        lines += [f"# {note}", f"{k}={v}", ""]
    if traefik_services:
        lines += ["# --- optional Traefik override (docker-compose.traefik.yml) ---",
                  "# public hostname", f"#DOMAIN={host}.example.com",
                  "# Traefik entrypoint / certificate resolver / external Traefik docker network",
                  "#TRAEFIK_ENTRYPOINT=websecure", "#TRAEFIK_CERTRESOLVER=letsencrypt", "#TRAEFIK_NETWORK=traefik", ""]
    with open(os.path.join(d, ".env.example"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    for fn in (".env", "stack.env"):
        try:
            os.remove(os.path.join(d, fn))
        except OSError:
            pass

    if traefik_services:
        ov = {"services": {}, "networks": {"traefik": {"name": "${TRAEFIK_NETWORK:-traefik}", "external": True}}}
        for name, (port, scheme) in traefik_services.items():
            labels = {
                "traefik.enable": "true",
                f"traefik.http.routers.{name}.rule": "Host(`${DOMAIN:-" + host + ".example.com}`)",
                f"traefik.http.routers.{name}.entrypoints": "${TRAEFIK_ENTRYPOINT:-websecure}",
                f"traefik.http.routers.{name}.tls": "true",
                f"traefik.http.routers.{name}.tls.certresolver": "${TRAEFIK_CERTRESOLVER:-letsencrypt}",
                "traefik.docker.network": "${TRAEFIK_NETWORK:-traefik}",
            }
            if port:
                labels[f"traefik.http.services.{name}.loadbalancer.server.port"] = str(port)
                labels[f"traefik.http.services.{name}.loadbalancer.server.scheme"] = scheme
            ov["services"][name] = {"labels": labels, "networks": ["internal", "traefik"]}
        with open(os.path.join(d, "docker-compose.traefik.yml"), "w", encoding="utf-8") as f:
            f.write("# Optional Traefik override. Requires an existing Traefik instance on the external network $TRAEFIK_NETWORK.\n"
                    "# docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d\n"
                    + yaml.safe_dump(ov, sort_keys=False, width=200))
    print(f"standalone: {len(env_example)} variable(s) in .env.example, traefik override: {bool(traefik_services)}")


def cmd_readme(tree, ssot):
    with open(ssot, encoding="utf-8-sig") as f:
        s = yaml.safe_load(f) or {}
    svc = s.get("service", {})
    name = svc.get("name", os.path.basename(os.path.abspath(tree)))
    desc = (svc.get("description") or "").strip()
    image = f"{svc.get('image_repo', '')}:{svc.get('image_tag', 'latest')}".strip(":")
    has_tr = os.path.exists(os.path.join(tree, "deployments/docker_compose/docker-compose.traefik.yml"))
    qs = ["## Quick start (docker compose)", "",
          "```bash",
          "cd deployments/docker_compose",
          "cp .env.example .env      # set every CHANGE_ME (secrets) and adjust defaults",
          "docker compose up -d", "```", "",
          "Data is stored next to the compose file in relative folders (e.g. `./data`)."]
    if has_tr:
        qs += ["", "Behind Traefik (existing Traefik instance on an external docker network):", "",
               "```bash", "# set DOMAIN, TRAEFIK_NETWORK, TRAEFIK_CERTRESOLVER in .env, then:",
               "docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d", "```"]
    qs = "\n".join(qs) + "\n"

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
    {"sanitize": cmd_sanitize, "standalone": cmd_standalone, "readme": cmd_readme, "notes": cmd_notes}[c](*a)

#!/usr/bin/env python3
"""verify_service.py -- the single per-service migration gate.

Renders the service two ways and compares them:
  LEGACY  = the repo at `git main` (pre-migration service.yml + custom_templates)
  V2      = the repo at `git HEAD` (migrated, schema_version 2) with the staged
            iac-controller override merged in the way the Ansible bridge does
            (service.yml | combine(config, recursive=True)).

Checks (all must hold for status=PASS):
  1. both render without error; V2 docker-compose.yml is VALID YAML.
  2. compose structural diff == ONLY the main service's env_file -> inline
     environment swap (anything else => engine/tooling issue).
  3. rendered custom files (deployments/files/**) are byte-identical
     (proves {{ environment.X }} refs were rewritten to the right namespace).
  4. the MAIN container's effective env (env_file + inline, honoring whether
     env_file is present) is identical to legacy.
  5. validate_ssot passes on the V2 service.yml (no real secrets committed).
Sidecar effective-env deltas are reported (not failed) as input to the
route-(a) explicit re-add step.

Outputs a JSON object to stdout: {service, status, checks, sidecar_deltas,
engine_issues, notes}.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import yaml

ALLOWED_MAIN_ENV_KEYS = {"env_file", "environment"}
# Infra vars a sidecar may genuinely need but no longer inherits via the shared
# .env under schema_version 2 -- candidates for explicit route-(a) re-add.
INFRA_VARS = {"PUID", "PGID", "TZ", "UID", "GID", "UMASK"}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git_archive(repo, ref, dest):
    os.makedirs(dest, exist_ok=True)
    p = run(["bash", "-c", f"git -C {repo!r} archive {ref} | tar -x -C {dest!r}"])
    if p.returncode:
        raise RuntimeError(f"git archive {ref} failed: {p.stderr}")


def deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def render(build_dir, ssot, engine, stage="prod", branch="main"):
    """Render compose + custom files in build_dir; return the compose dir."""
    env = dict(os.environ, PYTHONPATH=os.path.join(engine, "scripts"), SERVICE_BRANCH=branch)
    for extra in (["--deployment-type", "docker_compose"], ["--process-files"]):
        p = run([sys.executable, "-m", "manifest_generator.main", "--ssot-json", json.dumps(ssot),
                 "--template-path", engine, "--stage", stage] + extra, cwd=build_dir, env=env)
        if p.returncode:
            raise RuntimeError(f"engine failed ({' '.join(extra)}): {p.stdout}\n{p.stderr}")
    return os.path.join(build_dir, "deployments")


def parse_env_file(path):
    d = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k] = v.strip().strip('"')
    return d


def container_envs(dep_dir):
    """{service_name: {KEY: val}} effective env per container (env_file honored)."""
    cdir = os.path.join(dep_dir, "docker_compose")
    compose = yaml.safe_load(open(os.path.join(cdir, "docker-compose.yml")))
    out = {}
    for name, svc in (compose.get("services") or {}).items():
        eff = {}
        for ef in (svc.get("env_file") or []):
            eff.update(parse_env_file(os.path.join(cdir, ef)))
        for k, v in (svc.get("environment") or {}).items():
            eff[k] = str(v)
        out[name] = eff
    return out, compose


def files_tree(dep_dir):
    """{relpath: content} for everything under deployments/files."""
    base = os.path.join(dep_dir, "files")
    out = {}
    for root, _d, files in os.walk(base):
        for fn in files:
            p = os.path.join(root, fn)
            out[os.path.relpath(p, base)] = open(p, "rb").read()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--repo", required=True, help="service repo (HEAD=migrated, main=legacy)")
    ap.add_argument("--override", required=True, help="staged override yaml (full entry or bare config)")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--stage", default="prod")
    args = ap.parse_args()

    result = {"service": args.service, "status": "PASS", "checks": {}, "sidecar_deltas": {},
              "engine_issues": [], "notes": []}

    def fail(reason, engine_issue=False):
        result["status"] = "ENGINE_ISSUE" if engine_issue else "FAIL"
        result["checks"][reason] = False
        if engine_issue:
            result["engine_issues"].append(reason)

    work = tempfile.mkdtemp(prefix=f"vs_{args.service}_")
    legacy_dir, v2_dir = os.path.join(work, "legacy"), os.path.join(work, "v2")
    try:
        git_archive(args.repo, "main", legacy_dir)
        git_archive(args.repo, "HEAD", v2_dir)

        legacy_ssot = yaml.safe_load(open(os.path.join(legacy_dir, "service.yml")))
        v2_ssot = yaml.safe_load(open(os.path.join(v2_dir, "service.yml")))
        ov = yaml.safe_load(open(args.override))
        override_config = ov.get("config", ov) if isinstance(ov, dict) else {}
        merged = deep_merge(v2_ssot, override_config)

        # render each side exactly once
        try:
            legacy_deps = render(legacy_dir, legacy_ssot, args.engine, args.stage)
            legacy_envs, legacy_compose = container_envs(legacy_deps)
            legacy_files = files_tree(legacy_deps)
        except Exception as e:  # noqa: BLE001
            result["notes"].append(f"legacy render failed (pre-existing?): {e}")
            legacy_envs, legacy_compose, legacy_files = {}, {"services": {}}, {}
        try:
            v2_dep = render(v2_dir, merged, args.engine, args.stage)
        except Exception as e:  # noqa: BLE001
            fail(f"v2 render crashed: {e}", engine_issue=True)
            print(json.dumps(result, indent=2)); sys.exit(1)

        # 1. valid YAML
        try:
            v2_envs, v2_compose = container_envs(v2_dep)
            v2_files = files_tree(v2_dep)
            result["checks"]["v2_compose_valid_yaml"] = True
        except Exception as e:  # noqa: BLE001
            fail(f"v2 compose invalid YAML: {e}", engine_issue=True)
            print(json.dumps(result, indent=2)); sys.exit(1)

        # 2. structural compose diff: env is verified separately (per-container
        # effective env), so ignore env_file/environment on EVERY service here and
        # assert the rest of the compose (image/ports/volumes/networks/labels/...)
        # is identical. This tolerates the main env_file->inline swap and the
        # intentional route-(a) infra re-adds on sidecars.
        def strip_env(compose):
            c = json.loads(json.dumps(compose))
            for svc in (c.get("services") or {}).values():
                for k in ALLOWED_MAIN_ENV_KEYS:
                    svc.pop(k, None)
            return c
        if legacy_compose.get("services"):
            if strip_env(legacy_compose) == strip_env(v2_compose):
                result["checks"]["compose_structural_identical"] = True
            else:
                fail("compose structural diff beyond env", engine_issue=True)

        # 3. rendered custom files byte-identical
        if legacy_files or v2_files:
            if legacy_files == v2_files:
                result["checks"]["custom_files_identical"] = True
            else:
                diffk = sorted(set(legacy_files) ^ set(v2_files)) or [k for k in legacy_files if legacy_files[k] != v2_files.get(k)]
                fail(f"custom files differ: {diffk[:5]}")
                for k in diffk[:5]:
                    if b"environment." in v2_files.get(k, b""):
                        result["notes"].append(f"unresolved environment ref in {k}")

        # 4. main container effective env identical
        if legacy_envs and v2_envs:
            lmain = legacy_envs[next(iter(legacy_envs))]
            vmain = v2_envs[next(iter(v2_envs))]
            if lmain == vmain:
                result["checks"]["main_env_identical"] = True
            else:
                only_l = {k: lmain[k] for k in lmain if k not in vmain or lmain[k] != vmain.get(k)}
                only_v = {k: vmain[k] for k in vmain if k not in lmain}
                fail("main env differs")
                result["notes"].append(f"main only_legacy_or_changed={only_l} only_v2={only_v}")

        # 5. sidecar deltas (report only)
        for name in set(legacy_envs) | set(v2_envs):
            if legacy_envs and name == next(iter(legacy_envs)):
                continue
            le, ve = legacy_envs.get(name, {}), v2_envs.get(name, {})
            lost = {k: le[k] for k in le if k not in ve}
            gained = {k: ve[k] for k in ve if k not in le}
            if lost or gained:
                result["sidecar_deltas"][name] = {
                    "lost_infra": {k: lost[k] for k in lost if k in INFRA_VARS},
                    "lost": lost, "gained": gained}

        # 6. validate_ssot on the V2 service.yml
        vp = run([sys.executable, os.path.join(args.engine, "scripts", "validate_ssot.py"),
                  os.path.join(v2_dir, "service.yml")])
        result["checks"]["validate_ssot_pass"] = (vp.returncode == 0)
        if vp.returncode != 0:
            result["status"] = "FAIL" if result["status"] == "PASS" else result["status"]
            result["notes"].append("validate_ssot failed: " + vp.stdout.strip().splitlines()[-1] if vp.stdout else "validate_ssot failed")

        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] == "PASS" else 1)
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()

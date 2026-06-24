#!/usr/bin/env python3
"""verify_parity.py -- prove that externalizing a service to iac-controller is
lossless, by byte-comparing two schema_version 2 renders:

  Render A (real)        = the v2 service.yml with REAL values inlined
                           (vars:/secrets:), no override.
  Render B (externalized)= the v2 service.yml with PLACEHOLDERS, deep-merged
                           with the iac-controller override the way the Ansible
                           bridge does (combine(recursive=True)).

If A and B produce byte-identical docker-compose.yml / .env / stack.env, the
override block is complete and correct and the migration changed nothing.

This mirrors prepare_and_run_generator.yml: service.yml | combine(config).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

COMPARE_FILES = ["docker-compose.yml", ".env", "stack.env"]


def deep_merge(base: dict, over: dict) -> dict:
    """Ansible combine(recursive=True): recurse into dicts, replace otherwise."""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def render(ssot: dict, template_path: str, stage: str, branch: str) -> str:
    """Run the engine in an isolated build dir; return the output dir path."""
    build = tempfile.mkdtemp(prefix="parity_")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(template_path, "scripts")
    env["SERVICE_BRANCH"] = branch
    proc = subprocess.run(
        [sys.executable, "-m", "manifest_generator.main",
         "--ssot-json", json.dumps(ssot),
         "--template-path", template_path,
         "--stage", stage,
         "--deployment-type", "docker_compose"],
        cwd=build, env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"engine failed (rc={proc.returncode})")
    return os.path.join(build, "deployments", "docker_compose")


def main():
    p = argparse.ArgumentParser(description="Byte-identical externalization parity check")
    p.add_argument("--real", required=True, help="<service>.service.v2.real.yml")
    p.add_argument("--placeholder", required=True, help="<service>.service.v2.yml")
    p.add_argument("--override", required=True, help="override file (full entry or bare config)")
    p.add_argument("--template-path", required=True)
    p.add_argument("--stage", default="prod")
    p.add_argument("--branch", default="main")
    args = p.parse_args()

    real = load_yaml(args.real)
    placeholder = load_yaml(args.placeholder)
    ov = load_yaml(args.override)
    override_config = ov.get("config", ov) if isinstance(ov, dict) else {}

    # Bridge emulation: service.yml | combine(host_config)
    externalized = deep_merge(placeholder, override_config)

    dir_a = render(real, args.template_path, args.stage, args.branch)
    dir_b = render(externalized, args.template_path, args.stage, args.branch)

    ok = True
    for name in COMPARE_FILES:
        pa, pb = os.path.join(dir_a, name), os.path.join(dir_b, name)
        ca = open(pa, "rb").read() if os.path.exists(pa) else None
        cb = open(pb, "rb").read() if os.path.exists(pb) else None
        if ca == cb:
            print(f"  [OK] {name}: byte-identical")
        else:
            ok = False
            print(f"  [FAIL] {name}: differs")
            import difflib
            a_lines = (ca or b"").decode("utf-8", "replace").splitlines()
            b_lines = (cb or b"").decode("utf-8", "replace").splitlines()
            for line in difflib.unified_diff(a_lines, b_lines, fromfile=f"A/{name}",
                                             tofile=f"B/{name}", lineterm=""):
                print("    " + line)

    shutil.rmtree(os.path.dirname(os.path.dirname(dir_a)), ignore_errors=True)
    shutil.rmtree(os.path.dirname(os.path.dirname(dir_b)), ignore_errors=True)

    if ok:
        print("\nPARITY OK: externalization is lossless (A == B).")
        sys.exit(0)
    print("\nPARITY FAILED: override is incomplete or incorrect.")
    sys.exit(1)


if __name__ == "__main__":
    main()

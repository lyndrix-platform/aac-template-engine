#!/bin/bash
# cutover_one.sh <service> — production cutover for ONE already-migrated service.
# Re-syncs the repo to origin/main (absorbing renovate bumps), re-migrates from
# current main, verifies 5/5, and ONLY THEN merges to main and pushes (which
# triggers the orchestrator single_service deploy). Aborts before pushing if
# verify is not PASS, or if the freshly-extracted override differs from what is
# already committed in iac-controller (which would mean the deploy != what we
# verified). Idempotent and safe to re-run.
set -uo pipefail
svc="$1"
APPS=/home/marvin/gitlab/iac-environment/aac-application-defenitions/applications-repository
ENGINE=/home/marvin/gitlab/iac-environment/aac-template-engine
CTRL=/home/marvin/gitlab/iac-environment/iac-controller
REPO="$APPS/$svc"
export STAGE="${STAGE:-/tmp/aac-overrides}"

[ -d "$REPO" ] || { echo "$svc: NO_REPO"; exit 1; }

# 1. re-sync main to origin
git -C "$REPO" fetch -q origin 2>/dev/null
git -C "$REPO" checkout -q -f main 2>/dev/null
git -C "$REPO" reset -q --hard origin/main 2>/dev/null

# 2. re-migrate from current main + verify
out=$(bash "$ENGINE/scripts/migration/migrate_one.sh" "$svc" 2>/dev/null)
st=$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin).get('status','ERR'))" 2>/dev/null || echo ERR)
if [ "$st" != "PASS" ]; then
  echo "$svc: SKIP verify=$st"; exit 2
fi

# 3. guard: freshly-staged override must equal what is committed in iac-controller main
ov=$(ls "$STAGE/$svc.override."*prod*.yml 2>/dev/null | head -1)
if [ -n "$ov" ]; then
  if ! python3 - "$svc" "$ov" "$CTRL" <<'PY'
import sys,yaml
svc,ovf,ctrl=sys.argv[1],sys.argv[2],sys.argv[3]
fresh=(yaml.safe_load(open(ovf)) or {}).get("config",{})
import subprocess
for h in ("sites/hetzner/stages/prod/hosts.yml","sites/onprem/stages/prod/hosts.yml"):
    try: raw=subprocess.run(["git","-C",ctrl,"show",f"origin/main:environments/{h}"],capture_output=True,text=True).stdout
    except Exception: continue
    doc=yaml.safe_load(raw) or {}
    for host in (doc.get("hosts") or {}).values():
        for s in (host.get("services") or []):
            if isinstance(s,dict) and s.get("name")==svc:
                sys.exit(0 if (s.get("config") or {})==fresh else 7)
sys.exit(0)  # no committed placement -> nothing to mismatch
PY
  then echo "$svc: SKIP override drifted vs iac-controller (re-apply needed)"; exit 3; fi
fi

# 3b. leak gate: every committed placement's merged config must be free of
# publishable placeholders (example.com / CHANGE_ME). Catches a service that is
# placed on a host but whose iac-controller override is missing/incomplete, which
# would otherwise deploy the publishable default (e.g. domain_name: example.com).
if ! python3 "$ENGINE/scripts/migration/check_placement_leaks.py" "$svc"; then
  echo "$svc: SKIP placeholder leaks in iac-controller (fix override before cutover)"; exit 5
fi

# 4. merge + push (prod cutover)
git -C "$REPO" checkout -q main
git -C "$REPO" merge -q --no-ff feat/single-config-state \
  -m "Merge: migrate $svc to schema_version 2 (publishable, secrets externalized)" 2>/dev/null
if git -C "$REPO" push -q origin main 2>"/tmp/$svc.push.err"; then
  echo "$svc: PUSHED $(git -C "$REPO" rev-parse --short main)"
else
  echo "$svc: PUSH_FAILED $(tail -1 "/tmp/$svc.push.err")"; exit 4
fi

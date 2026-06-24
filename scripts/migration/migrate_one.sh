#!/bin/bash
# migrate_one.sh <service-name>
# Mechanically migrate one service to schema_version 2 and verify it.
# Re-runnable: recreates the feature branch from main each run.
# Emits the verify_service.py JSON (or a {status:FAIL/NEEDS_REVIEW} JSON) on stdout.
set -uo pipefail
svc="$1"
ENGINE=/home/marvin/gitlab/iac-environment/aac-template-engine
APPS=/home/marvin/gitlab/iac-environment/aac-application-defenitions/applications-repository
CTRL=/home/marvin/gitlab/iac-environment/iac-controller/environments
STAGE="${STAGE:-/tmp/aac-overrides}"
REPO="$APPS/$svc"
export PYTHONPATH="$ENGINE/scripts"
mkdir -p "$STAGE"

emit_fail() { echo "{\"service\":\"$svc\",\"status\":\"$1\",\"stage\":\"$2\",\"error\":\"${3//\"/ }\"}"; }

[ -d "$REPO" ] || { emit_fail FAIL setup "repo not found"; exit 1; }

SRC=$(mktemp -d); ART=$(mktemp -d)
trap 'rm -rf "$SRC" "$ART"' EXIT

# 1. extract from a clean main checkout (legacy service.yml + custom_templates)
git -C "$REPO" archive main 2>/dev/null | tar -x -C "$SRC" || { emit_fail FAIL archive "git archive main failed"; exit 1; }
if ! python "$ENGINE/scripts/migration/extract_overrides.py" \
      --service-yml "$SRC/service.yml" --name "$svc" --controller-root "$CTRL" --out-dir "$ART" >"/tmp/$svc.extract.log" 2>&1; then
  emit_fail FAIL extract "$(tail -1 "/tmp/$svc.extract.log")"; exit 1
fi

# 2. (re)create the feature branch from main
git -C "$REPO" checkout -q -f main 2>/dev/null || { emit_fail FAIL checkout "cannot checkout main"; exit 1; }
git -C "$REPO" branch -D feat/single-config-state >/dev/null 2>&1
git -C "$REPO" checkout -q -b feat/single-config-state || { emit_fail FAIL branch "cannot branch"; exit 1; }

# 3. apply v2 service.yml + rewritten custom templates
cp "$ART/$svc.service.v2.yml" "$REPO/service.yml"
(cd "$ART" && find custom_templates -type f 2>/dev/null) | while read -r f; do
  mkdir -p "$REPO/$(dirname "$f")"; cp "$ART/$f" "$REPO/$f"
done

# 4. stage override block(s)
rm -f "$STAGE/$svc.override."*.yml
cp "$ART"/"$svc".override.*.yml "$STAGE/" 2>/dev/null

# 5. commit
git -C "$REPO" add -A
git -C "$REPO" commit -q -m "feat: migrate to schema_version 2 single config state (publishable)" 2>/dev/null

# 6. verify (prefer a prod placement override)
ov=$(ls "$STAGE/$svc.override."*prod*.yml 2>/dev/null | head -1)
[ -z "$ov" ] && ov=$(ls "$STAGE/$svc.override"*.yml 2>/dev/null | head -1)
[ -z "$ov" ] && { echo "{\"service\":\"$svc\",\"status\":\"NEEDS_REVIEW\",\"note\":\"no override produced\"}"; exit 0; }

python "$ENGINE/scripts/migration/verify_service.py" \
  --service "$svc" --repo "$REPO" --override "$ov" --engine "$ENGINE" --stage prod 2>"/tmp/$svc.verify.err" \
  || true

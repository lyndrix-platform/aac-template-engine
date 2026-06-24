# Per-service migration runbook (schema_version 2)

You migrate **one** service `aac-X` to schema_version 2 and verify it. Work only on that
service's repo. Do **not** touch `iac-controller` or the engine. Return a structured JSON result.

## Paths
- Engine: `ENGINE=/home/marvin/gitlab/iac-environment/aac-template-engine` (branch `feat/single-config-state`)
- Service repo: `REPO=/home/marvin/gitlab/iac-environment/aac-application-defenitions/applications-repository/aac-X`
- Controller env root: `CTRL=/home/marvin/gitlab/iac-environment/iac-controller/environments`
- Staging dir (shared): `STAGE=<scratchpad>/overrides` (create if missing)
- `export PYTHONPATH="$ENGINE/scripts"`

## Steps

1. **Extract** from the legacy SSoT (NOT a migrated file):
   ```
   git -C "$REPO" show main:service.yml > /tmp/aac-X.legacy.yml
   python "$ENGINE/scripts/migration/extract_overrides.py" \
     --service-yml "$REPO/service.yml" --controller-root "$CTRL" --out-dir /tmp/aac-X-art
   ```
   (Run against `$REPO/service.yml` while the repo is still on `main`; the extractor refuses an
   already-v2 file.) Artifacts: `aac-X.service.v2.yml`, `aac-X.service.v2.real.yml`,
   `aac-X.override.<site>.<stage>.<host>.yml` (one per placement), and rewritten
   `custom_templates/**/*.j2` (only files whose `{{ environment.X }}` refs changed).

2. **Apply to the service repo**:
   ```
   git -C "$REPO" checkout -b feat/single-config-state   # or reuse if it exists
   cp /tmp/aac-X-art/aac-X.service.v2.yml "$REPO/service.yml"
   # copy any rewritten custom templates over their originals:
   (cd /tmp/aac-X-art && find custom_templates -type f 2>/dev/null) | while read f; do cp "/tmp/aac-X-art/$f" "$REPO/$f"; done
   ```

3. **Stage the override(s)** (do NOT edit iac-controller):
   ```
   mkdir -p "$STAGE"; cp /tmp/aac-X-art/aac-X.override.*.yml "$STAGE/"
   ```
   Pick the override matching the service's real stage (usually `*.prod.*`) for verification.

4. **Commit** the service repo (then verify against HEAD):
   ```
   git -C "$REPO" add -A && git -C "$REPO" commit -m "feat: migrate to schema_version 2 single config state (publishable)"
   ```

5. **Verify**:
   ```
   python "$ENGINE/scripts/migration/verify_service.py" --service aac-X --repo "$REPO" \
     --override "$STAGE/aac-X.override.<site>.prod.<host>.yml" --engine "$ENGINE" --stage prod
   ```
   PASS requires: `v2_compose_valid_yaml`, `compose_structural_identical`, `main_env_identical`,
   `validate_ssot_pass` all true, and `custom_files_identical` true when the service has custom files.

6. **Route (a) sidecar re-add** — inspect `sidecar_deltas[*].lost_infra` in the verify output. For each
   sidecar, decide whether it genuinely needs the lost infra vars and re-add ONLY those explicitly to
   that sidecar's own env block in `service.yml`, referencing the central state, e.g.:
   ```yaml
   dependencies:
     <dep>:
       overrides:        # (or directly under the dep if it has no import)
         environment:
           TZ: "{{ vars.TZ }}"
           PUID: "{{ vars.PUID }}"
           PGID: "{{ vars.PGID }}"
   ```
   Heuristic: **linuxserver/* images** → re-add `PUID`/`PGID`/`TZ`. **db images** (postgres/mariadb/
   mysql/redis) → re-add `TZ` only (they run as their own uid). Ignore non-infra "lost" vars (those are
   main-app config the sidecar never needed). Skip re-add for `network_mode: host` sidecars that already
   declare their own `TZ`. After editing, `git commit --amend` and re-run verify_service; document each
   decision in the result.

7. **Return** this JSON (and nothing else as the final message):
   ```json
   {"service":"aac-X","status":"DONE|ENGINE_ISSUE|NEEDS_REVIEW",
    "checks":{...from verify_service...},
    "sidecar_decisions":[{"sidecar":"...","readded":["TZ"],"reason":"..."}],
    "placements":["hetzner/prod/docker-atlas", ...],
    "engine_issues":[{"symptom":"...","sample":"...","suspected_cause":"..."}],
    "notes":["multi-stage: also placed in dev/test (CHANGE_ME)","profile-only","no-placement"]}
   ```

## Status meanings
- **DONE** — verify_service PASS after any sidecar re-adds; repo committed; override(s) staged.
- **ENGINE_ISSUE** — verify_service reported `engine_issues` (invalid YAML, render crash, or compose
  structural diff beyond the main env swap). Leave the committed branch as-is; do NOT hack the template.
  Record the symptom + a minimal sample; these are fixed centrally at the end, then re-verified.
- **NEEDS_REVIEW** — a non-engine ambiguity you could not safely resolve (e.g. multi-stage secrets that
  differ per stage, a sidecar whose infra needs are unclear). Describe it in `notes`.

## Hard rules
- Never write real secret values into `service.yml`; they belong only in the staged override.
- Never edit `iac-controller` or files under `$ENGINE`.
- Never push.
- If `validate_ssot` fails on your v2 `service.yml`, you left a real secret in it — fix the
  classification by moving it to the override, don't suppress the check.

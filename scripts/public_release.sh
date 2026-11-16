#!/usr/bin/env bash
# Public release sync: AaC service repo (GitLab, internal) -> github.com/<org>/<repo> (public).
#
# Flow: guards -> allowlisted tree from the release tag -> sanitize -> render docker-compose with
# the template engine (placeholders only) -> secret gates (gitleaks docker + grep) -> orphan
# `public` branch (one commit "release X.Y.Z") -> GitHub (main, tags X.Y.Z + vX.Y.Z, release).
# Internal history / internal tags NEVER leave GitLab: a fresh git repo is built from the
# public tree only and only that repo is pushed to GitHub.
#
# Modes: PR_MODE=publish (CI)  |  PR_MODE=simulate (local, no network, no push)
# Config (env): see defaults below. PUBLIC_INTERNAL_DOMAINS (required) lists internal domains. Secrets are read from env only and never printed.
set -euo pipefail

PR_MODE="${PR_MODE:-publish}"
PR_SRC="${PR_SRC:-$PWD}"
PR_TAG="${PR_TAG:-${CI_COMMIT_TAG:-}}"
PR_REF="${PR_REF:-$PR_TAG}"                       # git ref to export (simulate: HEAD)
PR_REPO="${PR_REPO:-${CI_PROJECT_NAME:-$(basename "$PR_SRC")}}"
PR_ORG="${PUBLIC_GH_ORG:-app-as-code}"
PR_OUT="${PR_OUT:-$(mktemp -d)}"
PR_ENGINE_PATH="${PR_ENGINE_PATH:-${TEMPLATE_PATH:-/opt/aac-template-engine}}"
PR_PYTHON="${PR_PYTHON:-python3}"
PR_HELPER="${PR_HELPER:-$(dirname "$(readlink -f "$0")")/public_release_prepare.py}"
PR_INCLUDE="${PUBLIC_INCLUDE_PATHS:-service.yml README.md LICENSE LICENSE.md CHANGELOG.md custom_templates}"
PR_STAGE="${PUBLIC_GEN_STAGE:-prod}"
GITLEAKS_IMAGE="${GITLEAKS_IMAGE:-zricethezav/gitleaks:v8.18.4}"
GH_TOKEN_VAR="${APP_AS_CODE_GITHUB_TOKEN:-}"
GL_TOKEN="${PUBLIC_GITLAB_PUSH_TOKEN:-${CI_GITLAB_TOKEN_GLOBAL_FESER:-${CI_JOB_TOKEN:-}}}"

# Hard-coded denylist: never published, independent of any variable.
DENYLIST=("aac-hermes-agent")

log()  { echo "[public-release] $*"; }
die()  { echo "[public-release] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. guards
for d in "${DENYLIST[@]}"; do
  [ "$PR_REPO" = "$d" ] && { log "SKIP: $PR_REPO is on the hard denylist."; exit 0; }
done
[ "${PUBLIC_RELEASE:-true}" = "false" ] && { log "SKIP: PUBLIC_RELEASE=false (opt-out)."; exit 0; }
[[ "$PR_TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { log "SKIP: '$PR_TAG' is not an X.Y.Z tag."; exit 0; }
[[ "$PR_REPO" =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid repo name"
[ "$PR_MODE" = "simulate" ] || [ "$PR_MODE" = "publish" ] || die "PR_MODE must be publish|simulate"
if [ "$PR_MODE" = "publish" ]; then
  [ -n "$GH_TOKEN_VAR" ] || die "APP_AS_CODE_GITHUB_TOKEN is not set (group-level, masked+protected)."
  [ -n "$GL_TOKEN" ] || die "no GitLab push token (CI_GITLAB_TOKEN_GLOBAL_FESER / PUBLIC_GITLAB_PUSH_TOKEN)."
  # tag must be on the default branch (main)
  DEF="${CI_DEFAULT_BRANCH:-main}"
  git -C "$PR_SRC" fetch --quiet origin "+refs/heads/$DEF:refs/remotes/origin/$DEF" || die "cannot fetch $DEF"
  git -C "$PR_SRC" merge-base --is-ancestor "$PR_REF" "origin/$DEF" || { log "SKIP: tag $PR_TAG is not on $DEF."; exit 0; }
fi
# Internal domains come from CI (never hard-coded here): space/comma separated, e.g. "internal.example.org example.org".
# Used for BOTH the replacement -> example.com and the grep gate. Empty => fail closed.
DOMS=()
for d in $(echo "${PUBLIC_INTERNAL_DOMAINS:-}" | tr ',' ' '); do
  [[ "$d" =~ ^[A-Za-z0-9.-]+$ ]] || die "invalid entry in PUBLIC_INTERNAL_DOMAINS"
  DOMS+=("${d//./\\.}")
done
[ "${#DOMS[@]}" -gt 0 ] || die "PUBLIC_INTERNAL_DOMAINS is empty - refusing to publish without the internal domain list (fail closed)"
DOM_RE="$(IFS='|'; echo "${DOMS[*]}")"
git -C "$PR_SRC" rev-parse --verify -q "$PR_REF^{commit}" >/dev/null || die "ref $PR_REF not found"

TREE="$PR_OUT/tree"; REPORT="$PR_OUT/report"; PUBGIT="$PR_OUT/.public-git"; SRCX="$PR_OUT/.src-export"
rm -rf "$TREE" "$REPORT" "$PUBGIT" "$SRCX"; mkdir -p "$TREE" "$REPORT" "$SRCX"

# ---------------------------------------------------------------- 2. allowlisted tree
paths=()
for p in $PR_INCLUDE; do
  git -C "$PR_SRC" cat-file -e "$PR_REF:$p" 2>/dev/null && paths+=("$p")
done
[ "${#paths[@]}" -gt 0 ] || die "allowlist produced an empty tree"
git -C "$PR_SRC" archive "$PR_REF" "${paths[@]}" | tar -x -C "$TREE"
[ -f "$TREE/service.yml" ] || die "service.yml missing at $PR_REF"
git -C "$PR_SRC" archive "$PR_REF" | tar -x -C "$SRCX"       # only for the diff report
log "allowlisted: ${paths[*]}"

# ---------------------------------------------------------------- 3. sanitize + render
"$PR_PYTHON" "$PR_HELPER" sanitize "$TREE/service.yml"
rm -rf "$TREE/deployments"
( cd "$TREE" && PYTHONPATH="$PR_ENGINE_PATH/scripts:${PYTHONPATH:-}" SERVICE_BRANCH=main "$PR_PYTHON" -m manifest_generator.main \
    --ssot-json service.yml --template-path "$PR_ENGINE_PATH" --deployment-type docker_compose --stage "$PR_STAGE" ) \
    > "$REPORT/render.log" 2>&1 || { tail -20 "$REPORT/render.log"; die "render failed"; }
rm -f "$TREE/deployments/ansible_context.json"
# neutral placeholders for anything internal that slipped into the rendered files
find "$TREE/deployments" -type f -print0 | xargs -0 sed -i -E \
  -e "s/[A-Za-z0-9.-]*($DOM_RE)/example.com/g" \
  -e 's/(^|[^0-9.])10\.[0-9]+\.[0-9]+\.[0-9]+/\1192.0.2.1/g' \
  -e 's/ - Ci Validation Host"/"/'
# keep the compose as rendered; only secrets -> ${KEY:?} and one .env.example
"$PR_PYTHON" "$PR_HELPER" finalize "$TREE"
COMPOSE="$TREE/deployments/docker_compose/docker-compose.yml"
[ -s "$COMPOSE" ] || die "no docker-compose.yml rendered"
DC="$TREE/deployments/docker_compose"
[ -f "$DC/.env.example" ] && cp "$DC/.env.example" "$DC/.env"      # temp: sidecars use env_file: .env (removed again below)
docker compose -f "$COMPOSE" config -q || die "docker compose config invalid"
rm -f "$DC/.env"
log "compose valid"
"$PR_PYTHON" "$PR_HELPER" readme "$TREE" "$TREE/service.yml"

# ---------------------------------------------------------------- 4. secret gates (fail => nothing pushed)
log "gate 1/2: gitleaks ($GITLEAKS_IMAGE)"
set +e
tar -C "$TREE" -cf - . | docker run -i --rm --entrypoint sh "$GITLEAKS_IMAGE" -c \
  'mkdir /scan && tar -x -C /scan && gitleaks detect --no-git --source /scan --redact --no-banner' \
  > "$REPORT/gitleaks.txt" 2>&1
GL_RC=$?
set -e
tail -5 "$REPORT/gitleaks.txt" | sed 's/^/    /'
[ "$GL_RC" -eq 0 ] || die "gitleaks found leaks (rc=$GL_RC) - see report; nothing pushed"

log "gate 2/2: grep"
PATTERNS=(-e "$DOM_RE" -e '(^|[^0-9.])10\.[0-9]+\.[0-9]+\.[0-9]+' -e 'glpat-' -e 'ghp_' -e 'hvs\.' -e 'lyk__' -e 'PRIVATE KEY')
if grep -rInE "${PATTERNS[@]}" "$TREE" | cut -d: -f1,2 > "$REPORT/grep-gate.txt" && [ -s "$REPORT/grep-gate.txt" ]; then
  sed "s#$TREE/##" "$REPORT/grep-gate.txt" | head -20 | sed 's/^/    hit: /'
  die "grep gate hit (file:line above, content withheld); nothing pushed"
fi
log "gates passed"

( cd "$TREE" && find . -type f | sort ) > "$REPORT/filelist.txt"
diff -ruN --exclude=.git "$SRCX" "$TREE" > "$REPORT/source-vs-public.diff" || true

# ---------------------------------------------------------------- 5. local public branch (orphan, fresh history)
askpass() { # $1 = env var name holding the secret; prints path of a helper (secret stays in env)
  local f; f="$(mktemp "$PR_OUT/.askpass.XXXXXX")"
  printf '#!/bin/sh\ncase "$1" in Username*) echo x-access-token;; *) printf %%s "$%s";; esac\n' "$1" > "$f"
  chmod 700 "$f"; echo "$f"
}
trap 'rm -f "$PR_OUT"/.askpass.* 2>/dev/null || true' EXIT
GL_URL="https://${CI_SERVER_HOST:-gitlab.invalid}/${CI_PROJECT_PATH:-x/$PR_REPO}.git"
GH_URL="https://github.com/${PR_ORG}/${PR_REPO}.git"
export PR_GL_SECRET="$GL_TOKEN" PR_GH_SECRET="$GH_TOKEN_VAR"
gitx() { git -C "$PUBGIT" -c user.name="AaC Public Release" -c user.email="noreply@example.com" -c commit.gpgsign=false "$@"; }
push_to() { # $1=askpass-var $2=url, rest=refspecs
  local ap; ap="$(askpass "$1")"; local url="$2"; shift 2
  local out rc=0
  out="$(GIT_ASKPASS="$ap" GIT_TERMINAL_PROMPT=0 gitx -c credential.helper= push --no-tags "$url" "$@" 2>&1)" || rc=$?
  printf '%s\n' "$out" | grep -vE '^remote: *$' | tail -3 | sed 's/^/    /'
  return "$rc"
}

git init -q -b public "$PUBGIT"
PREV=""
if [ "$PR_MODE" = "publish" ]; then
  if GIT_ASKPASS="$(askpass PR_GL_SECRET)" GIT_TERMINAL_PROMPT=0 gitx -c credential.helper= fetch -q --no-tags "$GL_URL" "+refs/heads/public:refs/remotes/gl/public" 2>/dev/null; then
    PREV="$(gitx rev-parse refs/remotes/gl/public)"
  fi
fi
SUBJECT="release $PR_TAG"
RELEASE_SHA=""
if [ -n "$PREV" ]; then
  RELEASE_SHA="$(gitx log --format='%H %s' "$PREV" | awk -v s="$SUBJECT" '$0 ~ " "s"$" {print $1; exit}')"
fi
if [ -n "$RELEASE_SHA" ]; then
  log "release commit for $PR_TAG already on public: ${RELEASE_SHA:0:8} (idempotent re-run)"
  gitx checkout -q -f "$RELEASE_SHA" 2>/dev/null || true
else
  if [ -n "$PREV" ]; then gitx checkout -q -B public "$PREV"; else gitx checkout -q --orphan public 2>/dev/null || true; fi
  gitx rm -rfq --ignore-unmatch . >/dev/null 2>&1 || true
  find "$PUBGIT" -mindepth 1 -maxdepth 1 -not -name .git -exec rm -rf {} +
  cp -a "$TREE"/. "$PUBGIT"/
  gitx add -A
  gitx commit -q --allow-empty -m "$SUBJECT"
  RELEASE_SHA="$(gitx rev-parse HEAD)"
  log "created commit ${RELEASE_SHA:0:8} \"$SUBJECT\" (parent: ${PREV:0:8})"
  # history must contain only public commits
  [ "$(gitx rev-list --count "$RELEASE_SHA")" -eq "$(gitx log --format=%s "$RELEASE_SHA" | grep -c '^release ')" ] || die "unexpected non-release commit in public history"
  if [ "$PR_MODE" = "publish" ]; then
    push_to PR_GL_SECRET "$GL_URL" "$RELEASE_SHA:refs/heads/public" || die "push to GitLab public failed (branch protection / token rights?)"
  fi
fi
echo "$RELEASE_SHA" > "$REPORT/public-commit.txt"

if [ "$PR_MODE" = "simulate" ]; then
  log "SIMULATE done: tree=$TREE report=$REPORT public commit=${RELEASE_SHA:0:8} - nothing pushed."
  exit 0
fi

# ---------------------------------------------------------------- 6. GitHub
gh_api() { # METHOD PATH [json-body]; echoes body, last line = HTTP code
  local m="$1" p="$2" b="${3:-}"
  local args=(-sS -X "$m" -w $'\n%{http_code}' -K - -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "https://api.github.com$p")
  [ -n "$b" ] && args+=(-d "$b")
  printf 'header = "Authorization: Bearer %s"\n' "$GH_TOKEN_VAR" | curl "${args[@]}"
}
code_of() { tail -n1; }
body_of() { sed '$d'; }

R="$(gh_api GET "/repos/$PR_ORG/$PR_REPO")"
case "$(echo "$R" | code_of)" in
  200) log "GitHub repo exists";;
  404) DESC="$("$PR_PYTHON" -c 'import yaml,sys;d=yaml.safe_load(open(sys.argv[1]));print((d.get("service",{}).get("description") or "")[:300].replace("\n"," "))' "$TREE/service.yml")"
       echo "$DESC" | grep -qiE "$DOM_RE|glpat-|ghp_|hvs\.|lyk__|(^|[^0-9.])10\.[0-9]+\." && DESC="AaC service definition and ready-to-use docker compose deployment"
       BODY="$(jq -nc --arg n "$PR_REPO" --arg d "$DESC" '{name:$n,description:$d,private:false,has_issues:true,has_wiki:false}')"
       C="$(gh_api POST "/orgs/$PR_ORG/repos" "$BODY")"
       [ "$(echo "$C" | code_of)" = "201" ] || die "repo create failed (HTTP $(echo "$C" | code_of)); token needs Administration:write on org"
       log "GitHub repo created (public)";;
  *) die "GitHub repo lookup failed (HTTP $(echo "$R" | code_of))";;
esac

remote_ref() { GIT_ASKPASS="$(askpass PR_GH_SECRET)" GIT_TERMINAL_PROMPT=0 gitx -c credential.helper= ls-remote "$GH_URL" "$1" | awk '{print $1}'; }

# main
RM="$(remote_ref refs/heads/main)"
if [ "$RM" = "$RELEASE_SHA" ]; then
  log "GitHub main already at ${RELEASE_SHA:0:8}"
else
  FORCE=()
  [ "${PUBLIC_FORCE_PUSH:-false}" = "true" ] && FORCE=(--force)
  push_to PR_GH_SECRET "$GH_URL" "${FORCE[@]}" "$RELEASE_SHA:refs/heads/main" \
    || die "push to GitHub main rejected (pre-existing unrelated history?). Set PUBLIC_FORCE_PUSH=true once to replace it with the clean public history."
fi
# tags: X.Y.Z and vX.Y.Z on the same commit, never moved
for t in "$PR_TAG" "v$PR_TAG"; do
  RT="$(remote_ref "refs/tags/$t")"
  if [ -z "$RT" ]; then
    push_to PR_GH_SECRET "$GH_URL" "$RELEASE_SHA:refs/tags/$t" || die "tag push $t failed"
  elif [ "$RT" != "$RELEASE_SHA" ]; then
    die "GitHub tag $t exists on a different commit (${RT:0:8}); refusing to move it"
  else
    log "tag $t already present"
  fi
done

# release (notes: CHANGELOG section, else commit subjects since the previous release tag)
R="$(gh_api GET "/repos/$PR_ORG/$PR_REPO/releases/tags/$PR_TAG")"
if [ "$(echo "$R" | code_of)" = "200" ]; then
  log "GitHub release $PR_TAG already exists - nothing to do"
else
  NOTES="$("$PR_PYTHON" "$PR_HELPER" notes "$TREE/CHANGELOG.md" "$PR_TAG" 2>/dev/null || true)"
  if [ -z "$NOTES" ]; then
    PT="$(git -C "$PR_SRC" tag --list '[0-9]*.[0-9]*.[0-9]*' --merged "$PR_REF" --sort=-v:refname | grep -vx "$PR_TAG" | head -1 || true)"
    RANGE="${PT:+$PT..}$PR_REF"
    NOTES="$(git -C "$PR_SRC" log --no-merges --format='- %s' "$RANGE" | head -50)"
  fi
  # notes come from internal history: apply the same grep gate, else fall back to a neutral text
  if [ -z "$NOTES" ] || printf '%s' "$NOTES" | grep -qE "$DOM_RE|(^|[^0-9.])10\.[0-9]+\.[0-9]+\.[0-9]+|glpat-|ghp_|hvs\.|lyk__|PRIVATE KEY"; then
    NOTES="Release $PR_TAG"
  fi
  BODY="$(jq -nc --arg t "$PR_TAG" --arg n "$NOTES" --arg c "$RELEASE_SHA" '{tag_name:$t,target_commitish:$c,name:$t,body:$n}')"
  C="$(gh_api POST "/repos/$PR_ORG/$PR_REPO/releases" "$BODY")"
  case "$(echo "$C" | code_of)" in 201) log "GitHub release $PR_TAG created";; 422) log "release already exists (422) - ok";; *) die "release create failed (HTTP $(echo "$C" | code_of))";; esac
fi
log "DONE $PR_REPO $PR_TAG -> https://github.com/$PR_ORG/$PR_REPO"

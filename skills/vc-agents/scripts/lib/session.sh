#!/usr/bin/env bash


spawn_session_base_name() {
  local root base
  root="$(spawn_repo_root)"
  base="$(basename "$root" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/^-*//; s/-*$//')"
  [[ -n "$base" ]] || base="vibecrafted"
  printf '%s\n' "$base"
}

spawn_operator_session_name_for_run_id() {
  local run_id="${1:-}"
  local base
  base="$(spawn_session_base_name)"
  if [[ -n "$run_id" ]]; then
    printf '%s-%s\n' "$base" "$run_id"
  else
    printf '%s\n' "$base"
  fi
}

spawn_skill_prefix() {
  local name="${1:-}"
  case "$name" in
    agents) printf 'agnt\n' ;; 
    decorate) printf 'deco\n' ;; 
    delegate) printf 'delg\n' ;; 
    dou) printf 'vdou\n' ;; 
    followup) printf 'fwup\n' ;; 
    hydrate) printf 'hydr\n' ;; 
    implement|prompt) printf 'impl\n' ;; 
    init) printf 'init\n' ;; 
    justdo) printf 'just\n' ;; 
    marbles) printf 'marb\n' ;; 
    partner) printf 'prtn\n' ;; 
    plan) printf 'plan\n' ;; 
    prune) printf 'prun\n' ;; 
    release) printf 'rels\n' ;; 
    research) printf 'rsch\n' ;; 
    review) printf 'rvew\n' ;; 
    scaffold) printf 'scaf\n' ;; 
    workflow) printf 'wflw\n' ;; 
    *) 
      if [[ -n "$name" ]]; then
        printf '%.4s\n' "$name"
      else
        printf 'impl\n'
      fi
      ;;
  esac
}

spawn_generate_run_id() {
  local prefix="${1:-impl}"
  printf '%s-%s\n' "$prefix" "$(date +%H%M%S)"
}

spawn_marbles_state_dir() {
  local run_id="$1"
  printf '%s/marbles/%s\n' "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}" "$run_id"
}

spawn_marbles_child_plan_path() {
  local store_dir="$1"
  local ancestor_plan="$2"
  local loop_nr="$3"
  local ancestor_slug
  ancestor_slug="$(spawn_slug_from_path "$ancestor_plan")"
  printf '%s/plans/marbles-%s_L%s.md\n' "$store_dir" "$ancestor_slug" "$loop_nr"
}

spawn_marbles_write_child_plan() {
  local ancestor_plan="$1"
  local child_plan="$2"

  mkdir -p "$(dirname "$child_plan")"
  cp "$ancestor_plan" "$child_plan"
  cat >> "$child_plan" <<'ROUND_CONTRACT'

---
## Worker Contract

### Hard Rule
- The worker must remain on the operator-assigned substrate.
- The worker is expected to maneuver intelligently within the assigned surface, inside the living tree, and around concurrent edits by others. That maneuverability is part of the craft.
- But `vc-marbles` does not permit escaping the assigned substrate.
- Do not switch branches.
- Do not create or move to a worktree.
- Do not relocate execution to another lane or clone.
- If the substrate is too poisoned to operate on, return control to the operator/runtime layer. Do not solve substrate invalidity by moving sideways.

## Exit Contract
- **COMMIT**: mandatory. One commit when done.
- **REPORT**: mandatory. Write to the report path given at the end of this prompt.
- **SCOPE**: do your work, commit, report, stop.
ROUND_CONTRACT
}

spawn_prepare_paths() {
  local agent="$1"
  local prompt_file="$2"
  local root="${3:-}"
  local mode="${4:-${VIBECRAFTED_SKILL_NAME:-}}"
  local skill_name="${VIBECRAFTED_SKILL_NAME:-$mode}"
  local lock_file=""
  local discovered_session=""
  local ambient_store_root="${VIBECRAFTED_STORE_ROOT:-${SPAWN_ROOT:-}}"

  if [[ -n "$root" ]]; then
    SPAWN_ROOT="$(spawn_abspath "$root")"
    [[ -d "$SPAWN_ROOT" ]] || spawn_die "Root directory not found: $SPAWN_ROOT"
  else
    SPAWN_ROOT="$(spawn_repo_root)"
  fi

  if [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
    discovered_session="$(spawn_effective_operator_session 2>/dev/null || true)"
    if [[ -n "$discovered_session" ]]; then
      export VIBECRAFTED_OPERATOR_SESSION="$discovered_session"
    fi
  fi

  SPAWN_PLAN="$(spawn_abspath "$prompt_file")"
  SPAWN_SLUG="$(spawn_slug_from_path "$prompt_file")"
  SPAWN_TS="$(spawn_timestamp)"
  SPAWN_AGENT="$agent"
  SPAWN_PROMPT_ID="${SPAWN_SLUG}_${SPAWN_TS%%_*}"
  SPAWN_SKILL_CODE="$(spawn_effective_skill_code 2>/dev/null || true)"
  if [[ -z "$SPAWN_SKILL_CODE" && -n "$skill_name" ]]; then
    SPAWN_SKILL_CODE="$(spawn_skill_prefix "$skill_name")"
  fi
  SPAWN_SKILL_NAME="$skill_name"
  SPAWN_LOOP_NR="${VIBECRAFTED_LOOP_NR:-0}"
  case "$SPAWN_LOOP_NR" in
    ''|*[!0-9]*) 
      SPAWN_LOOP_NR=0
      ;;
  esac
  SPAWN_RUN_ID="$(spawn_effective_run_id 2>/dev/null || true)"
  if [[ -n "$SPAWN_RUN_ID" ]]; then
    : 
  else
    SPAWN_RUN_ID="$(spawn_generate_run_id "${SPAWN_SKILL_CODE:-impl}")"
  fi
  lock_file="$(spawn_effective_run_lock 2>/dev/null || true)"
  if [[ -z "$lock_file" || ! -f "$lock_file" ]]; then
    lock_file="$VIBECRAFTED_HOME/locks/$(spawn_org_repo "$SPAWN_ROOT")/${SPAWN_RUN_ID}.lock"
  fi
  if [[ ! -f "$lock_file" ]]; then
    lock_file="$(spawn_create_run_lock "$SPAWN_RUN_ID" "$agent" "${skill_name:-${mode:-implement}}" "$SPAWN_ROOT")"
  fi
  SPAWN_RUN_LOCK="$lock_file"

  # Central store path (falls back to per-repo if no git remote)
  local store_base
  store_base="$(spawn_effective_store_dir "$SPAWN_ROOT" "$ambient_store_root")"

  SPAWN_PLAN_DIR="$store_base/plans"
  SPAWN_REPORT_DIR="$store_base/reports"
  SPAWN_TMP_DIR="$store_base/tmp"
  SPAWN_BASE="$SPAWN_REPORT_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}"
  SPAWN_REPORT="${SPAWN_BASE}.md"
  SPAWN_TRANSCRIPT="${SPAWN_BASE}.transcript.log"
  SPAWN_META="${SPAWN_BASE}.meta.json"
  SPAWN_LAUNCHER="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}_launch.sh"
  mkdir -p "$store_base/plans" "$SPAWN_REPORT_DIR" "$SPAWN_TMP_DIR"
  spawn_link_repo_artifacts "$store_base" "$SPAWN_ROOT"
  export SPAWN_ROOT SPAWN_PLAN SPAWN_SLUG SPAWN_TS SPAWN_AGENT SPAWN_PROMPT_ID SPAWN_RUN_ID SPAWN_RUN_LOCK SPAWN_SKILL_CODE SPAWN_SKILL_NAME SPAWN_LOOP_NR
  export SPAWN_PLAN_DIR SPAWN_REPORT_DIR SPAWN_TMP_DIR SPAWN_BASE SPAWN_REPORT SPAWN_TRANSCRIPT SPAWN_META SPAWN_LAUNCHER
}

spawn_scan_active() {
  local reports_dir="$1"
  local tmp_root="${TMPDIR:-/tmp}"
  local marker=""
  local recent_active=""

  tmp_root="${tmp_root%/}"
  marker="${tmp_root}/.vibecrafted-scan-marker"

  [[ -d "$reports_dir" ]] || {
    touch "$marker"
    return 0
  }

  if [[ -e "$marker" ]]; then
    recent_active="$(
      find "$reports_dir" -name '*.meta.json' -newer "$marker" 2>/dev/null | sort | while read -r f; do
        python3 - "$f" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
if payload.get("status") in ("launching", "running"):
    print(f"  {payload.get('run_id', '?'):10s} {payload.get('agent', '?'):8s} {payload.get('status', '?'):10s} {payload.get('mode', '?')}")
PY
      done
    )"
  else
    recent_active="$(
      find "$reports_dir" -name '*.meta.json' 2>/dev/null | sort | while read -r f; do
        python3 - "$f" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
if payload.get("status") in ("launching", "running"):
    print(f"  {payload.get('run_id', '?'):10s} {payload.get('agent', '?'):8s} {payload.get('status', '?'):10s} {payload.get('mode', '?')}")
PY
      done
    )"
  fi

  touch "$marker"
  [[ -n "$recent_active" ]] || return 0

  printf '\033[2mRecent active 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. runs:\n%s\033[0m\n' "$recent_active"
}

spawn_normalize_ambient_context

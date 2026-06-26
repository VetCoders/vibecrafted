#!/usr/bin/env bash

spawn_expected_run_lock_path() {
  local run_id="${1:-}"
  local root="${2:-$(spawn_repo_root)}"
  [[ -n "$run_id" ]] || return 1
  printf '%s/locks/%s/%s.lock\n' \
    "$VIBECRAFTED_HOME" \
    "$(spawn_org_repo "$root")" \
    "$run_id"
}

spawn_effective_run_lock() {
  spawn_normalize_ambient_context
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_RUN_LOCK:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_LOCK}"
}

spawn_create_run_lock() {
  local run_id="$1"
  local agent="$2"
  local skill="$3"
  local root="$4"
  local org_repo lock_dir lock_file

  org_repo="$(spawn_org_repo "$root")"
  lock_dir="$VIBECRAFTED_HOME/locks/$org_repo"
  mkdir -p "$lock_dir"
  lock_file="$lock_dir/${run_id}.lock"
  cat > "$lock_file" <<LOCK
run_id=$run_id
agent=$agent
skill=$skill
root=$root
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=running
LOCK
  printf '%s\n' "$lock_file"
}

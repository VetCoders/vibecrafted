#!/usr/bin/env bash

# Central artifact store: $HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/
# Override with VIBECRAFTED_HOME env var for custom location
# Falls back to <repo>/.vibecrafted/ if git remote unavailable
VIBECRAFTED_HOME="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"

spawn_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

spawn_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  local org_repo=""
  org_repo="$(spawn_org_repo "$root" 0)"
  if [[ -n "$org_repo" ]]; then
    local date_dir
    date_dir="$(date +%Y_%m%d)"
    printf '%s/artifacts/%s/%s\n' "$VIBECRAFTED_HOME" "$org_repo" "$date_dir"
  else
    # Fallback: per-repo
    printf '%s/.vibecrafted\n' "$root"
  fi
}

spawn_effective_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  if [[ -n "${VIBECRAFTED_STORE_DIR:-}" ]]; then
    spawn_abspath "$VIBECRAFTED_STORE_DIR"
    return 0
  fi
  spawn_store_dir "$root"
}

spawn_marbles_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  printf '%s/marbles\n' "$(spawn_store_dir "$root")"
}

spawn_abspath() {
  local path="$1"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$(cd "$(dirname "$path")" && pwd)" "$(basename "$path")"
  fi
}

spawn_slug_from_path() {
  local raw
  raw="$(basename "${1%.*}")"
  raw="$(printf '%s' "$raw" | tr ' ' '-' | tr -cs '[:alnum:]._-' '-')"
  raw="${raw#-}"
  raw="${raw%-}"
  [[ -n "$raw" ]] || raw="agent-task"
  # Truncate to max 60 chars to prevent filesystem-busting filenames.
  # Cut at a word boundary (dash or underscore) to keep slugs readable.
  if (( ${#raw} > 60 )); then
    raw="${raw:0:60}"
    # Trim trailing partial word
    raw="${raw%-}"
    [[ -n "$raw" ]] || raw="${1:0:60}"
  fi
  printf '%s\n' "$raw"
}

spawn_link_repo_artifacts() {
  local store_base="$1"
  local repo_root="$2"
  local repo_vibecrafted="$repo_root/.vibecrafted"

  [[ "$store_base" != "$repo_root/.vibecrafted" ]] || return 0

  mkdir -p "$repo_vibecrafted"
  ln -sfn "$store_base/plans" "$repo_vibecrafted/plans" 2>/dev/null || true
  ln -sfn "$store_base/reports" "$repo_vibecrafted/reports" 2>/dev/null || true
}

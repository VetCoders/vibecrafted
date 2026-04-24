# shellcheck shell=bash
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers (bash/zsh compatible)
# Source this from your $HOME/.bashrc or $HOME/.zshrc to get consistent wrapper commands
# for the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework installed under your local repository path.
# These are shell functions, not standalone binaries. Non-interactive callers
# should use an interactive shell so $HOME/.zshrc sources this file; fall back
# to `bash -ic` on bash-only systems.

_vetcoders_spawn_home() {
  local tool="$1"
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  local crafted_store="$crafted_home/skills/vc-agents"
  local current_store="$crafted_home/tools/vibecrafted-current/skills/vc-agents"
  local repo_root
  repo_root="${VIBECRAFTED_ROOT:-$(_vetcoders_repo_root)}"
  if [[ -d "$repo_root/skills/vc-agents" && -f "$repo_root/VERSION" && -f "$repo_root/scripts/vibecrafted" ]]; then
    printf '%s/skills/vc-agents' "$repo_root"
    return 0
  fi

  if [[ -d "$current_store" ]]; then
    printf '%s' "$current_store"
    return 0
  fi

  if [[ -d "$crafted_store" ]]; then
    printf '%s' "$crafted_store"
    return 0
  fi

  local legacy_store="$HOME/.agents/skills/vc-agents"
  if [[ -d "$legacy_store" ]]; then
    printf '%s' "$legacy_store"
    return 0
  fi

  printf '%s' "$crafted_store"
}

_vetcoders_spawn_script() {
  local tool="$1"
  local script_name="$2"
  local base
  base="$(_vetcoders_spawn_home "$tool")"
  [[ -f "$base/scripts/$script_name" ]] || {
    echo "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. spawn script not found: $base/scripts/$script_name" >&2
    return 1
  }
  printf '%s/scripts/%s' "$base" "$script_name"
}

_vetcoders_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

_vetcoders_org_repo() {
  local root="${1:-$(_vetcoders_repo_root)}"
  local org_repo=""
  org_repo="$(cd "$root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"
  if [[ -n "$org_repo" ]]; then
    printf '%s\n' "$org_repo"
  else
    printf '%s\n' "$(basename "$root")"
  fi
}

_vetcoders_store_dir() {
  local root="${1:-$(_vetcoders_repo_root)}"
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  local date_dir
  date_dir="$(date +%Y_%m%d)"
  printf '%s/artifacts/%s/%s\n' "$crafted_home" "$(_vetcoders_org_repo "$root")" "$date_dir"
}

_vetcoders_tmp_dir() {
  local root="${1:-$(_vetcoders_repo_root)}"
  local dir
  dir="$(_vetcoders_store_dir "$root")/tmp"
  mkdir -p "$dir"
  printf '%s\n' "$dir"
}

_vetcoders_tmp_script_path() {
  local prefix="$1"
  local root="${2:-$(_vetcoders_repo_root)}"
  local dir stamp context

  dir="$(_vetcoders_tmp_dir "$root")" || return 1
  stamp="$(_vetcoders_spawn_timestamp)"
  context="${VIBECRAFTED_RUN_ID:-${VIBECRAFTED_SKILL_CODE:-$(_vetcoders_session_base_name)}}"
  context="$(printf '%s' "$context" | tr -cs '[:alnum:]._-' '-')"
  context="${context#-}"
  context="${context%-}"
  [[ -n "$context" ]] || context="session"

  mktemp "${dir%/}/${prefix}.${stamp}_${context}.XXXXXX"
}

_vetcoders_find_meta_for_run_id() {
  local reports_dir="$1"
  local target_run_id="$2"
  python3 - "$reports_dir" "$target_run_id" <<'PY'
import json
import os
import sys

reports_dir, target_run_id = sys.argv[1:3]
if not os.path.isdir(reports_dir):
    sys.exit(0)

for name in sorted(os.listdir(reports_dir)):
    if not name.endswith(".meta.json"):
        continue
    path = os.path.join(reports_dir, name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        continue
    if payload.get("run_id") == target_run_id:
        print(path)
        break
PY
}

_vetcoders_marbles_tail_delay() {
  printf '%s\n' "${VIBECRAFTED_MARBLES_TAIL_DELAY:-5}"
}

_vetcoders_tail_marbles_l1_transcript() {
  local root="$1"
  local marbles_run_id="$2"
  local reports_dir loop_run_id meta_path transcript_path delay_s

  reports_dir="$(_vetcoders_store_dir "$root")/marbles/reports"
  loop_run_id="${marbles_run_id}-001"
  delay_s="$(_vetcoders_marbles_tail_delay)"

  # Only sleep if there is a reports dir to poll — skip the delay entirely
  # on headless/test paths where the meta file will never appear.
  [[ -d "$reports_dir" ]] || return 0
  sleep "$delay_s"

  meta_path="$(_vetcoders_find_meta_for_run_id "$reports_dir" "$loop_run_id" 2>/dev/null || true)"
  [[ -n "$meta_path" && -f "$meta_path" ]] || return 0

  transcript_path="$(
    python3 - "$meta_path" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
print(payload.get("transcript") or "", end="")
PY
  )"
  [[ -n "$transcript_path" && -f "$transcript_path" ]] || return 0

  printf '\n--- marbles L1 transcript tail (%s) ---\n' "$transcript_path"
  tail -n 15 "$transcript_path" 2>/dev/null || true
}

_vetcoders_session_base_name() {
  local root base
  root="$(_vetcoders_session_scope_root)"
  base="$(basename "$root" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/^-*//; s/-*$//')"
  [[ -n "$base" ]] || base="vibecrafted"
  printf '%s\n' "$base"
}

_vetcoders_zellij_session_scope() {
  case "${VIBECRAFTED_ZELLIJ_SESSION_SCOPE:-repo}" in
    folder) printf 'folder\n' ;;
    repo|*) printf 'repo\n' ;;
  esac
}

_vetcoders_session_scope_root() {
  case "$(_vetcoders_zellij_session_scope)" in
    folder)
      pwd -P
      ;;
    *)
      _vetcoders_repo_root
      ;;
  esac
}

_vetcoders_zellij_session_max_length() {
  printf '24\n'
}

_vetcoders_short_hash() {
  local value="$1"
  local hash=""
  hash="$(printf '%s' "$value" | shasum -a 256 2>/dev/null || printf '%s' "$value" | sha256sum 2>/dev/null)" || return 1
  hash="${hash%% *}"
  printf '%.4s\n' "$hash"
}

_vetcoders_compact_session_name() {
  local full_name="$1"
  local preserved_tail="${2:-}"
  local max_len hash prefix_len prefix compact

  max_len="$(_vetcoders_zellij_session_max_length)"
  if (( ${#full_name} <= max_len )); then
    printf '%s\n' "$full_name"
    return 0
  fi

  hash="$(_vetcoders_short_hash "$full_name" 2>/dev/null || true)"
  [[ -n "$hash" ]] || hash="sess"

  if [[ -n "$preserved_tail" ]]; then
    prefix_len=$(( max_len - ${#preserved_tail} - ${#hash} - 2 ))
    if (( prefix_len > 0 )); then
      prefix="${full_name:0:prefix_len}"
      prefix="${prefix%-}"
      [[ -n "$prefix" ]] || prefix="${hash:0:1}"
      compact="${prefix}-${hash}-${preserved_tail}"
      if (( ${#compact} <= max_len )); then
        printf '%s\n' "$compact"
        return 0
      fi
    fi
  fi

  prefix_len=$(( max_len - ${#hash} - 1 ))
  (( prefix_len > 0 )) || prefix_len=1
  prefix="${full_name:0:prefix_len}"
  prefix="${prefix%-}"
  [[ -n "$prefix" ]] || prefix="${hash:0:1}"
  compact="${prefix}-${hash}"
  printf '%.24s\n' "$compact"
}

_vetcoders_operator_session_name_for_run_id() {
  local run_id="${1:-}"
  local base
  base="$(_vetcoders_session_base_name)"
  if [[ -n "$run_id" ]]; then
    _vetcoders_compact_session_name "${base}-${run_id}" "$run_id"
  else
    _vetcoders_compact_session_name "$base"
  fi
}

_vetcoders_expected_run_lock_path() {
  local run_id="${1:-}"
  local root="${2:-$(_vetcoders_repo_root)}"
  [[ -n "$run_id" ]] || return 1
  printf '%s/locks/%s/%s.lock\n' \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}" \
    "$(_vetcoders_org_repo "$root")" \
    "$run_id"
}

_vetcoders_normalize_ambient_context() {
  local run_id lock expected_lock operator_session expected_session

  run_id="${VIBECRAFTED_RUN_ID:-}"
  lock="${VIBECRAFTED_RUN_LOCK:-}"
  operator_session="${VIBECRAFTED_OPERATOR_SESSION:-}"

  [[ -n "$run_id" ]] || {
    unset VIBECRAFTED_RUN_LOCK VIBECRAFTED_SKILL_CODE VIBECRAFTED_SKILL_NAME
    return 0
  }

  [[ -n "$lock" ]] || return 0

  expected_lock="$(_vetcoders_expected_run_lock_path "$run_id" 2>/dev/null || true)"
  if [[ -n "$expected_lock" && "$lock" == "$expected_lock" && -f "$lock" ]]; then
    return 0
  fi

  expected_session="$(_vetcoders_operator_session_name_for_run_id "$run_id")"
  unset VIBECRAFTED_RUN_LOCK VIBECRAFTED_SKILL_CODE VIBECRAFTED_SKILL_NAME

  if [[ "$(basename "$lock")" != "${run_id}.lock" ]]; then
    if [[ -n "$operator_session" && "$operator_session" != "$expected_session" ]]; then
      unset VIBECRAFTED_OPERATOR_SESSION
    fi
    return 0
  fi

  unset VIBECRAFTED_RUN_ID
  if [[ -n "$operator_session" ]]; then
    unset VIBECRAFTED_OPERATOR_SESSION
  fi
}

_vetcoders_skill_prefix() {
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

_vetcoders_generate_run_id() {
  local prefix="$1"
  # PID suffix defuses same-second collisions when parallel spawns race.
  # Format stays "prefix-HHMMSS-..." so existing regex matchers keep working.
  printf '%s-%s-%s\n' "$prefix" "$(date +%H%M%S)" "$$"
}

_vetcoders_spawn_timestamp() {
  if [[ -n "${VIBECRAFTED_SPAWN_TS:-}" ]]; then
    printf '%s\n' "${VIBECRAFTED_SPAWN_TS}"
  else
    date +%Y%m%d_%H%M
  fi
}

_vetcoders_marbles_store_dir() {
  local root="$1"
  if cd "$root" && git remote get-url origin >/dev/null 2>&1; then
    printf '%s/marbles\n' "$(_vetcoders_store_dir "$root")"
  else
    printf '%s/.vibecrafted/marbles\n' "$root"
  fi
}

_vetcoders_marbles_l1_report_path() {
  local root="$1"
  local stamp="$2"
  local tool="$3"
  printf '%s/reports/%s_marbles-ancestor_L1_%s.md\n' \
    "$(_vetcoders_marbles_store_dir "$root")" \
    "$stamp" \
    "$tool"
}

_vetcoders_has_ambient_spawn_context() {
  [[ -n "${SPAWN_AGENT:-}" ]] || return 1
  [[ -n "${SPAWN_RUN_ID:-}" ]] || return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  [[ "${SPAWN_RUN_ID}" == "${VIBECRAFTED_RUN_ID}" ]] || return 1
  [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] || return 1
  _vetcoders_in_zellij && return 1
  return 0
}

_vetcoders_effective_run_id() {
  _vetcoders_normalize_ambient_context
  _vetcoders_has_ambient_spawn_context && return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_ID}"
}

_vetcoders_effective_run_lock() {
  _vetcoders_normalize_ambient_context
  _vetcoders_has_ambient_spawn_context && return 1
  [[ -n "${VIBECRAFTED_RUN_LOCK:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_LOCK}"
}

_vetcoders_effective_skill_name() {
  _vetcoders_normalize_ambient_context
  _vetcoders_has_ambient_spawn_context && return 1
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_SKILL_NAME}"
}

_vetcoders_effective_skill_code() {
  _vetcoders_normalize_ambient_context
  _vetcoders_has_ambient_spawn_context && return 1
  [[ -n "${VIBECRAFTED_SKILL_CODE:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_SKILL_CODE}"
}

_vetcoders_create_run_lock() {
  local run_id="$1"
  local agent="$2"
  local skill="$3"
  local root="$4"
  local org_repo lock_dir lock_file
  org_repo="$(_vetcoders_org_repo "$root")"
  lock_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/locks/$org_repo"
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

_vetcoders_spawn_root_arg() {
  local arg
  while [[ $# -gt 0 ]]; do
    arg="$1"
    shift
    case "$arg" in
      --root)
        [[ $# -gt 0 ]] || break
        printf '%s\n' "$1"
        return 0
        ;;
    esac
  done
  return 1
}

_vetcoders_ensure_run_context() {
  local tool="$1"
  local mode="$2"
  local root="${3:-$(_vetcoders_repo_root)}"
  local skill_name
  local skill_code
  local run_id
  local lock_file

  skill_name="$(_vetcoders_effective_skill_name 2>/dev/null || true)"
  [[ -n "$skill_name" ]] || skill_name="$mode"
  skill_code="$(_vetcoders_effective_skill_code 2>/dev/null || true)"
  run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  lock_file="$(_vetcoders_effective_run_lock 2>/dev/null || true)"

  [[ -n "$skill_code" ]] || skill_code="$(_vetcoders_skill_prefix "$skill_name")"
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || export VIBECRAFTED_SKILL_NAME="$skill_name"
  export VIBECRAFTED_SKILL_CODE="$skill_code"

  # Preserve the first run_id created for this workflow so prompts, locks,
  # operator sessions, and spawned workers stay traceable as one run.
  if [[ -z "$run_id" ]]; then
    run_id="$(_vetcoders_generate_run_id "$skill_code")"
  fi
  export VIBECRAFTED_RUN_ID="$run_id"

  if [[ -z "$lock_file" || ! -f "$lock_file" ]]; then
    lock_file="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/locks/$(_vetcoders_org_repo "$root")/${run_id}.lock"
  fi
  if [[ ! -f "$lock_file" ]]; then
    lock_file="$(_vetcoders_create_run_lock "$run_id" "$tool" "$skill_name" "$root")"
  fi
  export VIBECRAFTED_RUN_LOCK="$lock_file"
}

_vetcoders_default_runtime() {
  printf '%s\n' "${VETCODERS_SPAWN_RUNTIME:-terminal}"
}

_vetcoders_in_zellij() {
  # ZELLIJ=0 is a valid pane index inside zellij — do NOT treat as false.
  # Only absent ZELLIJ means we're outside.
  [[ -n "${ZELLIJ_PANE_ID:-}" ]] || [[ -n "${ZELLIJ+set}" ]]
}

_vetcoders_guess_active_zellij_session() {
  command -v zellij >/dev/null 2>&1 || return 0
  local active
  active="$(zellij ls 2>/dev/null | _vetcoders_strip_ansi | grep -E '\(attached\)|\(current\)' | head -1 | awk '{print $1}')"
  printf '%s\n' "$active"
}

_vetcoders_current_zellij_session_name() {
  printf '%s\n' "${ZELLIJ_SESSION_NAME:-}"
}

_vetcoders_atuin_bin() {
  local override="${VIBECRAFTED_ATUIN_BIN:-}"
  if [[ -n "$override" && -x "$override" ]]; then
    printf '%s\n' "$override"
    return 0
  fi

  if [[ -n "${_VETCODERS_ATUIN_BIN:-}" && -x "${_VETCODERS_ATUIN_BIN}" ]]; then
    printf '%s\n' "${_VETCODERS_ATUIN_BIN}"
    return 0
  fi

  command -v atuin 2>/dev/null || return 1
}

_vetcoders_strip_ansi() {
  python3 -c 'import re, sys; print(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", sys.stdin.read()), end="")'
}

_vetcoders_osascript_bin() {
  local override="${VIBECRAFTED_OSASCRIPT_BIN:-}"
  if [[ -n "$override" && -x "$override" ]]; then
    printf '%s\n' "$override"
    return 0
  fi

  command -v osascript 2>/dev/null || return 1
}

_vetcoders_preferred_terminal() {
  local pref="${VIBECRAFTED_TERMINAL:-}"
  if [[ -n "$pref" ]]; then
    printf '%s\n' "$pref"
    return 0
  fi
  if [[ -d "/Applications/iTerm.app" ]]; then
    printf 'iterm\n'
    return 0
  fi
  case "${TERM_PROGRAM:-}" in
    iTerm.app) printf 'iterm\n' ;;
    *) printf 'terminal\n' ;;
  esac
}

_vetcoders_zellij_session_state() {
  local session_name="$1"
  local listing

  command -v zellij >/dev/null 2>&1 || {
    printf 'missing\n'
    return 0
  }

  listing="$(zellij ls 2>/dev/null | _vetcoders_strip_ansi || true)"
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    case "$line" in
      "$session_name "*)
        if [[ "$line" == *"(EXITED"* ]]; then
          printf 'dead\n'
        else
          printf 'live\n'
        fi
        return 0
        ;;
    esac
  done <<< "$listing"

  printf 'missing\n'
}

_vetcoders_open_iterm_command() {
  local command_text="$1"
  local osascript_bin
  osascript_bin="$(_vetcoders_osascript_bin)" || return 1
  [[ "$(_vetcoders_preferred_terminal)" == "iterm" ]] || return 1
  local command_json
  command_json="$(python3 - "$command_text" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1]))
PY
)"

  "$osascript_bin" <<EOF_APPLE
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      write text $command_json
    end tell
  end tell
end tell
EOF_APPLE
}

_vetcoders_open_terminal_command() {
  local command_text="$1"
  local osascript_bin
  osascript_bin="$(_vetcoders_osascript_bin)" || return 1
  local command_json
  command_json="$(python3 - "$command_text" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1]))
PY
)"

  "$osascript_bin" <<EOF_APPLE
 tell application "Terminal"
   activate
   do script $command_json
 end tell
EOF_APPLE
}

_vetcoders_operator_layout_file() {
  _vetcoders_frontier_file "zellij/layouts/operator.kdl"
}

_vetcoders_operator_session_name() {
  local run_id
  _vetcoders_normalize_ambient_context
  run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  _vetcoders_operator_session_name_for_run_id "$run_id"
}

_vetcoders_zellij_gc_script() {
  _vetcoders_spawn_script "vc-agents" "mission-control/zellij-gc.sh"
}

_vetcoders_auto_gc_dead_zellij_sessions() {
  local gc_script
  gc_script="$(_vetcoders_zellij_gc_script 2>/dev/null || true)"
  [[ -n "$gc_script" && -f "$gc_script" ]] || return 0
  bash "$gc_script" --apply --quiet >/dev/null 2>&1 || true
}


_vetcoders_wait_for_zellij_session() {
  local session_name="$1"
  local attempts="${2:-40}"
  local current=0

  while (( current < attempts )); do
    [[ "$(_vetcoders_zellij_session_state "$session_name")" == "live" ]] && return 0
    sleep 0.25
    ((current+=1))
  done

  return 1
}


_vetcoders_ensure_zellij_session() {
  local session_name="$1"
  local layout_file="$2"
  shift 2

  command -v zellij >/dev/null 2>&1 || {
    echo "zellij is required." >&2
    return 1
  }

  local inside_zellij=0
  # Align with spawn_in_zellij_context: ZELLIJ_PANE_ID or ZELLIJ being set
  # (even ZELLIJ=0 is a valid pane index inside Zellij).
  [[ -n "${ZELLIJ_PANE_ID:-}" || -n "${ZELLIJ+set}" ]] && inside_zellij=1

  local current_session="${ZELLIJ_SESSION_NAME:-}"

  # Already in the target session — nothing to do.
  if (( inside_zellij )) && [[ "$current_session" == "$session_name" ]]; then
    return 0
  fi

  case "$(_vetcoders_zellij_session_state "$session_name")" in
    live)
      if (( inside_zellij )); then
        zellij action switch-session "$session_name"
      else
        zellij "$@" attach "$session_name"
      fi
      ;;
    dead)
      # Dead (EXITED) sessions cannot be switched to — kill and recreate.
      zellij kill-session "$session_name" 2>/dev/null || true
      if [[ -n "$layout_file" ]]; then
        if (( inside_zellij )); then
          env -u ZELLIJ -u ZELLIJ_PANE_ID -u ZELLIJ_SESSION_NAME \
            zellij --session "$session_name" --new-session-with-layout "$layout_file" &
          local bg_pid_dead=$!
          local wait_dead=0
          while (( wait_dead < 20 )); do
            [[ "$(_vetcoders_zellij_session_state "$session_name")" == "live" ]] && break
            sleep 0.25
            ((wait_dead+=1))
          done
          kill "$bg_pid_dead" 2>/dev/null || true
          wait "$bg_pid_dead" 2>/dev/null || true
          zellij action switch-session "$session_name"
        else
          zellij "$@" --session "$session_name" --new-session-with-layout "$layout_file"
        fi
      else
        # No layout — try force-run which may resurrect the session.
        if (( inside_zellij )); then
          echo "Session '$session_name' is dead and no layout is available to recreate it." >&2
          return 1
        else
          zellij "$@" attach --force-run-commands "$session_name"
        fi
      fi
      ;;
    *)
      if [[ -n "$layout_file" ]]; then
        if (( inside_zellij )); then
          # Create the session in the background with Zellij env stripped to
          # prevent nested-client panic, then switch to it.
          env -u ZELLIJ -u ZELLIJ_PANE_ID -u ZELLIJ_SESSION_NAME \
            zellij --session "$session_name" --new-session-with-layout "$layout_file" &
          local bg_pid=$!
          # Wait briefly for session to appear.
          local wait_i=0
          while (( wait_i < 20 )); do
            [[ "$(_vetcoders_zellij_session_state "$session_name")" == "live" ]] && break
            sleep 0.25
            ((wait_i+=1))
          done
          # Kill the background client now that the session server is alive.
          kill "$bg_pid" 2>/dev/null || true
          wait "$bg_pid" 2>/dev/null || true
          zellij action switch-session "$session_name"
        else
          zellij "$@" --session "$session_name" --new-session-with-layout "$layout_file"
        fi
      else
        echo "Layout file missing and session not found." >&2
        return 1
      fi
      ;;
  esac
}

_vetcoders_prepare_operator_runtime() {
  local runtime="${1:-$(_vetcoders_default_runtime)}"
  local session_name layout_file state command_text
  _vetcoders_normalize_ambient_context
  _vetcoders_auto_gc_dead_zellij_sessions

  case "$runtime" in
    terminal|visible) ;;
    *) return 0 ;;
  esac

  # If we are already inside a Zellij session, naturally attach to it.
  if _vetcoders_in_zellij; then
    export VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    return 0
  fi

  # If spawned by a headless agent, attempt to naturally latch onto the user's active session.
  local guessed_session
  guessed_session="$(_vetcoders_guess_active_zellij_session)"
  if [[ -n "$guessed_session" ]]; then
    export VIBECRAFTED_OPERATOR_SESSION="$guessed_session"
    return 0
  fi

  session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  command -v zellij >/dev/null 2>&1 || return 0

  layout_file="$(_vetcoders_operator_layout_file 2>/dev/null || true)"
  [[ -n "$layout_file" ]] || return 0

  state="$(_vetcoders_zellij_session_state "$session_name")"
  case "$state" in
    live)
      export VIBECRAFTED_OPERATOR_SESSION="$session_name"
      return 0
      ;;
    dead)
      zellij kill-session "$session_name" 2>/dev/null || true
      command_text="zellij --session \"$session_name\" --new-session-with-layout \"$layout_file\""
      ;;
    *)
      command_text="zellij --session \"$session_name\" --new-session-with-layout \"$layout_file\""
      ;;
  esac
  if _vetcoders_open_iterm_command "$command_text"; then
    :
  elif _vetcoders_open_terminal_command "$command_text"; then
    :
  else
    return 0
  fi

  if _vetcoders_wait_for_zellij_session "$session_name"; then
    export VIBECRAFTED_OPERATOR_SESSION="$session_name"
  fi
}

_vetcoders_spawn_into_operator_session() {
  local tab_name="$1"
  local command_text="$2"
  local session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  local root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  local cmd_script

  command -v zellij >/dev/null 2>&1 || return 1
  # zellij rejects inline command args carrying shell-quoted multibyte
  # prompt content (printf '%q' + Polish UTF-8). Store the wrapper under the
  # vibecrafted artifact tree so it survives resurrect/attach and leaves a
  # readable trail for debugging.
  cmd_script="$(_vetcoders_tmp_script_path "vc-spawn-cmd" "$root_dir")"
  _vetcoders_write_command_script "$cmd_script" "$command_text" || return 1
  zellij --session "$session_name" action new-tab \
    --name "$tab_name" \
    --cwd "$root_dir" \
    -- "$cmd_script" >/dev/null
}

_vetcoders_frontier_candidates() {
  local repo_root crafted_sidecar candidate seen=""
  repo_root="$(_vetcoders_repo_root)"
  crafted_sidecar="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current/config"

  for candidate in \
    "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier" \
    "$crafted_sidecar" \
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/config}" \
    "$repo_root/config"
  do
    [[ -n "$candidate" && -d "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    printf '%s\n' "$candidate"
  done
}

_vetcoders_frontier_root() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/starship.toml" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done < <(_vetcoders_frontier_candidates)

  echo "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. frontier config not found. Run vc-frontier-install from the repo checkout." >&2
  return 1
}

# Resolve each frontier asset independently so repo-owned prompt/history presets
# can coexist with an external session companion repo.
_vetcoders_frontier_file() {
  local relative_path="$1"
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/$relative_path" ]]; then
      printf '%s/%s\n' "$candidate" "$relative_path"
      return 0
    fi
  done < <(_vetcoders_frontier_candidates)
  return 1
}

_vetcoders_frontier_source_root() {
  local repo_root crafted_root candidate seen=""
  repo_root="$(_vetcoders_repo_root)"
  crafted_root="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current"

  for candidate in \
    "${VIBECRAFTED_ROOT:-}" \
    "$repo_root" \
    "$crafted_root"
  do
    [[ -n "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    if [[ -f "$candidate/config/starship.toml" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

_vetcoders_load_frontier_sidecars() {
  local starship_config atuin_config zellij_config zellij_config_dir
  starship_config="$(_vetcoders_frontier_file "starship.toml" 2>/dev/null || true)"
  atuin_config="$(_vetcoders_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(_vetcoders_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  # Frontier tools (starship, atuin, zellij) are suggested for the runtime,
  # not required. Never override a user's existing config — only set env vars
  # when the user has no config of their own. Users opt in explicitly.
  if command -v starship >/dev/null 2>&1 && [[ -n "$starship_config" && -z "${STARSHIP_CONFIG:-}" ]]; then
    export STARSHIP_CONFIG="$starship_config"
  fi

  if command -v atuin >/dev/null 2>&1 && [[ -n "$atuin_config" && -z "${ATUIN_CONFIG:-}" ]]; then
    export ATUIN_CONFIG="$atuin_config"
  fi

  if command -v zellij >/dev/null 2>&1 && [[ -n "$zellij_config" && -z "${ZELLIJ_CONFIG_DIR:-}" ]]; then
    zellij_config_dir="$(dirname "$zellij_config")"
    export ZELLIJ_CONFIG_DIR="$zellij_config_dir"
  fi
}

_vetcoders_load_frontier_sidecars

_vetcoders_normalize_ambient_context

_VETCODERS_ATUIN_BIN="$(_vetcoders_atuin_bin 2>/dev/null || true)"

_vetcoders_atuin_home_fallback_enabled() {
  [[ "${VIBECRAFTED_ATUIN_HOME_FALLBACK:-1}" != "0" ]]
}

_vetcoders_atuin_home_fallback_cwd() {
  printf '%s\n' "${VIBECRAFTED_ATUIN_FALLBACK_CWD:-$HOME}"
}

_vetcoders_same_physical_dir() {
  local left="${1:-}"
  local right="${2:-}"
  local left_real right_real

  [[ -n "$left" && -n "$right" ]] || return 1
  left_real="$(cd "$left" 2>/dev/null && pwd -P)" || return 1
  right_real="$(cd "$right" 2>/dev/null && pwd -P)" || return 1
  [[ "$left_real" == "$right_real" ]]
}

_vetcoders_atuin_search_can_fallback() {
  local arg
  [[ "${1:-}" == "search" ]] || return 1
  shift

  for arg in "$@"; do
    case "$arg" in
      -c|--cwd|--exclude-cwd|--filter-mode|--delete|--delete-it-all)
        return 1
        ;;
    esac
  done

  return 0
}

_vetcoders_atuin_search_is_interactive() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      -i|--interactive|--shell-up-key-binding)
        return 0
        ;;
    esac
  done

  return 1
}

_vetcoders_atuin_run() {
  local atuin_bin
  atuin_bin="$(_vetcoders_atuin_bin)" || return 127
  "$atuin_bin" "$@"
}

_vetcoders_atuin_run_with_home_scope() {
  local fallback_cwd="$1"
  shift
  local -a argv=()

  argv+=("search" "--cwd" "$fallback_cwd")
  # Skip "search" from caller args if present
  [[ "${1:-}" == "search" ]] && shift
  argv+=("$@")
  _vetcoders_atuin_run "${argv[@]}"
}

_vetcoders_atuin_probe_current_scope() {
  local arg
  local -a argv=()

  argv+=("search" "--cmd-only" "--limit" "1")
  # Skip "search" from caller args if present
  [[ "${1:-}" == "search" ]] && shift
  for arg in "$@"; do
    case "$arg" in
      -i|--interactive|--shell-up-key-binding)
        continue
        ;;
      --cmd-only|--limit)
        continue
        ;;
    esac
    argv+=("$arg")
  done

  _vetcoders_atuin_run "${argv[@]}"
}

_vetcoders_wrap_atuin() {
  # Only wrap an explicit override target. This preserves normal Atuin init
  # behavior in user shells while keeping the controlled fallback contract
  # available for tests and opt-in environments.
  [[ -n "${VIBECRAFTED_ATUIN_BIN:-}" ]] || return 0

  atuin() {
    if _vetcoders_atuin_home_fallback_enabled && _vetcoders_atuin_search_can_fallback "$@"; then
      local probe_output fallback_cwd
      if _vetcoders_atuin_search_is_interactive "$@"; then
        probe_output="$(_vetcoders_atuin_probe_current_scope "$@")" || return $?
      else
        probe_output="$(_vetcoders_atuin_run "$@")" || return $?
      fi
      if [[ -n "$probe_output" ]]; then
        printf '%s' "$probe_output"
        return 0
      fi

      fallback_cwd="$(_vetcoders_atuin_home_fallback_cwd)"
      if [[ -n "$fallback_cwd" ]] && ! _vetcoders_same_physical_dir "${PWD:-.}" "$fallback_cwd"; then
        _vetcoders_atuin_run_with_home_scope "$fallback_cwd" "$@"
        return $?
      fi
    fi

    _vetcoders_atuin_run "$@"
  }
}

_vetcoders_wrap_atuin

_vetcoders_known_dashboard_layouts=(dashboard marbles workflow research operator)

_vetcoders_dashboard_layout_name() {
  local requested="${1:-dashboard}"
  case "$requested" in
    ""|dashboard|mc|mission-control|vc-dashboard) printf 'dashboard\n' ;;
    marbles|vc-marbles) printf 'marbles\n' ;;
    workflow|vc-workflow) printf 'workflow\n' ;;
    research|vc-research) printf 'research\n' ;;
    operator|vibecrafted) printf 'operator\n' ;;
    *)
      echo "Unknown dashboard layout: $requested" >&2
      echo "Available layouts: ${_vetcoders_known_dashboard_layouts[*]}" >&2
      return 1
      ;;
  esac
}

_vetcoders_dashboard_layout_file() {
  local layout_name
  layout_name="$(_vetcoders_dashboard_layout_name "${1:-}")" || return 1
  _vetcoders_frontier_file "zellij/layouts/${layout_name}.kdl"
}

_vetcoders_dashboard_session_name() {
  local layout_name base_session
  _vetcoders_normalize_ambient_context
  layout_name="$(_vetcoders_dashboard_layout_name "${1:-}")" || return 1
  base_session="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  printf '%s\n' "$base_session"
}

_vetcoders_launch_dashboard() {
  local first_arg="${1:-}"

  # Thin shim subcommands — delegate directly to native Zellij.
  case "$first_arg" in
    ls|list|sessions)
      command -v zellij >/dev/null 2>&1 || {
        echo "zellij is required." >&2; return 1
      }
      zellij list-sessions
      return
      ;;
    switch)
      shift
      command -v zellij >/dev/null 2>&1 || {
        echo "zellij is required." >&2; return 1
      }
      if [[ -n "${ZELLIJ+set}" ]]; then
        zellij action switch-session "${1:?session name required}"
      else
        zellij attach "${1:?session name required}"
      fi
      return
      ;;
    attach)
      shift
      command -v zellij >/dev/null 2>&1 || {
        echo "zellij is required." >&2; return 1
      }
      if [[ -n "${ZELLIJ+set}" ]]; then
        zellij action switch-session "${1:?session name required}"
      else
        zellij attach "${1:?session name required}"
      fi
      return
      ;;
    kill)
      shift
      command -v zellij >/dev/null 2>&1 || {
        echo "zellij is required." >&2; return 1
      }
      zellij kill-session "${1:?session name required}"
      return
      ;;
    gc)
      shift || true
      local gc_script
      gc_script="$(_vetcoders_zellij_gc_script 2>/dev/null || true)"
      [[ -n "$gc_script" && -f "$gc_script" ]] || {
        echo "zellij GC helper not found." >&2
        return 1
      }
      bash "$gc_script" "$@"
      return
      ;;
  esac

  local layout_name layout_file session_name repo_source repo_zellij_dir state inside_zellij current_session
  _vetcoders_normalize_ambient_context
  _vetcoders_auto_gc_dead_zellij_sessions
  layout_name="$(_vetcoders_dashboard_layout_name "${first_arg}")" || return 1
  (( $# )) && shift

  command -v zellij >/dev/null 2>&1 || {
    echo "zellij is required for vibecrafted dashboard." >&2
    return 1
  }

  _vetcoders_load_frontier_sidecars

  layout_file="$(_vetcoders_dashboard_layout_file "$layout_name" 2>/dev/null || true)"
  [[ -n "$layout_file" ]] || {
    echo "Dashboard layout not found for: $layout_name" >&2
    echo "Expected zellij/layouts/${layout_name}.kdl in the active frontier config roots." >&2
    return 1
  }

  if [[ "${VIBECRAFTED_PREFER_REPO_ZELLIJ:-0}" == "1" ]]; then
    repo_source="$(_vetcoders_repo_root)"
    repo_zellij_dir="$repo_source/config/zellij"
    if [[ -d "$repo_zellij_dir" && -f "$repo_zellij_dir/config.kdl" ]]; then
      local repo_layout="$repo_zellij_dir/layouts/${layout_name}.kdl"
      if [[ -f "$repo_layout" ]]; then
        layout_file="$repo_layout"
        export ZELLIJ_CONFIG_DIR="$repo_zellij_dir"
      fi
    fi
  fi

  session_name="$(_vetcoders_dashboard_session_name "$layout_name")"
  state="$(_vetcoders_zellij_session_state "$session_name")"
  [[ -n "${ZELLIJ_PANE_ID:-}" || -n "${ZELLIJ+set}" ]] && inside_zellij=1 || inside_zellij=0
  current_session="${ZELLIJ_SESSION_NAME:-}"

  if [[ "$layout_name" != "operator" && "$layout_name" != "dashboard" && "$state" == "live" ]]; then
    if (( inside_zellij )) && [[ "$current_session" == "$session_name" ]]; then
      zellij action new-tab --layout "$layout_file"
    else
      zellij --session "$session_name" action new-tab --layout "$layout_file"
      if (( inside_zellij )); then
        zellij action switch-session "$session_name"
      else
        zellij attach "$session_name"
      fi
    fi
    return 0
  fi

  _vetcoders_ensure_zellij_session "$session_name" "$layout_file" "$@"
}

_vetcoders_resume_operator_session() {
  local session_name layout_file
  _vetcoders_normalize_ambient_context
  session_name="$(_vetcoders_operator_session_name)"
  layout_file="$(_vetcoders_operator_layout_file 2>/dev/null || true)"

  _vetcoders_ensure_zellij_session "$session_name" "$layout_file"
}

_vetcoders_prompt_file() {
  local agent="$1"
  shift
  if [[ $# -eq 0 ]]; then
    echo "Usage: ${agent}-prompt <prompt>" >&2
    return 1
  fi

  local root ts prompt_text slug prompt_file
  root="$(_vetcoders_repo_root)"
  ts="$(date +%Y%m%d_%H%M)"
  prompt_text="$*"
  slug="$(printf '%s' "$prompt_text" | tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-48)"
  [[ -n "$slug" ]] || slug="adhoc-prompt"

  mkdir -p "$root/.vibecrafted/tmp"
  prompt_file="$root/.vibecrafted/tmp/${ts}_${slug}_${agent}_prompt.md"
  printf '%s\n' "$prompt_text" > "$prompt_file"
  printf '%s\n' "$prompt_file"
}

_vetcoders_contract_reset() {
  _vetcoders_contract_prompt=""
  _vetcoders_contract_file=""
  _vetcoders_contract_session=""
  _vetcoders_contract_count=""
  _vetcoders_contract_depth=""
  _vetcoders_contract_runtime=""
  _vetcoders_contract_root=""
  _vetcoders_contract_tail=""
}

_vetcoders_append_tail() {
  local piece="${1:-}"
  [[ -n "$piece" ]] || return 0
  if [[ -n "$_vetcoders_contract_tail" ]]; then
    _vetcoders_contract_tail+=" "
  fi
  _vetcoders_contract_tail+="$piece"
}

_vetcoders_parse_contract() {
  _vetcoders_contract_reset
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -p|--prompt)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --prompt" >&2; return 1; }
        # Greedy: everything after --prompt is the prompt text.
        # Flags must come BEFORE --prompt.
        _vetcoders_contract_prompt="$*"
        break
        ;;
      -f|--file|--task)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --file" >&2; return 1; }
        _vetcoders_contract_file="$1"
        ;;
      --session)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --session" >&2; return 1; }
        _vetcoders_contract_session="$1"
        ;;
      --count)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --count" >&2; return 1; }
        _vetcoders_contract_count="$1"
        ;;
      --depth)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --depth" >&2; return 1; }
        _vetcoders_contract_depth="$1"
        ;;
      --runtime)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --runtime" >&2; return 1; }
        _vetcoders_contract_runtime="$1"
        ;;
      --root)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --root" >&2; return 1; }
        _vetcoders_contract_root="$1"
        ;;
      --)
        shift
        while [[ $# -gt 0 ]]; do
          _vetcoders_append_tail "$1"
          shift
        done
        break
        ;;
      *)
        _vetcoders_append_tail "$1"
        ;;
    esac
    shift
  done

  if [[ -z "$_vetcoders_contract_prompt" && -n "$_vetcoders_contract_tail" ]]; then
    _vetcoders_contract_prompt="$_vetcoders_contract_tail"
  fi
}

_vetcoders_effective_runtime() {
  if [[ -n "$_vetcoders_contract_runtime" ]]; then
    printf '%s\n' "$_vetcoders_contract_runtime"
  else
    _vetcoders_default_runtime
  fi
}

_vetcoders_require_positive_int() {
  local value="${1:-}"
  local flag_name="${2:-value}"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
    echo "${flag_name} must be a positive integer." >&2
    return 1
  }
}

_vetcoders_require_file() {
  local file_path="${1:-}"
  [[ -n "$file_path" ]] || {
    echo "Missing file path." >&2
    return 1
  }
  [[ -f "$file_path" ]] || {
    echo "Input file not found: $file_path" >&2
    return 1
  }
}

_vetcoders_shell_quote() {
  local value="${1-}"
  # printf '%q' can emit invalid UTF-8 byte sequences for multibyte input.
  python3 - "$value" <<'PY'
import shlex
import sys

print(shlex.quote(sys.argv[1]), end="")
PY
}

_vetcoders_shell_quote_join() {
  local quoted=()
  local arg
  for arg in "$@"; do
    quoted+=("$(_vetcoders_shell_quote "$arg")")
  done
  printf '%s' "${quoted[*]}"
}

_vetcoders_write_command_script() {
  local script_path="$1"
  local command_text="$2"
  local shell_bin

  if command -v zsh >/dev/null 2>&1; then
    shell_bin="$(command -v zsh)"
  else
    shell_bin="$(command -v bash)"
  fi

  # Keep the temp script stable on disk: zellij can re-run or resurrect panes
  # against the original command path, so self-deleting wrappers break attach
  # and respawn semantics.
  mkdir -p "$(dirname "$script_path")"
  # shellcheck disable=SC2016
  printf '#!/usr/bin/env bash\nset -euo pipefail\n%s -lc %s\n' \
    "$(_vetcoders_shell_quote "$shell_bin")" \
    "$(_vetcoders_shell_quote "$command_text")" \
    > "$script_path"
  chmod +x "$script_path"
}

_vetcoders_compose_input_context() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local combined="$prompt_text"

  if [[ -n "$file_path" ]]; then
    _vetcoders_require_file "$file_path" || return 1
    local abs_file
    abs_file="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"
    local file_body
    file_body="$(cat "$file_path")"
    if [[ -n "$combined" ]]; then
      combined+=$'\n\n'
    fi
    combined+="Primary input file: $abs_file"
    combined+=$'\n\n```md\n'
    combined+="$file_body"
    combined+=$'\n```'
  fi

  printf '%s' "$combined"
}

_vetcoders_compose_skill_prompt() {
  local skill="$1"
  local prompt_text="${2:-}"
  local file_path="${3:-}"
  local base="Perform the vc-${skill} skill on this repository."
  local extra
  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    base+=$'\n\n'
    base+="$extra"
  fi
  printf '%s\n' "$base"
}

_vetcoders_init_runtime() {
  local runtime="${1:-terminal}"
  case "$runtime" in
    terminal|visible)
      printf '%s\n' "$runtime"
      ;;
    *)
      echo "vc-init is interactive-only: use --runtime terminal or visible." >&2
      return 1
      ;;
  esac
}

_vetcoders_compose_init_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local init_prompt="/vc-init"
  local extra

  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    init_prompt+=$'\n\n'
    init_prompt+="$extra"
  fi

  printf '%s' "$init_prompt"
}

_vetcoders_init_command_text() {
  local tool="$1"
  local init_prompt="$2"
  local quoted_prompt
  quoted_prompt="$(_vetcoders_shell_quote "$init_prompt")"

  case "$tool" in
    claude)
      printf 'claude --verbose --dangerously-skip-permissions %s' "$quoted_prompt"
      ;;
    codex)
      printf 'codex --dangerously-bypass-approvals-and-sandbox %s' "$quoted_prompt"
      ;;
    gemini)
      printf 'gemini -y -i %s' "$quoted_prompt"
      ;;
    *)
      echo "Unsupported init agent: $tool" >&2
      return 1
      ;;
  esac
}

_vetcoders_spawn_plan() {
  local tool="$1"
  local mode="$2"
  local plan_file="$3"
  shift 3
  local script root arg prev_arg=""
  local runtime="$(_vetcoders_default_runtime)"
  for arg in "$@"; do
    if [[ "$prev_arg" == "--runtime" ]]; then
      runtime="$arg"
      break
    fi
    prev_arg="$arg"
  done
  root="$(_vetcoders_spawn_root_arg "$@" 2>/dev/null || true)"
  [[ -n "$root" ]] || root="$(_vetcoders_repo_root)"
  _vetcoders_ensure_run_context "$tool" "$mode" "$root"
  _vetcoders_prepare_operator_runtime "$runtime" || return 1
  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  bash "$script" --mode "$mode" "$plan_file" "$@"
}

_vetcoders_prompt_text() {
  local tool="$1"
  local mode="$2"
  local prompt_text="$3"
  shift 3
  local prompt_file
  prompt_file="$(_vetcoders_prompt_file "$tool" "$prompt_text")" || return 1
  _vetcoders_spawn_plan "$tool" "$mode" "$prompt_file" "$@"
}

_vetcoders_prompt() {
  local tool="$1"
  local mode="$2"
  shift 2
  local prompt_file
  prompt_file="$(_vetcoders_prompt_file "$tool" "$@")" || return 1
  _vetcoders_spawn_plan "$tool" "$mode" "$prompt_file" --runtime "$(_vetcoders_default_runtime)"
}

_vetcoders_observe() {
  local tool="$1"
  shift
  local script
  script="$(_vetcoders_spawn_script "$tool" "observe.sh")" || return 1
  bash "$script" "$tool" "$@"
}

_vetcoders_await() {
  local tool="${1:-}"
  shift || true
  local script
  script="$(_vetcoders_spawn_script "${tool:-codex}" "await.sh")" || return 1
  if [[ -n "$tool" ]]; then
    bash "$script" "$tool" "$@"
  else
    bash "$script" "$@"
  fi
}

codex-review() {
  _vetcoders_spawn_plan codex review "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-plan() {
  _vetcoders_spawn_plan codex plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-implement() {
  _vetcoders_spawn_plan codex implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-review() {
  _vetcoders_spawn_plan claude review "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-plan() {
  _vetcoders_spawn_plan claude plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-implement() {
  _vetcoders_spawn_plan claude implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-review() {
  _vetcoders_spawn_plan gemini review "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-plan() {
  _vetcoders_spawn_plan gemini plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-implement() {
  _vetcoders_spawn_plan gemini implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-research() {
  _vetcoders_spawn_plan codex research "$1" --runtime "$(_vetcoders_default_runtime)"
}

claude-research() {
  _vetcoders_spawn_plan claude research "$1" --runtime "$(_vetcoders_default_runtime)"
}

gemini-research() {
  _vetcoders_spawn_plan gemini research "$1" --runtime "$(_vetcoders_default_runtime)"
}

codex-prompt() {
  _vetcoders_prompt codex implement "$@"
}

claude-prompt() {
  _vetcoders_prompt claude implement "$@"
}

gemini-prompt() {
  _vetcoders_prompt gemini implement "$@"
}

codex-observe() {
  _vetcoders_observe codex "$@"
}

codex-await() {
  _vetcoders_await codex "$@"
}

claude-observe() {
  _vetcoders_observe claude "$@"
}

claude-await() {
  _vetcoders_await claude "$@"
}

gemini-observe() {
  _vetcoders_observe gemini "$@"
}

gemini-await() {
  _vetcoders_await gemini "$@"
}

_vetcoders_skill() {
  local tool="$1"
  local skill="$2"
  shift 2
  local loop_nr="${VIBECRAFTED_LOOP_NR:-0}"
  local inherited_run_id
  local inherited_run_lock
  inherited_run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  inherited_run_lock="$(_vetcoders_effective_run_lock 2>/dev/null || true)"
  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  local prompt
  prompt="$(_vetcoders_compose_skill_prompt "$skill" "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  local skill_code root run_id run_lock
  skill_code="$(_vetcoders_skill_prefix "$skill")"
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "$skill_code")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    run_lock="$(_vetcoders_create_run_lock "$run_id" "$tool" "$skill" "$root")" || return 1
  fi
  local spawn_args=(--runtime "$(_vetcoders_effective_runtime)")
  [[ -n "$_vetcoders_contract_root" ]] && spawn_args+=(--root "$_vetcoders_contract_root")
  (
    # shellcheck disable=SC2030
    export VIBECRAFTED_RUN_ID="$run_id"
    # shellcheck disable=SC2030
    export VIBECRAFTED_RUN_LOCK="$run_lock"
    # shellcheck disable=SC2030
    export VIBECRAFTED_SKILL_CODE="$skill_code"
    export VIBECRAFTED_LOOP_NR="$loop_nr"
    # shellcheck disable=SC2030
    export VIBECRAFTED_SKILL_NAME="$skill"
    _vetcoders_prompt_text "$tool" implement "$prompt" "${spawn_args[@]}"
  )
}

_vetcoders_skill_entry() {
  local tool="$1"
  local skill="$2"
  shift 2
  _vetcoders_skill "$tool" "$skill" "$@"
}

_vetcoders_research_launcher_path() {
  local tool="$1"
  local prompt_file="$2"
  local root="$3"
  local run_id="$4"
  local run_lock="$5"
  local runtime="$6"
  local script output launcher

  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  output="$(
    env \
      VIBECRAFTED_RUN_ID="$run_id" \
      VIBECRAFTED_RUN_LOCK="$run_lock" \
      VIBECRAFTED_SKILL_CODE="rsch" \
      VIBECRAFTED_SKILL_NAME="research" \
      bash "$script" --dry-run --mode implement --runtime "$runtime" --root "$root" "$prompt_file" 2>&1
  )" || {
    printf '%s\n' "$output" >&2
    return 1
  }

  launcher="$(printf '%s\n' "$output" | awk -F': ' '/Dry run mode: launcher generated only:/ {print $NF}' | tail -1)"
  [[ -n "$launcher" && -f "$launcher" ]] || {
    printf 'Could not resolve %s research launcher.\n' "$tool" >&2
    printf '%s\n' "$output" >&2
    return 1
  }
  printf '%s\n' "$launcher"
}

_vetcoders_write_research_layout() {
  local layout_file="$1"
  local claude_script="$2"
  local codex_script="$3"
  local gemini_script="$4"

  cat > "$layout_file" <<EOF
layout {
    default_tab_template {
        pane size=1 borderless=true {
            plugin location="compact-bar"
        }
        children
        pane size=1 borderless=true {
            plugin location="status-bar"
        }
    }

    tab name="𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Research" {
        pane split_direction="vertical" {
            pane name="synthesis" size="55%" focus=true command="zsh"
            pane split_direction="horizontal" size="45%" {
                pane name="claude" command="bash" {
                    args "$claude_script"
                }
                pane name="codex" command="bash" {
                    args "$codex_script"
                }
                pane name="gemini" command="bash" {
                    args "$gemini_script"
                }
            }
        }
    }
}
EOF
}

_vetcoders_research_help() {
  cat <<'HELP'
⚒  research
─────────────────────────────────────────
Triple-agent research swarm launcher (claude + codex + gemini).

Usage:
  vc-research --prompt "Question to research"
  vc-research --file /path/to/plan.md

Common flags:
  -p, --prompt <text>            Inline prompt
  -f, --file <path.md>           Input file as prompt context
  --runtime <runtime>             Runtime backend (terminal|headless|visible)
  --root <path>                   Root workspace for this research run

Examples:
  vc-research --prompt "Compare API alternatives for oauth libraries"
  vc-research --file /path/to/research-plan.md
  vibecrafted research --prompt "State of the art for MCP streaming"

Do not pass an agent to vc-research.
Use `vibecrafted <agent> research <plan.md>` if you intentionally need single-agent mode.
HELP
}

_vetcoders_research() {
  local first_arg="${1:-}"
  local inherited_run_id inherited_run_lock
  local prompt root run_id run_lock runtime prompt_file layout_file
  local claude_launcher codex_launcher gemini_launcher
  local claude_cmd codex_cmd gemini_cmd session_name

  for _arg in "$@"; do
    case "$_arg" in
      help|-h|--help)
        _vetcoders_research_help
        return 0
        ;;
    esac
  done

  case "$first_arg" in
    claude|codex|gemini)
    printf 'vc-research is a triple-agent swarm launcher. Do not pass %s.\n' "$first_arg" >&2
    printf 'Use vc-research --prompt "..." or vc-research --file /path/to/plan.md.\n' >&2
    printf 'If you intentionally want one researcher, use vibecrafted <agent> research <plan.md>.\n' >&2
    return 1
      ;;
  esac

  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }
  [[ -n "$_vetcoders_contract_prompt" || -n "$_vetcoders_contract_file" ]] || {
    echo "vc-research requires --prompt or --file." >&2
    return 1
  }

  prompt="$(_vetcoders_compose_skill_prompt "research" "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  runtime="$(_vetcoders_effective_runtime)"
  prompt_file="$(_vetcoders_prompt_file "research" "$prompt")" || return 1

  inherited_run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  inherited_run_lock="$(_vetcoders_effective_run_lock 2>/dev/null || true)"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "rsch")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    run_lock="$(_vetcoders_create_run_lock "$run_id" "swarm" "research" "$root")" || return 1
  fi

  claude_launcher="$(_vetcoders_research_launcher_path claude "$prompt_file" "$root" "$run_id" "$run_lock" "$runtime")" || return 1
  codex_launcher="$(_vetcoders_research_launcher_path codex "$prompt_file" "$root" "$run_id" "$run_lock" "$runtime")" || return 1
  gemini_launcher="$(_vetcoders_research_launcher_path gemini "$prompt_file" "$root" "$run_id" "$run_lock" "$runtime")" || return 1

  if [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    command -v zellij >/dev/null 2>&1 || {
      echo "vc-research requires zellij for the shared research tab layout." >&2
      return 1
    }

    session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
    [[ -n "$session_name" ]] || {
      echo "Could not determine the operator zellij session." >&2
      return 1
    }

    claude_cmd="$(_vetcoders_tmp_script_path "vc-research-claude" "$root")"
    codex_cmd="$(_vetcoders_tmp_script_path "vc-research-codex" "$root")"
    gemini_cmd="$(_vetcoders_tmp_script_path "vc-research-gemini" "$root")"
    layout_file="$(_vetcoders_tmp_script_path "vc-research-layout" "$root").kdl"

    _vetcoders_write_command_script "$claude_cmd" "bash $(_vetcoders_shell_quote "$claude_launcher")" || return 1
    _vetcoders_write_command_script "$codex_cmd" "bash $(_vetcoders_shell_quote "$codex_launcher")" || return 1
    _vetcoders_write_command_script "$gemini_cmd" "bash $(_vetcoders_shell_quote "$gemini_launcher")" || return 1
    _vetcoders_write_research_layout "$layout_file" "$claude_cmd" "$codex_cmd" "$gemini_cmd"

    # Intended exports to env for the zellij child process — false-positive SC2031.
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_ID="$run_id"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_LOCK="$run_lock"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_CODE="rsch"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_NAME="research"
    zellij --session "$session_name" action new-tab --layout "$layout_file" >/dev/null
    printf 'Research swarm launched in shared tab (run_id=%s).\n' "$run_id"
    _vetcoders_await "" --describe "$claude_launcher" "$codex_launcher" "$gemini_launcher" || true
    printf '\nAwait:\n\n'
    printf 'vc-research-await --run-id %s\n' "$run_id"
    return 0
  fi

  printf 'Research swarm prepared (run_id=%s), but runtime %s does not use the shared zellij layout.\n' "$run_id" "$runtime"
  printf 'Launchers:\n'
  printf '  claude: %s\n' "$claude_launcher"
  printf '  codex:  %s\n' "$codex_launcher"
  printf '  gemini: %s\n' "$gemini_launcher"
  printf '\nAwait:\n\n'
  printf 'vc-research-await --run-id %s\n' "$run_id"
}

_vetcoders_skill_init() {
  local tool="$1"
  shift
  local runtime init_prompt command_text

  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is not supported by vibecrafted init." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is not supported by vibecrafted init." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is not supported by vibecrafted init." >&2
    return 1
  }

  command -v zellij >/dev/null 2>&1 || {
    echo "vc-init requires zellij so the operator session can be attached or created." >&2
    return 1
  }

  runtime="$(_vetcoders_init_runtime "${_vetcoders_contract_runtime:-terminal}")" || return 1
  init_prompt="$(_vetcoders_compose_init_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  command_text="$(_vetcoders_init_command_text "$tool" "$init_prompt")" || return 1

  _vetcoders_prepare_operator_runtime "$runtime" || return 1
  _vetcoders_spawn_into_operator_session "${tool}-init" "$command_text"
}

codex-dou() { _vetcoders_skill codex dou "$@"; }
claude-dou() { _vetcoders_skill claude dou "$@"; }
gemini-dou() { _vetcoders_skill gemini dou "$@"; }

codex-hydrate() { _vetcoders_skill codex hydrate "$@"; }
claude-hydrate() { _vetcoders_skill claude hydrate "$@"; }
gemini-hydrate() { _vetcoders_skill gemini hydrate "$@"; }

_vetcoders_marbles() {
  local tool="$1"
  shift
  local script marbles_cmd quoted_args quoted_env operator_session root_dir marbles_run_id runtime launch_ts launch_report
  local -a marbles_env
  script="$(_vetcoders_spawn_script "$tool" "marbles_spawn.sh")" || return 1
  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is only supported by vibecrafted resume." >&2
    return 1
  }

  local source_count=0
  [[ -n "$_vetcoders_contract_depth" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_file" ]] && ((source_count+=1))
  [[ -n "$_vetcoders_contract_prompt" ]] && ((source_count+=1))
  [[ $source_count -le 1 ]] || {
    echo "Marbles accepts one source at a time: use exactly one of --depth, --file, or --prompt." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_count" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_count" "--count" || return 1
  [[ -z "$_vetcoders_contract_depth" ]] || _vetcoders_require_positive_int "$_vetcoders_contract_depth" "--depth" || return 1

  # shellcheck disable=SC2031
  [[ -n "${VIBECRAFTED_SKILL_NAME:-}" ]] || export VIBECRAFTED_SKILL_NAME="marbles"
  # shellcheck disable=SC2031
  export VIBECRAFTED_SKILL_CODE="marb"

  root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  marbles_run_id="${VIBECRAFTED_MARBLES_RUN_ID:-$(_vetcoders_generate_run_id "marb")}"
  runtime="$(_vetcoders_effective_runtime)"
  marbles_env=(VIBECRAFTED_MARBLES_RUN_ID="$marbles_run_id")
  local marbles_args=(--agent "$tool" --runtime "$runtime")
  local source_args=()
  [[ -n "$_vetcoders_contract_root" ]] && marbles_args+=(--root "$_vetcoders_contract_root")
  [[ -n "$_vetcoders_contract_count" ]] && marbles_args+=(--count "$_vetcoders_contract_count")

  if [[ -n "$_vetcoders_contract_file" ]]; then
    source_args=(--file "$_vetcoders_contract_file")
  elif [[ -n "$_vetcoders_contract_prompt" ]]; then
    source_args=(--prompt "$_vetcoders_contract_prompt")
  else
    source_args=(--depth "${_vetcoders_contract_depth:-3}")
  fi
  if [[ "$runtime" == "headless" ]]; then
    marbles_args+=(--no-watch)
    launch_ts="$(_vetcoders_spawn_timestamp)"
    launch_report="$(_vetcoders_marbles_l1_report_path "$root_dir" "$launch_ts" "$tool")"
    marbles_env+=(VIBECRAFTED_SPAWN_TS="$launch_ts" VIBECRAFTED_SUPPRESS_REPORT_HINT=1)
    printf 'Agent launched. Report will land at: %s\n' "$launch_report"
  fi
  marbles_args+=("${source_args[@]}")

  quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
  quoted_args="$(_vetcoders_shell_quote_join "${marbles_args[@]}")"
  marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
  operator_session="${VIBECRAFTED_OPERATOR_SESSION:-}"
  if [[ -z "$operator_session" ]] && _vetcoders_in_zellij; then
    operator_session="$(_vetcoders_current_zellij_session_name)"
  fi
  if [[ -z "$operator_session" ]]; then
    operator_session="$(_vetcoders_operator_session_name)"
  fi

  # Inside zellij: each marbles run_id gets its own tab named
  # "marbles-<run_id>". Subsequent loops (L2, L3, ...) inherit
  # VIBECRAFTED_MARBLES_TAB_NAME via env and stay in the same tab — one
  # run_id = one tab, no crossover. The "marbles-" prefix distinguishes
  # the tab from workflow/research tabs which also carry run_ids.
  # Temp script keeps zellij args ASCII-safe (no inline UTF-8 prompt bytes).
  if [[ "$runtime" =~ ^(terminal|visible)$ ]] && _vetcoders_in_zellij && command -v zellij >/dev/null 2>&1; then
    local cmd_script marbles_tab_name
    export VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    marbles_tab_name="marbles-${marbles_run_id}"
    export VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name"
    marbles_env+=(VIBECRAFTED_MARBLES_TAB_NAME="$marbles_tab_name")
    quoted_env="$(_vetcoders_shell_quote_join "${marbles_env[@]}")"
    marbles_cmd="env ${quoted_env} bash $(_vetcoders_shell_quote "$script") ${quoted_args}"
    cmd_script="$(_vetcoders_tmp_script_path "vibecrafted-marbles" "$root_dir")"
    _vetcoders_write_command_script "$cmd_script" "$marbles_cmd" || return 1
    
    local original_tab
    original_tab="${ZELLIJ_TAB_NAME:-}"
    
    zellij action go-to-tab-name "$marbles_tab_name" --create >/dev/null 2>&1 || true
    zellij action new-pane \
      --name "$marbles_run_id" \
      --cwd "$root_dir" \
      -- "$cmd_script" >/dev/null || return 1
      
    if [[ -n "$original_tab" ]]; then
      zellij action go-to-tab-name "$original_tab" >/dev/null 2>&1 || true
    fi
    
    _vetcoders_tail_marbles_l1_transcript "$root_dir" "$marbles_run_id"
  elif [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "marbles" "$marbles_cmd" || return 1
      _vetcoders_tail_marbles_l1_transcript "$root_dir" "$marbles_run_id"
    else
      env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
    fi
  else
    env "${marbles_env[@]}" bash "$script" "${marbles_args[@]}"
  fi
}

_vetcoders_resume_agent() {
  local tool="$1"
  shift
  _vetcoders_parse_contract "$@" || return 1
  [[ -n "$_vetcoders_contract_session" ]] || {
    echo "Usage: vibecrafted resume <claude|codex|gemini> --session <session_id> [--prompt <text>] [--file <path>]" >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is only supported by vibecrafted marbles." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is only supported by vibecrafted marbles." >&2
    return 1
  }

  local resume_prompt
  resume_prompt="$(_vetcoders_compose_input_context "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1

  case "$tool" in
    claude)
      if [[ -n "$resume_prompt" ]]; then
        claude --resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        claude --resume "$_vetcoders_contract_session"
      fi
      ;;
    codex)
      if [[ -n "$resume_prompt" ]]; then
        codex resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        codex resume "$_vetcoders_contract_session"
      fi
      ;;
    gemini)
      if [[ -n "$resume_prompt" ]]; then
        gemini --resume "$_vetcoders_contract_session" "$resume_prompt"
      else
        gemini --resume "$_vetcoders_contract_session"
      fi
      ;;
    *)
      echo "Unknown agent for resume: $tool" >&2
      return 1
      ;;
  esac
}

vc-resume() {
  local tool="${1:-}"
  [[ -n "$tool" ]] || {
    echo "Usage: vibecrafted resume <claude|codex|gemini> --session <session_id> [--prompt <text>] [--file <path>]" >&2
    return 1
  }
  shift || true
  _vetcoders_resume_agent "$tool" "$@"
}

codex-marbles() { _vetcoders_marbles codex "$@"; }
claude-marbles() { _vetcoders_marbles claude "$@"; }
gemini-marbles() { _vetcoders_marbles gemini "$@"; }

# Marbles control subcommands
marbles-pause()   { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" pause "$@"; }
marbles-stop()    { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" stop "$@"; }
marbles-resume()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" resume "$@"; }
marbles-session() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" session "$@"; }
marbles-inspect() { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" inspect "$@"; }
marbles-delete()  { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" delete "$@"; }
marbles-gc()      { local s; s="$(_vetcoders_spawn_script claude "marbles_ctl.sh")" && bash "$s" gc "$@"; }

codex-decorate() { _vetcoders_skill codex decorate "$@"; }
claude-decorate() { _vetcoders_skill claude decorate "$@"; }
gemini-decorate() { _vetcoders_skill gemini decorate "$@"; }

codex-followup() { _vetcoders_skill codex followup "$@"; }
claude-followup() { _vetcoders_skill claude followup "$@"; }
gemini-followup() { _vetcoders_skill gemini followup "$@"; }

codex-prune() { _vetcoders_skill codex prune "$@"; }
claude-prune() { _vetcoders_skill claude prune "$@"; }
gemini-prune() { _vetcoders_skill gemini prune "$@"; }

codex-scaffold() { _vetcoders_skill codex scaffold "$@"; }
claude-scaffold() { _vetcoders_skill claude scaffold "$@"; }
gemini-scaffold() { _vetcoders_skill gemini scaffold "$@"; }

codex-release() { _vetcoders_skill codex release "$@"; }
claude-release() { _vetcoders_skill claude release "$@"; }
gemini-release() { _vetcoders_skill gemini release "$@"; }

codex-justdo() { _vetcoders_skill codex justdo "$@"; }
claude-justdo() { _vetcoders_skill claude justdo "$@"; }
gemini-justdo() { _vetcoders_skill gemini justdo "$@"; }

codex-partner() { _vetcoders_skill codex partner "$@"; }
claude-partner() { _vetcoders_skill claude partner "$@"; }
gemini-partner() { _vetcoders_skill gemini partner "$@"; }

codex-skill-agents() { _vetcoders_skill_entry codex agents "$@"; }
claude-skill-agents() { _vetcoders_skill_entry claude agents "$@"; }
gemini-skill-agents() { _vetcoders_skill_entry gemini agents "$@"; }

codex-skill-decorate() { _vetcoders_skill_entry codex decorate "$@"; }
claude-skill-decorate() { _vetcoders_skill_entry claude decorate "$@"; }
gemini-skill-decorate() { _vetcoders_skill_entry gemini decorate "$@"; }

codex-skill-delegate() { _vetcoders_skill_entry codex delegate "$@"; }
claude-skill-delegate() { _vetcoders_skill_entry claude delegate "$@"; }
gemini-skill-delegate() { _vetcoders_skill_entry gemini delegate "$@"; }

codex-skill-dou() { _vetcoders_skill_entry codex dou "$@"; }
claude-skill-dou() { _vetcoders_skill_entry claude dou "$@"; }
gemini-skill-dou() { _vetcoders_skill_entry gemini dou "$@"; }

codex-skill-followup() { _vetcoders_skill_entry codex followup "$@"; }
claude-skill-followup() { _vetcoders_skill_entry claude followup "$@"; }
gemini-skill-followup() { _vetcoders_skill_entry gemini followup "$@"; }

codex-skill-hydrate() { _vetcoders_skill_entry codex hydrate "$@"; }
claude-skill-hydrate() { _vetcoders_skill_entry claude hydrate "$@"; }
gemini-skill-hydrate() { _vetcoders_skill_entry gemini hydrate "$@"; }

codex-skill-init() { _vetcoders_skill_init codex "$@"; }
claude-skill-init() { _vetcoders_skill_init claude "$@"; }
gemini-skill-init() { _vetcoders_skill_init gemini "$@"; }

codex-skill-justdo() { _vetcoders_skill_entry codex justdo "$@"; }
claude-skill-justdo() { _vetcoders_skill_entry claude justdo "$@"; }
gemini-skill-justdo() { _vetcoders_skill_entry gemini justdo "$@"; }

# vc-implement is the front-face brand for vc-justdo. Both helper families hit
# the same dispatcher (skill id stays "justdo" so run_id prefix, locks, and
# already-trained agents keep working unchanged).
codex-skill-implement() { _vetcoders_skill_entry codex justdo "$@"; }
claude-skill-implement() { _vetcoders_skill_entry claude justdo "$@"; }
gemini-skill-implement() { _vetcoders_skill_entry gemini justdo "$@"; }

codex-skill-marbles() { _vetcoders_marbles codex "$@"; }
claude-skill-marbles() { _vetcoders_marbles claude "$@"; }
gemini-skill-marbles() { _vetcoders_marbles gemini "$@"; }

codex-skill-partner() { _vetcoders_skill_entry codex partner "$@"; }
claude-skill-partner() { _vetcoders_skill_entry claude partner "$@"; }
gemini-skill-partner() { _vetcoders_skill_entry gemini partner "$@"; }

codex-skill-prune() { _vetcoders_skill_entry codex prune "$@"; }
claude-skill-prune() { _vetcoders_skill_entry claude prune "$@"; }
gemini-skill-prune() { _vetcoders_skill_entry gemini prune "$@"; }

codex-skill-release() { _vetcoders_skill_entry codex release "$@"; }
claude-skill-release() { _vetcoders_skill_entry claude release "$@"; }
gemini-skill-release() { _vetcoders_skill_entry gemini release "$@"; }

codex-skill-research() { _vetcoders_skill_entry codex research "$@"; }
claude-skill-research() { _vetcoders_skill_entry claude research "$@"; }
gemini-skill-research() { _vetcoders_skill_entry gemini research "$@"; }
vc-research() { _vetcoders_research "$@"; }
vc-research-await() { _vetcoders_await "" --research "$@"; }

codex-skill-review() { _vetcoders_skill_entry codex review "$@"; }
claude-skill-review() { _vetcoders_skill_entry claude review "$@"; }
gemini-skill-review() { _vetcoders_skill_entry gemini review "$@"; }

codex-skill-scaffold() { _vetcoders_skill_entry codex scaffold "$@"; }
claude-skill-scaffold() { _vetcoders_skill_entry claude scaffold "$@"; }
gemini-skill-scaffold() { _vetcoders_skill_entry gemini scaffold "$@"; }

codex-skill-workflow() { _vetcoders_skill_entry codex workflow "$@"; }
claude-skill-workflow() { _vetcoders_skill_entry claude workflow "$@"; }
gemini-skill-workflow() { _vetcoders_skill_entry gemini workflow "$@"; }

_vetcoders_skill_wrapper_usage() {
  local skill="$1"
  case "$skill" in
    init)
      printf 'Usage: vc-init <claude|codex|gemini> [--prompt <text>] [--file <path>]\n' >&2
      ;;
    marbles)
      printf 'Usage: vc-marbles <claude|codex|gemini> [--prompt <text>|--file <path>|--depth <n>] [--count <n>]\n' >&2
      ;;
    *)
      printf 'Usage: vc-%s <claude|codex|gemini> [--prompt <text>] [--file <path>]\n' "$skill" >&2
      ;;
  esac
}

_vetcoders_has_agent() {
  local candidate="${1:-}"
  [[ "$candidate" == "claude" || "$candidate" == "codex" || "$candidate" == "gemini" ]]
}

_vetcoders_skill_wrapper() {
  local skill="$1"
  shift || true

  local tool="${1:-}"
  [[ -n "$tool" ]] || {
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  _vetcoders_has_agent "$tool" || {
    printf 'vc-%s expects <claude|codex|gemini> as the first argument.\n' "$skill" >&2
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  shift || true

  case "$skill" in
    init) _vetcoders_skill_init "$tool" "$@" ;;
    marbles) _vetcoders_marbles "$tool" "$@" ;;
    *) _vetcoders_skill_entry "$tool" "$skill" "$@" ;;
  esac
}

vc-agents() { _vetcoders_skill_wrapper agents "$@"; }
vc-decorate() { _vetcoders_skill_wrapper decorate "$@"; }
vc-delegate() { _vetcoders_skill_wrapper delegate "$@"; }
vc-dou() { _vetcoders_skill_wrapper dou "$@"; }
vc-followup() { _vetcoders_skill_wrapper followup "$@"; }
vc-hydrate() { _vetcoders_skill_wrapper hydrate "$@"; }
vc-init() { _vetcoders_skill_wrapper init "$@"; }
vc-intents() { _vetcoders_skill_wrapper intents "$@"; }
vc-justdo() { _vetcoders_skill_wrapper justdo "$@"; }
vc-implement() { _vetcoders_skill_wrapper justdo "$@"; }
vc-marbles() { _vetcoders_skill_wrapper marbles "$@"; }
vc-ownership() { _vetcoders_skill_wrapper ownership "$@"; }
vc-partner() { _vetcoders_skill_wrapper partner "$@"; }
vc-prune() { _vetcoders_skill_wrapper prune "$@"; }
vc-release() { _vetcoders_skill_wrapper release "$@"; }
vc-review() { _vetcoders_skill_wrapper review "$@"; }
vc-scaffold() { _vetcoders_skill_wrapper scaffold "$@"; }
vc-workflow() { _vetcoders_skill_wrapper workflow "$@"; }

vc-help() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  cat <<'HELP'
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Framework — Skills & Helpers

Pipeline:  scaffold → init → workflow → followup → marbles → dou → decorate → hydrate → release
Modes:     partner (collaborative) | implement (autonomous, alias: justdo)
Research:  research (triple-agent) | delegate (in-session)
Quality:   review | prune
Video:     screenscribe (foundation)

Spawn helpers (per agent):
  <agent>-implement <plan.md>    Full implementation from plan
  <agent>-review <plan.md>       PR review
  <agent>-plan <plan.md>         Planning only
  <agent>-prompt "text"          Quick one-shot prompt
  <agent>-scaffold                Architecture planning
  <agent>-followup               Post-implementation audit
  <agent>-dou                    Definition of Undone audit
  <agent>-hydrate                Market packaging
  <agent>-marbles                Convergence loop
  <agent>-decorate               Visual polish
  <agent>-release                Ship to market
  <agent>-prune                  Repo pruning
  <agent>-skill-implement        Autonomous e2e implementation (vc-implement)
  <agent>-justdo                 Autonomous e2e implementation (legacy alias)
  <agent>-partner                Collaborative partner mode
  <agent>-observe --last         Check last report
  <agent>-await --last           Wait for metadata completion + summary

Swarm launchers:
  vc-research --prompt "text"    Triple-agent research swarm
  vc-research-await --last       Wait for the latest research swarm

Command deck:
  vibecrafted help               Main command surface
  vibecrafted <skill> <agent>    Run a repo skill via the launcher
  vibecrafted resume <agent>     Resume a previous session
  vibecrafted workflow claude -p "Plan and implement auth"
  vibecrafted marbles codex --count 3 --depth 3
  vibecrafted init claude        First-context entrypoint

Uniform skill flags:
  -p, --prompt <text>            Inline prompt; captures the rest of the command line
  -f, --file <path.md>           Input file as prompt context
  --count <n>                    Marbles loop count (default: 3)
  --depth <n>                    Marbles plan crawl depth (default: 3)
  --session <id>                 Resume session id

Utilities:
  repo-full                      Full git context dump
  skills-sync                    Sync skills to agents
  vc-frontier-paths              Show frontier config paths
  vc-frontier-install            Install frontier presets (starship/atuin/zellij)
  vc-help                        This help

Frontier docs:  docs/FRONTIER.md (starship, atuin, optional zellij)
HELP
  printf '\nInbox:     %s/inbox/\n' "$crafted_home"
  printf 'Artifacts: %s/artifacts/<org>/<repo>/<YYYY_MMDD>/\n' "$crafted_home"
  printf 'Skills:    %s/skills/ (16 installed)\n' "$crafted_home"
}

skills-sync() {
  local script
  script="$(_vetcoders_spawn_script codex skills_sync.sh)" || return 1
  bash "$script" "$@"
}

repo-full() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "Not a git repository."
    return 1
  }

  local cwd root repo branch head_short head_full upstream origin_url default_remote default_branch
  local last_tag stash_count staged_count unstaged_count untracked_count worktree_count
  local upstream_ahead upstream_behind

  cwd="$(pwd)"
  root="$(git rev-parse --show-toplevel 2>/dev/null)"
  repo="$(basename "$root")"
  branch="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "DETACHED_HEAD")"
  head_short="$(git rev-parse --short HEAD 2>/dev/null)"
  head_full="$(git rev-parse HEAD 2>/dev/null)"
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "no upstream")"
  origin_url="$(git remote get-url origin 2>/dev/null || echo "no origin")"
  last_tag="$(git describe --tags --abbrev=0 2>/dev/null || echo "no tags")"
  stash_count="$(git stash list 2>/dev/null | wc -l | tr -d ' ')"
  staged_count="$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')"
  unstaged_count="$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')"
  untracked_count="$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
  worktree_count="$(git worktree list 2>/dev/null | wc -l | tr -d ' ')"

  default_remote="$(git remote | awk 'NR==1{print; exit}')"
  [[ -z "$default_remote" ]] && default_remote="origin"

  default_branch="$(git symbolic-ref --quiet --short "refs/remotes/${default_remote}/HEAD" 2>/dev/null | sed "s#^${default_remote}/##")"
  [[ -z "$default_branch" ]] && default_branch="$(git remote show "$default_remote" 2>/dev/null | sed -n '/HEAD branch/s/.*: //p' | head -n 1)"
  [[ -z "$default_branch" ]] && default_branch="unknown"

  # shellcheck disable=SC1083 # @{u} is git upstream ref syntax, not shell braces
  if git rev-parse '@{u}' >/dev/null 2>&1; then
    read -r upstream_ahead upstream_behind <<< "$(git rev-list --left-right --count HEAD...'@{u}' 2>/dev/null)"
  else
    upstream_ahead="-"
    upstream_behind="-"
  fi

  _repo_full_compare_ref() {
    local ref="$1"
    git rev-parse --verify "$ref" >/dev/null 2>&1 || return 0
    local ahead behind sha
    read -r ahead behind <<< "$(git rev-list --left-right --count HEAD..."$ref" 2>/dev/null)"
    sha="$(git rev-parse --short "$ref" 2>/dev/null)"
    printf "%-24s ahead:%-4s behind:%-4s sha:%s\n" "$ref" "$ahead" "$behind" "$sha"
  }

  # shellcheck disable=SC2016 # expressions in awk are intentional
  _repo_full_human_awk='
    function human(x) {
      split("B KB MB GB TB", u, " ");
      i=1;
      while (x >= 1024 && i < 5) { x /= 1024; i++ }
      return sprintf("%.1f %s", x, u[i]);
    }
    {
      size=$1;
      $1="";
      sub(/^\t/, "", $0);
      printf "%10s  %s\n", human(size), $0;
    }
  '

  echo "==================== REPO FULL ===================="
  echo "Repo:              $repo"
  echo "Working dir:       $cwd"
  echo "Root:              $root"
  echo "Branch:            $branch"
  echo "Default remote:    $default_remote"
  echo "Default branch:    $default_branch"
  echo "Upstream:          $upstream"
  echo "Ahead / Behind:    $upstream_ahead / $upstream_behind"
  echo "Origin:            $origin_url"
  echo "HEAD short:        $head_short"
  echo "HEAD full:         $head_full"
  echo "Last tag:          $last_tag"
  echo "Stashes:           $stash_count"
  echo "Worktrees:         $worktree_count"
  echo "Staged changes:    $staged_count"
  echo "Unstaged changes:  $unstaged_count"
  echo "Untracked files:   $untracked_count"
  echo

  echo "==================== HEAD COMMIT ===================="
  git show -s --format="Commit: %H%nAuthor: %an <%ae>%nDate:   %ad%nTitle:  %s" --date=iso HEAD
  echo

  echo "==================== STATUS ===================="
  git status -sb
  echo

  echo "==================== WORKTREE ===================="
  git status --short
  echo

  echo "==================== COMPARE TO IMPORTANT REFS ===================="
  {
    [[ "$upstream" != "no upstream" ]] && echo "$upstream"
    [[ "$default_branch" != "unknown" ]] && echo "${default_remote}/${default_branch}"
    echo "origin/develop"
    echo "origin/main"
  } | awk 'NF && !seen[$0]++' | while IFS= read -r ref; do
    _repo_full_compare_ref "$ref"
  done
  echo

  echo "==================== REMOTES ===================="
  git remote -v
  echo

  echo "==================== LOCAL BRANCHES (RECENT FIRST) ===================="
  git for-each-ref \
    --sort=-committerdate \
    refs/heads \
    --format='%(HEAD) %(refname:short) | upstream=%(upstream:short) | %(committerdate:short) | %(objectname:short) | %(subject)'
  echo

  echo "==================== LAST 20 COMMITS ===================="
  git log --oneline --decorate --graph -n 20
  echo

  echo "==================== STAGED DIFF STAT ===================="
  git diff --cached --stat
  echo

  echo "==================== UNSTAGED DIFF STAT ===================="
  git diff --stat
  echo

  echo "==================== STASH LIST ===================="
  git stash list 2>/dev/null
  echo

  echo "==================== WORKTREES ===================="
  git worktree list 2>/dev/null
  echo

  echo "==================== SUBMODULES ===================="
  if [[ -f "$root/.gitmodules" ]]; then
    git submodule status
  else
    echo "No submodules."
  fi
  echo

  echo "==================== TOP 10 LARGEST TRACKED FILES ===================="
  if git ls-files -z | grep -q . 2>/dev/null; then
    { git ls-files -z | xargs -0 stat -f "%z\t%N" 2>/dev/null ||
      git ls-files -z | xargs -0 stat -c "%s\t%n" 2>/dev/null; } \
      | sort -nr \
      | head -n 10 \
      | awk "$_repo_full_human_awk"
  else
    echo "No tracked files."
  fi
  echo

  echo "==================== GIT CONFIG ===================="
  echo "user.name:         $(git config --get user.name 2>/dev/null || echo "not set")"
  echo "user.email:        $(git config --get user.email 2>/dev/null || echo "not set")"
  echo "pull.rebase:       $(git config --get pull.rebase 2>/dev/null || echo "not set")"
  echo "init.defaultBranch:$(git config --get init.defaultBranch 2>/dev/null || echo "not set")"
  echo

  echo "==================== DONE ===================="
}

vc-start() {
  if [[ "${1:-}" == "resume" ]]; then
    shift || true
    _vetcoders_resume_operator_session "$@"
    return
  fi
  if [[ "${1:-}" == "operator" || "${1:-}" == "vibecrafted" ]]; then
    shift || true
  fi
  _vetcoders_launch_dashboard operator "$@"
}

vc-frontier-paths() {
  local starship_config atuin_config zellij_config
  starship_config="$(_vetcoders_frontier_file "starship.toml")" || return 1
  atuin_config="$(_vetcoders_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(_vetcoders_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  printf 'STARSHIP_CONFIG=%s\n' "$starship_config"
  [[ -n "$atuin_config" ]] && printf 'ATUIN_CONFIG=%s\n' "$atuin_config"
  [[ -n "$zellij_config" ]] && printf 'ZELLIJ_CONFIG_DIR=%s\n' "$(dirname "$zellij_config")"
  return 0
}

vc-dashboard() {
  _vetcoders_launch_dashboard "$@"
}

vc-frontier-install() {
  local repo_root script base
  repo_root="$(_vetcoders_frontier_source_root)" || {
    echo "Repo-owned frontier source not found." >&2
    return 1
  }
  base="$(_vetcoders_spawn_home "vc-agents")"
  script="$base/scripts/install-frontier-config.sh"
  
  [[ -f "$script" ]] || {
    echo "Frontier installer not found: $script" >&2
    return 1
  }
  bash "$script" --source "$repo_root" "$@"
}

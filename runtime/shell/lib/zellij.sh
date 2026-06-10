# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_zellij_missing_message() {
  local xdg_data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
  local runtime_bin="${VIBECRAFTED_RUNTIME_BIN:-${VIBECRAFTED_RUNTIME_HOME:-$xdg_data_home/vibecrafted}/bin}"
  echo "zellij is required for the Vibecrafted operator runtime." >&2
  echo "Expected zellij on PATH or bundled at: $runtime_bin/zellij" >&2
}

_vetcoders_require_zellij() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  command -v zellij >/dev/null 2>&1 || {
    _vetcoders_zellij_missing_message
    return 1
  }
}

# Zellij needs a real PTY to enable raw mode. When stdin/stdout are pipes
# (curl|bash, ssh without -t, agent subprocess), zellij panics with an
# unhelpful Rust traceback. Catch the missing-TTY case early and return a
# user-actionable message instead.
_vetcoders_require_tty() {
  if [[ -t 0 && -t 1 ]]; then
    return 0
  fi
  cat >&2 <<'EOF'

vc-init requires an interactive terminal (TTY) to spawn a zellij session.

Detected: stdin or stdout is not a TTY (pipe, redirect, or non-interactive
SSH/agent context). Zellij needs a real PTY to switch into raw mode.

To proceed:
  - Local terminal:        run `vibecrafted init <agent>` directly
  - SSH:                   add `-t`, e.g. `ssh -t user@host vibecrafted init claude`
  - Inside another agent:  zellij cannot start from a piped subprocess.
                           Use `vibecrafted <agent> <mode>` (no zellij wrapper)
                           or run vc-init in a separate user-attached shell.

EOF
  return 1
}

_vetcoders_in_zellij() {
  # ZELLIJ=0 is a valid pane index inside zellij — do NOT treat as false.
  # Only absent ZELLIJ means we're outside.
  [[ -n "${ZELLIJ_PANE_ID:-}" ]] || [[ -n "${ZELLIJ+set}" ]]
}

_vetcoders_guess_active_zellij_session() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
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
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
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
  _vetcoders_workflow_script "vc-operator" "mission-control/zellij-gc.sh"
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
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local session_name="$1"
  local layout_file="$2"
  shift 2

  _vetcoders_require_zellij || return 1

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
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local runtime="${1:-$(_vetcoders_default_runtime)}"
  local session_name layout_file
  _vetcoders_normalize_ambient_context
  _vetcoders_auto_gc_dead_zellij_sessions

  case "$runtime" in
    terminal|visible) ;;
    *) return 0 ;;
  esac

  # If we are already inside a Zellij session, naturally attach to it.
  if _vetcoders_in_zellij; then
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
    return 0
  fi

  if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
    return 0
  fi

  # If spawned by a headless agent, attempt to naturally latch onto the user's active session.
  local guessed_session
  guessed_session="$(_vetcoders_guess_active_zellij_session)"
  if [[ -n "$guessed_session" ]]; then
    export VIBECRAFTED_OPERATOR_SESSION="$guessed_session"
    return 0
  fi

  # No attachable session exists, so the only remaining option is to CREATE
  # one — which zellij cannot do without a real PTY. Without a controlling TTY
  # (scripts, CI, in-repo agent dispatch), degrade to headless instead of
  # hard-failing: leave VIBECRAFTED_OPERATOR_SESSION unset and return success so
  # the caller proceeds down the session-free dispatch path. The test bypass env
  # lets the suite exercise the create branch without a real TTY.
  # "brak TTY → headless" (runtime invariant: degrade, don't die).
  if [[ ! -t 0 || ! -t 1 ]] && [[ -z "${VIBECRAFTED_TEST_ALLOW_NON_TTY_ZELLIJ:-}" ]]; then
    printf 'no TTY; running headless (no operator session)\n' >&2
    return 0
  fi

  session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  layout_file="$(_vetcoders_operator_layout_file 2>/dev/null || true)"
  [[ -n "$layout_file" ]] || return 1

  if _vetcoders_ensure_zellij_session "$session_name" "$layout_file"; then
    export VIBECRAFTED_OPERATOR_SESSION="$session_name"
    return 0
  fi

  printf 'Failed to prepare Zellij operator session: %s\n' "$session_name" >&2
  return 1
}

_vetcoders_spawn_into_operator_session() {
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
  local tab_name="$1"
  local command_text="$2"
  local session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  local root_dir="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  local layout_file state
  local cmd_script

  _vetcoders_require_zellij || return 1
  if ! _vetcoders_in_zellij && [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
    layout_file="$(_vetcoders_operator_layout_file 2>/dev/null || true)"
    state="$(_vetcoders_zellij_session_state "$session_name")"
    if [[ "$state" != "live" ]]; then
      _vetcoders_ensure_zellij_session "$session_name" "$layout_file" || return 1
      export VIBECRAFTED_OPERATOR_SESSION="$session_name"
    fi
  fi
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


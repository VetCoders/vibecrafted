# shellcheck shell=bash
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers (bash/zsh compatible)
# Source this from your $HOME/.bashrc or $HOME/.zshrc to get consistent wrapper commands
# for the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework installed under your local repository path.
# These are shell functions, not standalone binaries. Non-interactive callers
# should use an interactive shell so $HOME/.zshrc sources this file; fall back
# to `bash -ic` on bash-only systems.
# Compatibility loader for central runtime helpers.
# Keep this file intentionally small so the skill tree remains a wrapper.
_vetcoders_script_dir() {
  local script_path="${BASH_SOURCE[0]:-$0}"
  local current_dir
  current_dir="$(cd "$(dirname "$script_path")" && pwd)"
  printf '%s\n' "$current_dir"
}

_vetcoders_runtime_repo_root() {
  local cursor
  cursor="$(_vetcoders_script_dir)"

  while [[ "$cursor" != "/" && -n "$cursor" ]]; do
    if [[ -f "$cursor/VERSION" && -f "$cursor/scripts/vibecrafted" ]]; then
      printf '%s\n' "$cursor"
      return 0
    fi
    cursor="$(cd "$cursor/.." && pwd)"
  done

  return 1
}

_vetcoders_runtime_helper_candidates() {
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s/runtime/helpers/vetcoders-runtime-core.sh\n' "${VIBECRAFTED_ROOT}"
  fi
  local repo_root
  repo_root="$(_vetcoders_runtime_repo_root 2>/dev/null || true)"
  if [[ -n "$repo_root" ]]; then
    printf '%s/runtime/helpers/vetcoders-runtime-core.sh\n' "$repo_root"
  fi
  printf '%s/tools/vibecrafted-current/runtime/helpers/vetcoders-runtime-core.sh\n' "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
}

_vetcoders_source_runtime_helpers() {
  local helper
  while IFS= read -r helper; do
    [[ -n "$helper" && -r "$helper" ]] || continue
    # shellcheck disable=SC1090
    source "$helper"
    return 0
  done < <(_vetcoders_runtime_helper_candidates)

  printf '%s\n' "Missing vetcoders runtime helpers in:" >&2
  _vetcoders_runtime_helper_candidates >&2
  return 1
}

_vetcoders_runtime_source_status=0
_vetcoders_source_runtime_helpers || {
  _vetcoders_runtime_source_status=$?
  unset -f _vetcoders_script_dir \
    _vetcoders_runtime_repo_root \
    _vetcoders_runtime_helper_candidates \
    _vetcoders_source_runtime_helpers
  if (return 0 2>/dev/null); then
    return "${_vetcoders_runtime_source_status}"
  fi
  exit "${_vetcoders_runtime_source_status}"
}
unset -f _vetcoders_script_dir \
  _vetcoders_runtime_repo_root \
  _vetcoders_runtime_helper_candidates \
  _vetcoders_source_runtime_helpers
unset _vetcoders_runtime_source_status
_vetcoders_default_runtime() {
  printf '%s\n' "${VETCODERS_SPAWN_RUNTIME:-terminal}"
}

_vetcoders_bundled_bin_dirs() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  [[ -d "$crafted_home/bin" ]] && printf '%s\n' "$crafted_home/bin"
  if [[ "$crafted_home" != "$HOME/.vibecrafted" ]]; then
    [[ -d "$HOME/.vibecrafted/bin" ]] && printf '%s\n' "$HOME/.vibecrafted/bin"
  fi
}

_vetcoders_path_with_bundled_bin_priority() {
  local current_path="${1:-}"
  local bundled_path=""
  local dir
  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    case ":$current_path:" in
      *":$dir:"*) ;;
      *) bundled_path="${bundled_path:+$bundled_path:}$dir" ;;
    esac
  done < <(_vetcoders_bundled_bin_dirs)
  printf '%s\n' "${bundled_path:+$bundled_path${current_path:+:}}$current_path"
}

_vetcoders_zellij_missing_message() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  echo "zellij is required for the Vibecrafted operator runtime." >&2
  echo "Expected zellij on PATH or bundled at: $crafted_home/bin/zellij" >&2
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
  local session_name layout_file state command_text zellij_bin zellij_cmd
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

  session_name="${VIBECRAFTED_OPERATOR_SESSION:-$(_vetcoders_operator_session_name)}"
  command -v zellij >/dev/null 2>&1 || return 0
  zellij_bin="$(command -v zellij)"
  zellij_cmd="$(_vetcoders_shell_quote "$zellij_bin")"

  layout_file="$(_vetcoders_operator_layout_file 2>/dev/null || true)"
  [[ -n "$layout_file" ]] || return 0

  state="$(_vetcoders_zellij_session_state "$session_name")"
  case "$state" in
    live)
      export VIBECRAFTED_OPERATOR_SESSION="$session_name"
      return 0
      ;;
    dead)
      "$zellij_bin" kill-session "$session_name" 2>/dev/null || true
      command_text="$zellij_cmd attach \"$session_name\" 2>/dev/null || $zellij_cmd --session \"$session_name\" --new-session-with-layout \"$layout_file\""
      ;;
    *)
      command_text="$zellij_cmd attach \"$session_name\" 2>/dev/null || $zellij_cmd --session \"$session_name\" --new-session-with-layout \"$layout_file\""
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
    polarize|vc-polarize) printf 'polarize\n' ;;
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
  _vetcoders_contract_task=""
  _vetcoders_contract_session=""
  _vetcoders_contract_count=""
  _vetcoders_contract_depth=""
  _vetcoders_contract_runtime=""
  _vetcoders_contract_root=""
  _vetcoders_contract_tail=""
  _vetcoders_contract_no_aicx=""
  _vetcoders_contract_no_context_corpus=""
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
      -f|--file)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --file" >&2; return 1; }
        _vetcoders_contract_file="$1"
        ;;
      --task)
        shift
        [[ $# -gt 0 ]] || { echo "Missing value for --task" >&2; return 1; }
        _vetcoders_contract_task="$1"
        ;;
      --no-aicx)
        _vetcoders_contract_no_aicx=1
        ;;
      --no-context-corpus)
        _vetcoders_contract_no_context_corpus=1
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

_vetcoders_polarize_prism_axes() {
  local task="$1"
  printf '%s\n' "$task"
  printf '%s\n' "$task code truth"
  printf '%s\n' "$task product truth"
}

_vetcoders_polarize_prism_command_text() {
  local root="$1"
  local task="$2"
  local no_aicx="${3:-}"
  local args=(loct prism --project "$root")
  if [[ "$no_aicx" == "1" ]]; then
    args+=(--no-aicx)
  else
    args+=(--with-aicx)
  fi
  while IFS= read -r axis; do
    [[ -n "$axis" ]] || continue
    args+=(--task "$axis")
  done < <(_vetcoders_polarize_prism_axes "$task")
  args+=(--json)
  _vetcoders_shell_quote_join "${args[@]}"
}

_vetcoders_write_polarize_prism_payload() {
  local root="$1"
  local run_id="$2"
  local task="$3"
  local no_aicx="${4:-}"
  local out_dir payload_file command_file
  local -a prism_args

  command -v loct >/dev/null 2>&1 || {
    echo "vc-polarize requires loct for prism preflight; loct not found on PATH." >&2
    return 1
  }

  out_dir="$(_vetcoders_store_dir "$root")/polarize/$run_id"
  mkdir -p "$out_dir"
  payload_file="$out_dir/prism.json"
  command_file="$out_dir/prism.command.txt"

  prism_args=(prism --project "$root")
  if [[ "$no_aicx" == "1" ]]; then
    prism_args+=(--no-aicx)
  else
    prism_args+=(--with-aicx)
  fi
  while IFS= read -r axis; do
    [[ -n "$axis" ]] || continue
    prism_args+=(--task "$axis")
  done < <(_vetcoders_polarize_prism_axes "$task")
  prism_args+=(--json)

  printf '%s\n' "$(_vetcoders_polarize_prism_command_text "$root" "$task" "$no_aicx")" > "$command_file"
  (cd "$root" && loct "${prism_args[@]}") > "$payload_file" || {
    echo "vc-polarize prism preflight failed. Command: $(cat "$command_file")" >&2
    return 1
  }

  printf '%s\n' "$payload_file"
}

_vetcoders_polarize_score() {
  local prism_json="$1"
  python3 - "$prism_json" <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(int(data.get("total_score", 0)))
PY
}

_vetcoders_polarize_band_select() {
  local prism_json="$1"
  python3 - "$prism_json" <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
band_action = str(data.get("band_action", "")).strip().lower()
if band_action in {"abort", "memo", "pass", "doctrine"}:
    print(band_action)
    raise SystemExit(0)
score = int(data.get("total_score", 0))
if score < 5:
    print("abort")
elif score < 9:
    print("memo")
elif score < 13:
    print("pass")
else:
    print("doctrine")
PY
}

_vetcoders_polarize_band_range() {
  case "${1:-}" in
    abort) printf '0..4\n' ;;
    memo) printf '5..8\n' ;;
    pass) printf '9..12\n' ;;
    doctrine) printf '13..15\n' ;;
    *) printf 'unknown\n' ;;
  esac
}

_vetcoders_capture_session_uuid() {
  local agent_log="$1"
  [[ -r "$agent_log" ]] || return 0
  grep -oE 'session: [0-9a-f-]{36}' "$agent_log" | tail -n1 | awk '{print $2}'
}

_vetcoders_write_polarize_memo() {
  local prism_json="$1"
  local run_id="$2"
  local root="$3"
  local task="${4:-}"
  local band="${5:-memo}"
  local score memo_file

  score="$(_vetcoders_polarize_score "$prism_json")" || return 1
  memo_file="$(_vetcoders_store_dir "$root")/polarize/$run_id/memo.md"
  mkdir -p "$(dirname "$memo_file")"
  {
    printf '# vc-polarize memo\n\n'
    printf 'Run: %s\n' "$run_id"
    printf 'Band: %s (score %s/15)\n' "$band" "$score"
    [[ -z "$task" ]] || printf 'Task: %s\n' "$task"
    printf 'Prism payload: %s\n\n' "$prism_json"
    printf 'Runner action: memo only. No full polarize agent pass was dispatched.\n'
  } > "$memo_file"
  printf '%s\n' "$memo_file"
}

_vetcoders_polarize_emit_context_pack() {
  local agent="$1"
  local session_uuid="$2"
  local prism_json="$3"
  local run_id="$4"
  local target_repo="$5"
  local band="$6"
  local task="${7:-}"
  local org_repo org repo date pack_dir slug raw_path sidecar_path

  org_repo="$(_vetcoders_org_repo "$target_repo" 2>/dev/null || true)"
  if [[ "$org_repo" == */* ]]; then
    org="${org_repo%%/*}"
    repo="${org_repo##*/}"
  else
    org="local"
    repo="$(basename "$target_repo")"
  fi

  date="$(date +%Y_%m%d)"
  pack_dir="$HOME/.aicx/context-corpus/$org/$repo/$date/loct-context-pack/$run_id"
  slug="${run_id}_${band}"
  raw_path="$pack_dir/raw/${slug}.md"
  sidecar_path="$pack_dir/sidecars/${slug}.json"
  mkdir -p "$pack_dir/raw" "$pack_dir/sidecars"

  if [[ "$band" == "memo" ]]; then
    local memo_file
    memo_file="$(_vetcoders_write_polarize_memo "$prism_json" "$run_id" "$target_repo" "$task" "$band")" || return 0
    cp "$memo_file" "$raw_path" || return 0
  else
    [[ -n "$session_uuid" ]] || {
      printf 'vc-polarize: no session UUID found; skipping context-pack emission.\n' >&2
      return 0
    }
    command -v aicx >/dev/null 2>&1 || {
      printf 'vc-polarize: aicx not found; skipping context-pack emission. Use --no-context-corpus to silence this optional step.\n' >&2
      return 0
    }
    aicx extract --agent "$agent" --session "$session_uuid" --output "$raw_path" || {
      printf 'vc-polarize: aicx extract failed for session %s; skipping context-pack emission.\n' "$session_uuid" >&2
      return 0
    }
  fi

  python3 - "$prism_json" "$sidecar_path" "$band" "$target_repo" "$slug" "$raw_path" "$task" <<'PY'
import hashlib
import json
import pathlib
import re
import subprocess
import sys

prism_path, sidecar_path, band, target_repo, slug, raw_path, task = sys.argv[1:]
prism = json.loads(pathlib.Path(prism_path).read_text(encoding="utf-8"))
try:
    head = subprocess.check_output(
        ["git", "-C", target_repo, "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
except Exception:
    head = "unknown"

terms = []
for framing in prism.get("task_framings", []):
    value = framing.get("task", "")
    terms.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", value.lower()))
terms.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", task.lower()))
keywords = sorted(set(terms)) or ["polarize"]
allowed = ["format_examples"] if band == "memo" else [
    "format_examples",
    "section_order",
    "keyword_index",
]
raw_bytes = pathlib.Path(raw_path).read_bytes()
sidecar = {
    "schema_version": "context_corpus.v1",
    "artifact_family": "loct-context-pack",
    "truth_status": {
        "role": "example",
        "runtime_authoritative": False,
        "stale_against_current_head": False,
        "current_head_when_ingested": head,
    },
    "learning_use": {
        "allowed": allowed,
        "forbidden": ["current_code_truth", "implementation_claims", "gate_status"],
    },
    "keywords": keywords,
    "band": band,
    "total_score": prism.get("total_score"),
    "slug": slug,
    "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
}
sidecar_file = pathlib.Path(sidecar_path)
sidecar_file.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
index_entry = {
    "id": slug,
    "path": f"raw/{slug}.md",
    "artifact_family": "loct-context-pack",
    "schema_version": "context_corpus.v1",
    "truth_status.role": "example",
    "keywords": keywords,
    "band": band,
}
idx_path = sidecar_file.parent.parent / "index.jsonl"
with idx_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(index_entry, sort_keys=True) + "\n")
PY
}

_vetcoders_compose_polarize_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local task="${3:-}"
  local payload_file="${4:-}"
  local prism_command="${5:-}"
  local band="${6:-}"
  local score="${7:-}"
  local base payload_body

  base="$(_vetcoders_compose_skill_prompt "polarize" "$prompt_text" "$file_path")" || return 1
  if [[ -n "$task" ]]; then
    base+=$'\n\n'
    base+="Polarize task: $task"
  fi
  if [[ -n "$band" && -n "$score" ]]; then
    base+=$'\n'
    base+="Band: $band (score $score/15)"
    base+=$'\n'
    base+="Runner action: $band"
  fi
  if [[ -n "$payload_file" ]]; then
    payload_body="$(cat "$payload_file")"
    base+=$'\n\n'
    base+="Prism preflight command: $prism_command"
    base+=$'\n'
    base+="Prism payload file: $payload_file"
    base+=$'\n\n'
    base+="The full prism payload is injected below. Treat it as the starting evidence pack, then verify live runtime truth before editing."
    base+=$'\n\n```json\n'
    base+="$payload_body"
    base+=$'\n```'
  fi

  printf '%s\n' "$base"
}

_vetcoders_research_file_body() {
  local file_path="$1"

  python3 - "$file_path" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

if lines and lines[0].strip() == "---":
    body_start = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = idx + 1
            break
    if body_start is not None:
        text = "".join(lines[body_start:]).lstrip("\n")

print(text, end="")
PY
}

_vetcoders_compose_research_worker_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local combined="$prompt_text"

  if [[ -n "$file_path" ]]; then
    _vetcoders_require_file "$file_path" || return 1
    local abs_file
    abs_file="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"
    local file_body
    file_body="$(_vetcoders_research_file_body "$file_path")" || return 1
    if [[ -n "$combined" ]]; then
      combined+=$'\n\n'
    fi
    combined+="Research plan file: $abs_file"
    combined+=$'\n\n'
    combined+="$file_body"
  fi

  printf '%s\n' "$combined"
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
    agy)
      printf 'agy --prompt-interactive --dangerously-skip-permissions --add-dir . %s' "$quoted_prompt"
      ;;
    junie)
      printf 'junie --task=%s --project=. --skip-update-check --use-local-cache' "$quoted_prompt"
      ;;
    grok)
      printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen --single %s' "$quoted_prompt"
      ;;
    *)
      echo "Unsupported init agent: $tool" >&2
      return 1
      ;;
  esac
}

# Operator-mode launcher helpers — parallel to init helpers above.
# vc-operator is NOT a dispatchable Iter-3 worker mode; it is an
# interactive session entry point per the vc-init pattern. Invocation
# opens the operator's primary tab in zellij with the agent of choice
# preloaded with the /vc-operator skill prompt.

_vetcoders_operator_runtime() {
  local runtime="${1:-terminal}"
  case "$runtime" in
    terminal|visible)
      printf '%s\n' "$runtime"
      ;;
    *)
      echo "vc-operator is interactive-only: use --runtime terminal or visible." >&2
      return 1
      ;;
  esac
}

_vetcoders_compose_operator_prompt() {
  local prompt_text="${1:-}"
  local file_path="${2:-}"
  local operator_prompt="/vc-operator"
  local extra

  extra="$(_vetcoders_compose_input_context "$prompt_text" "$file_path")" || return 1
  if [[ -n "$extra" ]]; then
    operator_prompt+=$'\n\n'
    operator_prompt+="$extra"
  fi

  printf '%s' "$operator_prompt"
}

_vetcoders_operator_command_text() {
  local tool="$1"
  local operator_prompt="$2"
  local quoted_prompt
  quoted_prompt="$(_vetcoders_shell_quote "$operator_prompt")"

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
    agy)
      printf 'agy --prompt-interactive --dangerously-skip-permissions --add-dir . %s' "$quoted_prompt"
      ;;
    junie)
      printf 'junie --task=%s --project=. --skip-update-check --use-local-cache' "$quoted_prompt"
      ;;
    grok)
      printf 'grok --cwd . --permission-mode bypassPermissions --no-alt-screen --single %s' "$quoted_prompt"
      ;;
    *)
      echo "Unsupported operator agent: $tool" >&2
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
  local runtime
  runtime="$(_vetcoders_default_runtime)"
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

_vetcoders_dispatch_skill_prompt() {
  local tool="$1"
  local skill="$2"
  local skill_code="$3"
  local loop_nr="$4"
  local run_id="$5"
  local run_lock="$6"
  local prompt="$7"
  shift 7

  (
    # shellcheck disable=SC2030
    export VIBECRAFTED_RUN_ID="$run_id"
    # shellcheck disable=SC2030
    export VIBECRAFTED_RUN_LOCK="$run_lock"
    # shellcheck disable=SC2030
    export VIBECRAFTED_SKILL_CODE="$skill_code"
    # shellcheck disable=SC2030
    export VIBECRAFTED_LOOP_NR="$loop_nr"
    # shellcheck disable=SC2030
    export VIBECRAFTED_SKILL_NAME="$skill"
    _vetcoders_prompt_text "$tool" implement "$prompt" "$@"
  )
}

_vetcoders_launch_receipt_field() {
  local json_path="$1"
  local field_name="$2"
  [[ -f "$json_path" ]] || return 0
  python3 - "$json_path" "$field_name" <<'PY'
import json
import sys

path, field = sys.argv[1:3]
try:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

value = payload.get(field, "")
if value is None:
    value = ""
print(value, end="")
PY
}

_vetcoders_print_launch_receipt() {
  local tool="$1"
  local skill="$2"
  local run_id="$3"
  local root="$4"
  local dispatch_rc="${5:-0}"
  local crafted_home control_json status report transcript launcher

  [[ "${VIBECRAFTED_SUPPRESS_LAUNCH_RECEIPT:-0}" != "1" ]] || return 0
  [[ -n "$run_id" ]] || return 0

  crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  control_json="$crafted_home/control_plane/runs/${run_id}.json"

  status="$(_vetcoders_launch_receipt_field "$control_json" "state")"
  [[ -n "$status" ]] || status="$(_vetcoders_launch_receipt_field "$control_json" "status")"
  report="$(_vetcoders_launch_receipt_field "$control_json" "latest_report")"
  [[ -n "$report" ]] || report="$(_vetcoders_launch_receipt_field "$control_json" "report")"
  transcript="$(_vetcoders_launch_receipt_field "$control_json" "latest_transcript")"
  [[ -n "$transcript" ]] || transcript="$(_vetcoders_launch_receipt_field "$control_json" "transcript")"
  launcher="$(_vetcoders_launch_receipt_field "$control_json" "launcher")"

  printf '\n'
  printf '==================== VIBECRAFTED LAUNCH RECEIPT ====================\n'
  printf 'run_id:     %s\n' "$run_id"
  printf 'agent:      %s\n' "$tool"
  printf 'skill:      %s\n' "$skill"
  printf 'root:       %s\n' "$root"
  printf 'dispatch:   %s\n' "$dispatch_rc"
  [[ -z "$status" ]] || printf 'status:     %s\n' "$status"
  printf 'control:    %s\n' "$control_json"
  [[ -z "$report" ]] || printf 'report:     %s\n' "$report"
  [[ -z "$transcript" ]] || printf 'transcript: %s\n' "$transcript"
  [[ -z "$launcher" ]] || printf 'launcher:   %s\n' "$launcher"
  printf 'observe:    vibecrafted %s observe --run-id %s\n' "$tool" "$run_id"
  printf 'await:      vibecrafted %s await --run-id %s\n' "$tool" "$run_id"
  printf '=====================================================================\n'
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

_vetcoders_loop() {
  local script
  script="$(_vetcoders_frontier_file "runtime/scripts/vibecrafted-loop.sh" 2>/dev/null || true)"
  if [[ -z "$script" && -n "${VIBECRAFTED_ROOT:-}" ]]; then
    script="${VIBECRAFTED_ROOT}/runtime/scripts/vibecrafted-loop.sh"
  fi
  [[ -n "$script" && -f "$script" ]] || {
    echo "vibecrafted loop runtime script not found." >&2
    return 1
  }
  bash "$script" "$@"
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

agy-review() {
  _vetcoders_spawn_plan agy review "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-plan() {
  _vetcoders_spawn_plan agy plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

agy-implement() {
  _vetcoders_spawn_plan agy implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-review() {
  _vetcoders_spawn_plan junie review "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-plan() {
  _vetcoders_spawn_plan junie plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-implement() {
  _vetcoders_spawn_plan junie implement "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-review() {
  _vetcoders_spawn_plan grok review "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-plan() {
  _vetcoders_spawn_plan grok plan "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-implement() {
  _vetcoders_spawn_plan grok implement "$1" --runtime "$(_vetcoders_default_runtime)"
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

agy-research() {
  _vetcoders_spawn_plan agy research "$1" --runtime "$(_vetcoders_default_runtime)"
}

junie-research() {
  _vetcoders_spawn_plan junie research "$1" --runtime "$(_vetcoders_default_runtime)"
}

grok-research() {
  _vetcoders_spawn_plan grok research "$1" --runtime "$(_vetcoders_default_runtime)"
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

agy-prompt() {
  _vetcoders_prompt agy implement "$@"
}

junie-prompt() {
  _vetcoders_prompt junie implement "$@"
}

grok-prompt() {
  _vetcoders_prompt grok implement "$@"
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

agy-observe() {
  _vetcoders_observe agy "$@"
}

agy-await() {
  _vetcoders_await agy "$@"
}

junie-observe() {
  _vetcoders_observe junie "$@"
}

junie-await() {
  _vetcoders_await junie "$@"
}

grok-observe() {
  _vetcoders_observe grok "$@"
}

grok-await() {
  _vetcoders_await grok "$@"
}

_vetcoders_skill() {
  local tool="$1"
  local skill="$2"
  shift 2
  # shellcheck disable=SC2031
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
  local skill_code root run_id run_lock
  skill_code="$(_vetcoders_skill_prefix "$skill")"
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "$skill_code")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    run_lock="$(_vetcoders_create_run_lock "$run_id" "$tool" "$skill" "$root")" || return 1
  fi
  local prompt prism_payload prism_command prism_band prism_score memo_file
  if [[ "$skill" == "polarize" && -n "$_vetcoders_contract_task" ]]; then
    prism_payload="$(_vetcoders_write_polarize_prism_payload "$root" "$run_id" "$_vetcoders_contract_task" "$_vetcoders_contract_no_aicx")" || return 1
    prism_command="$(_vetcoders_polarize_prism_command_text "$root" "$_vetcoders_contract_task" "$_vetcoders_contract_no_aicx")"
    prism_band="$(_vetcoders_polarize_band_select "$prism_payload")" || return 1
    prism_score="$(_vetcoders_polarize_score "$prism_payload")" || return 1
    case "$prism_band" in
      abort)
        printf 'vc-polarize aborted: prism score %s/15 is below threshold. Inspect %s\n' "$prism_score" "$prism_payload" >&2
        return 12
        ;;
      memo)
        memo_file="$(_vetcoders_write_polarize_memo "$prism_payload" "$run_id" "$root" "$_vetcoders_contract_task" "$prism_band")" || return 1
        if [[ -z "$_vetcoders_contract_no_context_corpus" ]]; then
          _vetcoders_polarize_emit_context_pack "$tool" "" "$prism_payload" "$run_id" "$root" "$prism_band" "$_vetcoders_contract_task"
        else
          printf 'vc-polarize: --no-context-corpus set; skipped context-corpus emission.\n' >&2
        fi
        printf 'vc-polarize: emitted local memo (band %s, score %s/15). No agent dispatched. Memo: %s\n' "$(_vetcoders_polarize_band_range "$prism_band")" "$prism_score" "$memo_file"
        return 0
        ;;
      pass|doctrine)
        prompt="$(_vetcoders_compose_polarize_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file" "$_vetcoders_contract_task" "$prism_payload" "$prism_command" "$prism_band" "$prism_score")" || return 1
        ;;
      *)
        printf 'vc-polarize: unknown prism band %s from %s\n' "$prism_band" "$prism_payload" >&2
        return 1
        ;;
    esac
  else
    if [[ -n "$_vetcoders_contract_task" ]]; then
      if [[ -n "$_vetcoders_contract_prompt" ]]; then
        _vetcoders_contract_prompt+=$'\n\n'
      fi
      _vetcoders_contract_prompt+="Task: $_vetcoders_contract_task"
    fi
    prompt="$(_vetcoders_compose_skill_prompt "$skill" "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  fi
  local spawn_args=(--runtime "$(_vetcoders_effective_runtime)")
  [[ -n "$_vetcoders_contract_root" ]] && spawn_args+=(--root "$_vetcoders_contract_root")
  if [[ "$skill" == "polarize" && "$prism_band" =~ ^(pass|doctrine)$ ]]; then
    local dispatch_output dispatch_status agent_log session_uuid
    agent_log="$(_vetcoders_store_dir "$root")/polarize/$run_id/${tool}.stdout.log"
    mkdir -p "$(dirname "$agent_log")"
    dispatch_output="$(_vetcoders_dispatch_skill_prompt "$tool" "$skill" "$skill_code" "$loop_nr" "$run_id" "$run_lock" "$prompt" "${spawn_args[@]}")"
    dispatch_status=$?
    printf '%s\n' "$dispatch_output"
    printf '%s\n' "$dispatch_output" > "$agent_log"
    _vetcoders_print_launch_receipt "$tool" "$skill" "$run_id" "$root" "$dispatch_status"
    [[ "$dispatch_status" -eq 0 ]] || return "$dispatch_status"
    if [[ -z "$_vetcoders_contract_no_context_corpus" ]]; then
      session_uuid="$(_vetcoders_capture_session_uuid "$agent_log")"
      _vetcoders_polarize_emit_context_pack "$tool" "$session_uuid" "$prism_payload" "$run_id" "$root" "$prism_band" "$_vetcoders_contract_task"
    else
      printf 'vc-polarize: --no-context-corpus set; skipped context-corpus emission.\n' >&2
    fi
    return 0
  fi

  _vetcoders_dispatch_skill_prompt "$tool" "$skill" "$skill_code" "$loop_nr" "$run_id" "$run_lock" "$prompt" "${spawn_args[@]}"
  local _dispatch_rc=$?
  _vetcoders_print_launch_receipt "$tool" "$skill" "$run_id" "$root" "$_dispatch_rc"
  _vetcoders_maybe_spawn_await_pane "$tool" "$skill" "$run_id" "$root"
  return "$_dispatch_rc"
}

# Spawn a zellij side-pane running vibecrafted-await-watch for the just-fired
# worker, so the operator gets live transcript tail + automatic exit when the
# worker is done (status=completed/failed, or wrapper dies + transcript idle).
#
# Silent no-op unless:
#   - the operator is inside an active zellij session
#   - the await-watch helper is installed and executable
#   - jq is available (helper needs it to parse meta.json)
#
# Resolves meta.json by greping the artifacts dir for a meta whose .run_id
# matches the freshly-launched dispatch's run_id. Worker filename is
# prompt_id-based, not run_id-based, so content grep is the only reliable
# resolver.
_vetcoders_maybe_spawn_await_pane() {
  local tool="$1" skill="$2" run_id="$3" root="$4"
  command -v zellij >/dev/null 2>&1 || return 0
  _vetcoders_in_zellij || return 0
  command -v jq >/dev/null 2>&1 || return 0

  local helper
  helper="$(_vetcoders_frontier_file "skills/vc-agents/scripts/vibecrafted-await-watch.sh" 2>/dev/null || true)"
  [[ -n "$helper" && -x "$helper" ]] || return 0

  # Best effort: short delay so the wrapper has a moment to drop meta.json.
  ( sleep 1
    local pane_name="await:${tool}:${run_id##*-}"
    local cwd="${root:-$PWD}"
    zellij action new-pane \
      --name "$pane_name" \
      --close-on-exit \
      --cwd "$cwd" \
      -- "$helper" --run-id "$run_id" >/dev/null 2>&1 || true
  ) &
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
  local run_dir="$7"
  local script output launcher

  script="$(_vetcoders_spawn_script "$tool" "${tool}_spawn.sh")" || return 1
  output="$(
    env \
      VIBECRAFTED_RUN_ID="$run_id" \
      VIBECRAFTED_RUN_LOCK="$run_lock" \
      VIBECRAFTED_SKILL_CODE="rsch" \
      VIBECRAFTED_SKILL_NAME="research" \
      VIBECRAFTED_RESEARCH_MODE="1" \
      VIBECRAFTED_STORE_DIR="$run_dir" \
      VIBECRAFTED_STORE_ROOT="$root" \
      VIBECRAFTED_RESEARCH_RUN_DIR="$run_dir" \
      bash "$script" --dry-run --mode research --runtime "$runtime" --root "$root" "$prompt_file" 2>&1
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

_vetcoders_runtime_manifest_path() {
  local candidate
  for candidate in \
    "${VIBECRAFTED_ROOT:-}" \
    "$(_vetcoders_repo_root)" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current"
  do
    [[ -n "$candidate" && -f "$candidate/install.toml" ]] || continue
    printf '%s/install.toml\n' "$candidate"
    return 0
  done
  return 1
}

_vetcoders_research_agents() {
  local manifest

  if [[ -n "${VIBECRAFTED_RESEARCH_AGENTS:-}" ]]; then
    printf '%s\n' "${VIBECRAFTED_RESEARCH_AGENTS}" | tr ', ' '\n' | awk 'NF'
    return 0
  fi

  manifest="$(_vetcoders_runtime_manifest_path 2>/dev/null || true)"
  if [[ -n "$manifest" ]]; then
    python3 - "$manifest" <<'PY' 2>/dev/null && return 0
import sys
try:
    import tomllib
except ModuleNotFoundError:
    sys.exit(1)

with open(sys.argv[1], "rb") as handle:
    data = tomllib.load(handle)

agents = (
    data.get("runtime", {})
    .get("picking", {})
    .get("research", {})
    .get("default_agents", [])
)
for agent in agents:
    if isinstance(agent, str) and agent.strip():
        print(agent.strip())
PY
  fi

  printf '%s\n' claude codex junie
}

_vetcoders_write_research_layout() {
  local layout_file="$1"
  shift
  local entry agent script

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
EOF

  for entry in "$@"; do
    agent="${entry%%=*}"
    script="${entry#*=}"
    [[ -n "$agent" && "$agent" != "$entry" ]] || continue
    cat >> "$layout_file" <<EOF
                pane name="$agent" command="bash" {
                    args "$script"
                }
EOF
  done

  cat >> "$layout_file" <<EOF
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
Triple-agent research swarm launcher (claude + codex + junie by default).

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
  local prompt root run_id run_lock runtime run_dir prompt_file layout_file summary_file
  local session_name agent launcher cmd_file
  local -a research_agents launchers launcher_entries command_entries

  for _arg in "$@"; do
    case "$_arg" in
      help|-h|--help)
        _vetcoders_research_help
        return 0
        ;;
    esac
  done

  case "$first_arg" in
    claude|codex|gemini|agy|junie|grok)
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

  prompt="$(_vetcoders_compose_research_worker_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  root="${_vetcoders_contract_root:-$(_vetcoders_repo_root)}"
  runtime="$(_vetcoders_effective_runtime)"

  inherited_run_id="$(_vetcoders_effective_run_id 2>/dev/null || true)"
  inherited_run_lock="$(_vetcoders_effective_run_lock 2>/dev/null || true)"
  run_id="$inherited_run_id"
  [[ -n "$run_id" ]] || run_id="$(_vetcoders_generate_run_id "rsch")"
  run_lock="$inherited_run_lock"
  if [[ -z "$run_lock" || ! -f "$run_lock" ]]; then
    run_lock="$(_vetcoders_create_run_lock "$run_id" "swarm" "research" "$root")" || return 1
  fi

  run_dir="$(_vetcoders_research_run_dir "$root" "$run_id")"
  mkdir -p "$run_dir/plans" "$run_dir/reports" "$run_dir/logs" "$run_dir/tmp"
  prompt_file="$(_vetcoders_research_prompt_file "$run_dir" "$prompt")" || return 1

  research_agents=()
  while IFS= read -r agent; do
    case "$agent" in
      claude|codex|gemini|agy|junie|grok) research_agents+=("$agent") ;;
      "") ;;
      *) printf 'Ignoring unsupported research agent from runtime picking config: %s\n' "$agent" >&2 ;;
    esac
  done < <(_vetcoders_research_agents)
  if (( ${#research_agents[@]} == 0 )); then
    research_agents=(claude codex junie)
  fi

  launchers=()
  launcher_entries=()
  for agent in "${research_agents[@]}"; do
    launcher="$(_vetcoders_research_launcher_path "$agent" "$prompt_file" "$root" "$run_id" "$run_lock" "$runtime" "$run_dir")" || return 1
    launchers+=("$launcher")
    launcher_entries+=("$agent=$launcher")
  done

  summary_file="$(_vetcoders_write_research_summary "$run_dir" "$run_id" "$root" "$prompt_file" "${launcher_entries[@]}")" || return 1

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

    layout_file="$run_dir/tmp/research.kdl"

    command_entries=()
    for entry in "${launcher_entries[@]}"; do
      agent="${entry%%=*}"
      launcher="${entry#*=}"
      cmd_file="$run_dir/tmp/${agent}_cmd.sh"
      _vetcoders_write_command_script "$cmd_file" "bash $(_vetcoders_shell_quote "$launcher")" || return 1
      command_entries+=("$agent=$cmd_file")
    done
    _vetcoders_write_research_layout "$layout_file" "${command_entries[@]}"

    # Intended exports to env for the zellij child process — false-positive SC2031.
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_ID="$run_id"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RUN_LOCK="$run_lock"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_CODE="rsch"
    # shellcheck disable=SC2031
    export VIBECRAFTED_SKILL_NAME="research"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RESEARCH_MODE="1"
    # shellcheck disable=SC2031
    export VIBECRAFTED_STORE_DIR="$run_dir"
    # shellcheck disable=SC2031
    export VIBECRAFTED_STORE_ROOT="$root"
    # shellcheck disable=SC2031
    export VIBECRAFTED_RESEARCH_RUN_DIR="$run_dir"
    zellij --session "$session_name" action new-tab --layout "$layout_file" >/dev/null
    printf 'Research swarm launched in shared tab (run_id=%s).\n' "$run_id"
    printf '  run dir: %s\n' "$run_dir"
    printf '  reports: %s\n' "$run_dir/reports"
    printf '  summary: %s\n' "$summary_file"
    _vetcoders_await "" --describe "${launchers[@]}" || true
    printf '\nAwait:\n\n'
    printf 'vc-research-await --run-id %s\n' "$run_id"
    return 0
  fi

  printf 'Research swarm prepared (run_id=%s), but runtime %s does not use the shared zellij layout.\n' "$run_id" "$runtime"
  printf 'Run directory: %s\n' "$run_dir"
  printf 'Reports: %s\n' "$run_dir/reports"
  printf 'Summary: %s\n' "$summary_file"
  printf 'Launchers:\n'
  for entry in "${launcher_entries[@]}"; do
    agent="${entry%%=*}"
    launcher="${entry#*=}"
    printf '  %s: %s\n' "$agent" "$launcher"
  done
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

  _vetcoders_require_zellij || return 1

  runtime="$(_vetcoders_init_runtime "${_vetcoders_contract_runtime:-terminal}")" || return 1
  init_prompt="$(_vetcoders_compose_init_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  command_text="$(_vetcoders_init_command_text "$tool" "$init_prompt")" || return 1

  _vetcoders_prepare_operator_runtime "$runtime" || return 1
  _vetcoders_spawn_into_operator_session "${tool}-init" "$command_text"
}

# vc-operator launcher — interactive operator session entry point.
# Behaves like _vetcoders_skill_init: spawns a zellij session with the
# selected agent preloaded with the /vc-operator skill prompt. NOT a
# background Iter-3 dispatchable mode.
_vetcoders_skill_operator() {
  local tool="$1"
  shift
  local runtime operator_prompt command_text

  _vetcoders_parse_contract "$@" || return 1
  [[ -z "$_vetcoders_contract_count" ]] || {
    echo "--count is not supported by vibecrafted operator." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_depth" ]] || {
    echo "--depth is not supported by vibecrafted operator." >&2
    return 1
  }
  [[ -z "$_vetcoders_contract_session" ]] || {
    echo "--session is not supported by vibecrafted operator." >&2
    return 1
  }

  _vetcoders_require_zellij || return 1

  runtime="$(_vetcoders_operator_runtime "${_vetcoders_contract_runtime:-terminal}")" || return 1
  operator_prompt="$(_vetcoders_compose_operator_prompt "$_vetcoders_contract_prompt" "$_vetcoders_contract_file")" || return 1
  command_text="$(_vetcoders_operator_command_text "$tool" "$operator_prompt")" || return 1

  _vetcoders_prepare_operator_runtime "$runtime" || return 1
  _vetcoders_spawn_into_operator_session "${tool}-operator" "$command_text"
}

codex-dou() { _vetcoders_skill codex dou "$@"; }
claude-dou() { _vetcoders_skill claude dou "$@"; }
gemini-dou() { _vetcoders_skill gemini dou "$@"; }
agy-dou() { _vetcoders_skill agy dou "$@"; }
junie-dou() { _vetcoders_skill junie dou "$@"; }
grok-dou() { _vetcoders_skill grok dou "$@"; }

codex-hydrate() { _vetcoders_skill codex hydrate "$@"; }
claude-hydrate() { _vetcoders_skill claude hydrate "$@"; }
gemini-hydrate() { _vetcoders_skill gemini hydrate "$@"; }
agy-hydrate() { _vetcoders_skill agy hydrate "$@"; }
junie-hydrate() { _vetcoders_skill junie hydrate "$@"; }
grok-hydrate() { _vetcoders_skill grok hydrate "$@"; }

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
  if [[ -n "$_vetcoders_contract_task" ]]; then
    [[ -z "$_vetcoders_contract_file" ]] || {
      echo "Marbles accepts one file source: use either --task or --file, not both." >&2
      return 1
    }
    _vetcoders_contract_file="$_vetcoders_contract_task"
  fi

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
    VIBECRAFTED_OPERATOR_SESSION="$(_vetcoders_current_zellij_session_name)"
    export VIBECRAFTED_OPERATOR_SESSION
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

    printf 'Marbles run launched in zellij tab: %s\n' "$marbles_tab_name"
    printf '  run_id:  %s\n' "$marbles_run_id"
    printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      
    if [[ -n "$original_tab" ]]; then
      zellij action go-to-tab-name "$original_tab" >/dev/null 2>&1 || true
    fi
    
    _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
  elif [[ "$runtime" =~ ^(terminal|visible)$ ]]; then
    _vetcoders_prepare_operator_runtime "$runtime" || return 1
    if [[ -n "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
      _vetcoders_spawn_into_operator_session "marbles" "$marbles_cmd" || return 1
      printf 'Marbles run launched in operator session: %s\n' "$VIBECRAFTED_OPERATOR_SESSION"
      printf '  run_id:  %s\n' "$marbles_run_id"
      printf '  inspect: vc-marbles inspect %s\n' "$marbles_run_id"
      _vetcoders_marbles_emit_probe "$root_dir" "$marbles_run_id" "launched"
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
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] --session <session_id> [--prompt <text>] [--file <path>]" >&2
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
    agy)
      if [[ -n "$resume_prompt" ]]; then
        agy --conversation "$_vetcoders_contract_session" --prompt-interactive "$resume_prompt"
      else
        agy --conversation "$_vetcoders_contract_session"
      fi
      ;;
    junie)
      if [[ -n "$resume_prompt" ]]; then
        junie --session-id="$_vetcoders_contract_session" --resume --task="$resume_prompt" --project=. --skip-update-check
      else
        junie --session-id="$_vetcoders_contract_session" --resume --project=. --skip-update-check
      fi
      ;;
    grok)
      if [[ -n "$resume_prompt" ]]; then
        grok --resume "$_vetcoders_contract_session" --cwd . --permission-mode bypassPermissions --no-alt-screen --single "$resume_prompt"
      else
        grok --resume "$_vetcoders_contract_session" --cwd . --permission-mode bypassPermissions --no-alt-screen
      fi
      ;;
    *)
      echo "Unknown agent for resume: $tool" >&2
      return 1
      ;;
  esac
}

_vetcoders_agent_for_session() {
  local session_id="$1"
  [[ -n "$session_id" ]] || return 1
  python3 - "$session_id" "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/artifacts" <<'PY'
import json
import pathlib
import sys

session_id, artifacts_root = sys.argv[1:3]
root = pathlib.Path(artifacts_root)
if not root.is_dir():
    raise SystemExit(1)

matches = []
for meta_path in root.rglob("*.meta.json"):
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    if payload.get("session_id") != session_id:
        continue
    agent = payload.get("agent")
    if agent:
        try:
            mtime = meta_path.stat().st_mtime
        except OSError:
            mtime = 0
        matches.append((mtime, agent))

if not matches:
    raise SystemExit(1)
print(sorted(matches)[-1][1])
PY
}

vc-resume() {
  local tool="${1:-}"
  [[ -n "$tool" ]] || {
    echo "Usage: vc-resume [<claude|codex|gemini|agy|junie|grok>] --session <session_id> [--prompt <text>] [--file <path>]" >&2
    return 1
  }
  if [[ "$tool" == "--session" ]]; then
    _vetcoders_parse_contract "$@" || return 1
    tool="$(_vetcoders_agent_for_session "$_vetcoders_contract_session")" || {
      echo "Could not infer agent for session: $_vetcoders_contract_session" >&2
      echo "Usage: vc-resume <claude|codex|gemini|agy|junie|grok> --session $_vetcoders_contract_session" >&2
      return 1
    }
  else
    shift || true
  fi
  _vetcoders_resume_agent "$tool" "$@"
}

codex-marbles() { _vetcoders_marbles codex "$@"; }
claude-marbles() { _vetcoders_marbles claude "$@"; }
gemini-marbles() { _vetcoders_marbles gemini "$@"; }
agy-marbles() { _vetcoders_marbles agy "$@"; }
junie-marbles() { _vetcoders_marbles junie "$@"; }
grok-marbles() { _vetcoders_marbles grok "$@"; }

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
agy-decorate() { _vetcoders_skill agy decorate "$@"; }
junie-decorate() { _vetcoders_skill junie decorate "$@"; }
grok-decorate() { _vetcoders_skill grok decorate "$@"; }

codex-followup() { _vetcoders_skill codex followup "$@"; }
claude-followup() { _vetcoders_skill claude followup "$@"; }
gemini-followup() { _vetcoders_skill gemini followup "$@"; }
agy-followup() { _vetcoders_skill agy followup "$@"; }
junie-followup() { _vetcoders_skill junie followup "$@"; }
grok-followup() { _vetcoders_skill grok followup "$@"; }

codex-prune() { _vetcoders_skill codex prune "$@"; }
claude-prune() { _vetcoders_skill claude prune "$@"; }
gemini-prune() { _vetcoders_skill gemini prune "$@"; }
agy-prune() { _vetcoders_skill agy prune "$@"; }
junie-prune() { _vetcoders_skill junie prune "$@"; }
grok-prune() { _vetcoders_skill grok prune "$@"; }

codex-scaffold() { _vetcoders_skill codex scaffold "$@"; }
claude-scaffold() { _vetcoders_skill claude scaffold "$@"; }
gemini-scaffold() { _vetcoders_skill gemini scaffold "$@"; }
agy-scaffold() { _vetcoders_skill agy scaffold "$@"; }
junie-scaffold() { _vetcoders_skill junie scaffold "$@"; }
grok-scaffold() { _vetcoders_skill grok scaffold "$@"; }

codex-release() { _vetcoders_skill codex release "$@"; }
claude-release() { _vetcoders_skill claude release "$@"; }
gemini-release() { _vetcoders_skill gemini release "$@"; }
agy-release() { _vetcoders_skill agy release "$@"; }
junie-release() { _vetcoders_skill junie release "$@"; }
grok-release() { _vetcoders_skill grok release "$@"; }

codex-justdo() { _vetcoders_skill codex justdo "$@"; }
claude-justdo() { _vetcoders_skill claude justdo "$@"; }
gemini-justdo() { _vetcoders_skill gemini justdo "$@"; }
agy-justdo() { _vetcoders_skill agy justdo "$@"; }
junie-justdo() { _vetcoders_skill junie justdo "$@"; }
grok-justdo() { _vetcoders_skill grok justdo "$@"; }

codex-partner() { _vetcoders_skill codex partner "$@"; }
claude-partner() { _vetcoders_skill claude partner "$@"; }
gemini-partner() { _vetcoders_skill gemini partner "$@"; }
agy-partner() { _vetcoders_skill agy partner "$@"; }
junie-partner() { _vetcoders_skill junie partner "$@"; }
grok-partner() { _vetcoders_skill grok partner "$@"; }

codex-skill-agents() { _vetcoders_skill_entry codex agents "$@"; }
claude-skill-agents() { _vetcoders_skill_entry claude agents "$@"; }
gemini-skill-agents() { _vetcoders_skill_entry gemini agents "$@"; }

codex-skill-audit() { _vetcoders_skill_entry codex audit "$@"; }
claude-skill-audit() { _vetcoders_skill_entry claude audit "$@"; }
gemini-skill-audit() { _vetcoders_skill_entry gemini audit "$@"; }

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

codex-skill-polarize() { _vetcoders_skill_entry codex polarize "$@"; }
claude-skill-polarize() { _vetcoders_skill_entry claude polarize "$@"; }
gemini-skill-polarize() { _vetcoders_skill_entry gemini polarize "$@"; }

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
      printf 'Usage: vc-init <claude|codex|gemini|agy|junie|grok> [--prompt <text>] [--file <path>]\n' >&2
      ;;
    marbles)
      printf 'Usage: vc-marbles <claude|codex|gemini|agy|junie|grok> [--prompt <text>|--file <path>|--depth <n>] [--count <n>]\n' >&2
      printf '       vc-marbles <pause|stop|resume|session|inspect|delete|gc> [args]\n' >&2
      ;;
    polarize)
      printf 'Usage: vc-polarize <claude|codex|gemini|agy|junie|grok> --task <text> [--prompt <text>] [--file <path>] [--no-aicx] [--no-context-corpus]\n' >&2
      printf '       vc-polarize <claude|codex|gemini|agy|junie|grok> [--prompt <text>] [--file <path>]\n' >&2
      ;;
    *)
      printf 'Usage: vc-%s <claude|codex|gemini|agy|junie|grok> [--prompt <text>] [--file <path>]\n' "$skill" >&2
      ;;
  esac
}

_vetcoders_has_agent() {
  local candidate="${1:-}"
  case "$candidate" in
    claude|codex|gemini|agy|junie|grok) return 0 ;;
    *) return 1 ;;
  esac
}

_vetcoders_is_help_flag() {
  local candidate="${1:-}"
  [[ "$candidate" == "help" || "$candidate" == "-h" || "$candidate" == "--help" ]]
}

_vetcoders_skill_wrapper() {
  local skill="$1"
  shift || true

  local tool="${1:-}"
  if [[ "$skill" == "marbles" ]]; then
    case "$tool" in
      pause|stop|resume|session|inspect|delete|gc)
        shift || true
        "marbles-$tool" "$@"
        return
        ;;
    esac
  fi

  [[ -n "$tool" ]] || {
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  _vetcoders_has_agent "$tool" || {
    printf 'vc-%s expects <claude|codex|gemini|agy|junie|grok> as the first argument.\n' "$skill" >&2
    _vetcoders_skill_wrapper_usage "$skill"
    return 1
  }
  shift || true

  if _vetcoders_is_help_flag "${1:-}"; then
    _vetcoders_skill_wrapper_usage "$skill"
    return 0
  fi

  case "$skill" in
    init) _vetcoders_skill_init "$tool" "$@" ;;
    operator) _vetcoders_skill_operator "$tool" "$@" ;;
    marbles) _vetcoders_marbles "$tool" "$@" ;;
    *) _vetcoders_skill_entry "$tool" "$skill" "$@" ;;
  esac
}

vc-agents() { _vetcoders_skill_wrapper agents "$@"; }
vc-audit() { _vetcoders_skill_wrapper audit "$@"; }
vc-decorate() { _vetcoders_skill_wrapper decorate "$@"; }
vc-delegate() { _vetcoders_skill_wrapper delegate "$@"; }
vc-dou() { _vetcoders_skill_wrapper dou "$@"; }
vc-followup() { _vetcoders_skill_wrapper followup "$@"; }
vc-hydrate() { _vetcoders_skill_wrapper hydrate "$@"; }
vc-init() { _vetcoders_skill_wrapper init "$@"; }
vc-intents() { _vetcoders_skill_wrapper intents "$@"; }
vc-justdo() { _vetcoders_skill_wrapper justdo "$@"; }
vc-implement() { _vetcoders_skill_wrapper justdo "$@"; }
vc-loop() { _vetcoders_loop "$@"; }
vc-marbles() { _vetcoders_skill_wrapper marbles "$@"; }
vc-operator() { _vetcoders_skill_wrapper operator "$@"; }
vc-ownership() { _vetcoders_skill_wrapper ownership "$@"; }
vc-partner() { _vetcoders_skill_wrapper partner "$@"; }
vc-polarize() { _vetcoders_skill_wrapper polarize "$@"; }
vc-prune() { _vetcoders_skill_wrapper prune "$@"; }
vc-release() { _vetcoders_skill_wrapper release "$@"; }
vc-review() { _vetcoders_skill_wrapper review "$@"; }
vc-scaffold() { _vetcoders_skill_wrapper scaffold "$@"; }
vc-workflow() { _vetcoders_skill_wrapper workflow "$@"; }

vc-help() {
  local crafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
  cat <<'HELP'
𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Framework — Skills & Helpers

Pipeline:  scaffold → init → workflow → implement → followup → marbles → audit → dou → decorate → hydrate → release
Modes:     partner (shared steering) | ownership (take the wheel)
Research:  research (triple-agent) | delegate (in-session)
Quality:   audit (plan falsification) | review (bounded diff/PR/commit) | followup (post-implementation direction) | prune
Video:     screenscribe (foundation)

Spawn helpers (per agent):
  <agent>-implement <plan.md>    Full implementation from plan
  <agent>-review <plan.md>       Bounded PR, branch, commit-range, or artifact review
  <agent>-plan <plan.md>         Planning only
  <agent>-prompt "text"          Quick one-shot prompt
  <agent>-scaffold                Architecture planning
  <agent>-followup               Post-implementation direction audit
  <agent>-skill-audit            Plan-vs-code falsification
  <agent>-dou                    Definition of Undone audit
  <agent>-hydrate                Market packaging
  <agent>-marbles                Convergence loop
  <agent>-decorate               Visual polish
  <agent>-release                Ship to market
  <agent>-prune                  Repo pruning
  <agent>-skill-implement        Autonomous e2e implementation (vc-implement)
  <agent>-justdo                 Alias for autonomous e2e implementation
  <agent>-partner                Collaborative partner mode with the user in the loop
  <agent>-observe --last         Check last report
  <agent>-await --last           Wait for metadata completion + summary

Swarm launchers:
  vc-research --prompt "text"    Triple-agent research swarm
  vc-research-await --last       Wait for the latest research swarm

Command deck:
  vibecrafted help               Main command surface
  vibecrafted <skill> <agent>    Run a repo skill via the launcher
  vibecrafted resume <agent>     Resume a previous session
  vibecrafted loop start --file plan.md --completion-promise READY
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

_repo_full_rescue_emit_txt() {
  local file="$1"
  awk '
    /^REPO:/ || /^REMOTE:/ || /^BRANCH:/ || /^HEAD:/ || /^UPSTREAM:/ { print }
    /^===== STATUS =====/ { p=1; print; next }
    /^===== LOCAL DIFF FILES =====/ { p=1; print; next }
    /^===== LOCAL DIFF MATCHES ONLY =====/ { p=1; print; next }
    /^===== RELEASE\/WATCH\/LSP\/MCP COMMIT MSG MATCHES SINCE MAY 1 =====/ { p=1; print; next }
    /^===== STASHES =====/ { p=1; print; next }
    /^===== STASH MATCHES =====/ { p=1; print; next }
    /^===== CURRENT TREE MATCHES/ { p=0; next }
    /^===== RECENT COMMITS SINCE MAY 1/ { p=0; next }
    /^===== / && p { p=0 }
    p { print }
  ' "$file" | sed '/^$/N;/^\n$/D'
}

_repo_full_rescue_emit_patch() {
  local file="$1"
  local max_matches="${REPO_RESCUE_MAX_MATCHES:-120}"
  local pattern='release|publish|homebrew|npm|watch|lsp|mcp|install|aicx|fallback|sign|notary|formula|loctree-mcp|loctree-lsp|artifact|prebuilt|postinstall'

  echo "----- PATCH STAT -----"
  git apply --stat "$file" 2>/dev/null || awk '
    /^diff --git / {
      old=$3; new=$4;
      sub(/^a\//, "", old);
      sub(/^b\//, "", new);
      print old " -> " new;
    }
  ' "$file" | awk 'NF && !seen[$0]++'

  echo
  echo "----- MATCHED SIGNALS (bounded) -----"
  if command -v rg >/dev/null 2>&1; then
    rg -n -i "$pattern" "$file" | head -n "$max_matches"
  else
    awk -v pat="$pattern" -v max="$max_matches" '
      BEGIN { IGNORECASE=1 }
      $0 ~ pat {
        print FNR ":" $0;
        count++;
        if (count >= max) exit;
      }
    ' "$file"
  fi
}

_repo_full_rescue_emit_plain() {
  local file="$1"
  local max_lines="${REPO_RESCUE_MAX_LINES:-120}"
  local pattern='repo|remote|branch|head|upstream|status|stash|diff|release|publish|homebrew|npm|watch|lsp|mcp|install|aicx|fallback'
  if command -v rg >/dev/null 2>&1; then
    rg -n -i "$pattern" "$file" | head -n "$max_lines"
  else
    awk -v pat="$pattern" -v max="$max_lines" '
      BEGIN { IGNORECASE=1 }
      $0 ~ pat {
        print FNR ":" $0;
        count++;
        if (count >= max) exit;
      }
    ' "$file"
  fi
}

_repo_full_rescue_emit_file() {
  local file="$1"
  local bytes lines
  bytes="$(wc -c < "$file" | tr -d ' ')"
  lines="$(wc -l < "$file" | tr -d ' ')"

  echo
  echo "================================================================================"
  echo "### $(basename "$file")"
  echo "Path:  $file"
  echo "Size:  $bytes bytes"
  echo "Lines: $lines"
  echo

  case "$file" in
    *.patch|*.diff) _repo_full_rescue_emit_patch "$file" ;;
    *.txt) _repo_full_rescue_emit_txt "$file" ;;
    *.md|*.markdown) _repo_full_rescue_emit_plain "$file" ;;
    *) echo "Skipped: unsupported rescue evidence type." ;;
  esac
}

_repo_full_rescue() {
  local rescue_dir="${1:-${REPO_RESCUE_DIR:-$HOME/Desktop/loctree-release-rescue}}"
  local pattern="${2:-*}"
  local root branch head files_found=0 file

  if [[ ! -d "$rescue_dir" ]]; then
    echo "Rescue directory not found: $rescue_dir"
    echo "Usage: repo-full --rescue [evidence-dir] [glob]"
    return 1
  fi

  root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  branch="$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "DETACHED_OR_NO_GIT")"
  head="$(git rev-parse --short HEAD 2>/dev/null || echo "no-git")"

  echo "==================== REPO RESCUE ===================="
  echo "Working dir:       $(pwd)"
  echo "Root:              $root"
  echo "Branch:            $branch"
  echo "HEAD short:        $head"
  echo "Evidence dir:      $rescue_dir"
  echo "Evidence glob:     $pattern"
  echo "Generated at:      $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo

  while IFS= read -r file; do
    files_found=1
    _repo_full_rescue_emit_file "$file"
  done < <(find "$rescue_dir" -maxdepth 1 -type f -name "$pattern" -print 2>/dev/null | sort)

  [[ "$files_found" != "0" ]] || echo "No rescue evidence files matched."
  echo
  echo "==================== RESCUE DONE ===================="
}

repo-full() {
  if [[ "${1:-}" == "--rescue" ]]; then
    shift
    _repo_full_rescue "$@"
    return
  fi

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

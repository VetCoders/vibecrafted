# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

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
  local PATH="${PATH:-}"
  PATH="$(_vetcoders_path_with_bundled_bin_priority "$PATH")"
  export PATH
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


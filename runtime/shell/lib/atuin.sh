# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

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


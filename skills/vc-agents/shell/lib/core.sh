# shellcheck shell=bash
# Extracted from vetcoders.sh; sourced only by the compatibility facade.

_vetcoders_script_dir() {
  local script_path=""
  if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    script_path="${BASH_SOURCE[0]}"
  elif [[ -n "${ZSH_VERSION:-}" ]]; then
    script_path="$(eval 'printf "%s\n" "${(%):-%x}"')"
  else
    script_path="$0"
  fi
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
  printf '%s/vibecrafted-current/runtime/helpers/vetcoders-runtime-core.sh\n' "${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}"
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
  local xdg_data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
  local runtime_bin="${VIBECRAFTED_RUNTIME_BIN:-${VIBECRAFTED_RUNTIME_HOME:-$xdg_data_home/vibecrafted}/bin}"
  [[ -d "$runtime_bin" ]] && printf '%s\n' "$runtime_bin"
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

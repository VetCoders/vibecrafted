# shellcheck shell=bash
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shell helpers (bash/zsh compatible)
# Compatibility facade. Public callers source this file; implementation lives in lib/*.sh.
# Keep the load order explicit and acyclic: modules do not source each other.

_vetcoders_shell_facade_dir() {
  local script_path=""
  if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    script_path="${BASH_SOURCE[0]}"
  elif [[ -n "${ZSH_VERSION:-}" ]]; then
    script_path="$(eval 'printf "%s\n" "${(%):-%x}"')"
  else
    script_path="$0"
  fi
  cd "$(dirname "$script_path")" && pwd
}

_vetcoders_shell_lib_candidates() {
  local facade_dir="$(_vetcoders_shell_facade_dir)"
  [[ -n "$facade_dir" ]] && printf '%s/lib\n' "$facade_dir"
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s/runtime/shell/lib\n' "$VIBECRAFTED_ROOT"
  fi
  printf '%s/vibecrafted-current/runtime/shell/lib\n' "${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}"
  printf '%s/runtime/shell/lib\n' "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
}

_vetcoders_resolve_shell_lib_dir() {
  local candidate
  while IFS= read -r candidate; do
    [[ -n "$candidate" && -r "$candidate/core.sh" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done < <(_vetcoders_shell_lib_candidates)
  return 1
}

_vetcoders_source_shell_module() {
  local module_name="$1"
  local module_path="${_vetcoders_shell_lib_dir}/${module_name}.sh"
  [[ -r "$module_path" ]] || {
    printf 'Missing Vibecrafted shell module: %s\n' "$module_path" >&2
    return 1
  }
  # shellcheck disable=SC1090
  source "$module_path"
}

_vetcoders_shell_lib_dir="$(_vetcoders_resolve_shell_lib_dir 2>/dev/null || true)"
if [[ -z "$_vetcoders_shell_lib_dir" ]]; then
  _vetcoders_runtime_helper="${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current/runtime/helpers/vetcoders-runtime-core.sh"
  if [[ -r "$_vetcoders_runtime_helper" ]]; then
    # shellcheck disable=SC1090
    source "$_vetcoders_runtime_helper"
    unset -f _vetcoders_shell_facade_dir _vetcoders_shell_lib_candidates _vetcoders_resolve_shell_lib_dir _vetcoders_source_shell_module
    unset _vetcoders_shell_lib_dir _vetcoders_runtime_helper
    return 0
  fi
  printf 'Missing Vibecrafted shell module directory. Checked:\n' >&2
  _vetcoders_shell_lib_candidates | sed 's/^/  - /' >&2
  unset -f _vetcoders_shell_facade_dir _vetcoders_shell_lib_candidates _vetcoders_resolve_shell_lib_dir _vetcoders_source_shell_module
  unset _vetcoders_shell_lib_dir _vetcoders_runtime_helper
  return 1
fi

# Load order: core -> runtime substrates -> workflow helpers -> public dispatch.
_vetcoders_source_shell_module core || return $?
_vetcoders_source_shell_module zellij || return $?
_vetcoders_source_shell_module frontier || return $?
_vetcoders_source_shell_module atuin || return $?
_vetcoders_source_shell_module dashboard || return $?
_vetcoders_source_shell_module prompts || return $?
_vetcoders_source_shell_module quote || return $?
_vetcoders_source_shell_module polarize || return $?
_vetcoders_source_shell_module research_prompts || return $?
_vetcoders_source_shell_module operator || return $?
_vetcoders_source_shell_module dispatch_core || return $?
_vetcoders_source_shell_module observe || return $?
_vetcoders_source_shell_module dispatch_wrappers || return $?
_vetcoders_source_shell_module research || return $?
_vetcoders_source_shell_module operator_entrypoints || return $?
_vetcoders_source_shell_module skill_shortcuts || return $?
_vetcoders_source_shell_module marbles || return $?
_vetcoders_source_shell_module dispatch || return $?

unset -f _vetcoders_shell_facade_dir _vetcoders_shell_lib_candidates _vetcoders_resolve_shell_lib_dir _vetcoders_source_shell_module
unset _vetcoders_shell_lib_dir

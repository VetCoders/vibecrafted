# shellcheck shell=bash
# Loader for the shared launcher rlimit helper. The implementation lives in
# runtime/scripts/lib/ulimits.sh so shell facades and worker launchers use one
# policy.

_vetcoders_source_launcher_ulimits() {
  local candidate
  for candidate in \
    "${_vetcoders_shell_lib_dir%/shell/lib}/scripts/lib/ulimits.sh" \
    "${VIBECRAFTED_ROOT:-}/runtime/scripts/lib/ulimits.sh" \
    "${VIBECRAFTED_TOOLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/vibecrafted/tools}/vibecrafted-current/runtime/scripts/lib/ulimits.sh" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/runtime/scripts/lib/ulimits.sh"; do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    # shellcheck disable=SC1090
    source "$candidate"
    vc_raise_launcher_limits
    return 0
  done
  printf '[warn] launcher ulimit helper not found; continuing without rlimit raise\n' >&2
  return 0
}

_vetcoders_source_launcher_ulimits
unset -f _vetcoders_source_launcher_ulimits

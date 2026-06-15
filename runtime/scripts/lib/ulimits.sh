# shellcheck shell=bash

# Shared launcher rlimit hardening. Source this before spawning vc-frame,
# zellij panes/tabs, or worker launchers.

vc_ulimit_warn() {
  printf '[warn] %s\n' "$*" >&2
}

vc_ulimit_is_positive_int() {
  case "${1:-}" in
    ''|*[!0-9]*) return 1 ;;
    0) return 1 ;;
    *) return 0 ;;
  esac
}

vc_ulimit_raise_nofile() {
  local requested="${VC_ULIMIT_NOFILE:-}"
  local hard=""
  local target=""

  if [[ -n "$requested" ]]; then
    target="$requested"
  else
    hard="$(ulimit -Hn 2>/dev/null || true)"
    if vc_ulimit_is_positive_int "$hard"; then
      target="$hard"
    else
      target="65536"
    fi
  fi

  if ulimit -S -n "$target" 2>/dev/null; then
    return 0
  fi

  if [[ -z "$requested" && "$target" != "65536" ]] && ulimit -S -n 65536 2>/dev/null; then
    return 0
  fi

  vc_ulimit_warn "could not raise open-file limit (ulimit -n) to ${target}; continuing"
  return 0
}

vc_ulimit_raise_fsize() {
  local target="${VC_ULIMIT_FSIZE:-unlimited}"
  [[ -n "$target" ]] || target="unlimited"

  if ulimit -S -f "$target" 2>/dev/null; then
    return 0
  fi

  vc_ulimit_warn "could not raise file-size limit (ulimit -f) to ${target}; continuing"
  return 0
}

vc_raise_launcher_limits() {
  vc_ulimit_raise_nofile
  vc_ulimit_raise_fsize
}

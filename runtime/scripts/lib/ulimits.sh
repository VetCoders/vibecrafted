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
  local soft="" hard="" target=""

  soft="$(ulimit -Sn 2>/dev/null || true)"
  hard="$(ulimit -Hn 2>/dev/null || true)"

  # Soft cap already unlimited: raising it can only LOWER the headroom the
  # fleet relies on. A clamp to a fixed number here (the old 65536) starves
  # high-FD agents into EMFILE crashes. Leave an unlimited soft cap alone.
  [[ "$soft" == "unlimited" ]] && return 0

  if [[ -n "$requested" ]]; then
    target="$requested"
  elif [[ "$hard" == "unlimited" ]]; then
    # Unlimited hard ceiling — lift the soft cap all the way to it. The kernel
    # still clamps real opens at kern.maxfilesperproc, so this never overshoots.
    target="unlimited"
  elif vc_ulimit_is_positive_int "$hard"; then
    target="$hard"
  else
    # No trustworthy ceiling to raise toward; leave the current limit as-is
    # rather than guessing a number that might be a decrease.
    return 0
  fi

  # Never DECREASE an existing numeric soft limit — only raise toward the hard
  # ceiling. This is the invariant that the old fixed-65536 fallback violated.
  if [[ "$target" != "unlimited" ]] \
     && vc_ulimit_is_positive_int "$soft" \
     && [[ "$target" -le "$soft" ]]; then
    return 0
  fi

  if ulimit -S -n "$target" 2>/dev/null; then
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

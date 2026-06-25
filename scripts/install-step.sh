#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: install-step.sh <step-name> -- <command> [args...]\n' >&2
}

if [[ $# -lt 3 || "${2:-}" != "--" ]]; then
  usage
  exit 2
fi

step_name="$1"
shift 2

log_path="${VIBECRAFTED_INSTALL_LOG:-$HOME/.vibecrafted/install.log}"
verbose="${VERBOSE:-0}"
mkdir -p "$(dirname "$log_path")"

printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$step_name" >>"$log_path"
printf '$' >>"$log_path"
for arg in "$@"; do
  printf ' %q' "$arg" >>"$log_path"
done
printf '\n' >>"$log_path"

fail() {
  local status="$1"
  printf '  ✗ %s\n\n' "$step_name" >&2
  printf 'Install failed during: %s\n\n' "$step_name" >&2
  # Surface the real error: install-step.sh redirects step output into the log,
  # so a bare "✗ <step>" is undebuggable in non-interactive/CI runs where the
  # log file is never inspected. Echo the tail to stderr so the failing command
  # output lands in the captured CI transcript.
  if [[ -f "$log_path" ]]; then
    printf '%s (last %d lines):\n' "$log_path" "${INSTALL_STEP_LOG_TAIL:-50}" >&2
    tail -n "${INSTALL_STEP_LOG_TAIL:-50}" "$log_path" >&2 || true
    printf '\n' >&2
  fi
  printf 'Log:\n  %s\n\n' "$log_path" >&2
  printf 'Next:\n  vibecrafted doctor\n' >&2
  return "$status"
}

if [[ "$verbose" == "1" ]]; then
  printf '  > %s\n' "$step_name"
  "$@" 2>&1 | tee -a "$log_path"
  status="${PIPESTATUS[0]}"
  if [[ "$status" -ne 0 ]]; then
    fail "$status"
    exit "$status"
  fi
  printf '  ✓ %s\n' "$step_name"
  exit 0
fi

if [[ -t 1 ]]; then
  (
    "$@" >>"$log_path" 2>&1
  ) &
  pid="$!"
  frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  index=0
  while kill -0 "$pid" 2>/dev/null; do
    printf '\r  %s %s' "${frames[$index]}" "$step_name"
    index=$(((index + 1) % ${#frames[@]}))
    sleep 0.1
  done
  if ! wait "$pid"; then
    status="$?"
    printf '\r'
    fail "$status"
    exit "$status"
  fi
  printf '\r  ✓ %s\n' "$step_name"
else
  if "$@" >>"$log_path" 2>&1; then
    printf '  ✓ %s\n' "$step_name"
  else
    status="$?"
    fail "$status"
    exit "$status"
  fi
fi

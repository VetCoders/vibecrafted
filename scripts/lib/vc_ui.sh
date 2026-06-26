# shellcheck shell=bash
# vc_ui.sh — 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. shared CLI output contract (bash side).
# Mirror of vibecrafted_core/ui.py — keep the two in lockstep.
#
# Contract (docs/CLI_PRODUCT_SPEC.md §3):
#   - one spinner (braille, copper, 80 ms), one success line, one error shape
#   - color only on a TTY, NO_COLOR honored, glyph is the prefix (no [error])
#   - stage messages are verb + object: scanning · resolving · staging ·
#     installing · finalizing
#
# Usage: source this file, then call vc_stage / vc_ok / vc_err / vc_warn /
# vc_next. Long-running sections wrap with vc_spin_start "scanning repo" and
# vc_spin_stop_ok "scanned repo".

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  VC_BOLD='\033[1m'
  VC_DIM='\033[2m'
  VC_COPPER='\033[38;5;173m'
  VC_STEEL='\033[38;5;247m'
  VC_GREEN='\033[32m'
  VC_YELLOW='\033[33m'
  VC_CYAN='\033[36m'
  VC_RED='\033[31m'
  VC_RESET='\033[0m'
else
  VC_BOLD='' VC_DIM='' VC_COPPER='' VC_STEEL='' VC_GREEN=''
  VC_YELLOW='' VC_CYAN='' VC_RED='' VC_RESET=''
fi
# Consumers style their own headers with the brand tokens.
export VC_BOLD VC_DIM VC_COPPER VC_STEEL VC_GREEN VC_YELLOW VC_CYAN VC_RED VC_RESET

VC_SPINNER_FRAMES='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
VC_SPINNER_PID=''

# vc_stage <message> — one bounded stage line (the non-animated form).
vc_stage() {
  printf '%b▸%b %s\n' "$VC_COPPER" "$VC_RESET" "$*"
}

# vc_ok <result> — success: one line, the key result only.
vc_ok() {
  printf '%b✓%b %s\n' "$VC_GREEN" "$VC_RESET" "$*"
}

# vc_warn <message> — warning: one line, optional, never apologetic.
vc_warn() {
  printf '%b!%b %s\n' "$VC_YELLOW" "$VC_RESET" "$*"
}

# vc_err <what failed> [fix] [log path] — error shape, always stderr.
vc_err() {
  printf '%b✗%b %s\n' "$VC_RED" "$VC_RESET" "$1" >&2
  [[ -n "${2:-}" ]] && printf '  %b→ fix:%b %s\n' "$VC_DIM" "$VC_RESET" "$2" >&2
  [[ -n "${3:-}" ]] && printf '  %blog: %s%b\n' "$VC_DIM" "$3" "$VC_RESET" >&2
  return 0
}

# vc_next <command> [hint] — exactly one next step, dim.
vc_next() {
  printf '  %b→ next:%b %b%s%b' "$VC_DIM" "$VC_RESET" "$VC_CYAN" "$1" "$VC_RESET"
  [[ -n "${2:-}" ]] && printf ' %b%s%b' "$VC_DIM" "$2" "$VC_RESET"
  printf '\n'
}

# vc_spin_start <message> — live spinner on a TTY, single ▸ line otherwise.
# The line is replaced on stop; a stage never occupies two lines.
vc_spin_start() {
  local message="$*"
  if [[ ! -t 1 || -n "${NO_COLOR:-}" ]]; then
    vc_stage "$message"
    return 0
  fi
  (
    local i=0 frame
    while :; do
      frame="${VC_SPINNER_FRAMES:$((i % 10)):1}"
      printf '\r\033[K%b%s%b %s' "$VC_COPPER" "$frame" "$VC_RESET" "$message"
      i=$((i + 1))
      sleep 0.08
    done
  ) &
  VC_SPINNER_PID=$!
}

_vc_spin_clear() {
  if [[ -n "$VC_SPINNER_PID" ]]; then
    kill "$VC_SPINNER_PID" 2>/dev/null || true
    wait "$VC_SPINNER_PID" 2>/dev/null || true
    VC_SPINNER_PID=''
    [[ -t 1 && -z "${NO_COLOR:-}" ]] && printf '\r\033[K'
  fi
  return 0
}

# vc_spin_stop_ok <result> — replace the spinner line with the success line.
vc_spin_stop_ok() {
  _vc_spin_clear
  vc_ok "$*"
}

# vc_spin_stop_err <what failed> [fix] [log path]
vc_spin_stop_err() {
  _vc_spin_clear
  vc_err "$@"
}

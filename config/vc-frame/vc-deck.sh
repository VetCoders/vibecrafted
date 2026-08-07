#!/usr/bin/env bash
# vc-deck — launch-or-focus a vc-terminal window hosting the vc-frame deck.
#
# The missing piece of the iTerm→vc-terminal migration: nothing on the system
# could summon a vc-terminal surface on demand (Hammerspoon, Spotlight,
# scripts). This script is that verb.
#
# Usage:
#   vc-deck.sh                     attach/focus the operator deck (default session: deck)
#   vc-deck.sh <session>           attach/focus a specific vc-frame session
#   vc-deck.sh --run '<command>'   open a new vc-terminal window running <command>
#
# Env:
#   VC_TERMINAL_BIN   override the alacritty binary inside vc-terminal.app
#   VC_DECK_SESSION   default session name (fallback: deck)
set -euo pipefail

VC_TERMINAL_BIN="${VC_TERMINAL_BIN:-/Applications/vc-terminal.app/Contents/MacOS/alacritty}"
SESSION="${VC_DECK_SESSION:-deck}"
RUN_CMD=""

die() {
  printf 'vc-deck: %s\n' "$1" >&2
  exit 1
}

case "${1:-}" in
  -h|--help)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  --run)
    [[ -n "${2:-}" ]] || die "--run requires a command string"
    RUN_CMD="$2"
    ;;
  "")
    ;;
  *)
    SESSION="$1"
    ;;
esac

[[ -x "$VC_TERMINAL_BIN" ]] || die "vc-terminal binary not found: $VC_TERMINAL_BIN"

# Any live alacritty IPC socket (socket name carries the owning pid).
live_socket() {
  local sock pid
  for sock in "${TMPDIR:-/tmp/}"Alacritty-*.sock; do
    [[ -e "$sock" ]] || continue
    pid="${sock##*Alacritty-}"
    pid="${pid%.sock}"
    if kill -0 "$pid" 2>/dev/null; then
      printf '%s\n' "$sock"
      return 0
    fi
  done
  return 1
}

# Spawn a vc-terminal window running the given command. Prefers a window in
# the live instance (msg create-window); cold-starts the app otherwise.
spawn_window() {
  local command_text="$1"
  local sock
  if sock="$(live_socket)"; then
    if "$VC_TERMINAL_BIN" msg --socket "$sock" create-window \
        -e /bin/zsh -lc "$command_text" 2>/dev/null; then
      open -a vc-terminal 2>/dev/null || true
      return 0
    fi
  fi
  open -na vc-terminal --args -e /bin/zsh -lc "$command_text"
}

if [[ -n "$RUN_CMD" ]]; then
  spawn_window "$RUN_CMD"
  exit 0
fi

# Launch-or-focus: if a client is already attached to this session, just bring
# the app forward instead of stacking another client onto the same session.
if pgrep -f "vc-frame attach ${SESSION}( |$)" >/dev/null 2>&1; then
  open -a vc-terminal
  exit 0
fi

# attach -c: resurrects an EXITED session or creates a fresh one — the deck
# comes up regardless of prior state.
spawn_window "vc-frame attach -c ${SESSION}"

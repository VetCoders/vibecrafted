#!/usr/bin/env bash
# vc-composer.sh — Command Composer with Paste Stack integration
#
# Contract (same door as compact-bar chip and Super+e / Alt+e):
#   1. Open a draft file in $VC_COMPOSER (or $EDITOR / vim)
#   2. Seed the draft from the top of the Paste Stack when empty / requested
#   3. On non-empty save: push body to Paste Stack, hide floating panes,
#      write-chars into the underlying pane (unexecuted — Enter is human)
#   4. Clean up the temp draft
#
# Install/symlink to:
#   ~/.config/vetcoders/frontier/vc-frame/vc-composer.sh
#   or ~/.config/vc-frame/vc-composer.sh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PASTE_STACK="${SCRIPT_DIR}/paste-stack.sh"
if [[ ! -x "$PASTE_STACK" ]]; then
  # Installed next to this script under config, or under assets during dev.
  for candidate in \
    "${HOME}/.config/vetcoders/frontier/vc-frame/paste-stack.sh" \
    "${HOME}/.config/vc-frame/paste-stack.sh" \
    "${SCRIPT_DIR}/paste-stack.sh"
  do
    if [[ -x "$candidate" ]]; then
      PASTE_STACK="$candidate"
      break
    fi
  done
fi

f="$(mktemp "${TMPDIR:-/tmp}/vc-composer.XXXXXX")" || exit 1
cleanup() { rm -f -- "$f"; }
trap cleanup EXIT

# Seed from Paste Stack top when the env asks for it (default: seed if stack
# has content and VC_COMPOSER_SEED is not "0").
seed="${VC_COMPOSER_SEED:-1}"
if [[ "$seed" != "0" && -x "$PASTE_STACK" ]]; then
  "$PASTE_STACK" top "$f" || true
fi

# VC_COMPOSER expands unquoted on purpose — command line, not a path.
# shellcheck disable=SC2086
${VC_COMPOSER:-${EDITOR:-vim}} "$f"

if [[ -s "$f" ]]; then
  if [[ -x "$PASTE_STACK" ]]; then
    "$PASTE_STACK" push "$f" || true
  fi
  # Hide the floating atelier so write-chars lands on the work pane beneath.
  vc-frame action toggle-floating-panes || true
  vc-frame action write-chars "$(cat -- "$f")"
fi

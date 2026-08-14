#!/usr/bin/env bash
# Push repo shell/deck sources into the active vibecrafted-current generation
# tree so interactive `zsh -ic 'vc-*'` picks up thin-alias + --help fixes.
#
# Usage (from repo root):
#   bash scripts/sync-vc-alias-runtime.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEN="${VIBECRAFTED_CURRENT:-$HOME/.local/share/vibecrafted/tools/vibecrafted-current}"
CANONICAL_DECK="$ROOT/vibecrafted-core/vibecrafted_core/deck/vibecrafted"
CHECKOUT_MIRROR="$ROOT/scripts/vibecrafted"

if [[ ! -d "$GEN" ]]; then
  printf 'sync-vc-alias-runtime: missing generation tree: %s\n' "$GEN" >&2
  printf 'Run vibecrafted update / make install-tools first.\n' >&2
  exit 1
fi

# The packaged deck is the runtime-generation entrypoint and the single source
# of truth. Keep the checkout-facing scripts path as an exact compatibility
# mirror; never overwrite the packaged owner from its projection.
cp -f "$CANONICAL_DECK" "$CHECKOUT_MIRROR"

copy_one() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  cp -f "$src" "$dest"
  printf 'synced %s\n' "$dest"
}

copy_one "$CANONICAL_DECK" "$GEN/scripts/vibecrafted"
copy_one "$CANONICAL_DECK" "$GEN/vibecrafted-core/vibecrafted_core/deck/vibecrafted"
copy_one "$ROOT/vibecrafted-core/vibecrafted_core/runtime/shell/lib/dispatch.sh" \
  "$GEN/runtime/shell/lib/dispatch.sh"
copy_one "$ROOT/vibecrafted-core/vibecrafted_core/runtime/shell/lib/marbles.sh" \
  "$GEN/runtime/shell/lib/marbles.sh"
# Nested package layout (some generations keep a full vibecrafted-core tree).
if [[ -d "$GEN/vibecrafted-core/vibecrafted_core/runtime/shell/lib" ]]; then
  copy_one "$ROOT/vibecrafted-core/vibecrafted_core/runtime/shell/lib/dispatch.sh" \
    "$GEN/vibecrafted-core/vibecrafted_core/runtime/shell/lib/dispatch.sh"
  copy_one "$ROOT/vibecrafted-core/vibecrafted_core/runtime/shell/lib/marbles.sh" \
    "$GEN/vibecrafted-core/vibecrafted_core/runtime/shell/lib/marbles.sh"
fi

printf 'sync-vc-alias-runtime: OK (generation=%s)\n' "$GEN"

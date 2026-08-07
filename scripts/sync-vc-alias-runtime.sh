#!/usr/bin/env bash
# Push repo shell/deck sources into the active vibecrafted-current generation
# tree so interactive `zsh -ic 'vc-*'` picks up thin-alias + --help fixes.
#
# Usage (from repo root):
#   bash scripts/sync-vc-alias-runtime.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEN="${VIBECRAFTED_CURRENT:-$HOME/.local/share/vibecrafted/tools/vibecrafted-current}"

if [[ ! -d "$GEN" ]]; then
  printf 'sync-vc-alias-runtime: missing generation tree: %s\n' "$GEN" >&2
  printf 'Run vibecrafted update / make install-tools first.\n' >&2
  exit 1
fi

# Keep packaged deck twin identical to scripts/vibecrafted (installers copy both).
cp -f "$ROOT/scripts/vibecrafted" "$ROOT/vibecrafted-core/vibecrafted_core/deck/vibecrafted"

copy_one() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  cp -f "$src" "$dest"
  printf 'synced %s\n' "$dest"
}

copy_one "$ROOT/scripts/vibecrafted" "$GEN/scripts/vibecrafted"
copy_one "$ROOT/scripts/vibecrafted" "$GEN/vibecrafted-core/vibecrafted_core/deck/vibecrafted"
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

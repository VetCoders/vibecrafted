#!/usr/bin/env bash
# ============================================================================
# vendor-src.sh — refresh src/ with clean tracked source for the builder stage.
#
# Foundations have no prebuilt linux/arm64 bundles, so the Containerfile builder
# compiles them from source. This script vendors that source as `git archive
# HEAD` of the sibling checkouts (tracked files only — no target/, no cruft, no
# .git, no private creds), keeping the Docker build context tiny (~54 MB).
#
# Run from vc-workspace/ before a fresh build if the sibling sources moved:
#   ./vendor-src.sh
#
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # vc-runtime multiroot
DEST="$SCRIPT_DIR/src"

rm -rf "$DEST"
mkdir -p "$DEST/aicx" "$DEST/loctree-suite"

for repo in aicx loctree-suite; do
  src="$RUNTIME_DIR/$repo"
  [ -d "$src/.git" ] || { echo "Error: $src is not a git checkout"; exit 1; }
  git config --global --add safe.directory "$src" 2>/dev/null || true
  head="$(git -C "$src" rev-parse --short HEAD)"
  dirty="$(git -C "$src" status --porcelain | grep -vc '^??' || true)"
  echo "  $repo @ $head  (uncommitted tracked: $dirty)"
  git -C "$src" archive HEAD | tar -x -C "$DEST/$repo"
done

cat > "$DEST/README.md" <<'EOF'
# vc-workspace/src — vendored build source (generated)

Clean tracked source (`git archive HEAD`) of `aicx` + `loctree-suite`, consumed
by the Containerfile builder stage. **Generated — do not edit by hand.**
Regenerate with `../vendor-src.sh`. Gitignored; not committed.
EOF

echo "Done -> $DEST"

#!/usr/bin/env bash
# pipeline-init.sh — Initialize canonical ERi artifact paths
# Usage: bash pipeline-init.sh <slug> [root-dir]
# Created by M&K (c)2024-2026 VetCoders

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../vc-agents/scripts/common.sh
source "$SCRIPT_DIR/../../vc-agents/scripts/common.sh"

SLUG="${1:?Usage: pipeline-init.sh <slug> [root-dir]}"
ROOT_INPUT="${2:-$(pwd)}"
ROOT="$(spawn_abspath "$ROOT_INPUT")"
[[ -d "$ROOT" ]] || spawn_die "Root directory not found: $ROOT"

# Canonical store: $VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/{plans,reports,tmp}/
STORE_BASE="$(spawn_store_dir "$ROOT")"
PLAN_DIR="$STORE_BASE/plans"
REPORT_DIR="$STORE_BASE/reports"
TMP_DIR="$STORE_BASE/tmp"
TS="$(spawn_timestamp)"
CONTEXT_FILE="$PLAN_DIR/${TS}_${SLUG}_CONTEXT.md"
RESEARCH_FILE="$PLAN_DIR/${TS}_${SLUG}_RESEARCH.md"

[[ ! -e "$CONTEXT_FILE" ]] || spawn_die "Context file already exists: $CONTEXT_FILE"

mkdir -p "$PLAN_DIR" "$REPORT_DIR" "$TMP_DIR"
spawn_link_repo_artifacts "$STORE_BASE" "$ROOT"

cat > "$CONTEXT_FILE" <<EOF
# Examination: $SLUG

Date: $(date +%Y-%m-%d)
Artifact Root: $STORE_BASE
Context File: $CONTEXT_FILE
Research File: $RESEARCH_FILE

## Repo Health
- <!-- fill from repo-view -->

## Task Understanding
- User request: <!-- original request -->
- Interpreted scope: <!-- what needs to change -->

## Target Modules
<!-- fill from focus() -->

## Critical Files (slice results)
| File | LOC | Dependencies | Consumers | Risk |
|------|-----|-------------|-----------|------|

## Existing Symbols
<!-- fill from find() -->

## Risk Map
| File | Blast Radius | Mitigation |
|------|-------------|------------|

## Open Questions (for Research phase)
1.

## Phase Decision
- [ ] Research needed
- [ ] Skip to Implement
EOF

echo "Workflow artifact day initialized: $STORE_BASE"
echo ""
echo "Created:"
echo "  $CONTEXT_FILE      (Phase 1: Examination output)"
echo ""
echo "Canonical layout:"
echo "  $PLAN_DIR          (plans, CONTEXT.md, RESEARCH.md)"
echo "  $REPORT_DIR        (spawned agent reports)"
echo "  $TMP_DIR           (runtime scratch)"
if [[ "$STORE_BASE" != "$ROOT/.vibecrafted" ]]; then
  echo ""
  echo "Convenience symlinks:"
  echo "  $ROOT/.vibecrafted/plans -> $PLAN_DIR"
  echo "  $ROOT/.vibecrafted/reports -> $REPORT_DIR"
fi
echo ""
echo "Next: Run Phase 1 (Examine) with loctree MCP tools"
echo "  If Phase 2 is needed, write: $RESEARCH_FILE"

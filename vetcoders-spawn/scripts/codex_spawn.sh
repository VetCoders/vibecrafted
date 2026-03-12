#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: codex_spawn.sh [--mode <mode>] [--runtime <terminal|visible|headless|background|detached>] [--root <repo-root>] [--dry-run] <plan.md>

Modes are labels for the artifact metadata, e.g. implement, review, or plan.
Runtime modes:
- terminal / visible: launch via Terminal.app
- headless / background / detached: run launcher as detached background process
- default: terminal
EOF_USAGE
}

mode="implement"
runtime="terminal"
root=""
plan_file=""
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --mode"
      mode="$1"
      ;;
    --runtime)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --runtime"
      runtime="$1"
      ;;
    --root)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --root"
      root="$1"
      ;;
    --dry-run)
      dry_run=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      [[ -z "$plan_file" ]] || spawn_die "Unexpected argument: $1"
      plan_file="$1"
      ;;
  esac
  shift
done

[[ -n "$plan_file" ]] || {
  usage
  exit 1
}
spawn_require_file "$plan_file"
spawn_validate_runtime "$runtime"
spawn_prepare_paths codex "$plan_file" "$root"
spawn_write_meta "$SPAWN_META" "launching" "codex" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER"

if (( !dry_run )); then
  spawn_require_command codex
fi

qroot="$(printf '%q' "$SPAWN_ROOT")"
qplan="$(printf '%q' "$SPAWN_PLAN")"
qreport="$(printf '%q' "$SPAWN_REPORT")"
qtranscript="$(printf '%q' "$SPAWN_TRANSCRIPT")"

launch_cmd="set -o pipefail && cd $qroot && codex exec -C $qroot --dangerously-bypass-approvals-and-sandbox --output-last-message $qreport - < $qplan 2>&1 | tee -a $qtranscript"

spawn_generate_launcher "$SPAWN_LAUNCHER" \
  "$SPAWN_META" \
  "$SPAWN_REPORT" \
  "$SPAWN_TRANSCRIPT" \
  "$SCRIPT_DIR/common.sh" \
  "$launch_cmd" \
  "" \
  "" \
  ""

chmod +x "$SPAWN_LAUNCHER"
spawn_print_launch codex "$mode" "$runtime"
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run"
printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"

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
success_hook_extra=""
failure_hook_extra=""

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
    --success-hook)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --success-hook"
      success_hook_extra="$1"
      ;;
    --failure-hook)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --failure-hook"
      failure_hook_extra="$1"
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
spawn_prepare_paths codex "$plan_file" "$root" "$mode"
spawn_scan_active "$SPAWN_REPORT_DIR"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_codex_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT" codex
spawn_write_meta "$SPAWN_META" "launching" "codex" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER"

if (( !dry_run )); then
  spawn_require_command codex
fi

qroot="$(printf '%q' "$SPAWN_ROOT")"
qruntime="$(printf '%q' "$runtime_input")"
qreport="$(printf '%q' "$SPAWN_REPORT")"
qtranscript="$(printf '%q' "$SPAWN_TRANSCRIPT")"

# Codex --json emits JSONL events. jq filter extracts readable text + tool tags + session ID.
qfilter="$(printf '%q' "$SCRIPT_DIR/codex_stream_filter.jq")"
launch_cmd="set -o pipefail && cd $qroot && codex exec -C $qroot --json --dangerously-bypass-approvals-and-sandbox --output-last-message $qreport - < $qruntime 2>&1 | grep --line-buffered '^{' | jq --unbuffered -rj -f $qfilter | tee -a $qtranscript ; echo ; { grep -o 'session: [a-f0-9-]*' $qtranscript 2>/dev/null | tail -1 | awk '{print \$2}' | xargs -I{} printf '\\n\\033[33m━━━ session: {} ━━━\\033[0m\\n'; } || true"

# shellcheck disable=SC2016
codex_success_hook='
  if [[ ! -s "$report" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "completed"
    cat >> "$report" <<TXT
Codex completed without writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

# shellcheck disable=SC2016
codex_failure_hook='
  if [[ ! -s "$report" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "failed"
    cat >> "$report" <<TXT
Codex failed before writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

combined_success="${codex_success_hook}${success_hook_extra:+
$success_hook_extra}"
combined_failure="${codex_failure_hook}${failure_hook_extra:+
$failure_hook_extra}"

spawn_generate_launcher "$SPAWN_LAUNCHER" \
  "$SPAWN_META" \
  "$SPAWN_REPORT" \
  "$SPAWN_TRANSCRIPT" \
  "$SCRIPT_DIR/common.sh" \
  "$launch_cmd" \
  "" \
  "$combined_success" \
  "$combined_failure"


chmod +x "$SPAWN_LAUNCHER"
spawn_print_launch codex "$mode" "$runtime"
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run" "codex-${VIBECRAFTED_SKILL_NAME:-$mode}"
printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"

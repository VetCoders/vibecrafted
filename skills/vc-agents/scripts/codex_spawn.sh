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
spawn_scan_active "${SPAWN_LOG_DIR:-$SPAWN_REPORT_DIR}"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_codex_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT" codex
spawn_write_meta "$SPAWN_META" "launching" "codex" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER"

if (( !dry_run )); then
  spawn_require_command codex
fi

qroot="$(spawn_shell_quote "$SPAWN_ROOT")"
qruntime="$(spawn_shell_quote "$runtime_input")"
qreport="$(spawn_shell_quote "$SPAWN_REPORT")"
qtranscript="$(spawn_shell_quote "$SPAWN_TRANSCRIPT")"
qraw="$(spawn_shell_quote "${SPAWN_TRANSCRIPT%.log}.raw.jsonl")"
qlast_message="$(spawn_shell_quote "${SPAWN_TRANSCRIPT%.log}.last-message.md")"
qbridge="$(spawn_shell_quote "$SCRIPT_DIR/codex_stream_bridge.py")"
bridge_flags=""
case "$runtime" in
  terminal|visible)
    bridge_flags="--echo-stdout"
    ;;
esac
last_message_fallback=""
missing_report_guard=""
if [[ "$mode" == "research" || "${VIBECRAFTED_SKILL_NAME:-}" == "research" || "${VIBECRAFTED_SKILL_CODE:-}" == "rsch" || "${VIBECRAFTED_RESEARCH_MODE:-0}" == "1" ]]; then
  # Research reports must be written as first-class artifacts by the worker.
  # Copying Codex's final handoff message into the report path creates a false
  # "completed" report when Codex only says "see the report path".
  missing_report_guard="if [[ \$pipeline_status -eq 0 && ! -s $qreport ]]; then pipeline_status=65; fi;"
else
  last_message_fallback="if [[ \$pipeline_status -eq 0 && ! -s $qreport && -s $qlast_message ]]; then cp $qlast_message $qreport || pipeline_status=\$?; fi;"
fi
# Keep fallback report creation in launcher hooks, not inside the child `bash -c`
# shell, because sourced spawn helpers are not inherited there as functions.
launch_cmd="set -o pipefail && cd $qroot && { rm -f $qlast_message; codex exec -C $qroot --json --dangerously-bypass-approvals-and-sandbox --output-last-message $qlast_message - < $qruntime 2>&1 | python3 $qbridge --transcript $qtranscript --raw $qraw ${bridge_flags}; pipeline_status=\$?; $last_message_fallback $missing_report_guard echo; { grep -o 'session: [a-f0-9-]*' $qtranscript 2>/dev/null | tail -1 | awk '{print \$2}' | xargs -I{} printf '\\n\\033[33m━━━ session: {} ━━━\\033[0m\\n'; } || true; exit \$pipeline_status; }"

# shellcheck disable=SC2016
codex_success_hook='
  report_bytes="$(wc -c < "$report" 2>/dev/null || printf 0)"
  if [[ ! -s "$report" || "$report_bytes" -lt 256 ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "completed"
    cat >> "$report" <<TXT
Codex completed without writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

# shellcheck disable=SC2016
codex_failure_hook='
  report_bytes="$(wc -c < "$report" 2>/dev/null || printf 0)"
  if [[ ! -s "$report" || "$report_bytes" -lt 256 ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "failed"
    cat >> "$report" <<TXT
Codex failed before writing a standalone report file.
See transcript for the full event stream:
$transcript
Last message, if present:
${transcript%.log}.last-message.md
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
if [[ "${VIBECRAFTED_SUPPRESS_REPORT_HINT:-0}" != "1" ]]; then
  printf 'Agent launched.\n'
  bash "$SCRIPT_DIR/await.sh" codex --describe "$SPAWN_LAUNCHER" 2>/dev/null || true
  printf '\nAwait:\n\n'
  printf 'vibecrafted codex await --run-id %s\n' "$SPAWN_RUN_ID"
fi

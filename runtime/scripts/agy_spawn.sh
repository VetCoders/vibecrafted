#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: agy_spawn.sh [--mode <mode>] [--runtime <terminal|visible|headless|background|detached>] [--root <repo-root>] [--dry-run] <plan.md>

Portable Antigravity/Gemini (agy) spawn wrapper.
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
spawn_prepare_paths agy "$plan_file" "$root" "$mode"
spawn_scan_active "${SPAWN_LOG_DIR:-$SPAWN_REPORT_DIR}"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_agy_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT" agy
spawn_write_meta "$SPAWN_META" "launching" "agy" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER"

if (( !dry_run )); then
  spawn_require_command agy
fi

qroot="$(spawn_shell_quote "$SPAWN_ROOT")"
qruntime="$(spawn_shell_quote "$runtime_input")"
qreport="$(spawn_shell_quote "$SPAWN_REPORT")"
qtranscript="$(spawn_shell_quote "$SPAWN_TRANSCRIPT")"

# shellcheck disable=SC2016
agy_success_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "completed"
    cat >> "$report" <<TXT
Agy completed without writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

# shellcheck disable=SC2016
agy_failure_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "unknown" "failed"
    cat >> "$report" <<TXT
Agy failed before writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

launch_cmd="set -o pipefail && cd $qroot && { agy --print --dangerously-skip-permissions --add-dir $qroot --print-timeout 30m '' < $qruntime 2>&1 | tee -a $qtranscript; pipeline_status=\$?; if [[ \$pipeline_status -eq 0 && ! -s $qreport ]]; then pipeline_status=65; fi; echo; { grep -oE '\\[[0-9]{2}:[0-9]{2}:[0-9]{2}\\] session: [[:alnum:]-]+' $qtranscript 2>/dev/null | tail -1 | awk '{print \$3}' | xargs -I{} printf '\\n\\033[33m━━━ session: {} ━━━\\033[0m\\n'; } || true; exit \$pipeline_status; }"

combined_success="${agy_success_hook}${success_hook_extra:+
$success_hook_extra}"
combined_failure="${agy_failure_hook}${failure_hook_extra:+
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
spawn_print_launch agy "$mode" "$runtime" "$dry_run"
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run" "agy-${VIBECRAFTED_SKILL_NAME:-$mode}"
if [[ "${VIBECRAFTED_SUPPRESS_REPORT_HINT:-0}" != "1" ]]; then
  if (( dry_run )); then
    printf 'Dry run: agent not launched.\n'
  else
    printf 'Agent launched.\n'
    bash "$SCRIPT_DIR/await.sh" agy --describe "$SPAWN_LAUNCHER" 2>/dev/null || true
    printf '\nAwait:\n\n'
    printf 'vibecrafted agy await --run-id %s\n' "$SPAWN_RUN_ID"
  fi
fi

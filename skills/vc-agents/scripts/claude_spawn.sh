#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: claude_spawn.sh [--mode <mode>] [--runtime <terminal|visible|headless|background|detached>] [--model <model>] [--root <repo-root>] [--dry-run] <plan.md>

Portable Claude spawn wrapper.
EOF_USAGE
}

mode="implement"
runtime="terminal"
model="${CLAUDE_SPAWN_MODEL:-claude-opus-4-6}"
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
    --model)
      shift
      [[ $# -gt 0 ]] || spawn_die "Missing value for --model"
      model="$1"
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
spawn_prepare_paths claude "$plan_file" "$root"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_claude_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT"
spawn_write_meta "$SPAWN_META" "launching" "claude" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER" "$model"

if (( !dry_run )); then
  spawn_require_command claude
fi

qroot="$(printf '%q' "$SPAWN_ROOT")"
qruntime="$(printf '%q' "$runtime_input")"
qreport="$(printf '%q' "$SPAWN_REPORT")"
qtranscript="$(printf '%q' "$SPAWN_TRANSCRIPT")"
qmodel="$(printf '%q' "$model")"

claude_success_hook='
  if [[ ! -s "$report" ]]; then
    cat > "$report" <<TXT
Claude completed without writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

claude_failure_hook='
  if [[ ! -s "$report" ]]; then
    cat > "$report" <<TXT
Claude failed before writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

launch_cmd="set -o pipefail && cd $qroot && prompt=\$(cat $qruntime) && claude -p --output-format stream-json --include-partial-messages --verbose --dangerously-skip-permissions --model $qmodel \"\$prompt\" 2>&1 | tee -a $qtranscript"

spawn_generate_launcher "$SPAWN_LAUNCHER" \
  "$SPAWN_META" \
  "$SPAWN_REPORT" \
  "$SPAWN_TRANSCRIPT" \
  "$SCRIPT_DIR/common.sh" \
  "$launch_cmd" \
  "" \
  "$claude_success_hook" \
  "$claude_failure_hook"

chmod +x "$SPAWN_LAUNCHER"
spawn_print_launch claude "$mode" "$runtime"
printf '  model:  %s\n' "$model"
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run"
printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"

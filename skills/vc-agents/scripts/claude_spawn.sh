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
model="${CLAUDE_SPAWN_MODEL:-}"
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
spawn_prepare_paths claude "$plan_file" "$root" "$mode"
spawn_scan_active "$SPAWN_REPORT_DIR"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_claude_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT" claude
spawn_write_meta "$SPAWN_META" "launching" "claude" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER" "$model"

if (( !dry_run )); then
  spawn_require_command claude
fi

qroot="$(printf '%q' "$SPAWN_ROOT")"
qruntime="$(printf '%q' "$runtime_input")"
qtranscript="$(printf '%q' "$SPAWN_TRANSCRIPT")"
qmodel="$(printf '%q' "$model")"

# shellcheck disable=SC2016
claude_success_hook='
  if [[ ! -s "$report" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "${SPAWN_MODEL:-unknown}" "completed"
    cat >> "$report" <<TXT
Claude completed without writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

# shellcheck disable=SC2016
claude_failure_hook='
  if [[ ! -s "$report" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "${SPAWN_MODEL:-unknown}" "failed"
    cat >> "$report" <<TXT
Claude failed before writing a standalone report file.
See transcript for the full event stream:
$transcript
TXT
  fi'

model_flag=""
[[ -n "$model" ]] && model_flag="--model $qmodel"
qfilter="$(printf '%q' "$SCRIPT_DIR/claude_stream_filter.jq")"
# Claude sometimes emits non-JSON noise before the JSONL stream.
# Keep only JSON object lines so jq never chokes on banners, warnings, or status text.
# Stream-json → grep JSON objects → jq (external filter file) → clean text to terminal AND transcript
# Raw JSONL lives in $HOME/.claude/projects/ — aicx ingests from there, not from us
launch_cmd="set -o pipefail && cd $qroot && claude -p --output-format stream-json --verbose --dangerously-skip-permissions $model_flag -- \"\$(cat $qruntime)\" 2>&1 | grep --line-buffered '^[[:space:]]*{' | jq --unbuffered -rj -f $qfilter | tee -a $qtranscript ; echo ; { grep -o 'session: [a-f0-9-]*' $qtranscript 2>/dev/null | tail -1 | awk '{print \$2}' | xargs -I{} printf '\\n\\033[33m━━━ session: {} ━━━\\033[0m\\n'; } || true"

# Combine built-in hooks with caller-provided hooks (marbles chain, etc.)
combined_success="${claude_success_hook}${success_hook_extra:+
$success_hook_extra}"
combined_failure="${claude_failure_hook}${failure_hook_extra:+
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
spawn_print_launch claude "$mode" "$runtime"
[[ -n "$model" ]] && printf '  model:  %s\n' "$model" || printf '  model:  (CLI default)\n'
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run" "claude-${VIBECRAFTED_SKILL_NAME:-$mode}"
printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"

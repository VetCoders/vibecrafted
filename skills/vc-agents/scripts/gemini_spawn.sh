#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<EOF_USAGE
Usage: gemini_spawn.sh [--mode <mode>] [--runtime <terminal|visible|headless|background|detached>] [--model <model>] [--root <repo-root>] [--dry-run] <plan.md>

Portable Gemini spawn wrapper.
EOF_USAGE
}

mode="implement"
runtime="terminal"
model="${GEMINI_MODEL:-}"
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
spawn_prepare_paths gemini "$plan_file" "$root" "$mode"
spawn_scan_active "$SPAWN_REPORT_DIR"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_gemini_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT" gemini
spawn_write_meta "$SPAWN_META" "launching" "gemini" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER" "$model"

if (( !dry_run )); then
  spawn_require_command gemini
fi

qroot="$(spawn_shell_quote "$SPAWN_ROOT")"
qruntime="$(spawn_shell_quote "$runtime_input")"
qtranscript="$(spawn_shell_quote "$SPAWN_TRANSCRIPT")"
qmodel="$(spawn_shell_quote "$model")"

# shellcheck disable=SC2016
gemini_success_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "${SPAWN_MODEL:-unknown}" "completed"
    cat "$transcript" >> "$report"
  fi'

# shellcheck disable=SC2016
gemini_failure_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    spawn_write_frontmatter "$report" "$SPAWN_AGENT" "${SPAWN_MODEL:-unknown}" "failed"
    cat "$transcript" >> "$report"
  fi'

model_flag=""
[[ -n "$model" ]] && model_flag="--model $qmodel"
qfilter="$(spawn_shell_quote "$SCRIPT_DIR/gemini_stream_filter.jq")"
# Gemini emits non-JSON noise (YOLO banner, MCP bootstrap) before JSONL.
# grep '^{' strips non-JSON lines so jq doesn't choke.
vibecrafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
qvhome="$(spawn_shell_quote "$vibecrafted_home")"
launch_cmd="set -o pipefail && cd $qroot && { GEMINI_FORCE_FILE_STORAGE=true gemini -p '' -y $model_flag --include-directories $qvhome -o stream-json < $qruntime 2>&1 | grep --line-buffered '^{' | jq --unbuffered -rj -f $qfilter | tee -a $qtranscript; pipeline_status=\$?; exit \$pipeline_status; }"

# Combine built-in hooks with caller-provided hooks (marbles chain, etc.)
combined_success="${gemini_success_hook}${success_hook_extra:+
$success_hook_extra}"
combined_failure="${gemini_failure_hook}${failure_hook_extra:+
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
spawn_print_launch gemini "$mode" "$runtime"
[[ -n "$model" ]] && printf '  model:  %s\n' "$model" || printf '  model:  (CLI default)\n'
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run" "gemini-${VIBECRAFTED_SKILL_NAME:-$mode}"
if [[ "${VIBECRAFTED_SUPPRESS_REPORT_HINT:-0}" != "1" ]]; then
  printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"
fi

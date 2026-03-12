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
model="${GEMINI_MODEL:-gemini-3.1-pro-preview}"
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
spawn_prepare_paths gemini "$plan_file" "$root"
runtime_input="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_gemini_prompt.md"
spawn_build_runtime_prompt "$SPAWN_PLAN" "$runtime_input" "$SPAWN_REPORT"
spawn_write_meta "$SPAWN_META" "launching" "gemini" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$SPAWN_LAUNCHER" "$model"

if (( !dry_run )); then
  spawn_require_command gemini
fi

qroot="$(printf '%q' "$SPAWN_ROOT")"
qruntime="$(printf '%q' "$runtime_input")"
qreport="$(printf '%q' "$SPAWN_REPORT")"
qtranscript="$(printf '%q' "$SPAWN_TRANSCRIPT")"
qmodel="$(printf '%q' "$model")"

gemini_pre_hook='
  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    printf "%s\n" "[INFO] GEMINI_API_KEY inherited from current shell env." | tee -a "$transcript"
  else
    gemini_api_key="$(spawn_gemini_api_key 2>/dev/null || true)"
    if [[ -n "$gemini_api_key" ]]; then
      export GEMINI_API_KEY="$gemini_api_key"
      printf "%s\n" "[INFO] GEMINI_API_KEY resolved from macOS Keychain." | tee -a "$transcript"
    else
      printf "%s\n" "[INFO] No GEMINI_API_KEY found in env or Keychain; relying on Gemini CLI Google-account auth if configured." | tee -a "$transcript"
    fi
  fi'

gemini_success_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    cp "$transcript" "$report"
  fi'

gemini_failure_hook='
  if [[ ! -s "$report" && -s "$transcript" ]]; then
    cp "$transcript" "$report"
  fi'

launch_cmd="set -o pipefail && cd $qroot && prompt=\$(cat $qruntime) && gemini -p \"\$prompt\" -y --model $qmodel -o text 2>&1 | tee -a $qtranscript"

spawn_generate_launcher "$SPAWN_LAUNCHER" \
  "$SPAWN_META" \
  "$SPAWN_REPORT" \
  "$SPAWN_TRANSCRIPT" \
  "$SCRIPT_DIR/common.sh" \
  "$launch_cmd" \
  "$gemini_pre_hook" \
  "$gemini_success_hook" \
  "$gemini_failure_hook"

chmod +x "$SPAWN_LAUNCHER"
spawn_print_launch gemini "$mode" "$runtime"
printf '  model:  %s\n' "$model"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  printf '  auth:   GEMINI_API_KEY from current shell env\n'
elif spawn_gemini_api_key >/dev/null 2>&1; then
  printf '  auth:   GEMINI_API_KEY resolved from macOS Keychain\n'
else
  printf '  auth:   no env/keychain key found; launcher will rely on Gemini CLI account auth\n'
fi
spawn_launch "$SPAWN_LAUNCHER" "$runtime" "$dry_run"
printf 'Agent launched. Report will land at: %s\n' "$SPAWN_REPORT"

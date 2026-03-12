#!/usr/bin/env bash
set -euo pipefail

spawn_die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

spawn_require_file() {
  local path="${1:-}"
  [[ -n "$path" ]] || spawn_die "Missing required file path."
  [[ -f "$path" ]] || spawn_die "File not found: $path"
}

spawn_require_command() {
  local cmd="${1:-}"
  [[ -n "$cmd" ]] || spawn_die "Missing required command name."
  command -v "$cmd" >/dev/null 2>&1 || spawn_die "Required command not found: $cmd"
}

spawn_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

spawn_abspath() {
  local path="$1"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$(cd "$(dirname "$path")" && pwd)" "$(basename "$path")"
  fi
}

spawn_slug_from_path() {
  local raw
  raw="$(basename "${1%.*}")"
  raw="$(printf '%s' "$raw" | tr ' ' '-' | tr -cs '[:alnum:]._-' '-')"
  raw="${raw#-}"
  raw="${raw%-}"
  [[ -n "$raw" ]] || raw="agent-task"
  printf '%s\n' "$raw"
}

spawn_timestamp() {
  date +%Y%m%d_%H%M
}

spawn_write_meta() {
  local meta_path="$1"
  local status="$2"
  local agent="$3"
  local mode="$4"
  local root="$5"
  local input_ref="$6"
  local report="$7"
  local transcript="$8"
  local launcher="$9"
  local model="${10:-__NONE__}"

  python3 - "$meta_path" "$status" "$agent" "$mode" "$root" "$input_ref" "$report" "$transcript" "$launcher" "$model" <<'PY'
import datetime as dt
import json
import sys

meta_path, status, agent, mode, root, input_ref, report, transcript, launcher, model = sys.argv[1:11]
payload = {
    "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "status": status,
    "agent": agent,
    "mode": mode,
    "root": root,
    "input": input_ref,
    "report": report,
    "transcript": transcript,
    "launcher": launcher,
    "exit_code": None,
}
if model != "__NONE__":
    payload["model"] = model
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

spawn_finish_meta() {
  local meta_path="$1"
  local status="$2"
  local exit_code="${3:-0}"

  python3 - "$meta_path" "$status" "$exit_code" <<'PY'
import datetime as dt
import json
import sys

meta_path, status, exit_code = sys.argv[1:4]
with open(meta_path, "r", encoding="utf-8") as fh:
    payload = json.load(fh)
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
payload["status"] = status
payload["exit_code"] = int(exit_code)
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

spawn_prepare_paths() {
  local agent="$1"
  local prompt_file="$2"
  local root="${3:-}"

  if [[ -n "$root" ]]; then
    SPAWN_ROOT="$(spawn_abspath "$root")"
    [[ -d "$SPAWN_ROOT" ]] || spawn_die "Root directory not found: $SPAWN_ROOT"
  else
    SPAWN_ROOT="$(spawn_repo_root)"
  fi

  SPAWN_PLAN="$(spawn_abspath "$prompt_file")"
  SPAWN_SLUG="$(spawn_slug_from_path "$prompt_file")"
  SPAWN_TS="$(spawn_timestamp)"
  SPAWN_REPORT_DIR="$SPAWN_ROOT/.ai-agents/reports"
  SPAWN_TMP_DIR="$SPAWN_ROOT/.ai-agents/tmp"
  SPAWN_BASE="$SPAWN_REPORT_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}"
  SPAWN_REPORT="${SPAWN_BASE}.md"
  SPAWN_TRANSCRIPT="${SPAWN_BASE}.transcript.log"
  SPAWN_META="${SPAWN_BASE}.meta.json"
  SPAWN_LAUNCHER="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}_launch.sh"
  mkdir -p "$SPAWN_REPORT_DIR" "$SPAWN_TMP_DIR"
}

spawn_build_runtime_prompt() {
  local source_file="$1"
  local runtime_file="$2"
  local report_path="$3"

  cat "$source_file" > "$runtime_file"
  cat >> "$runtime_file" <<EOF_PROMPT

At the end of the task, write your final human-readable report to this exact path:
$report_path

Keep streaming useful progress to stdout while you work. If you cannot write a
standalone report file, finish normally and let the transcript act as the fallback
artifact.
EOF_PROMPT
}

spawn_gemini_api_key() {
  local value=""

  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    printf '%s' "$GEMINI_API_KEY"
    return 0
  fi

  command -v security >/dev/null 2>&1 || return 1

  value="$(security find-generic-password -w -s GEMINI_API_KEY -a GEMINI_API_KEY 2>/dev/null || true)"
  [[ -n "$value" ]] && {
    printf '%s' "$value"
    return 0
  }

  local service_name
  for service_name in GEMINI_API_KEY gemini-cli google-generative-ai GoogleAIStudio; do
    value="$(security find-generic-password -w -s "$service_name" 2>/dev/null || true)"
    [[ -n "$value" ]] && {
      printf '%s' "$value"
      return 0
    }
  done

  local account_name
  for account_name in GEMINI_API_KEY gemini-cli gemini google; do
    value="$(security find-generic-password -w -a "$account_name" 2>/dev/null || true)"
    [[ -n "$value" ]] && {
      printf '%s' "$value"
      return 0
    }
  done

  return 1
}

spawn_generate_launcher() {
  local launcher="$1"
  local meta_path="$2"
  local report_path="$3"
  local transcript_path="$4"
  local common_path="$5"
  local command="$6"
  local pre_hook="${7:-}"
  local success_hook="${8:-}"
  local failure_hook="${9:-}"

  [[ -n "$launcher" ]] || spawn_die "Missing launcher path."
  [[ -f "$common_path" ]] || spawn_die "common.sh not found: $common_path"
  [[ -n "$command" ]] || spawn_die "Missing command payload for launcher."

  local q_meta q_report q_transcript q_common q_cmd
  q_meta="$(printf '%q' "$meta_path")"
  q_report="$(printf '%q' "$report_path")"
  q_transcript="$(printf '%q' "$transcript_path")"
  q_common="$(printf '%q' "$common_path")"
  q_cmd="$(printf '%q' "$command")"

  cat > "$launcher" <<EOF_LAUNCH
#!/usr/bin/env bash
set -euo pipefail
source $q_common

meta=$q_meta
report=$q_report
transcript=$q_transcript
SPAWN_CMD=$q_cmd

rm -f "\$transcript" "\$report"
EOF_LAUNCH

  if [[ -n "$pre_hook" ]]; then
    printf '%s\n' "$pre_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
if zsh -ic "$SPAWN_CMD"; then
EOF_LAUNCH

  if [[ -n "$success_hook" ]]; then
    printf '%s\n' "$success_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
  spawn_finish_meta "$meta" "completed" "0"
else
  exit_code=$?
EOF_LAUNCH

  if [[ -n "$failure_hook" ]]; then
    printf '%s\n' "$failure_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
  spawn_finish_meta "$meta" "failed" "$exit_code"
  exit "$exit_code"
fi
EOF_LAUNCH
}

spawn_launch_headless() {
  local launcher="$1"
  [[ -x "$launcher" ]] || spawn_die "Launcher is not executable: $launcher"
  nohup "$launcher" >/dev/null 2>&1 &
  local launcher_pid=$!
  printf 'Spawned headless launcher (pid=%s): %s\n' "$launcher_pid" "$launcher"
}

spawn_open_terminal() {
  local launcher="$1"
  command -v osascript >/dev/null 2>&1 || spawn_die "osascript is required for visible Terminal spawns."

  local command_json
  command_json="$(python3 - "$launcher" <<'PY'
import json
import shlex
import sys

launcher = sys.argv[1]
print(json.dumps("zsh -ic " + shlex.quote(launcher)))
PY
)"

  osascript <<EOF_APPLE
 tell application "Terminal"
   activate
   do script $command_json
 end tell
EOF_APPLE
}

spawn_launch() {
  local launcher="$1"
  local runtime="${2:-terminal}"
  local dry_run="${3:-0}"

  if (( dry_run )); then
    printf 'Dry run mode: launcher generated only: %s\n' "$launcher"
    return 0
  fi

  case "$runtime" in
    terminal|visible)
      if command -v osascript >/dev/null 2>&1; then
        spawn_open_terminal "$launcher"
      else
        printf 'Runtime fallback: visible Terminal requested, but osascript is unavailable. Running headless.\n' >&2
        spawn_launch_headless "$launcher"
      fi
      ;;
    headless|background|detached)
      spawn_launch_headless "$launcher"
      ;;
    *)
      spawn_die "Unsupported runtime '$runtime'. Use terminal or headless."
      ;;
  esac
}

spawn_validate_runtime() {
  local runtime="${1:-terminal}"
  case "$runtime" in
    terminal|visible|headless|background|detached)
      return 0
      ;;
    *)
      spawn_die "Invalid runtime '$runtime'. Valid values: terminal, visible, headless, background, detached."
      ;;
  esac
}

spawn_print_launch() {
  local agent="$1"
  local mode="$2"
  local runtime="${3:-terminal}"
  printf 'Spawning %s-%s with runtime=%s\n' "$agent" "$mode" "$runtime"
  printf '  plan:   %s\n' "$SPAWN_PLAN"
  printf '  report: %s\n' "$SPAWN_REPORT"
  printf '  trace:  %s\n' "$SPAWN_TRANSCRIPT"
  printf '  meta:   %s\n' "$SPAWN_META"
  printf '  launch: %s\n' "$SPAWN_LAUNCHER"
}

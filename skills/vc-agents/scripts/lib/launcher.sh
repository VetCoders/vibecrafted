#!/usr/bin/env bash

spawn_print_dashboard_hint() {
  printf '\nRun:\n\nvibecrafted dashboard\n\nto monitor your sessions live.\n'
}

spawn_watch_startup() {
  local meta_path="$1"
  local transcript_path="$2"
  local report_path="$3"
  local seconds="${4:-${VIBECRAFTED_SPAWN_WATCH_SECONDS:-10}}"
  local rc=0

  [[ "$seconds" =~ ^[0-9]+$ ]] || seconds=10
  (( seconds > 0 )) || return 0

  if python3 - "$meta_path" "$transcript_path" "$report_path" "$seconds" <<'PY'
import json
import os
import re
import sys
import time

meta_path, transcript_path, report_path, seconds_raw = sys.argv[1:5]
seconds = max(int(seconds_raw), 0)
deadline = time.monotonic() + seconds
ansi_re = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
failure_markers = (
    "Not logged in",
    "Please run /login",
    "Invalid UTF-8",
    "Permission denied",
    "Traceback",
    "panic",
)


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :].lstrip("\n")


def report_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return ""


def meta_status(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("status") or "")


initial_transcript = strip_frontmatter(read_text(transcript_path))
initial_report_size = report_size(report_path)
activity = bool(initial_transcript.strip()) or initial_report_size > 0
printed_len = 0

if initial_transcript:
    sys.stdout.write(initial_transcript)
    sys.stdout.flush()
    printed_len = len(initial_transcript)

clean_initial = ansi_re.sub("", initial_transcript)
if any(marker in clean_initial for marker in failure_markers):
    raise SystemExit(10)

status = meta_status(meta_path)
if status == "failed":
    raise SystemExit(10)
if status == "completed":
    raise SystemExit(0)

while time.monotonic() < deadline:
    status = meta_status(meta_path)
    if status == "failed":
        raise SystemExit(10)
    if status == "completed":
        raise SystemExit(0)

    transcript_body = strip_frontmatter(read_text(transcript_path))
    if len(transcript_body) > printed_len:
        appended = transcript_body[printed_len:]
        clean = ansi_re.sub("", appended)
        if appended.strip():
            activity = True
            sys.stdout.write(appended)
            sys.stdout.flush()
        printed_len = len(transcript_body)
        if any(marker in clean for marker in failure_markers):
            raise SystemExit(10)

    if report_size(report_path) > initial_report_size:
        activity = True

    time.sleep(0.2)

raise SystemExit(0 if activity else 11)
PY
  then
    rc=0
  else
    rc=$?
  fi

  case "$rc" in
    0)
      printf '\nStartup check: passed in the first %ss.\n' "$seconds"
      ;; 
    10)
      printf '\nStartup check: failed in the first %ss.\n' "$seconds"
      ;; 
    11)
      printf '\nStartup check: still launching after %ss.\n' "$seconds"
      ;; 
    *)
      printf '\nStartup check: inconclusive (watch rc=%s).\n' "$rc"
      ;; 
  esac

  spawn_print_dashboard_hint
  return 0
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
  local q_root q_agent q_prompt_id q_run_id q_run_lock q_loop_nr q_skill_code
  local q_operator_session q_spawn_direction
  q_meta="$(spawn_shell_quote "$meta_path")"
  q_report="$(spawn_shell_quote "$report_path")"
  q_transcript="$(spawn_shell_quote "$transcript_path")"
  q_common="$(spawn_shell_quote "$common_path")"
  q_cmd="$(spawn_shell_quote "$command")"
  q_root="$(spawn_shell_quote "${SPAWN_ROOT:-}")"
  q_agent="$(spawn_shell_quote "${SPAWN_AGENT:-}")"
  q_prompt_id="$(spawn_shell_quote "${SPAWN_PROMPT_ID:-}")"
  q_run_id="$(spawn_shell_quote "${SPAWN_RUN_ID:-}")"
  q_run_lock="$(spawn_shell_quote "${SPAWN_RUN_LOCK:-}")"
  q_loop_nr="$(spawn_shell_quote "${SPAWN_LOOP_NR:-0}")"
  q_skill_code="$(spawn_shell_quote "${SPAWN_SKILL_CODE:-}")"
  q_skill_name="$(spawn_shell_quote "${SPAWN_SKILL_NAME:-${VIBECRAFTED_SKILL_NAME:-}}")"
  q_operator_session="$(spawn_shell_quote "${VIBECRAFTED_OPERATOR_SESSION:-}")"
  q_spawn_direction="$(spawn_shell_quote "${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-}")"

  cat > "$launcher" <<EOF_LAUNCH
#!/usr/bin/env bash
set -euo pipefail
source $q_common

meta=$q_meta
report=$q_report
transcript=$q_transcript
SPAWN_CMD=$q_cmd
export SPAWN_ROOT=$q_root
export SPAWN_AGENT=$q_agent
export SPAWN_PROMPT_ID=$q_prompt_id
export SPAWN_RUN_ID=$q_run_id
export SPAWN_RUN_LOCK=$q_run_lock
export SPAWN_LOOP_NR=$q_loop_nr
export SPAWN_SKILL_CODE=$q_skill_code
export SPAWN_SKILL_NAME=$q_skill_name
export VIBECRAFTED_RUN_ID=$q_run_id
export VIBECRAFTED_RUN_LOCK=$q_run_lock
export VIBECRAFTED_SKILL_CODE=$q_skill_code
export VIBECRAFTED_SKILL_NAME=\${VIBECRAFTED_SKILL_NAME:-$q_skill_name}
export VIBECRAFTED_OPERATOR_SESSION=\${VIBECRAFTED_OPERATOR_SESSION:-$q_operator_session}
export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=\${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-$q_spawn_direction}
startup_watch_pid=""

rm -f "\$transcript" "\$report"
spawn_write_frontmatter "\$transcript" "\$SPAWN_AGENT" "unknown" "transcript"
if [[ -n "\${SPAWN_ROOT:-}" ]]; then
  cd "\$SPAWN_ROOT"
fi
EOF_LAUNCH

  if [[ -n "$pre_hook" ]]; then
    printf '%s\n' "$pre_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
spawn_export_frontier_sidecars
export PATH="${PATH:-/usr/local/bin:/usr/bin:/bin}"
if [[ "${VIBECRAFTED_INLINE_STARTUP_WATCH:-1}" != "0" ]]; then
  spawn_watch_startup "$meta" "$transcript" "$report" &
  startup_watch_pid=$!
fi

if bash -c "$SPAWN_CMD"; then
EOF_LAUNCH

  if [[ -n "$success_hook" ]]; then
    printf '%s\n' "$success_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
  if [[ -n "$startup_watch_pid" ]]; then
    wait "$startup_watch_pid" 2>/dev/null || true
  fi
  spawn_finish_meta "$meta" "completed" "0"
else
  exit_code=$?
EOF_LAUNCH

  if [[ -n "$failure_hook" ]]; then
    printf '%s\n' "$failure_hook" >> "$launcher"
  fi

  cat >> "$launcher" <<'EOF_LAUNCH'
  if [[ -n "$startup_watch_pid" ]]; then
    wait "$startup_watch_pid" 2>/dev/null || true
  fi
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

spawn_osascript_bin() {
  local override="${VIBECRAFTED_OSASCRIPT_BIN:-}"
  if [[ -n "$override" && -x "$override" ]]; then
    printf '%s\n' "$override"
    return 0
  fi

  command -v osascript 2>/dev/null || return 1
}

# Detect preferred terminal app. Priority:
#   1. VIBECRAFTED_TERMINAL env (explicit override: iterm, terminal)
#   2. iTerm2 installed at /Applications
#   3. TERM_PROGRAM from current session
#   4. Fallback: terminal (Terminal.app)
spawn_preferred_terminal() {
  local pref="${VIBECRAFTED_TERMINAL:-}"
  if [[ -n "$pref" ]]; then
    printf '%s\n' "$pref"
    return 0
  fi
  # Detect installed terminal apps (survives agent/vscode context)
  if [[ -d "/Applications/iTerm.app" ]]; then
    printf 'iterm\n'
    return 0
  fi
  # Session-level detection as last resort
  case "${TERM_PROGRAM:-}" in
    iTerm.app) printf 'iterm\n' ;; 
    *) printf 'terminal\n' ;; 
  esac
}

spawn_open_terminal() {
  local launcher="$1"
  local osascript_bin
  osascript_bin="$(spawn_osascript_bin)" || spawn_die "osascript is required for visible Terminal spawns."

  local command_json
  command_json="$(python3 - "$launcher" "${SPAWN_ROOT:-}" <<'PY'
import json
import shlex
import sys

launcher = sys.argv[1]
root = sys.argv[2] if len(sys.argv) > 2 else ""
parts = []
if root:
    parts.append("cd " + shlex.quote(root))
parts.append("bash " + shlex.quote(launcher))
print(json.dumps(" && ".join(parts)))
PY
)"

  "$osascript_bin" <<EOF_APPLE
 tell application "Terminal" 
   activate 
   do script $command_json
 end tell
EOF_APPLE
}

spawn_open_iterm() {
  local launcher="$1"
  local osascript_bin
  osascript_bin="$(spawn_osascript_bin)" || return 1
  [[ "$(spawn_preferred_terminal)" == "iterm" ]] || return 1

  local command_json
  command_json="$(python3 - "$launcher" "${SPAWN_ROOT:-}" <<'PY'
import json
import shlex
import sys

launcher = sys.argv[1]
root = sys.argv[2] if len(sys.argv) > 2 else ""
parts = []
if root:
    parts.append("cd " + shlex.quote(root))
parts.append("bash " + shlex.quote(launcher))
print(json.dumps(" && ".join(parts)))
PY
)"

  "$osascript_bin" <<EOF_APPLE
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      write text $command_json
    end tell
  end tell
end tell
EOF_APPLE
}

spawn_launch() {
  local launcher="$1"
  local runtime="${2:-terminal}"
  local dry_run="${3:-0}"
  local pane_name="${4:-$(basename "$launcher" .sh)}"

  pane_name="$(printf '%s' "$pane_name" | tr ' ' '-' | tr -cs '[:alnum:]._-' '-')"
  pane_name="${pane_name#-}"
  pane_name="${pane_name%-}"
  [[ -n "$pane_name" ]] || pane_name="agent"

  if [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]]; then
    local discovered_session=""
    discovered_session="$(spawn_effective_operator_session 2>/dev/null || true)"
    if [[ -n "$discovered_session" ]]; then
      export VIBECRAFTED_OPERATOR_SESSION="$discovered_session"
    fi
  fi

  if (( dry_run )); then
    printf 'Dry run mode: launcher generated only: %s\n' "$launcher"
    return 0
  fi

  case "$runtime" in
    terminal|visible)
      if spawn_in_zellij_pane "$launcher" "$pane_name"; then
        :
      elif spawn_in_operator_session "$launcher" "$pane_name"; then
        :
      elif spawn_open_iterm "$launcher" 2>/dev/null; then
        :
      elif spawn_osascript_bin >/dev/null 2>&1; then
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

spawn_print_launch() {
  local agent="$1"
  local mode="$2"
  local runtime="${3:-terminal}"

  # ── 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. branded spawn output ──────────────────────────────
  local _dim='\033[2m'    _bold='\033[1m'
  local _copper='\033[38;5;173m'  _steel='\033[38;5;247m'
  local _reset='\033[0m'
  local _bar="$_steel──────────────────────────────────$_reset"

  printf '\n%b ⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. · %s-%s%b\n' "$_bold$_copper" "$agent" "$mode" "$_reset"
  printf '%b\n' "$_bar"
  printf '%b  plan:    %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_PLAN:-—}" "$_reset"
  printf '%b  report:  %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_REPORT:-—}" "$_reset"
  printf '%b  trace:   %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_TRANSCRIPT:-—}" "$_reset"
  printf '%b  runtime: %b%s%b\n'   "$_steel" "$_reset" "$runtime" "$_reset"
  printf '%b\n' "$_bar"
  printf '%b  Agent launched.%b\n\n' "$_dim" "$_reset"
}

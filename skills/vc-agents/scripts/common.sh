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

spawn_require_positive_int() {
  local value="${1:-}"
  local flag_name="${2:-value}"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || spawn_die "${flag_name} must be a positive integer"
}

spawn_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

# Central artifact store: ~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/
# Override with VIBECRAFTED_HOME env var for custom location
# Falls back to <repo>/.vibecrafted/ if git remote unavailable
VIBECRAFTED_HOME="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"

spawn_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  local org_repo=""
  org_repo="$(cd "$root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"
  if [[ -n "$org_repo" ]]; then
    local date_dir
    date_dir="$(date +%Y_%m%d)"
    printf '%s/artifacts/%s/%s' "$VIBECRAFTED_HOME" "$org_repo" "$date_dir"
  else
    # Fallback: per-repo
    printf '%s/.vibecrafted' "$root"
  fi
}

spawn_effective_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  if [[ -n "${VIBECRAFT_STORE_DIR:-}" ]]; then
    spawn_abspath "$VIBECRAFT_STORE_DIR"
    return 0
  fi
  spawn_store_dir "$root"
}

spawn_marbles_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  printf '%s/marbles\n' "$(spawn_store_dir "$root")"
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

spawn_framework_version() {
  local script_root=""
  local candidate=""
  local state_file=""
  local state_version=""

  script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd || true)"

  for candidate in \
    "${VIBECRAFT_ROOT:+$VIBECRAFT_ROOT/VERSION}" \
    "${SPAWN_ROOT:+$SPAWN_ROOT/VERSION}" \
    "${script_root:+$script_root/VERSION}" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current/VERSION"
  do
    [[ -n "$candidate" ]] || continue
    if [[ -f "$candidate" ]]; then
      tr -d '\r\n' < "$candidate"
      return 0
    fi
  done

  for state_file in \
    "${script_root:+$script_root/skills/.vc-install.json}" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/skills/.vc-install.json"
  do
    [[ -n "$state_file" ]] || continue
    [[ -f "$state_file" ]] || continue
    state_version="$(
      python3 - "$state_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
print(payload.get("framework_version", ""))
PY
    )"
    if [[ -n "$state_version" ]]; then
      printf '%s\n' "$state_version"
      return 0
    fi
  done

  printf 'unknown\n'
}

spawn_link_repo_artifacts() {
  local store_base="$1"
  local repo_root="$2"
  local repo_vibecrafted="$repo_root/.vibecrafted"

  [[ "$store_base" != "$repo_root/.vibecrafted" ]] || return 0

  mkdir -p "$repo_vibecrafted"
  ln -sfn "$store_base/plans" "$repo_vibecrafted/plans" 2>/dev/null || true
  ln -sfn "$store_base/reports" "$repo_vibecrafted/reports" 2>/dev/null || true
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
  local prompt_id="${SPAWN_PROMPT_ID:-}"
  local run_id="${SPAWN_RUN_ID:-}"
  local loop_nr="${SPAWN_LOOP_NR:-0}"
  local skill_code="${SPAWN_SKILL_CODE:-}"
  local framework_version
  framework_version="$(spawn_framework_version)"

  python3 - "$meta_path" "$status" "$agent" "$mode" "$root" "$input_ref" "$report" "$transcript" "$launcher" "$model" "$prompt_id" "$run_id" "$loop_nr" "$skill_code" "$framework_version" <<'PY'
import datetime as dt
import json
import sys

meta_path, status, agent, mode, root, input_ref, report, transcript, launcher, model, prompt_id, run_id, loop_nr, skill_code, framework_version = sys.argv[1:16]
try:
    loop_nr_value = int(loop_nr)
except ValueError:
    loop_nr_value = loop_nr
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
    "prompt_id": prompt_id,
    "run_id": run_id,
    "loop_nr": loop_nr_value,
    "skill_code": skill_code,
    "framework_version": framework_version,
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
completed_at = dt.datetime.now(dt.timezone.utc)
started_at = payload.get("updated_at")
duration_s = None
if isinstance(started_at, str):
    try:
        started_dt = dt.datetime.fromisoformat(started_at)
    except ValueError:
        started_dt = None
    if started_dt is not None:
        duration_s = round((completed_at - started_dt).total_seconds(), 3)
payload["updated_at"] = completed_at.isoformat()
payload["completed_at"] = completed_at.isoformat()
payload["duration_s"] = duration_s
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
  SPAWN_AGENT="$agent"
  SPAWN_PROMPT_ID="${SPAWN_SLUG}_${SPAWN_TS%%_*}"
  SPAWN_SKILL_CODE="${VIBECRAFT_SKILL_CODE:-}"
  SPAWN_LOOP_NR="${VIBECRAFT_LOOP_NR:-0}"
  case "$SPAWN_LOOP_NR" in
    ''|*[!0-9]*)
      SPAWN_LOOP_NR=0
      ;;
  esac
  SPAWN_RUN_ID="${VIBECRAFT_RUN_ID:-$(printf '%s-%03d' "${SPAWN_SKILL_CODE:-impl}" "$SPAWN_LOOP_NR")}"

  # Central store path (falls back to per-repo if no git remote)
  local store_base
  store_base="$(spawn_effective_store_dir "$SPAWN_ROOT")"

  SPAWN_PLAN_DIR="$store_base/plans"
  SPAWN_REPORT_DIR="$store_base/reports"
  SPAWN_TMP_DIR="$store_base/tmp"
  SPAWN_BASE="$SPAWN_REPORT_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}"
  SPAWN_REPORT="${SPAWN_BASE}.md"
  SPAWN_TRANSCRIPT="${SPAWN_BASE}.transcript.log"
  SPAWN_META="${SPAWN_BASE}.meta.json"
  SPAWN_LAUNCHER="$SPAWN_TMP_DIR/${SPAWN_TS}_${SPAWN_SLUG}_${agent}_launch.sh"
  mkdir -p "$store_base/plans" "$SPAWN_REPORT_DIR" "$SPAWN_TMP_DIR"
  spawn_link_repo_artifacts "$store_base" "$SPAWN_ROOT"
  export SPAWN_ROOT SPAWN_PLAN SPAWN_SLUG SPAWN_TS SPAWN_AGENT SPAWN_PROMPT_ID SPAWN_RUN_ID SPAWN_SKILL_CODE SPAWN_LOOP_NR
  export SPAWN_PLAN_DIR SPAWN_REPORT_DIR SPAWN_TMP_DIR SPAWN_BASE SPAWN_REPORT SPAWN_TRANSCRIPT SPAWN_META SPAWN_LAUNCHER
}

spawn_scan_active() {
  local reports_dir="$1"
  local marker="${TMPDIR:-/tmp}/.vibecrafted-scan-marker"
  local recent_active=""

  [[ -d "$reports_dir" ]] || {
    touch "$marker"
    return 0
  }

  if [[ -e "$marker" ]]; then
    recent_active="$(
      find "$reports_dir" -name '*.meta.json' -newer "$marker" 2>/dev/null | sort | while read -r f; do
        python3 - "$f" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
if payload.get("status") in ("launching", "running"):
    print(f"  {payload.get('run_id', '?'):10s} {payload.get('agent', '?'):8s} {payload.get('status', '?'):10s} {payload.get('mode', '?')}")
PY
      done
    )"
  else
    recent_active="$(
      find "$reports_dir" -name '*.meta.json' 2>/dev/null | sort | while read -r f; do
        python3 - "$f" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
if payload.get("status") in ("launching", "running"):
    print(f"  {payload.get('run_id', '?'):10s} {payload.get('agent', '?'):8s} {payload.get('status', '?'):10s} {payload.get('mode', '?')}")
PY
      done
    )"
  fi

  touch "$marker"
  [[ -n "$recent_active" ]] || return 0

  printf '\033[2mRecent active 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. runs:\n%s\033[0m\n' "$recent_active"
}

spawn_build_runtime_prompt() {
  local source_file="$1"
  local runtime_file="$2"
  local report_path="$3"
  local agent="${4:-${SPAWN_AGENT:-agent}}"

  cat "$source_file" > "$runtime_file"
  cat >> "$runtime_file" <<EOF_PROMPT

At the end of the task, write your final human-readable report to this exact path:
Report path: $report_path

Keep streaming useful progress to stdout while you work. If you cannot write a
standalone report file, finish normally and let the transcript act as the fallback
artifact.

When writing your report file, include YAML frontmatter at the top:
---
agent: $agent
run_id: ${SPAWN_RUN_ID:-unknown}
prompt_id: ${SPAWN_PROMPT_ID:-unknown}
started_at: (ISO 8601 when you began)
model: (your model name)
---
EOF_PROMPT
}

spawn_frontier_root() {
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/starship.toml" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(spawn_frontier_candidates)

  return 1
}

spawn_frontier_candidates() {
  local script_root candidate seen=""
  script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd || true)"

  for candidate in \
    "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/frontier" \
    "${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/tools/vibecrafted-current/config" \
    "${VIBECRAFT_ROOT:+$VIBECRAFT_ROOT/config}" \
    "${SPAWN_ROOT:+$SPAWN_ROOT/config}" \
    "${script_root:+$script_root/config}"
  do
    [[ -n "$candidate" && -d "$candidate" ]] || continue
    case ":$seen:" in
      *":$candidate:"*) continue ;;
    esac
    seen="${seen:+$seen:}$candidate"
    printf '%s\n' "$candidate"
  done

  return 0
}

# Resolve each frontier asset independently so repo-owned prompt/history presets
# can coexist with an external session companion repo.
spawn_frontier_file() {
  local relative_path="$1"
  local candidate
  while IFS= read -r candidate; do
    if [[ -f "$candidate/$relative_path" ]]; then
      printf '%s/%s\n' "$candidate" "$relative_path"
      return 0
    fi
  done < <(spawn_frontier_candidates)
  return 1
}

spawn_export_frontier_sidecars() {
  local starship_config atuin_config zellij_config zellij_config_dir
  starship_config="$(spawn_frontier_file "starship.toml" 2>/dev/null || true)"
  atuin_config="$(spawn_frontier_file "atuin/config.toml" 2>/dev/null || true)"
  zellij_config="$(spawn_frontier_file "zellij/config.kdl" 2>/dev/null || true)"

  if [[ -z "${STARSHIP_CONFIG:-}" ]] && command -v starship >/dev/null 2>&1 && [[ -n "$starship_config" ]]; then
    export STARSHIP_CONFIG="$starship_config"
  fi

  if [[ -z "${ATUIN_CONFIG:-}" ]] && command -v atuin >/dev/null 2>&1 && [[ -n "$atuin_config" ]]; then
    export ATUIN_CONFIG="$atuin_config"
  fi

  if [[ -z "${ZELLIJ_CONFIG_DIR:-}" ]] && command -v zellij >/dev/null 2>&1 && [[ -n "$zellij_config" ]]; then
    zellij_config_dir="$(dirname "$zellij_config")"
    export ZELLIJ_CONFIG_DIR="$zellij_config_dir"
  fi
}

# spawn_gemini_api_key — REMOVED
# Gemini CLI handles its own auth (OAuth or GEMINI_API_KEY from env).
# The keychain prober was overriding OAuth sessions and causing auth failures.
# If GEMINI_API_KEY is needed, set it in your shell env before spawning.

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
  local q_root q_agent q_prompt_id q_run_id q_loop_nr q_skill_code
  q_meta="$(printf '%q' "$meta_path")"
  q_report="$(printf '%q' "$report_path")"
  q_transcript="$(printf '%q' "$transcript_path")"
  q_common="$(printf '%q' "$common_path")"
  q_cmd="$(printf '%q' "$command")"
  q_root="$(printf '%q' "${SPAWN_ROOT:-}")"
  q_agent="$(printf '%q' "${SPAWN_AGENT:-}")"
  q_prompt_id="$(printf '%q' "${SPAWN_PROMPT_ID:-}")"
  q_run_id="$(printf '%q' "${SPAWN_RUN_ID:-}")"
  q_loop_nr="$(printf '%q' "${SPAWN_LOOP_NR:-0}")"
  q_skill_code="$(printf '%q' "${SPAWN_SKILL_CODE:-}")"

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
export SPAWN_LOOP_NR=$q_loop_nr
export SPAWN_SKILL_CODE=$q_skill_code

rm -f "\$transcript" "\$report"
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

if bash -c "$SPAWN_CMD"; then
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

  osascript <<EOF_APPLE
 tell application "Terminal"
   activate
   do script $command_json
 end tell
EOF_APPLE
}

spawn_open_iterm() {
  local launcher="$1"
  command -v osascript >/dev/null 2>&1 || return 1
  [[ "${TERM_PROGRAM:-}" == "iTerm.app" || -n "${ITERM_SESSION_ID:-}" ]] || return 1

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

  osascript <<EOF_APPLE
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

spawn_in_zellij_pane() {
  local launcher="$1"
  local pane_name="${2:-agent}"
  if [[ -n "${ZELLIJ:-}" ]] && command -v zellij >/dev/null 2>&1; then
    # Spawned agent opens to the right of the orchestrator (bottom zone)
    zellij run --name "$pane_name" --direction right -- /bin/zsh -l -c "bash '$launcher'"
    return 0
  fi
  return 1
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

  if (( dry_run )); then
    printf 'Dry run mode: launcher generated only: %s\n' "$launcher"
    return 0
  fi

  case "$runtime" in
    terminal|visible)
      if spawn_in_zellij_pane "$launcher" "$pane_name"; then
        :
      elif spawn_open_iterm "$launcher" 2>/dev/null; then
        :
      elif command -v osascript >/dev/null 2>&1; then
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

  # ── 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. branded spawn output ──────────────────────────────
  local _dim='\033[2m'    _bold='\033[1m'
  local _copper='\033[38;5;173m'  _steel='\033[38;5;247m'
  local _reset='\033[0m'
  local _bar="${_steel}──────────────────────────────────${_reset}"

  printf '\n%b ⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. · %s-%s%b\n' "$_bold$_copper" "$agent" "$mode" "$_reset"
  printf '%b\n' "$_bar"
  printf '%b  plan:    %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_PLAN:-—}" "$_reset"
  printf '%b  report:  %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_REPORT:-—}" "$_reset"
  printf '%b  trace:   %b%s%b\n'   "$_steel" "$_reset" "${SPAWN_TRANSCRIPT:-—}" "$_reset"
  printf '%b  runtime: %b%s%b\n'   "$_steel" "$_reset" "$runtime" "$_reset"
  printf '%b\n' "$_bar"
  printf '%b  Agent launched.%b\n\n' "$_dim" "$_reset"
}

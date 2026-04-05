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

spawn_org_repo() {
  local root="${1:-$(spawn_repo_root)}"
  local fallback_to_basename="${2:-1}"
  local org_repo=""
  org_repo="$(cd "$root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"
  if [[ -n "$org_repo" ]]; then
    printf '%s\n' "$org_repo"
  elif [[ "$fallback_to_basename" == "1" ]]; then
    printf '%s\n' "$(basename "$root")"
  else
    printf '\n'
  fi
}

spawn_skill_prefix() {
  local name="${1:-}"
  case "$name" in
    agents) printf 'agnt\n' ;;
    decorate) printf 'deco\n' ;;
    delegate) printf 'delg\n' ;;
    dou) printf 'vdou\n' ;;
    followup) printf 'fwup\n' ;;
    hydrate) printf 'hydr\n' ;;
    implement|prompt) printf 'impl\n' ;;
    init) printf 'init\n' ;;
    justdo) printf 'just\n' ;;
    marbles) printf 'marb\n' ;;
    partner) printf 'prtn\n' ;;
    plan) printf 'plan\n' ;;
    prune) printf 'prun\n' ;;
    release) printf 'rels\n' ;;
    research) printf 'rsch\n' ;;
    review) printf 'rvew\n' ;;
    scaffold) printf 'scaf\n' ;;
    workflow) printf 'wflw\n' ;;
    *)
      if [[ -n "$name" ]]; then
        printf '%.4s\n' "$name"
      else
        printf 'impl\n'
      fi
      ;;
  esac
}

spawn_generate_run_id() {
  local prefix="${1:-impl}"
  printf '%s-%s\n' "$prefix" "$(date +%H%M%S)"
}

spawn_has_ambient_run_context() {
  [[ -n "${SPAWN_AGENT:-}" ]] || return 1
  [[ -n "${SPAWN_RUN_ID:-}" ]] || return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  [[ "${SPAWN_RUN_ID}" == "${VIBECRAFTED_RUN_ID}" ]] || return 1
  [[ -z "${VIBECRAFTED_OPERATOR_SESSION:-}" ]] || return 1
  spawn_in_zellij_context && return 1
  return 0
}

spawn_effective_run_id() {
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_RUN_ID:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_ID}"
}

spawn_effective_run_lock() {
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_RUN_LOCK:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_RUN_LOCK}"
}

spawn_effective_skill_code() {
  spawn_has_ambient_run_context && return 1
  [[ -n "${VIBECRAFTED_SKILL_CODE:-}" ]] || return 1
  printf '%s\n' "${VIBECRAFTED_SKILL_CODE}"
}

# Central artifact store: $HOME/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/
# Override with VIBECRAFTED_HOME env var for custom location
# Falls back to <repo>/.vibecrafted/ if git remote unavailable
VIBECRAFTED_HOME="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"

spawn_store_dir() {
  local root="${1:-$(spawn_repo_root)}"
  local org_repo=""
  org_repo="$(spawn_org_repo "$root" 0)"
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
  if [[ -n "${VIBECRAFTED_STORE_DIR:-}" ]]; then
    spawn_abspath "$VIBECRAFTED_STORE_DIR"
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
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/VERSION}" \
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
import re
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

# Parse session_id from transcript (strip ANSI, match "session: <uuid>")
transcript_path = payload.get("transcript", "")
if transcript_path:
    try:
        with open(transcript_path, "r", errors="replace") as tf:
            raw = tf.read(64 * 1024)  # first 64KB is enough
        clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
        m = re.search(r'session: ([a-f0-9-]{8,})', clean)
        if m:
            payload["session_id"] = m.group(1)
    except (OSError, IOError):
        pass  # transcript not readable — skip silently

with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

spawn_create_run_lock() {
  local run_id="$1"
  local agent="$2"
  local skill="$3"
  local root="$4"
  local org_repo lock_dir lock_file

  org_repo="$(spawn_org_repo "$root")"
  lock_dir="$VIBECRAFTED_HOME/locks/$org_repo"
  mkdir -p "$lock_dir"
  lock_file="$lock_dir/${run_id}.lock"
  cat > "$lock_file" <<LOCK
run_id=$run_id
agent=$agent
skill=$skill
root=$root
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=running
LOCK
  printf '%s\n' "$lock_file"
}

spawn_prepare_paths() {
  local agent="$1"
  local prompt_file="$2"
  local root="${3:-}"
  local mode="${4:-${VIBECRAFTED_SKILL_NAME:-}}"
  local skill_name="${VIBECRAFTED_SKILL_NAME:-$mode}"
  local lock_file=""

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
  SPAWN_SKILL_CODE="$(spawn_effective_skill_code 2>/dev/null || true)"
  if [[ -z "$SPAWN_SKILL_CODE" && -n "$skill_name" ]]; then
    SPAWN_SKILL_CODE="$(spawn_skill_prefix "$skill_name")"
  fi
  SPAWN_LOOP_NR="${VIBECRAFTED_LOOP_NR:-0}"
  case "$SPAWN_LOOP_NR" in
    ''|*[!0-9]*)
      SPAWN_LOOP_NR=0
      ;;
  esac
  SPAWN_RUN_ID="$(spawn_effective_run_id 2>/dev/null || true)"
  if [[ -n "$SPAWN_RUN_ID" ]]; then
    :
  else
    SPAWN_RUN_ID="$(spawn_generate_run_id "${SPAWN_SKILL_CODE:-impl}")"
  fi
  lock_file="$(spawn_effective_run_lock 2>/dev/null || true)"
  if [[ -z "$lock_file" || ! -f "$lock_file" ]]; then
    lock_file="$VIBECRAFTED_HOME/locks/$(spawn_org_repo "$SPAWN_ROOT")/${SPAWN_RUN_ID}.lock"
  fi
  if [[ ! -f "$lock_file" ]]; then
    lock_file="$(spawn_create_run_lock "$SPAWN_RUN_ID" "$agent" "${skill_name:-${mode:-implement}}" "$SPAWN_ROOT")"
  fi
  SPAWN_RUN_LOCK="$lock_file"

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
  export SPAWN_ROOT SPAWN_PLAN SPAWN_SLUG SPAWN_TS SPAWN_AGENT SPAWN_PROMPT_ID SPAWN_RUN_ID SPAWN_RUN_LOCK SPAWN_SKILL_CODE SPAWN_LOOP_NR
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


spawn_write_frontmatter() {
  local target_file="$1"
  local agent="${2:-${SPAWN_AGENT:-unknown}}"
  local model="${3:-${SPAWN_MODEL:-unknown}}"
  local status="${4:-pending}"

  cat > "$target_file" <<EOF_FM
---
run_id: ${SPAWN_RUN_ID:-unknown}
prompt_id: ${SPAWN_PROMPT_ID:-unknown}
agent: $agent
skill: ${SPAWN_SKILL_CODE:-unknown}
model: $model
status: $status
---

EOF_FM
}

spawn_build_runtime_prompt() {
  local source_file="$1"
  local runtime_file="$2"
  local report_path="$3"
  local agent="${4:-${SPAWN_AGENT:-agent}}"
  local model="${5:-${SPAWN_MODEL:-unknown}}"

  spawn_write_frontmatter "$runtime_file" "$agent" "$model" "prompt"

  # Strip existing frontmatter (so we don't have double) and append the plan
  awk '
    BEGIN { in_fm=0; fm_done=0; }
    NR==1 && /^---[ 	]*$/ { in_fm=1; next; }
    in_fm && /^---[ 	]*$/ { in_fm=0; fm_done=1; next; }
    in_fm { next; }
    { print }
  ' "$source_file" >> "$runtime_file"

  cat >> "$runtime_file" <<EOF_PROMPT

At the end of the task, write your final human-readable report to this exact path:
Report path: $report_path

Keep streaming useful progress to stdout while you work. If you cannot write a
standalone report file, finish normally and let the transcript act as the fallback
artifact.

When writing your report file, include YAML frontmatter at the top (use the exact frontmatter that this prompt starts with, but change status to 'completed' or 'failed').
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
    "${VIBECRAFTED_ROOT:+$VIBECRAFTED_ROOT/config}" \
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

  # Re-pin the active frontier assets every time so spawned sessions do not
  # inherit stale shell config from an unrelated install or repo.
  if command -v starship >/dev/null 2>&1 && [[ -n "$starship_config" ]]; then
    export STARSHIP_CONFIG="$starship_config"
  fi

  if command -v atuin >/dev/null 2>&1 && [[ -n "$atuin_config" ]]; then
    export ATUIN_CONFIG="$atuin_config"
  fi

  if command -v zellij >/dev/null 2>&1 && [[ -n "$zellij_config" ]]; then
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
  local q_root q_agent q_prompt_id q_run_id q_run_lock q_loop_nr q_skill_code
  local q_operator_session q_spawn_direction
  q_meta="$(printf '%q' "$meta_path")"
  q_report="$(printf '%q' "$report_path")"
  q_transcript="$(printf '%q' "$transcript_path")"
  q_common="$(printf '%q' "$common_path")"
  q_cmd="$(printf '%q' "$command")"
  q_root="$(printf '%q' "${SPAWN_ROOT:-}")"
  q_agent="$(printf '%q' "${SPAWN_AGENT:-}")"
  q_prompt_id="$(printf '%q' "${SPAWN_PROMPT_ID:-}")"
  q_run_id="$(printf '%q' "${SPAWN_RUN_ID:-}")"
  q_run_lock="$(printf '%q' "${SPAWN_RUN_LOCK:-}")"
  q_loop_nr="$(printf '%q' "${SPAWN_LOOP_NR:-0}")"
  q_skill_code="$(printf '%q' "${SPAWN_SKILL_CODE:-}")"
  q_operator_session="$(printf '%q' "${VIBECRAFTED_OPERATOR_SESSION:-}")"
  q_spawn_direction="$(printf '%q' "${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-}")"

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
export VIBECRAFTED_RUN_ID=$q_run_id
export VIBECRAFTED_RUN_LOCK=$q_run_lock
export VIBECRAFTED_SKILL_CODE=$q_skill_code
export VIBECRAFTED_OPERATOR_SESSION=$q_operator_session
export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=$q_spawn_direction

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

spawn_in_zellij_context() {
  [[ "${ZELLIJ:-}" == "0" ]] && return 1
  [[ -n "${ZELLIJ_PANE_ID:-}" ]] || [[ -n "${ZELLIJ:-}" ]]
}

spawn_current_zellij_session_name() {
  printf '%s\n' "${ZELLIJ_SESSION_NAME:-}"
}

spawn_in_target_zellij_session() {
  local target_session="${VIBECRAFTED_OPERATOR_SESSION:-}"
  spawn_in_zellij_context || return 1
  [[ -n "$target_session" ]] || return 0
  [[ "$(spawn_current_zellij_session_name)" == "$target_session" ]]
}

spawn_pane_direction() {
  # Grid policy: 4 per row, 8 per tab, 9th opens new tab.
  # Uses SPAWN_LOOP_NR (marbles) or VIBECRAFTED_PANE_SEQ (manual).
  local seq="${SPAWN_LOOP_NR:-${VIBECRAFTED_PANE_SEQ:-0}}"
  local max_per_row=4
  local max_per_tab=8

  if (( seq >= max_per_tab )); then
    printf 'new-tab\n'
  elif (( seq > 0 && seq % max_per_row == 0 )); then
    printf 'down\n'
  else
    printf 'right\n'
  fi
}

spawn_in_zellij_pane() {
  local launcher="$1"
  local pane_name="${2:-agent}"
  local direction="${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-$(spawn_pane_direction)}"

  if spawn_in_zellij_context && command -v zellij >/dev/null 2>&1; then
    if [[ "$direction" == "new-tab" ]]; then
      zellij action new-tab \
        --name "$pane_name" \
        --cwd "${SPAWN_ROOT:-$(pwd)}" \
        -- /bin/zsh -l -c "bash '$launcher'"
    else
      zellij action new-pane \
        --direction "$direction" \
        --name "$pane_name" \
        --cwd "${SPAWN_ROOT:-$(pwd)}" \
        -- /bin/zsh -l -c "bash '$launcher'"
    fi
    return 0
  fi
  return 1
}

spawn_in_operator_session() {
  local launcher="$1"
  local pane_name="${2:-agent}"
  local session_name="${VIBECRAFTED_OPERATOR_SESSION:-}"
  local direction="${VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION:-$(spawn_pane_direction)}"

  [[ -n "$session_name" ]] || return 1
  command -v zellij >/dev/null 2>&1 || return 1

  # External spawn into existing operator session — route as pane or new tab per grid policy.
  if [[ "$direction" == "new-tab" ]]; then
    zellij --session "$session_name" action new-tab \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- /bin/zsh -l -c "bash '$launcher'"
  else
    zellij --session "$session_name" action new-pane \
      --direction "$direction" \
      --name "$pane_name" \
      --cwd "${SPAWN_ROOT:-$(pwd)}" \
      -- /bin/zsh -l -c "bash '$launcher'"
  fi
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

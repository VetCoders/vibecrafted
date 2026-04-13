#!/usr/bin/env bash
set -euo pipefail
# Marbles chain trigger — called by success_hook inside agent launcher.
# Spawns the next loop iteration or writes CONVERGENCE.md when done.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

failed=0
if [[ "${1:-}" == "--failed" ]]; then
  failed=1
  shift
fi

state_dir="$1"
total_count="$2"
current="$3"
run_id="$4"
root_dir="$5"
runtime="$6"
scripts_dir="$7"
session_lock="$8"
store="${9:-$(spawn_marbles_store_dir "$root_dir")}"

state_file="$state_dir/state.json"
god_plan="$state_dir/god.md"
ancestor_plan="$state_dir/ancestor.md"
ancestor_slug="$(spawn_slug_from_path "$ancestor_plan")"
next=$((current + 1))
report_sync_timeout_s="${VIBECRAFTED_MARBLES_REPORT_TIMEOUT_S:-5400}"
case "$report_sync_timeout_s" in
  ''|*[!0-9]*)
    report_sync_timeout_s=5400
    ;;
esac
report_poll_s=5

_state_json_edit() {
  local mutator="$1"
  shift

  command -v python3 >/dev/null 2>&1 || return 1

  STATE_JSON_MUTATOR="$mutator" python3 - "$state_file" "$@" <<'PY'
import datetime
import fcntl
import json
import os
import sys
import tempfile

state_path = sys.argv[1]
args = sys.argv[2:]
mutator = os.environ["STATE_JSON_MUTATOR"]

lock = open(state_path + ".lock", "a+", encoding="utf-8")
try:
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        with open(state_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {}

    exec(mutator, {"datetime": datetime}, {"payload": payload, "args": args})

    dir_path = os.path.dirname(state_path) or "."
    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(state_path) + ".", dir=dir_path
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_path, state_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
finally:
    lock.close()
PY
}

_loop_child_plan() {
  local loop_nr="$1"
  spawn_marbles_child_plan_path "$store" "$ancestor_plan" "$loop_nr"
}

_find_meta_for_loop() {
  local loop_nr="$1"
  local expected_run_id="${run_id}-$(printf '%03d' "$loop_nr")"
  spawn_find_meta_for_run_id "$store/reports" "$expected_run_id"
}

_read_loop_state() {
  local loop_nr="$1"
  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

target = None
for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        target = loop

if target is None:
    print("\t")
else:
    print(f"{target.get('status', '')}\t{target.get('report', '')}")
PY
  else
    printf '\t\n'
  fi
}

_read_session_id() {
  local loop_nr="$1"
  local meta_path=""
  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    spawn_read_meta_field "$meta_path" "session_id"
    return 0
  fi

  if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        print(loop.get("session_id", ""), end="")
        raise SystemExit(0)
PY
  fi
}

_read_loop_agent() {
  local loop_nr="$1"
  local meta_path=""
  local agent_name=""

  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    agent_name="$(spawn_read_meta_field "$meta_path" "agent")"
  fi

  if [[ -z "$agent_name" ]]; then
    local child_plan=""
    child_plan="$(_loop_child_plan "$loop_nr")"
    if [[ -f "$child_plan" ]]; then
      agent_name="$(spawn_frontmatter_field "$child_plan" "agent")"
    fi
  fi

  if [[ -z "$agent_name" && -f "$ancestor_plan" ]]; then
    agent_name="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
  fi

  printf '%s' "$agent_name"
}

_loop_report_path() {
  local loop_nr="$1"
  local meta_path=""
  local report_path=""

  meta_path="$(_find_meta_for_loop "$loop_nr")"
  if [[ -n "$meta_path" ]]; then
    report_path="$(spawn_read_meta_field "$meta_path" "report")"
  fi

  if [[ -z "$report_path" && -f "$state_file" ]]; then
    local loop_state=""
    loop_state="$(_read_loop_state "$loop_nr")"
    report_path="${loop_state#*$'\t'}"
  fi

  printf '%s' "$report_path"
}

_wait_for_loop_report() {
  local loop_nr="$1"
  local timeout_s="${2:-0}"
  local elapsed=0
  local report_path=""

  while true; do
    report_path="$(_loop_report_path "$loop_nr")"
    if [[ -n "$report_path" && -s "$report_path" ]]; then
      printf '%s\n' "$report_path"
      return 0
    fi

    if [[ -f "$state_file" ]]; then
      local loop_state=""
      local loop_status=""
      loop_state="$(_read_loop_state "$loop_nr")"
      loop_status="${loop_state%%$'\t'*}"
      if [[ "$loop_status" == "timed_out" || "$loop_status" == "failed" || "$loop_status" == "stopped" ]]; then
        return 2
      fi
    fi

    local meta_path=""
    meta_path="$(_find_meta_for_loop "$loop_nr")"
    if [[ -n "$meta_path" ]]; then
      local meta_status=""
      meta_status="$(spawn_read_meta_field "$meta_path" "status")"
      if [[ "$meta_status" == "failed" ]]; then
        return 2
      fi
    fi

    if (( timeout_s > 0 && elapsed >= timeout_s )); then
      return 1
    fi

    sleep "$report_poll_s"
    (( elapsed += report_poll_s ))
  done
}

_update_lock() {
  local key="$1"
  local val="$2"
  [[ -f "$session_lock" ]] || return 0
  if sed --version >/dev/null 2>&1; then
    sed -i "s/^${key}=.*/${key}=${val}/" "$session_lock"
  else
    sed -i '' "s/^${key}=.*/${key}=${val}/" "$session_lock"
  fi
}

_refresh_state_steering_fields() {
  # NOTE: does NOT update ancestor_mtime — that field tracks the mtime baseline
  # for steering detection.  The baseline is consumed (updated) after the
  # steering check in the main loop via _consume_ancestor_mtime_signal.
  if [[ -f "$state_file" ]]; then
    if ! _state_json_edit "$(cat <<'PY'
payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
payload["god_plan"] = args[0]
payload["ancestor_plan"] = args[1]
payload["plan"] = args[1]
PY
)" "$god_plan" "$ancestor_plan"; then
      printf '    [warn] state refresh failed (python exit %d) — loop continues with stale state\n' "$?" >&2
    fi
  fi
}

_consume_ancestor_mtime_signal() {
  local current_mtime=""
  current_mtime="$(spawn_ancestor_mtime_iso "$ancestor_plan")"
  if [[ -n "$current_mtime" && -f "$state_file" ]]; then
    _state_json_edit "$(cat <<'PY'
payload["ancestor_mtime"] = args[0]
PY
)" "$current_mtime" >/dev/null || true
  fi
}

_rewrite_loop_plan_frontmatter() {
  local loop_plan="$1"
  local loop_agent="$2"
  local loop_model="$3"

  [[ -f "$loop_plan" ]] || return 0

  python3 - "$loop_plan" "$loop_agent" "$loop_model" <<'PY'
import pathlib
import re
import sys

plan, agent, model = sys.argv[1:4]
text = pathlib.Path(plan).read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
if not m:
    raise SystemExit(0)
fm = m.group(1)
fm = re.sub(r"^agent:.*$", f"agent: {agent}", fm, flags=re.MULTILINE)
if model:
    if re.search(r"^model:", fm, re.MULTILINE):
        fm = re.sub(r"^model:.*$", f"model: {model}", fm, flags=re.MULTILINE)
    else:
        fm += f"model: {model}\n"
elif re.search(r"^model:", fm, re.MULTILINE):
    fm = re.sub(r"^model:.*\n", "", fm, flags=re.MULTILINE)
pathlib.Path(plan).write_text(f"---\n{fm}---\n{text[m.end():]}", encoding="utf-8")
PY
}

_write_missing_report_failure() {
  local loop_nr="$1"
  local reason="$2"
  local loop_agent="$3"
  local convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $loop_agent
status: FAILED
failed_at_loop: $loop_nr
total_loops: $total_count
reason: missing_report
---

# Marbles Convergence — FAILED

Loop $loop_nr of $total_count did not produce an observed report.

- Reason: $reason
- Sync timeout: ${report_sync_timeout_s}s
- Effect: no further loops were spawned, so the loop budget was not consumed
- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles blocked at loop %s/%s\033[0m\n' "$loop_nr" "$total_count"
  printf '    Missing report guard: %s\n' "$reason"
  printf '    Convergence: %s\n' "$convergence"
}

_write_invalid_ancestor_failure() {
  local loop_nr="$1"
  local invalid_agent="$2"
  local convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $invalid_agent
status: FAILED
failed_at_loop: $loop_nr
total_loops: $total_count
reason: invalid_ancestor_agent
---

# Marbles Convergence — FAILED

'ancestor.md' requested an invalid agent for loop $loop_nr.

- Invalid agent: ${invalid_agent:-<empty>}
- Expected: claude, codex, or gemini
- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles blocked before loop %s/%s\033[0m\n' "$loop_nr" "$total_count"
  printf '    Invalid ancestor agent: %s\n' "${invalid_agent:-<empty>}"
  printf '    Convergence: %s\n' "$convergence"
}

_collect_reports() {
  local up_to="$1"
  local loop_nr=""
  local report_path=""

  for ((loop_nr = 1; loop_nr <= up_to; loop_nr++)); do
    report_path="$(_loop_report_path "$loop_nr")"
    if [[ -n "$report_path" && -f "$report_path" ]]; then
      printf '%s\n' "$report_path"
    fi
  done
}

_launch_verification() {
  local loop_nr="$1"
  local is_final="${2:-0}"
  local sid=""
  local loop_agent=""
  local report_path=""

  sid="$(_read_session_id "$loop_nr")"
  if [[ -z "$sid" ]]; then
    printf '    ⚠ No session_id for L%s — skipping verification\n' "$loop_nr"
    return 0
  fi

  report_path="$(_loop_report_path "$loop_nr")"
  if [[ -z "$report_path" ]]; then
    printf '    ⚠ No report path for L%s — skipping verification\n' "$loop_nr"
    return 0
  fi

  loop_agent="$(_read_loop_agent "$loop_nr")"
  [[ -n "$loop_agent" ]] || loop_agent="codex"

  local reports_list=""
  while IFS= read -r rpt; do
    [[ -n "$rpt" ]] || continue
    reports_list="${reports_list}
- ${rpt}"
  done < <(_collect_reports "$loop_nr")

  local verified_path="${report_path%.md}_verified.md"
  local prompt="You are resuming to self-audit your own report from marbles loop L${loop_nr}.

## Instructions
1. Read ALL reports from this batch:${reports_list}
2. Re-read your own report critically
3. Write a verified report to: ${verified_path}
4. The verified report should:
   - Confirm or correct your original findings
   - Note any contradictions with other loops' reports
   - Add anything you missed"

  if (( is_final )); then
    prompt="${prompt}

## Final Loop — Convergence Assessment
This is the final loop. Your verified report MUST include:
- **Convergence verdict**: Has the codebase converged? (yes/no/partial)
- **Remaining issues**: Any P0/P1 still open after all loops
- **Next workflow recommendation**: What should the team do next (e.g., ship, another marbles run with different focus, manual review of specific area)
"
  fi

  prompt="${prompt}

## Constraints
- Do NOT modify any code files — only write your verified report
- Be honest about uncertainty — flag anything you cannot verify
- Keep the verified report concise and actionable"

  if [[ -f "$state_file" ]]; then
    _state_json_edit "$(cat <<'PY'
payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in payload.get("loops", []):
    if loop.get("loop") == int(args[0]):
        loop["verification_status"] = "pending"
PY
)" "$loop_nr" >/dev/null || true
  fi

  printf '    🔍 Verification L%s → session %s\n' "$loop_nr" "${sid:0:13}…"
  case "$loop_agent" in
    claude) nohup claude --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    codex)  nohup codex resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    gemini) nohup gemini --resume "$sid" "$prompt" >/dev/null 2>&1 & ;;
    *) printf '    ⚠ Unknown loop agent %s — skipping verification\n' "$loop_agent" ;;
  esac
}

_write_spawn_failure_artifacts() {
  local loop_nr="$1"
  local loop_agent="$2"
  local loop_plan="$3"
  local reason="$4"
  local exit_code="${5:-1}"
  local loop_run_id="${run_id}-$(printf '%03d' "$loop_nr")"
  local stamp=""
  local base=""
  local report_path=""
  local transcript_path=""
  local meta_path=""
  local prompt_id="marbles-ancestor_L${loop_nr}_$(date +%Y%m%d)"

  stamp="$(spawn_timestamp)"
  base="$store/reports/${stamp}_marbles-${ancestor_slug}_L${loop_nr}_${loop_agent}"
  report_path="${base}.md"
  transcript_path="${base}.transcript.log"
  meta_path="${base}.meta.json"

  mkdir -p "$store/reports"

  spawn_write_frontmatter "$transcript_path" "$loop_agent" "unknown" "failed"
  cat >> "$transcript_path" <<TXT
Scheduling failure before loop ${loop_nr} could launch.
Reason: ${reason}
Exit code: ${exit_code}
Run ID: ${loop_run_id}
Plan: ${loop_plan}
TXT

  spawn_write_frontmatter "$report_path" "$loop_agent" "unknown" "failed"
  cat >> "$report_path" <<TXT
Marbles failed before loop ${loop_nr} could launch.

- Reason: ${reason}
- Exit code: ${exit_code}
- Planned agent: ${loop_agent}
- Planned run_id: ${loop_run_id}
- Plan: ${loop_plan}
- Ancestor: ${ancestor_plan}
TXT

  SPAWN_PROMPT_ID="$prompt_id" \
  SPAWN_RUN_ID="$loop_run_id" \
  SPAWN_LOOP_NR="$loop_nr" \
  SPAWN_SKILL_CODE="impl" \
  spawn_write_meta \
    "$meta_path" \
    "failed" \
    "$loop_agent" \
    "implement" \
    "$root_dir" \
    "$loop_plan" \
    "$report_path" \
    "$transcript_path" \
    "$scripts_dir/${loop_agent}_spawn.sh"

  SPAWN_PROMPT_ID="$prompt_id" \
  SPAWN_RUN_ID="$loop_run_id" \
  SPAWN_LOOP_NR="$loop_nr" \
  SPAWN_SKILL_CODE="impl" \
  spawn_finish_meta "$meta_path" "failed" "$exit_code"

  printf '    ⚠ Next loop L%s failed before launch metadata stabilized (%s, exit %s)\n' \
    "$loop_nr" "$reason" "$exit_code"
}

_launch_next_loop() {
  local loop_nr="$1"
  local loop_agent="$2"
  local loop_model="$3"
  local loop_plan="$4"
  local loop_run_id="${run_id}-$(printf '%03d' "$loop_nr")"
  local q_state=""
  local q_root=""
  local q_runtime=""
  local q_scripts=""
  local q_lock=""
  local q_store=""
  local success_hook=""
  local failure_hook=""
  local spawn_args=()

  _update_lock current "$loop_nr"
  printf '\n\033[38;5;173m ⚒  Marbles loop %s/%s starting...\033[0m\n' "$loop_nr" "$total_count"

  q_state="$(spawn_shell_quote "$state_dir")"
  q_root="$(spawn_shell_quote "$root_dir")"
  q_runtime="$(spawn_shell_quote "$runtime")"
  q_scripts="$(spawn_shell_quote "$scripts_dir")"
  q_lock="$(spawn_shell_quote "$session_lock")"
  q_store="$(spawn_shell_quote "$store")"

  success_hook="bash $q_scripts/marbles_next.sh $q_state $total_count $loop_nr $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"
  failure_hook="bash $q_scripts/marbles_next.sh --failed $q_state $total_count $loop_nr $run_id $q_root $q_runtime $q_scripts $q_lock $q_store"

  spawn_args=(
    --mode implement
    --runtime "$runtime"
    --root "$root_dir"
    --success-hook "$success_hook"
    --failure-hook "$failure_hook"
  )
  if [[ -n "$loop_model" && "$loop_agent" != "codex" ]]; then
    spawn_args+=(--model "$loop_model")
  fi

  VIBECRAFTED_LOOP_NR="$loop_nr" \
  VIBECRAFTED_RUN_ID="$loop_run_id" \
  VIBECRAFTED_SKILL_CODE="marb" \
  VIBECRAFTED_SKILL_NAME="marbles" \
  VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=right \
  VIBECRAFTED_MARBLES_TAB_NAME="${VIBECRAFTED_MARBLES_TAB_NAME:-}" \
  VIBECRAFTED_STORE_DIR="$store" \
  VIBECRAFTED_STORE_ROOT="$root_dir" \
  bash "$scripts_dir/${loop_agent}_spawn.sh" "${spawn_args[@]}" "$loop_plan"
}

current_agent="$(_read_loop_agent "$current")"
[[ -n "$current_agent" ]] || current_agent="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
[[ -n "$current_agent" ]] || current_agent="unknown"

if (( failed )); then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"
  cat > "$convergence" <<CONV
---
run_id: $run_id
agent: $current_agent
status: FAILED
failed_at_loop: $current
total_loops: $total_count
---

# Marbles Convergence — FAILED

Loop $current of $total_count failed.
Check individual loop reports for details.

- GOD: $god_plan
- ANCESTOR: $ancestor_plan
CONV

  _update_lock status failed
  printf '\n\033[31m ✗  Marbles failed at loop %s/%s\033[0m\n' "$current" "$total_count"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

if _wait_for_loop_report "$current" "$report_sync_timeout_s" >/dev/null; then
  :
else
  wait_status=$?
  case "$wait_status" in
    2)
      _write_missing_report_failure "$current" "watcher or launcher marked loop as failed" "$current_agent"
      ;;
    *)
      _write_missing_report_failure "$current" "report not observed within ${report_sync_timeout_s}s" "$current_agent"
      ;;
  esac
  exit 0
fi

# Capture ancestor_mtime BEFORE refresh so the steering check below can detect
# whether the child modified ancestor.md during this loop.
_pre_refresh_ancestor_mtime=""
if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
  _pre_refresh_ancestor_mtime="$(python3 -c "
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    print(json.load(f).get('ancestor_mtime', ''))
" "$state_file")"
fi

_refresh_state_steering_fields

if [[ $next -gt $total_count ]]; then
  convergence="$store/reports/$(spawn_timestamp)_marbles-${ancestor_slug}_CONVERGENCE.md"

  {
    cat <<HEADER
---
run_id: $run_id
agent: $current_agent
status: completed
loops_completed: $total_count
god_plan: $god_plan
ancestor_plan: $ancestor_plan
---

# Marbles Convergence — Complete

$total_count loops completed successfully.

## Steering Surfaces
- GOD: $god_plan
- ANCESTOR: $ancestor_plan

## Loop Reports
HEADER

    while IFS= read -r rpt; do
      [[ -n "$rpt" ]] || continue
      printf '\n### %s\n\n' "$(basename "$rpt")"
      head -20 "$rpt" 2>/dev/null || printf '(report not readable)\n'
      printf '\n...\n'
    done < <(_collect_reports "$total_count")

    printf '\n---\n𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents (c)2024-2026 VetCoders\n'
  } > "$convergence"

  _launch_verification "$current" 1
  _update_lock status completed
  printf '\n\033[32m ✓  Marbles complete: %s loops · %s\033[0m\n' "$total_count" "$run_id"
  printf '    Convergence: %s\n' "$convergence"
  exit 0
fi

_launch_verification "$current" 0

# --- Resolve next-loop agent and model ---
# Sources, in priority order:
#   1. Ancestor steering: if the child modified ancestor.md (mtime changed)
#      AND set a different agent than the session seed, honour explicit steering.
#   2. Rotation schedule: if mode is not "single", compute the scheduled agent.
#   3. Ancestor raw agent (unsteered seed) / current agent fallback.
# Model follows the same hierarchy: steering override → ancestor raw → empty.
_rotation_mode="single"
_seed_agent=""
# Use the mtime captured BEFORE _refresh_state_steering_fields updated it.
# After refresh, state.json.ancestor_mtime == current file mtime, hiding
# changes the child made during this loop.
_stored_ancestor_mtime="$_pre_refresh_ancestor_mtime"
if [[ -f "$state_file" ]] && command -v python3 >/dev/null 2>&1; then
  read -r _rotation_mode _seed_agent < <(python3 - "$state_file" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
print(d.get("rotation", "single"), d.get("agent", ""))
PY
  )
fi

next_plan="$(_loop_child_plan "$next")"
next_plan_tmp="${next_plan}.tmp"
rm -f "$next_plan_tmp"
spawn_marbles_write_child_plan "$ancestor_plan" "$next_plan_tmp"

_ancestor_agent="$(spawn_frontmatter_field "$next_plan_tmp" "agent")"
_ancestor_model="$(spawn_frontmatter_field "$next_plan_tmp" "model")"

# Determine if ancestor.md was explicitly steered by the previous child.
# Steering requires: (a) ancestor has a non-empty agent, (b) it differs from
# the session seed, and (c) ancestor.md mtime changed since session start
# (or no stored mtime exists for backward compat).
_ancestor_steered=0
if [[ -n "$_ancestor_agent" && -n "$_seed_agent" && "$_ancestor_agent" != "$_seed_agent" ]]; then
  _current_ancestor_mtime="$(spawn_ancestor_mtime_iso "$ancestor_plan")"
  if [[ -z "$_stored_ancestor_mtime" ]]; then
    # No stored mtime — trust the diff (backward compat with older state files)
    _ancestor_steered=1
  elif [[ "$_current_ancestor_mtime" != "$_stored_ancestor_mtime" ]]; then
    _ancestor_steered=1
  fi
fi

next_agent=""
next_model=""
_steering_source=""

if (( _ancestor_steered )); then
  next_agent="$_ancestor_agent"
  next_model="$_ancestor_model"
  _steering_source="ancestor-override ($next_agent via child steering)"
elif [[ "$_rotation_mode" != "single" && -n "$_rotation_mode" ]]; then
  _rotation_base="${_seed_agent:-${_ancestor_agent:-$current_agent}}"
  next_agent="$(spawn_rotation_schedule_agent "$_rotation_mode" "$_rotation_base" "$next")"
  next_model="$_ancestor_model"
  _steering_source="rotation-${_rotation_mode} (base=$_rotation_base, loop=$next → $next_agent)"
else
  next_model="$_ancestor_model"
  _steering_source="seed-fallback"
fi

# Fallbacks: ancestor raw agent, then current agent
if [[ -z "$next_agent" ]]; then
  next_agent="${_ancestor_agent:-$current_agent}"
  [[ -n "$_steering_source" && "$_steering_source" != "seed-fallback" ]] || \
    _steering_source="seed ($next_agent)"
fi

printf '    ↳ steering: %s\n' "$_steering_source"

# Consume the mtime signal so the next round sees only changes made by this child.
_consume_ancestor_mtime_signal

if [[ ! "$next_agent" =~ ^(claude|codex|gemini)$ ]]; then
  rm -f "$next_plan_tmp"
  _write_invalid_ancestor_failure "$next" "$next_agent"
  exit 0
fi

_rewrite_loop_plan_frontmatter "$next_plan_tmp" "$next_agent" "$next_model"
mv "$next_plan_tmp" "$next_plan"

launch_rc=0
_launch_next_loop "$next" "$next_agent" "$next_model" "$next_plan" || launch_rc=$?
if (( launch_rc != 0 )); then
  next_run_id="${run_id}-$(printf '%03d' "$next")"
  if [[ -z "$(spawn_find_meta_for_run_id "$store/reports" "$next_run_id")" ]]; then
    _write_spawn_failure_artifacts \
      "$next" \
      "$next_agent" \
      "$next_plan" \
      "next-loop spawn failed before meta.json was created" \
      "$launch_rc"
  fi
  exit "$launch_rc"
fi

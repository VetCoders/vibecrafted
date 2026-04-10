#!/usr/bin/env bash
set -euo pipefail
# Marbles Watcher — temporal guardian for convergence loops.
# Monitors promise → confirmed → done lifecycle per loop.
# Captures session IDs, tracks convergence trajectory, handles pause/stop.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

run_id="$1"
state_dir="$2"
total_count="$3"
root_dir="$4"
runtime="$5"
store="$6"
session_lock="$7"

ancestor_plan="$state_dir/ancestor.md"
god_plan="$state_dir/god.md"
state_file="$state_dir/state.json"
report_timeout_s="${VIBECRAFTED_MARBLES_REPORT_TIMEOUT_S:-5400}"
meta_timeout_s="${VIBECRAFTED_MARBLES_META_TIMEOUT_S:-60}"
case "$report_timeout_s" in
  ''|*[!0-9]*)
    report_timeout_s=5400
    ;;
esac
case "$meta_timeout_s" in
  ''|*[!0-9]*)
    meta_timeout_s=60
    ;;
esac
report_poll_s=5

_bold='\033[1m'
_copper='\033[38;5;173m'
_steel='\033[38;5;247m'
_green='\033[32m'
_yellow='\033[33m'
_red='\033[31m'
_dim='\033[2m'
_reset='\033[0m'

_write_state() {
  local tmp="$state_file.tmp"
  cat > "$tmp"
  mv "$tmp" "$state_file"
}

_init_state() {
  local initial_agent=""
  initial_agent="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
  [[ -n "$initial_agent" ]] || initial_agent="unknown"

  _write_state <<EOF
{
  "run_id": "$run_id",
  "agent": "$initial_agent",
  "mode": "steered",
  "plan": "$ancestor_plan",
  "god_plan": "$god_plan",
  "ancestor_plan": "$ancestor_plan",
  "root": "$root_dir",
  "runtime": "$runtime",
  "total_loops": $total_count,
  "current_loop": 0,
  "status": "initialized",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "watcher_pid": $$,
  "loops": [],
  "trajectory": []
}
EOF
}

_update_status() {
  local new_status="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$new_status" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

payload["status"] = sys.argv[2]
payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_start() {
  local loop_nr="$1"
  local transcript="$2"
  local agent_name="$3"
  local focus="$4"
  local ancestor_slug="$5"
  local model="${6:-}"

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$transcript" "$agent_name" "$focus" "$ancestor_slug" "$model" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

loop_nr = int(sys.argv[2])
transcript, agent_name, focus, ancestor_slug, model = sys.argv[3:8]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

payload["current_loop"] = loop_nr
payload["status"] = "promise"
payload["updated_at"] = now

loops = payload.get("loops", [])
target = None
for loop in loops:
    if loop.get("loop") == loop_nr:
      target = loop
      break

if target is None:
    target = {"loop": loop_nr, "started_at": now}
    loops.append(target)

target["status"] = "promise"
target["transcript"] = transcript
target["agent"] = agent_name
target["focus"] = focus
target["ancestor_slug"] = ancestor_slug
if model:
    target["model"] = model
elif "model" in target:
    target.pop("model", None)

payload["loops"] = loops

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_confirmed() {
  local loop_nr="$1"
  local session_id="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$session_id" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

payload["status"] = "confirmed"
payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        loop["status"] = "confirmed"
        loop["session_id"] = sys.argv[3]

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_done() {
  local loop_nr="$1"
  local report="$2"
  local duration="$3"
  local p0="${4:-}"
  local p1="${5:-}"
  local p2="${6:-}"
  local score="${7:-}"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$report" "$duration" "$p0" "$p1" "$p2" "$score" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

loop_nr = int(sys.argv[2])
report = sys.argv[3]
duration = int(sys.argv[4])
p0 = int(sys.argv[5]) if sys.argv[5] else None
p1 = int(sys.argv[6]) if sys.argv[6] else None
p2 = int(sys.argv[7]) if sys.argv[7] else None
score = int(sys.argv[8]) if sys.argv[8] else None
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

payload["updated_at"] = now
for loop in payload.get("loops", []):
    if loop.get("loop") == loop_nr:
        loop["status"] = "done"
        loop["report"] = report
        loop["duration_s"] = duration
        loop["completed_at"] = now
        loop["metrics"] = {"p0": p0, "p1": p1, "p2": p2, "score": score}

payload.setdefault("trajectory", []).append(score)

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_timeout() {
  local loop_nr="$1"
  local reason="$2"
  local duration="$3"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$reason" "$duration" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

loop_nr = int(sys.argv[2])
reason = sys.argv[3]
duration = int(sys.argv[4])
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

payload["status"] = "timed_out"
payload["updated_at"] = now
for loop in payload.get("loops", []):
    if loop.get("loop") == loop_nr:
        loop["status"] = "timed_out"
        loop["failure_reason"] = reason
        loop["duration_s"] = duration
        loop["completed_at"] = now

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_failed() {
  local loop_nr="$1"
  local reason="$2"
  local duration="$3"
  local report_path="${4:-}"
  local exit_code="${5:-}"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$reason" "$duration" "$report_path" "$exit_code" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

loop_nr = int(sys.argv[2])
reason = sys.argv[3]
duration = int(sys.argv[4])
report_path = sys.argv[5]
exit_code_raw = sys.argv[6]
exit_code = int(exit_code_raw) if exit_code_raw else None
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

payload["status"] = "failed"
payload["updated_at"] = now
for loop in payload.get("loops", []):
    if loop.get("loop") == loop_nr:
        loop["status"] = "failed"
        loop["failure_reason"] = reason
        loop["duration_s"] = duration
        loop["completed_at"] = now
        if report_path:
            loop["report"] = report_path
        if exit_code is not None:
            loop["exit_code"] = exit_code

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_verification_done() {
  local loop_nr="$1"
  local verified_report="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$verified_report" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]):
        loop["verification_status"] = "completed"
        loop["verified_report"] = sys.argv[3]

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_bg_poll_verification() {
  local loop_nr="$1"
  local report_path="$2"
  local verified_path=""
  local max_wait=600
  local elapsed=0

  [[ -n "$report_path" ]] || return 0
  verified_path="${report_path%.md}_verified.md"

  while (( elapsed < max_wait )); do
    if [[ -s "$verified_path" ]]; then
      _record_verification_done "$loop_nr" "$verified_path"
      printf '    %b✓ verified%b  L%s → %s\n' "$_green" "$_reset" "$loop_nr" "$(basename "$verified_path")"
      return 0
    fi
    sleep 10
    (( elapsed += 10 ))
  done

  if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in payload.get("loops", []):
    if loop.get("loop") == int(sys.argv[2]) and loop.get("verification_status") == "pending":
        loop["verification_status"] = "timed_out"

with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
    mv "$state_file.tmp" "$state_file" 2>/dev/null || true
  fi
  printf '    %b⚠ verification timed out%b  L%s\n' "$_yellow" "$_reset" "$loop_nr"
}

_verification_pids=()

_render_chain() {
  local current="$1"
  local total="$2"
  local chain=""
  for ((i = 1; i <= total; i++)); do
    if (( i <= current )); then
      chain+="◉"
    else
      chain+="○"
    fi
    if (( i < total )); then
      chain+="───"
    fi
  done
  printf '%s' "$chain"
}

_render_loop_phase() {
  local loop_nr="$1"
  local phase="$2"
  local detail="${3:-}"
  local chain=""
  chain="$(_render_chain "$loop_nr" "$total_count")"

  case "$phase" in
    promise)
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %bpromise    ░░░░░░░░░░░░░░░░░░░░%b\n' "$_dim" "$_reset"
      printf '    spawning %s...\n' "$detail"
      ;;
    confirmed)
      printf '\r\033[3A'
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %bconfirmed%b  session: %s\n' "$_green" "$_reset" "${detail:0:13}"
      printf '    ████░░░░░░░░░░░░░░░░  agent working\n'
      ;;
    done)
      printf '\r\033[3A'
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %breport ✓%b   %s\n' "$_green" "$_reset" "$detail"
      ;;
    timeout)
      printf '\r\033[3A'
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %btimeout%b   %s\n' "$_red" "$_reset" "$detail"
      ;;
    failed)
      printf '\r\033[3A'
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %bfailed%b    %s\n' "$_red" "$_reset" "$detail"
      ;;
  esac
}

_capture_session_id() {
  local transcript="$1"
  local session_id=""
  local attempts=0

  while [[ -z "$session_id" ]] && (( attempts < 15 )); do
    sleep 2
    (( attempts++ ))

    [[ -f "$transcript" ]] || continue
    session_id=$(sed 's/\x1b\[[0-9;]*m//g' "$transcript" 2>/dev/null \
      | grep -m1 -oE 'session: [a-zA-Z0-9-]{8,}' \
      | awk '{print $2}' || true)
  done

  printf '%s' "$session_id"
}

_extract_metrics() {
  local report="$1"
  local p0=""
  local p1=""
  local p2=""
  local score=""

  if [[ -f "$report" ]]; then
    p0=$(grep -iE '^\s*-?\s*P0:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    p1=$(grep -iE '^\s*-?\s*P1:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    p2=$(grep -iE '^\s*-?\s*P2:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    score=$(grep -iE '(score|convergence).*[0-9]+\s*/\s*100' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
  fi

  printf '%s %s %s %s' "${p0:-}" "${p1:-}" "${p2:-}" "${score:-}"
}

_wait_for_loop_meta() {
  local loop_nr="$1"
  local timeout_s="$2"
  local elapsed=0
  local meta_path=""
  local expected_run_id="${run_id}-$(printf '%03d' "$loop_nr")"

  while true; do
    meta_path="$(spawn_find_meta_for_run_id "$store/reports" "$expected_run_id")"
    if [[ -n "$meta_path" ]]; then
      printf '%s\n' "$meta_path"
      return 0
    fi

    if [[ -f "$state_dir/stop" ]]; then
      return 1
    fi

    if (( timeout_s > 0 && elapsed >= timeout_s )); then
      return 2
    fi

    sleep 2
    (( elapsed += 2 ))
  done
}

_log_file_size() {
  local file_path="$1"
  if [[ -f "$file_path" ]]; then
    wc -c < "$file_path" 2>/dev/null | tr -d ' '
  else
    printf '0\n'
  fi
}

_wait_for_report_path() {
  local report_path="$1"
  local timeout_s="$2"
  local transcript_file="${3:-}"
  local meta_path="${4:-}"
  local stall_limit_s="${VIBECRAFTED_MARBLES_STALL_LIMIT_S:-600}"
  local elapsed=0
  local last_size=0
  local stall_elapsed=0

  while true; do
    if [[ -n "$meta_path" ]]; then
      local meta_status=""
      meta_status="$(spawn_read_meta_field "$meta_path" "status")"
      if [[ "$meta_status" == "failed" ]]; then
        return 4
      fi
    fi

    if [[ -n "$report_path" && -s "$report_path" ]]; then
      printf '%s\n' "$report_path"
      return 0
    fi

    if [[ -n "$meta_path" && -z "$report_path" ]]; then
      report_path="$(spawn_read_meta_field "$meta_path" "report")"
      if [[ -n "$report_path" && -s "$report_path" ]]; then
        printf '%s\n' "$report_path"
        return 0
      fi
    fi

    if [[ -f "$state_dir/stop" ]]; then
      return 1
    fi

    if [[ -n "$transcript_file" && -f "$transcript_file" ]]; then
      local current_size=""
      current_size="$(_log_file_size "$transcript_file")"
      if (( current_size > last_size )); then
        last_size=$current_size
        stall_elapsed=0
      else
        (( stall_elapsed += report_poll_s ))
      fi

      if (( stall_limit_s > 0 && stall_elapsed >= stall_limit_s )); then
        return 3
      fi
    fi

    if (( timeout_s > 0 && elapsed >= timeout_s )); then
      return 2
    fi

    sleep "$report_poll_s"
    (( elapsed += report_poll_s ))
  done
}

_check_pause() {
  if [[ -f "$state_dir/pause" ]]; then
    _update_status "paused"
    printf '\n %b⏸ PAUSED%b  (vc-marbles resume %s)\n' "$_yellow" "$_reset" "$run_id"
    while [[ -f "$state_dir/pause" ]]; do
      sleep 3
      [[ -f "$state_dir/stop" ]] && return 1
    done
    _update_status "running"
    printf ' %b▶ RESUMED%b\n' "$_green" "$_reset"
  fi
  return 0
}

_check_stop() {
  if [[ -f "$state_dir/stop" ]]; then
    _update_status "stopped"
    printf '\n %b■ STOPPED%b  by user\n' "$_red" "$_reset"
    return 1
  fi
  return 0
}

_check_locker() {
  if command -v rust-ai-locker >/dev/null 2>&1; then
    local heavy_count=""
    heavy_count=$(rust-ai-locker scan --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('heavy',[])))" 2>/dev/null || echo "0")
    if [[ "$heavy_count" -gt 0 ]]; then
      printf '    %b⚠ %s heavy process(es) detected — consider waiting%b\n' "$_yellow" "$heavy_count" "$_reset"
    fi
  fi
}

_init_state

ancestor_slug="$(spawn_slug_from_path "$ancestor_plan")"
total_start=$(date +%s)
converged=0
stopped=0
timed_out=0
timed_out_loop=0
failed=0
failed_loop=0

for ((loop_nr = 1; loop_nr <= total_count; loop_nr++)); do
  if ! _check_stop; then
    stopped=1
    break
  fi
  if ! _check_pause; then
    stopped=1
    break
  fi

  _check_locker

  ln_plan="$(spawn_marbles_child_plan_path "$store" "$ancestor_plan" "$loop_nr")"
  loop_agent=""
  loop_focus=""
  loop_model=""
  if [[ -f "$ln_plan" ]]; then
    loop_agent="$(spawn_frontmatter_field "$ln_plan" "agent")"
    loop_focus="$(spawn_frontmatter_field "$ln_plan" "focus")"
    loop_model="$(spawn_frontmatter_field "$ln_plan" "model")"
  fi
  if [[ -z "$loop_agent" ]]; then
    loop_agent="$(spawn_frontmatter_field "$ancestor_plan" "agent")"
  fi
  [[ -n "$loop_agent" ]] || loop_agent="unknown"

  _record_loop_start "$loop_nr" "" "$loop_agent" "$loop_focus" "$ancestor_slug" "$loop_model"

  promise_detail="$loop_agent"
  if [[ -n "$loop_focus" ]]; then
    promise_detail="$promise_detail · $loop_focus"
  fi
  _render_loop_phase "$loop_nr" "promise" "$promise_detail"

  loop_start=$(date +%s)

  meta_path=""
  if ! meta_path="$(_wait_for_loop_meta "$loop_nr" "$meta_timeout_s")"; then
    meta_status=$?
    loop_end=$(date +%s)
    duration=$((loop_end - loop_start))
    duration_fmt="$(printf '%dm %02ds' $((duration/60)) $((duration%60)))"
    if (( meta_status == 1 )); then
      _check_stop || true
      stopped=1
      break
    fi
    timed_out=1
    timed_out_loop=$loop_nr
    _record_loop_timeout "$loop_nr" "meta-missing" "$duration"
    _render_loop_phase "$loop_nr" "timeout" "$duration_fmt  no meta.json within ${meta_timeout_s}s"
    break
  fi

  actual_transcript="$(spawn_read_meta_field "$meta_path" "transcript")"
  actual_report_hint="$(spawn_read_meta_field "$meta_path" "report")"
  actual_meta_status="$(spawn_read_meta_field "$meta_path" "status")"
  actual_exit_code="$(spawn_read_meta_field "$meta_path" "exit_code")"
  _record_loop_start "$loop_nr" "$actual_transcript" "$loop_agent" "$loop_focus" "$ancestor_slug" "$loop_model"

  if [[ "$actual_meta_status" == "failed" ]]; then
    loop_end=$(date +%s)
    duration=$((loop_end - loop_start))
    duration_fmt="$(printf '%dm %02ds' $((duration/60)) $((duration%60)))"
    _record_loop_failed "$loop_nr" "spawn-failed" "$duration" "$actual_report_hint" "$actual_exit_code"
    detail="$duration_fmt  failed before report"
    if [[ -n "$actual_exit_code" ]]; then
      detail="$detail  exit ${actual_exit_code}"
    fi
    _render_loop_phase "$loop_nr" "failed" "$detail"
    failed=1
    failed_loop=$loop_nr
    break
  fi

  session_id=""
  if [[ -n "$actual_transcript" ]]; then
    session_id="$(_capture_session_id "$actual_transcript")"
  fi
  if [[ -z "$session_id" ]]; then
    session_id="$(spawn_read_meta_field "$meta_path" "session_id")"
  fi
  if [[ -n "$session_id" ]]; then
    _record_confirmed "$loop_nr" "$session_id"
    _render_loop_phase "$loop_nr" "confirmed" "$session_id"
  fi

  actual_report=""
  if [[ -n "$actual_report_hint" && -s "$actual_report_hint" ]]; then
    actual_report="$actual_report_hint"
  fi

  wait_status=0
  if [[ -z "$actual_report" ]]; then
    if ! actual_report="$(_wait_for_report_path "$actual_report_hint" "$report_timeout_s" "$actual_transcript" "$meta_path")"; then
      wait_status=$?
    fi
  fi

  if [[ -z "$actual_report" || ! -s "$actual_report" ]] && (( wait_status != 0 )); then
    loop_end=$(date +%s)
    duration=$((loop_end - loop_start))
    duration_fmt="$(printf '%dm %02ds' $((duration/60)) $((duration%60)))"

    if (( wait_status == 1 )); then
      _check_stop || true
      stopped=1
      break
    fi

    if (( wait_status == 4 )); then
      exit_code_hint="$(spawn_read_meta_field "$meta_path" "exit_code")"
      _record_loop_failed "$loop_nr" "spawn-failed" "$duration" "$actual_report_hint" "$exit_code_hint"
      detail="$duration_fmt  failed before report"
      if [[ -n "$exit_code_hint" ]]; then
        detail="$detail  exit ${exit_code_hint}"
      fi
      _render_loop_phase "$loop_nr" "failed" "$detail"
      failed=1
      failed_loop=$loop_nr
      break
    fi

    timed_out=1
    timed_out_loop=$loop_nr
    if (( wait_status == 3 )); then
      _record_loop_timeout "$loop_nr" "agent-stalled" "$duration"
      _render_loop_phase "$loop_nr" "timeout" "$duration_fmt  transcript stalled"
    else
      _record_loop_timeout "$loop_nr" "report-missing" "$duration"
      _render_loop_phase "$loop_nr" "timeout" "$duration_fmt  no report within ${report_timeout_s}s"
    fi
    break
  fi

  loop_end=$(date +%s)
  duration=$((loop_end - loop_start))
  duration_fmt="$(printf '%dm %02ds' $((duration/60)) $((duration%60)))"

  read -r p0 p1 p2 score <<< "$(_extract_metrics "$actual_report")"
  _record_loop_done "$loop_nr" "$actual_report" "$duration" "$p0" "$p1" "$p2" "$score"

  detail="$duration_fmt"
  if [[ -n "$p0" || -n "$p1" || -n "$p2" ]]; then
    detail="$duration_fmt  P0:${p0:-?} P1:${p1:-?} P2:${p2:-?}"
    [[ -n "$score" ]] && detail="$detail  score:${score}/100"
  fi
  _render_loop_phase "$loop_nr" "done" "$detail"

  _bg_poll_verification "$loop_nr" "$actual_report" &
  _verification_pids+=($!)

  if [[ "${p0:-}" == "0" && "${p1:-}" == "0" && "${p2:-}" == "0" ]] \
     && [[ -n "$p0" && -n "$p1" && -n "$p2" ]]; then
    converged=1
    break
  fi
done

total_end=$(date +%s)
total_duration=$((total_end - total_start))
total_fmt="$(printf '%dm %02ds' $((total_duration/60)) $((total_duration%60)))"

trajectory=""
if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
  trajectory=$(python3 - "$state_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

scores = [str(score) for score in payload.get("trajectory", []) if score is not None]
print(" → ".join(scores))
PY
  )
fi

if (( converged )); then
  _update_status "converged"
  loops_saved=$((total_count - loop_nr))
  printf '\n %b⚒  Converged · %s/%s loops · %s%b\n' "$_bold$_green" "$loop_nr" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s  circle full\n' "$(_render_chain "$loop_nr" "$total_count")"
  [[ -n "$trajectory" ]] && printf '  %s\n' "$trajectory"
  printf '  ████████████████████████████████████████████████\n'
  (( loops_saved > 0 )) && printf '\n  loops saved: %s (converged early)\n' "$loops_saved"
elif (( timed_out )); then
  _update_status "failed"
  completed_loops=$((timed_out_loop - 1))
  printf '\n %b⚒  Failed · timeout at L%s/%s · %s%b\n' "$_bold$_red" "$timed_out_loop" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s\n' "$(_render_chain "$completed_loops" "$total_count")"
  printf '  report pathing is meta.json-only; loop not consumed\n'
elif (( failed )); then
  _update_status "failed"
  completed_loops=$((failed_loop - 1))
  printf '\n %b⚒  Failed · loop failure at L%s/%s · %s%b\n' "$_bold$_red" "$failed_loop" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s\n' "$(_render_chain "$completed_loops" "$total_count")"
  printf '  loop consumed truthfully; failure surfaced from launch metadata\n'
elif (( stopped )); then
  _update_status "stopped"
  printf '\n %b⚒  Stopped · %s%b\n' "$_bold$_yellow" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s\n' "$(_render_chain "$((loop_nr-1))" "$total_count")"
else
  _update_status "completed"
  printf '\n %b⚒  Complete · %s loops · %s%b\n' "$_bold$_copper" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s\n' "$(_render_chain "$total_count" "$total_count")"
  [[ -n "$trajectory" ]] && printf '  %s\n' "$trajectory"
fi

if (( ${#_verification_pids[@]} > 0 )); then
  printf '\n  %bverification:%b ' "$_dim" "$_reset"
  for _vpid in "${_verification_pids[@]}"; do
    if kill -0 "$_vpid" 2>/dev/null; then
      _vwait=0
      while kill -0 "$_vpid" 2>/dev/null && (( _vwait < 30 )); do
        sleep 5
        (( _vwait += 5 ))
      done
    fi
  done

  if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
    python3 - "$state_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

pending = completed = timed = 0
for loop in payload.get("loops", []):
    status = loop.get("verification_status", "")
    if status == "completed":
        completed += 1
    elif status == "pending":
        pending += 1
    elif status == "timed_out":
        timed += 1

parts = []
if completed:
    parts.append(f"{completed} done")
if pending:
    parts.append(f"{pending} pending")
if timed:
    parts.append(f"{timed} timed out")
print(", ".join(parts) if parts else "none tracked")
PY
  fi
fi

printf '\n  lock released: %s\n' "$run_id"
printf '%b──────────────────────────────────%b\n\n' "$_steel" "$_reset"

for _vpid in "${_verification_pids[@]:-}"; do
  kill "$_vpid" 2>/dev/null || true
done

rm -f "$session_lock" 2>/dev/null || true

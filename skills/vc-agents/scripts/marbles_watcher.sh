#!/usr/bin/env bash
set -euo pipefail
# Marbles Watcher — temporal guardian for convergence loops.
# Monitors promise → confirmed → done lifecycle per loop.
# Captures session IDs, tracks convergence trajectory, handles pause/stop.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

# ── Args ──────────────────────────────────────────────────────────────
run_id="$1"
agent="$2"
original_plan="$3"
total_count="$4"
root_dir="$5"
runtime="$6"
store="$7"
session_lock="$8"

# ── State directory ───────────────────────────────────────────────────
state_dir="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/marbles/$run_id"
mkdir -p "$state_dir"
state_file="$state_dir/state.json"

# ── Colors ────────────────────────────────────────────────────────────
_bold='\033[1m'
_copper='\033[38;5;173m'
_steel='\033[38;5;247m'
_green='\033[32m'
_yellow='\033[33m'
_red='\033[31m'
_dim='\033[2m'
_reset='\033[0m'

# ── State helpers ─────────────────────────────────────────────────────
_write_state() {
  local tmp="$state_file.tmp"
  cat > "$tmp"
  mv "$tmp" "$state_file"
}

_init_state() {
  _write_state <<EOF
{
  "run_id": "$run_id",
  "agent": "$agent",
  "mode": "single",
  "plan": "$original_plan",
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
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
d["status"] = sys.argv[2]
d["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_start() {
  local loop_nr="$1" transcript="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$transcript" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["current_loop"] = int(sys.argv[2])
d["status"] = "promise"
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
d["loops"].append({
  "loop": int(sys.argv[2]),
  "status": "promise",
  "transcript": sys.argv[3],
  "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
})
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_confirmed() {
  local loop_nr="$1" session_id="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$session_id" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["status"] = "confirmed"
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in d["loops"]:
    if loop["loop"] == int(sys.argv[2]):
        loop["status"] = "confirmed"
        loop["session_id"] = sys.argv[3]
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_loop_done() {
  local loop_nr="$1" report="$2" duration="$3"
  local p0="${4:-}" p1="${5:-}" p2="${6:-}" score="${7:-}"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$report" "$duration" "$p0" "$p1" "$p2" "$score" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
nr, report, dur = int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
p0 = int(sys.argv[5]) if sys.argv[5] else None
p1 = int(sys.argv[6]) if sys.argv[6] else None
p2 = int(sys.argv[7]) if sys.argv[7] else None
score = int(sys.argv[8]) if sys.argv[8] else None
for loop in d["loops"]:
    if loop["loop"] == nr:
        loop["status"] = "done"
        loop["report"] = report
        loop["duration_s"] = dur
        loop["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        loop["metrics"] = {"p0": p0, "p1": p1, "p2": p2, "score": score}
d["trajectory"].append(score)
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

# ── Verification tracking ─────────────────────────────────────────────
_record_verification_start() {
  local loop_nr="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in d["loops"]:
    if loop["loop"] == int(sys.argv[2]):
        loop["verification_status"] = "pending"
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

_record_verification_done() {
  local loop_nr="$1" verified_report="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$state_file" "$loop_nr" "$verified_report" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in d["loops"]:
    if loop["loop"] == int(sys.argv[2]):
        loop["verification_status"] = "completed"
        loop["verified_report"] = sys.argv[3]
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file"
  fi
}

# ── Background verification poller ───────────────────────────────────
# Polls for *_verified.md file for a given loop, updates state.json on arrival.
# Runs as background subshell — does not block main watcher loop.
_bg_poll_verification() {
  local loop_nr="$1" slug="$2" agent_name="$3"
  local pattern="*_marbles-${slug}_L${loop_nr}_${agent_name}_verified.md"
  local max_wait=600  # 10 minutes max
  local elapsed=0

  while (( elapsed < max_wait )); do
    local found
    found=$(find "$store/reports" -name "$pattern" -size +0c 2>/dev/null | head -1 || true)
    if [[ -n "$found" ]]; then
      _record_verification_done "$loop_nr" "$found"
      printf '    %b✓ verified%b  L%s → %s\n' "$_green" "$_reset" "$loop_nr" "$(basename "$found")"
      return 0
    fi
    sleep 10
    (( elapsed += 10 ))
  done

  # Timed out — mark as skipped
  if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
    python3 - "$state_file" "$loop_nr" <<'PY'
import json, sys, datetime
with open(sys.argv[1]) as f: d = json.load(f)
d["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for loop in d["loops"]:
    if loop["loop"] == int(sys.argv[2]):
        if loop.get("verification_status") == "pending":
            loop["verification_status"] = "timed_out"
with open(sys.argv[1] + ".tmp", "w") as f: json.dump(d, f, indent=2)
PY
    mv "$state_file.tmp" "$state_file" 2>/dev/null || true
  fi
  printf '    %b⚠ verification timed out%b  L%s\n' "$_yellow" "$_reset" "$loop_nr"
}

# Track background poller PIDs for cleanup
_verification_pids=()

# ── Visual helpers ────────────────────────────────────────────────────
_render_chain() {
  local current="$1" total="$2"
  local chain=""
  for ((i=1; i<=total; i++)); do
    if ((i <= current)); then
      chain+="◉"
    else
      chain+="○"
    fi
    if ((i < total)); then
      chain+="───"
    fi
  done
  printf '%s' "$chain"
}

_render_loop_phase() {
  local loop_nr="$1" phase="$2" detail="${3:-}"
  local chain
  chain="$(_render_chain "$loop_nr" "$total_count")"

  case "$phase" in
    promise)
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %bpromise    ░░░░░░░░░░░░░░░░░░░░%b\n' "$_dim" "$_reset"
      printf '    spawning %s...\n' "$agent"
      ;;
    confirmed)
      printf '\r\033[3A'  # move up to overwrite promise
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$chain"
      printf '    %bconfirmed%b  session: %s\n' "$_green" "$_reset" "${detail:0:13}"
      printf '    ████░░░░░░░░░░░░░░░░  agent working\n'
      ;;
    done)
      printf '\r\033[3A'  # move up to overwrite confirmed
      local done_chain
      done_chain="$(_render_chain "$loop_nr" "$total_count")"
      printf '\n %bL%s%b %s\n' "$_bold" "$loop_nr" "$_reset" "$done_chain"
      printf '    %breport ✓%b   %s\n' "$_green" "$_reset" "$detail"
      ;;
  esac
}

# ── Session ID capture ────────────────────────────────────────────────
# All agents emit "session: <uuid>" in transcripts after stream filtering.
# Strip ANSI escapes first — gemini/codex transcripts bleed \e[0m into UUIDs.
_capture_session_id() {
  local transcript="$1" agent_type="$2"
  local session_id="" attempts=0

  while [[ -z "$session_id" ]] && ((attempts < 15)); do
    sleep 2
    ((attempts++))

    if [[ ! -f "$transcript" ]]; then
      continue
    fi

    # Universal: strip ANSI escapes, then match "session: <uuid>"
    session_id=$(sed 's/\x1b\[[0-9;]*m//g' "$transcript" 2>/dev/null \
      | grep -m1 -oE 'session: [a-f0-9-]{8,}' \
      | awk '{print $2}' || true)
  done

  printf '%s' "$session_id"
}

# ── Report metric extraction ─────────────────────────────────────────
_extract_metrics() {
  local report="$1"
  local p0="" p1="" p2="" score=""

  if [[ -f "$report" ]]; then
    p0=$(grep -iE '^\s*-?\s*P0:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    p1=$(grep -iE '^\s*-?\s*P1:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    p2=$(grep -iE '^\s*-?\s*P2:?\s*' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
    score=$(grep -iE '(score|convergence).*[0-9]+\s*/\s*100' "$report" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)
  fi

  printf '%s %s %s %s' "${p0:-}" "${p1:-}" "${p2:-}" "${score:-}"
}

# ── Wait for report file ─────────────────────────────────────────────
_wait_for_report() {
  local report_path="$1"
  while [[ ! -s "$report_path" ]]; do
    sleep 5
    # Check for stop/pause between polls
    if [[ -f "$state_dir/stop" ]]; then
      return 1
    fi
  done
  return 0
}

# ── Check sentinels ──────────────────────────────────────────────────
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

# ── Locker check (advisory) ──────────────────────────────────────────
_check_locker() {
  if command -v rust-ai-locker >/dev/null 2>&1; then
    local heavy_count
    heavy_count=$(rust-ai-locker scan --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('heavy',[])))" 2>/dev/null || echo "0")
    if [[ "$heavy_count" -gt 0 ]]; then
      printf '    %b⚠ %s heavy process(es) detected — consider waiting%b\n' "$_yellow" "$heavy_count" "$_reset"
    fi
  fi
}

# ══════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════

_init_state

plan_slug="$(spawn_slug_from_path "$original_plan")"
total_start=$(date +%s)
converged=0

for ((loop_nr=1; loop_nr<=total_count; loop_nr++)); do
  # ── Sentinel checks ──────────────────────────────────────────────
  _check_stop || break
  _check_pause || break

  # ── Locker advisory ──────────────────────────────────────────────
  _check_locker

  # ── Resolve paths for this loop ──────────────────────────────────
  ln_plan="$store/plans/marbles-${plan_slug}_L${loop_nr}.md"
  # Plan file already created by marbles_spawn.sh (L1) or marbles_next.sh (L2+)
  # We just need to know the expected report + transcript paths
  report_base="$(spawn_timestamp)_marbles-${plan_slug}_L${loop_nr}_${agent}"
  expected_report="$store/reports/${report_base}.md"
  expected_transcript="$store/reports/${report_base}.transcript.log"

  # Spawn scripts own the timestamp prefix, but the plan slug is stable for this run.
  # Matching on the slug keeps us inside the current marbles run without racing
  # against state-file timestamps that are updated during observation.
  report_pattern="*_marbles-${plan_slug}_L${loop_nr}_${agent}.md"
  transcript_pattern="*_marbles-${plan_slug}_L${loop_nr}_${agent}.transcript.log"

  # ── Promise phase ────────────────────────────────────────────────
  _record_loop_start "$loop_nr" "$expected_transcript"
  _render_loop_phase "$loop_nr" "promise"

  loop_start=$(date +%s)

  # ── For L1, the agent was already spawned by marbles_spawn.sh
  #    For L2+, marbles_next.sh handles spawning via success_hook
  #    Watcher's job is to OBSERVE, not spawn ──────────────────────

  # ── Capture session ID ───────────────────────────────────────────
  # Find the actual transcript file (may have different timestamp prefix)
  sleep 3  # brief wait for transcript file to appear
  actual_transcript=""
  for _try in $(seq 1 10); do
    actual_transcript=$(find "$store/reports" -name "$transcript_pattern" 2>/dev/null | sort | tail -1 || true)
    [[ -n "$actual_transcript" ]] && break
    sleep 2
  done

  if [[ -n "$actual_transcript" ]]; then
    session_id=$(_capture_session_id "$actual_transcript" "$agent")
    if [[ -n "$session_id" ]]; then
      _record_confirmed "$loop_nr" "$session_id"
      _render_loop_phase "$loop_nr" "confirmed" "$session_id"
    fi
  fi

  # ── Wait for report ──────────────────────────────────────────────
  actual_report=""
  while [[ -z "$actual_report" || ! -s "$actual_report" ]]; do
    sleep 5
    actual_report=$(find "$store/reports" -name "$report_pattern" \
      ! -name '*_verified*' \
      ! -name '*.meta.json' ! -name '*.transcript.log' \
      2>/dev/null | sort | tail -1 || true)
    # Check stop during wait
    if [[ -f "$state_dir/stop" ]]; then
      _check_stop
      break 2  # break outer for loop
    fi
  done

  # ── Report landed ────────────────────────────────────────────────
  loop_end=$(date +%s)
  duration=$((loop_end - loop_start))
  duration_fmt="$(printf '%dm %02ds' $((duration/60)) $((duration%60)))"

  # Extract metrics (best-effort)
  read -r p0 p1 p2 score <<< "$(_extract_metrics "$actual_report")"

  _record_loop_done "$loop_nr" "$actual_report" "$duration" "$p0" "$p1" "$p2" "$score"

  # Build detail line
  detail="$duration_fmt"
  if [[ -n "$p0" || -n "$p1" || -n "$p2" ]]; then
    detail="$duration_fmt  P0:${p0:-?} P1:${p1:-?} P2:${p2:-?}"
    [[ -n "$score" ]] && detail="$detail  score:${score}/100"
  fi
  _render_loop_phase "$loop_nr" "done" "$detail"

  # ── Start background verification poller for this loop ──────────
  _bg_poll_verification "$loop_nr" "$plan_slug" "$agent" &
  _verification_pids+=($!)

  # ── Early convergence check ──────────────────────────────────────
  if [[ "${p0:-}" == "0" && "${p1:-}" == "0" && "${p2:-}" == "0" ]] \
     && [[ -n "$p0" && -n "$p1" && -n "$p2" ]]; then
    converged=1
    break
  fi
done

# ══════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════

total_end=$(date +%s)
total_duration=$((total_end - total_start))
total_fmt="$(printf '%dm %02ds' $((total_duration/60)) $((total_duration%60)))"

# Read trajectory from state
trajectory=""
if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
  trajectory=$(python3 -c "
import json
with open('$state_file') as f: d = json.load(f)
scores = [str(s) for s in d.get('trajectory',[]) if s is not None]
print(' → '.join(scores))
" 2>/dev/null || true)
fi

if ((converged)); then
  _update_status "converged"
  loops_saved=$((total_count - loop_nr))
  printf '\n %b⚒  Converged · %s/%s loops · %s%b\n' "$_bold$_green" "$loop_nr" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s  circle full\n' "$(_render_chain "$loop_nr" "$total_count")"
  [[ -n "$trajectory" ]] && printf '  %s\n' "$trajectory"
  printf '  ████████████████████████████████████████████████\n'
  ((loops_saved > 0)) && printf '\n  loops saved: %s (converged early)\n' "$loops_saved"
else
  _update_status "completed"
  printf '\n %b⚒  Complete · %s loops · %s%b\n' "$_bold$_copper" "$total_count" "$total_fmt" "$_reset"
  printf '%b──────────────────────────────────%b\n' "$_steel" "$_reset"
  printf '  %s\n' "$(_render_chain "$total_count" "$total_count")"
  [[ -n "$trajectory" ]] && printf '  %s\n' "$trajectory"
fi

# ── Wait briefly for any pending verifications ───────────────────────
if (( ${#_verification_pids[@]} > 0 )); then
  printf '\n  %bverification:%b ' "$_dim" "$_reset"
  # Give background pollers up to 30s grace period for quick completions
  for _vpid in "${_verification_pids[@]}"; do
    # Non-blocking check — if already done, great; if not, let it run
    if kill -0 "$_vpid" 2>/dev/null; then
      # Still running — wait up to 30s
      _vwait=0
      while kill -0 "$_vpid" 2>/dev/null && (( _vwait < 30 )); do
        sleep 5
        (( _vwait += 5 ))
      done
    fi
  done

  # Report final verification status from state.json
  if command -v python3 >/dev/null 2>&1 && [[ -f "$state_file" ]]; then
    python3 - "$state_file" <<'PY'
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
pending = completed = timed = 0
for loop in d.get("loops", []):
    vs = loop.get("verification_status", "")
    if vs == "completed": completed += 1
    elif vs == "pending": pending += 1
    elif vs == "timed_out": timed += 1
parts = []
if completed: parts.append(f"{completed} done")
if pending: parts.append(f"{pending} pending")
if timed: parts.append(f"{timed} timed out")
print(", ".join(parts) if parts else "none tracked")
PY
  fi
fi

printf '\n  lock released: %s\n' "$run_id"
printf '%b──────────────────────────────────%b\n\n' "$_steel" "$_reset"

# Kill any remaining background pollers (they'll die naturally but be clean)
for _vpid in "${_verification_pids[@]:-}"; do
  kill "$_vpid" 2>/dev/null || true
done

# Cleanup lock
rm -f "$session_lock" 2>/dev/null || true

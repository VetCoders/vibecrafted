#!/usr/bin/env bash
set -euo pipefail
# Marbles CTL — control interface for active marbles sessions.
# Subcommands: pause, stop, resume, session, inspect, delete

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

MARBLES_DIR="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/marbles"

_bold='\033[1m'
_copper='\033[38;5;173m'
_steel='\033[38;5;247m'
_green='\033[32m'
_yellow='\033[33m'
_red='\033[31m'
_dim='\033[2m'
_reset='\033[0m'

usage() {
  cat <<EOF
Usage: marbles_ctl.sh <command> [args]

Commands:
  pause <run_id|--all>    Pause active session(s) after current loop
  stop <run_id|--all>     Stop active session(s)
  resume <run_id>         Resume paused session
  session [--json]        List active sessions
  inspect <run_id>        Show full state for a session
  delete <run_id>         Archive a session under marbles/deleted/<run_id>
  gc [--dry-run|--hard]   Clean up stale sessions (default: mark as gc)
EOF
}

# ── Helpers ───────────────────────────────────────────────────────────
_session_dir_for_run_id() {
  local rid="$1"
  local direct="$MARBLES_DIR/$rid"
  if [[ -d "$direct" ]]; then
    printf '%s\n' "$direct"
    return 0
  fi

  local candidate
  shopt -s nullglob
  for candidate in "$MARBLES_DIR"/*/"$rid"; do
    [[ -d "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    shopt -u nullglob
    return 0
  done
  shopt -u nullglob
  return 1
}

_find_active_sessions() {
  find "$MARBLES_DIR" -maxdepth 2 -name "state.json" 2>/dev/null | while IFS= read -r sf; do
    local dir
    dir="$(dirname "$sf")"
    local rid
    rid="$(basename "$dir")"
    local status
    status=$(python3 - "$sf" <<'PY' 2>/dev/null || echo "?"
import json
import sys

with open(sys.argv[1]) as handle:
    print(json.load(handle).get("status", "?"))
PY
)
    case "$status" in
      initialized|promise|confirmed|running|paused)
        printf '%s\n' "$rid"
        ;;
    esac
  done
}

_signal_session() {
  local rid="$1" signal="$2"
  local sdir="$MARBLES_DIR/$rid"
  if [[ ! -d "$sdir" ]]; then
    printf '%b✗ Session not found: %s%b\n' "$_red" "$rid" "$_reset"
    return 1
  fi
  touch "$sdir/$signal"
  printf '%b✓ %s → %s%b\n' "$_green" "$rid" "$signal" "$_reset"
}

# ── Commands ──────────────────────────────────────────────────────────
cmd_pause() {
  local target="${1:---all}"
  if [[ "$target" == "--all" ]]; then
    local found=0
    while IFS= read -r rid; do
      [[ -n "$rid" ]] || continue
      _signal_session "$rid" "pause"
      ((++found))
    done < <(_find_active_sessions)
    ((found > 0)) || printf '%bNo active sessions to pause%b\n' "$_dim" "$_reset"
  else
    _signal_session "$target" "pause"
  fi
}

cmd_stop() {
  local target="${1:---all}"
  if [[ "$target" == "--all" ]]; then
    local found=0
    while IFS= read -r rid; do
      [[ -n "$rid" ]] || continue
      _signal_session "$rid" "stop"
      ((++found))
    done < <(_find_active_sessions)
    ((found > 0)) || printf '%bNo active sessions to stop%b\n' "$_dim" "$_reset"
  else
    _signal_session "$target" "stop"
  fi
}

cmd_resume() {
  local rid="${1:-}"
  [[ -n "$rid" ]] || spawn_die "Usage: marbles_ctl.sh resume <run_id>"
  local sdir="$MARBLES_DIR/$rid"
  if [[ ! -f "$sdir/pause" ]]; then
    printf '%bSession %s is not paused%b\n' "$_yellow" "$rid" "$_reset"
    return 1
  fi
  rm -f "$sdir/pause"
  printf '%b▶ Resumed: %s%b\n' "$_green" "$rid" "$_reset"
}

cmd_session() {
  local json_mode=0
  [[ "${1:-}" == "--json" ]] && json_mode=1

  mkdir -p "$MARBLES_DIR"

  if ((json_mode)); then
    python3 - "$MARBLES_DIR" <<'PY'
import json, os, sys, glob

marbles_dir = sys.argv[1]
sessions = []
for sf in sorted(glob.glob(os.path.join(marbles_dir, "*/state.json"))):
    try:
        with open(sf) as f:
            d = json.load(f)
        status = d.get("status", "?")
        if status in ("completed", "converged", "stopped", "failed", "gc"):
            continue
        sessions.append(d)
    except Exception:
        continue
print(json.dumps(sessions, indent=2))
PY
    return
  fi

  printf '\n %bActive Marbles Sessions%b\n' "$_bold$_copper" "$_reset"
  printf '%b──────────────────────────────────────────────────────────────%b\n' "$_steel" "$_reset"

  local found=0
  for sf in "$MARBLES_DIR"/*/state.json; do
    [[ -f "$sf" ]] || continue
    local row
    row=$(python3 - "$sf" <<'PY'
import json, sys, os

try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
except Exception:
    sys.exit(0)

status = d.get("status", "?")
if status in ("completed", "converged", "stopped", "failed", "gc"):
    sys.exit(0)

run_id = d.get("run_id", "?")
agent = d.get("agent", "?")
root = d.get("root", "")
repo = os.path.basename(root) if root else "?"
current = d.get("current_loop", 0)
total = d.get("total_loops", "?")
trajectory = d.get("trajectory", [])
last_score = next((s for s in reversed(trajectory) if s is not None), None)
score_str = f"{last_score}/100" if last_score is not None else "--"

status_icon = {"promise": "○", "confirmed": "◉", "paused": "⏸", "running": "◉", "initialized": "○"}.get(status, "?")

print(f"  {run_id:<16s} {repo:<16s} {agent:<8s} L{current}/{total}  {status_icon} {status:<12s} {score_str}")
PY
    ) || true
    if [[ -n "$row" ]]; then
      printf '%s\n' "$row"
      ((++found))
    fi
  done

  if ((found == 0)); then
    printf '  %b(no active sessions)%b\n' "$_dim" "$_reset"
  fi
  printf '%b──────────────────────────────────────────────────────────────%b\n\n' "$_steel" "$_reset"
}

cmd_inspect() {
  local rid="${1:-}"
  [[ -n "$rid" ]] || spawn_die "Usage: marbles_ctl.sh inspect <run_id>"
  local session_dir
  session_dir="$(_session_dir_for_run_id "$rid")" || spawn_die "No state found for $rid"
  local sf="$session_dir/state.json"
  [[ -f "$sf" ]] || spawn_die "No state found for $rid"

  python3 - "$sf" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    d = json.load(f)

print(f"\n  Run:      {d.get('run_id')}")
print(f"  Agent:    {d.get('agent')}")
print(f"  Status:   {d.get('status')}")
print(f"  Plan:     {d.get('plan')}")
print(f"  Root:     {d.get('root')}")
print(f"  Loops:    {d.get('current_loop')}/{d.get('total_loops')}")
print(f"  Started:  {d.get('started_at')}")
print(f"  Updated:  {d.get('updated_at', '-')}")

trajectory = d.get("trajectory", [])
scores = [str(s) for s in trajectory if s is not None]
if scores:
    print(f"\n  Trajectory: {' → '.join(scores)}")
    bar_len = 48
    last = trajectory[-1] if trajectory else 0
    if last and isinstance(last, (int, float)):
        filled = int(bar_len * last / 100)
        print(f"  {'█' * filled}{'░' * (bar_len - filled)}")

loops = d.get("loops", [])
if loops:
    print(f"\n  Loop Details:")
    for lp in loops:
        nr = lp.get("loop", "?")
        st = lp.get("status", "?")
        sid = lp.get("session_id", "-")
        dur = lp.get("duration_s")
        dur_str = f"{dur//60}m {dur%60:02d}s" if dur else "-"
        m = lp.get("metrics", {})
        if m and any(v is not None for v in m.values()):
            metrics_str = f"P0:{m.get('p0','?')} P1:{m.get('p1','?')} P2:{m.get('p2','?')} score:{m.get('score','?')}"
        else:
            metrics_str = "-"
        print(f"    L{nr}: {st:<12s} {dur_str:<8s} {sid[:13] if sid != '-' else '-':<14s} {metrics_str}")

print()
PY
}

cmd_delete() {
  local rid="${1:-}"
  [[ -n "$rid" ]] || spawn_die "Usage: marbles_ctl.sh delete <run_id>"

  mkdir -p "$MARBLES_DIR"

  local session_dir
  session_dir="$(_session_dir_for_run_id "$rid")" || spawn_die "No session found for $rid"

  local current_parent
  current_parent="$(dirname "$session_dir")"

  local target_state="deleted"
  local target_parent="$MARBLES_DIR/$target_state"
  local target_dir="$target_parent/$rid"

  if [[ "$session_dir" == "$target_dir" ]]; then
    printf '%bSession %s is already archived in %s%b\n' "$_dim" "$rid" "$target_state" "$_reset"
    return 0
  fi
  [[ ! -e "$target_dir" ]] || spawn_die "Target archive path already exists: $target_dir"

  local state_file="$session_dir/state.json"
  [[ -f "$state_file" ]] || spawn_die "No state found for $rid"

  local session_meta status watcher_alive
  session_meta=$(python3 - "$state_file" <<'PY'
import json
import os
import sys

status = "?"
alive = 0

try:
    with open(sys.argv[1]) as handle:
        payload = json.load(handle)
    status = str(payload.get("status", "?"))
    pid = payload.get("watcher_pid")
    if pid is not None:
        try:
            pid = int(pid)
        except Exception:
            pid = None
    if pid is not None:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = 0
        except PermissionError:
            alive = 1
        else:
            alive = 1
except Exception:
    pass

print(f"{status}\t{alive}")
PY
)
  IFS=$'\t' read -r status watcher_alive <<< "$session_meta"
  case "$status" in
    initialized|promise|confirmed|running|paused)
      if [[ "$watcher_alive" == "1" ]]; then
        printf '%bSession %s appears live; stop it first%b\n' "$_yellow" "$rid" "$_reset" >&2
        return 1
      fi
      ;;
  esac

  mkdir -p "$target_parent"
  mv "$session_dir" "$target_dir"

  python3 - "$target_dir/state.json" "$status" "$session_dir" "$target_state" <<'PY'
import datetime
import json
import sys

state_path, previous_status, archived_from, target_state = sys.argv[1:5]
archived_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

with open(state_path) as handle:
    payload = json.load(handle)

payload["previous_status"] = previous_status
payload["status"] = target_state
payload["archived_from"] = archived_from
payload["archived_at"] = archived_at
payload["updated_at"] = archived_at
payload["deleted_at"] = archived_at

with open(state_path, "w") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY

  printf '%b✓ %s → %s/%s%b\n' "$_green" "$rid" "$target_state" "$rid" "$_reset"
}

cmd_gc() {
  local dry_run=0
  local hard=0
  local stale_minutes="${VIBECRAFTED_MARBLES_STALE_MINUTES:-60}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run=1 ;;
      --hard) hard=1 ;;
      --stale-minutes)
        shift
        [[ $# -gt 0 ]] || spawn_die "--stale-minutes requires a positive integer value"
        [[ "$1" =~ ^[1-9][0-9]*$ ]] || spawn_die "--stale-minutes must be a positive integer (got: $1)"
        stale_minutes="$1"
        ;;
      *) spawn_die "Unknown gc option: $1" ;;
    esac
    shift
  done

  mkdir -p "$MARBLES_DIR"

  python3 - "$MARBLES_DIR" "$stale_minutes" "$dry_run" "$hard" <<'PY'
import json
import os
import shutil
import sys
import time

marbles_dir = sys.argv[1]
stale_minutes = int(sys.argv[2])
dry_run = sys.argv[3] == "1"
hard_delete = sys.argv[4] == "1"
stale_threshold = time.time() - (stale_minutes * 60)
found = 0
cleaned = 0

for entry in sorted(os.listdir(marbles_dir)):
    state_path = os.path.join(marbles_dir, entry, "state.json")
    if not os.path.isfile(state_path):
        continue

    try:
        with open(state_path) as f:
            state = json.load(f)
    except Exception:
        continue

    status = state.get("status", "")
    if status in ("completed", "converged", "stopped", "failed", "gc"):
        continue

    # Check staleness: use updated_at or started_at or file mtime
    updated = state.get("updated_at") or state.get("started_at") or ""
    if updated:
        try:
            from datetime import datetime, timezone
            if updated.endswith("Z"):
                updated = updated[:-1] + "+00:00"
            ts = datetime.fromisoformat(updated).timestamp()
        except Exception:
            ts = os.path.getmtime(state_path)
    else:
        ts = os.path.getmtime(state_path)

    if ts > stale_threshold:
        continue  # Not stale yet

    found += 1
    run_id = state.get("run_id", entry)
    agent = state.get("agent", "?")
    root = os.path.basename(state.get("root", "?"))
    current = state.get("current_loop", 0)
    total = state.get("total_loops", 0)

    if dry_run:
        print(f"  [dry-run] {run_id:<18s} {root:<18s} {agent:<8s} L{current}/{total}  {status}")
    elif hard_delete:
        session_dir = os.path.join(marbles_dir, entry)
        shutil.rmtree(session_dir, ignore_errors=True)
        cleaned += 1
        print(f"  \033[31m✗ deleted\033[0m  {run_id:<18s} {root:<18s} {agent:<8s} L{current}/{total}")
    else:
        state["status"] = "gc"
        state["gc_reason"] = f"stale ({stale_minutes}m threshold)"
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        cleaned += 1
        print(f"  \033[33m⚠ gc\033[0m      {run_id:<18s} {root:<18s} {agent:<8s} L{current}/{total}")

if found == 0:
    print("  (no stale sessions found)")
elif not dry_run:
    mode = "deleted" if hard_delete else "marked gc"
    print(f"\n  {cleaned} session(s) {mode}")
else:
    print(f"\n  {found} session(s) would be affected")
PY
}

# ── Dispatch ──────────────────────────────────────────────────────────
cmd="${1:-}"
shift || true

case "$cmd" in
  pause)   cmd_pause "$@" ;;
  stop)    cmd_stop "$@" ;;
  resume)  cmd_resume "$@" ;;
  session) cmd_session "$@" ;;
  inspect) cmd_inspect "$@" ;;
  delete)  cmd_delete "$@" ;;
  gc)      cmd_gc "$@" ;;
  -h|--help|"") usage ;;
  *) spawn_die "Unknown command: $cmd. Use: pause, stop, resume, session, inspect, delete, gc" ;;
esac

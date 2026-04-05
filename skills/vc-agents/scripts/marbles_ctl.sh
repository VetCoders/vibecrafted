#!/usr/bin/env bash
set -euo pipefail
# Marbles CTL — control interface for active marbles sessions.
# Subcommands: pause, stop, resume, session, inspect

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
EOF
}

# ── Helpers ───────────────────────────────────────────────────────────
_find_active_sessions() {
  find "$MARBLES_DIR" -maxdepth 2 -name "state.json" 2>/dev/null | while IFS= read -r sf; do
    local dir
    dir="$(dirname "$sf")"
    local rid
    rid="$(basename "$dir")"
    local status
    status=$(python3 -c "import json; print(json.load(open('$sf')).get('status','?'))" 2>/dev/null || echo "?")
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
      ((found++))
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
      ((found++))
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
        if status in ("completed", "converged", "stopped", "failed"):
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
if status in ("completed", "converged", "stopped", "failed"):
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
      ((found++))
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
  local sf="$MARBLES_DIR/$rid/state.json"
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

# ── Dispatch ──────────────────────────────────────────────────────────
cmd="${1:-}"
shift || true

case "$cmd" in
  pause)   cmd_pause "$@" ;;
  stop)    cmd_stop "$@" ;;
  resume)  cmd_resume "$@" ;;
  session) cmd_session "$@" ;;
  inspect) cmd_inspect "$@" ;;
  -h|--help|"") usage ;;
  *) spawn_die "Unknown command: $cmd. Use: pause, stop, resume, session, inspect" ;;
esac

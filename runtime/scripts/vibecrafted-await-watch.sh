#!/usr/bin/env bash
# vibecrafted-await-watch — auto-tail-await-die pane helper
#
# Spawned as a zellij side-pane by `_vetcoders_skill` after every
# non-marbles dispatch. Tails the worker's transcript log, watches the
# meta status + size delta + worker process liveness, and self-
# terminates when the worker is done (or the wrapper zombies).
#
# Args (one of):
#   --meta <path>       direct meta.json path (preferred — no resolve cost)
#   --run-id <id>       run_id; helper greps artifacts/ for matching meta
#   <run_id>            positional shorthand for --run-id
#
# Env tunables:
#   VIBECRAFTED_AWAIT_IDLE_TIMEOUT  seconds of zero transcript growth
#                                   before "probably done" check
#                                   (default: 60)
#   VIBECRAFTED_AWAIT_POLL          status / size poll interval
#                                   (default: 3)
#
# Exit conditions (in priority order):
#   1. meta status == completed | failed   → exit clean, report exit_code
#   2. launcher_pid dead AND transcript idle >IDLE_TIMEOUT
#                                          → exit "worker done, status frozen"
#   3. transcript idle >2*IDLE_TIMEOUT     → exit "possible zombie wrapper"
#
# Self-installs pane title via ANSI OSC 2.

set -uo pipefail

RUN_ID=""
META=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --meta)
      shift; META="${1:-}"; shift
      ;;
    --run-id)
      shift; RUN_ID="${1:-}"; shift
      ;;
    -h|--help)
      sed -n '2,9p' "$0"; exit 0
      ;;
    *)
      # Positional shorthand: treat as run_id
      RUN_ID="$1"; shift
      ;;
  esac
done

if [[ -z "$META" && -z "$RUN_ID" ]]; then
  echo "Usage: vibecrafted-await-watch (--meta <path> | --run-id <id> | <run_id>)" >&2
  exit 2
fi

IDLE_TIMEOUT="${VIBECRAFTED_AWAIT_IDLE_TIMEOUT:-60}"
POLL="${VIBECRAFTED_AWAIT_POLL:-3}"
ARTIFACTS_ROOT="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/artifacts"

# Resolve meta from run_id if needed.
# Meta filename does NOT include run_id (timestamp + prompt_id + agent only),
# so we grep .run_id field content across recent meta.json files.
if [[ -z "$META" && -n "$RUN_ID" ]]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "[await-watch] jq required to resolve run_id $RUN_ID" >&2
    exit 3
  fi
  while IFS= read -r candidate; do
    [[ -f "$candidate" ]] || continue
    if [[ "$(jq -r '.run_id // ""' "$candidate" 2>/dev/null)" == "$RUN_ID" ]]; then
      META="$candidate"
      break
    fi
  done < <(find "$ARTIFACTS_ROOT" -maxdepth 6 -name "*.meta.json" -type f -newermt '7 days ago' 2>/dev/null)
fi

if [[ -z "$META" || ! -f "$META" ]]; then
  short_id="${RUN_ID##*-}"
  printf '\033]2;await:%s:not-found\007' "${short_id:-?}"
  echo "[await-watch] meta.json not found (run_id=$RUN_ID meta=$META)" >&2
  sleep 10
  exit 1
fi

# Backfill RUN_ID from meta if needed (for display)
if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(jq -r '.run_id // "?"' "$META" 2>/dev/null || echo '?')"
fi

# Resolve paths + worker pid from meta
if ! command -v jq >/dev/null 2>&1; then
  echo "[await-watch] jq not found on PATH — required for meta parsing" >&2
  exit 3
fi

TRANSCRIPT="$(jq -r '.transcript // ""' "$META")"
WORKER_PID="$(jq -r '.launcher_pid // 0' "$META")"
AGENT="$(jq -r '.agent // "?"' "$META")"
MODE="$(jq -r '.mode // .skill_code // "?"' "$META")"

# Pane title — short run_id, agent, mode
title="await:${AGENT}:${MODE}:${RUN_ID##*-}"
printf '\033]2;%s\007' "$title"

# Header
printf '\033[1;33m──── %s ────\033[0m\n' "$title"
printf 'run_id:     %s\n' "$RUN_ID"
printf 'agent:      %s\n' "$AGENT"
printf 'mode:       %s\n' "$MODE"
printf 'meta:       %s\n' "$META"
printf 'transcript: %s\n' "$TRANSCRIPT"
printf 'worker pid: %s\n' "$WORKER_PID"
printf 'idle exit:  %ss (zombie threshold: %ss)\n' "$IDLE_TIMEOUT" "$((IDLE_TIMEOUT * 2))"
printf '\033[1;33m─────────────────\033[0m\n\n'

# Wait briefly for transcript to appear (worker bootstrap window)
boot_wait=0
while [[ ! -f "$TRANSCRIPT" && $boot_wait -lt 30 ]]; do
  sleep 1
  boot_wait=$((boot_wait + 1))
done

if [[ ! -f "$TRANSCRIPT" ]]; then
  echo "[await-watch] transcript never appeared after 30s — worker likely failed to start" >&2
  exit 4
fi

# Tail in background, kill on our exit
tail -F "$TRANSCRIPT" 2>/dev/null &
TAIL_PID=$!
cleanup() {
  kill "$TAIL_PID" 2>/dev/null || true
  wait "$TAIL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM HUP

# Monitor loop
last_size=$(wc -c < "$TRANSCRIPT" 2>/dev/null || echo 0)
last_change_at=$SECONDS
final_status=""

while true; do
  sleep "$POLL"

  # Re-read status (worker may have updated meta)
  status="$(jq -r '.status // "unknown"' "$META" 2>/dev/null || echo unknown)"
  case "$status" in
    completed|failed)
      final_status="$status"
      exit_code="$(jq -r '.exit_code // "?"' "$META" 2>/dev/null || echo '?')"
      printf '\n\033[1;32m[await-watch] worker %s (exit_code=%s)\033[0m\n' "$status" "$exit_code"
      break
      ;;
  esac

  # Transcript size delta
  size="$(wc -c < "$TRANSCRIPT" 2>/dev/null || echo 0)"
  if [[ "$size" != "$last_size" ]]; then
    last_size=$size
    last_change_at=$SECONDS
  fi

  idle=$(( SECONDS - last_change_at ))

  # Exit condition 2: worker dead + idle past threshold
  if [[ "$idle" -gt "$IDLE_TIMEOUT" ]] && [[ "$WORKER_PID" -gt 0 ]]; then
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
      final_status="orphan-exit"
      printf '\n\033[1;33m[await-watch] worker pid %s dead + transcript idle %ss — exiting (status frozen at "%s")\033[0m\n' "$WORKER_PID" "$idle" "$status"
      break
    fi
  fi

  # Exit condition 3: extreme idle even with live wrapper (zombie)
  if [[ "$idle" -gt "$((IDLE_TIMEOUT * 2))" ]]; then
    final_status="zombie-suspect"
    printf '\n\033[1;31m[await-watch] transcript idle %ss + wrapper still alive (pid %s) — suspected zombie, exiting\033[0m\n' "$idle" "$WORKER_PID"
    break
  fi
done

# Final summary
final_size=$(wc -c < "$TRANSCRIPT" 2>/dev/null || echo 0)
printf '\n──── done: %s ────\n' "$final_status"
printf 'final transcript size: %s bytes\n' "$final_size"
printf 'final meta status:     %s\n' "$status"
printf '────────────────────────\n'

# Keep pane open for ~30s so operator can read final state, then self-close.
# zellij --close-on-exit will reap the pane after we exit.
sleep 30

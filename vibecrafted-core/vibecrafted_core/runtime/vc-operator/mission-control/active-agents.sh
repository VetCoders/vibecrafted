#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

while :; do
  mc_header "Active Agents"

  if ! command -v jq >/dev/null 2>&1; then
    mc_note "jq not available. Install jq to render agent metadata."
    sleep 5
    continue
  fi

  payload="$(
    find "$MC_ARTIFACT_ROOT" -type f -name '*.meta.json' -mtime -1 2>/dev/null |
      while read -r file; do
        jq -r '
          select(.status == "launching" or .status == "running" or .status == "in-progress" or .status == "ghost")
          | [(.updated_at // "-"), (.status // "-"), (.liveness // "unknown_legacy"), (.agent // "-"), (.mode // "-"), (.run_id // "-")]
          | @tsv
        ' "$file" 2>/dev/null || true
      done |
      sort -r |
      head -n 20
  )"

  if [[ -z "$payload" ]]; then
    mc_note "No recent agent metadata found in the last 24 hours."
    sleep 2
    continue
  fi

  printf '%supdated_at                status       liveness        agent     mode      run_id%s\n' "$MC_STEEL" "$MC_RESET"
  printf '%s------------------------  -----------  --------------  --------  --------  ----------------%s\n' "$MC_STEEL" "$MC_RESET"

  while IFS=$'\t' read -r updated status liveness agent mode run_id; do
    color="$(mc_status_color "$status")"
    live_color="$(mc_status_color "$liveness")"
    printf '%-24s  %s%-11s%s  %s%-14s%s  %-8s  %-8s  %s\n' \
      "$updated" "$color" "$status" "$MC_RESET" "$live_color" "$liveness" "$MC_RESET" "$agent" "$mode" "$run_id"
  done <<< "$payload"

  sleep 2
done

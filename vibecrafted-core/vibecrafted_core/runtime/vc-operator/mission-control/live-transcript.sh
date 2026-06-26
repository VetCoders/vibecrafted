#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

while :; do
  mc_header "Live Transcript"

  latest_transcript="$(find "$MC_ARTIFACT_ROOT" -type f -name '*.transcript.log' 2>/dev/null | sort | tail -n 1)"

  if [[ -z "$latest_transcript" ]]; then
    mc_note "Waiting for transcript logs..."
    sleep 2
    continue
  fi

  printf '%sfile:%s %s\n\n' "$MC_STEEL" "$MC_RESET" "$latest_transcript"
  tail -n 80 "$latest_transcript" 2>/dev/null || mc_note "Transcript exists but is not readable yet."

  sleep 2
done

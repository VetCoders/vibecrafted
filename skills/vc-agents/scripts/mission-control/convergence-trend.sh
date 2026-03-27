#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

while :; do
  mc_header "Convergence"

  if ! command -v jq >/dev/null 2>&1; then
    mc_note "jq not available. Install jq to render convergence metadata."
    sleep 5
    continue
  fi

  payload="$(
    find "$MC_ARTIFACT_ROOT" -type f -name '*.meta.json' 2>/dev/null |
      while read -r file; do
        jq -r '
          [
            (.updated_at // "-"),
            (.run_id // "-"),
            (.agent // "-"),
            (.status // "-"),
            ((.findings // "-") | tostring),
            ((.usage.input_tokens // .usage.prompt_tokens // "-") | tostring)
          ]
          | @tsv
        ' "$file" 2>/dev/null || true
      done |
      sort -r |
      head -n 12
  )"

  if [[ -z "$payload" ]]; then
    mc_note "No convergence metadata available yet."
    sleep 5
    continue
  fi

  printf '%supdated_at                run_id            agent     status       findings   in_tokens%s\n' "$MC_STEEL" "$MC_RESET"
  printf '%s------------------------  ----------------  --------  -----------  ---------  ---------%s\n' "$MC_STEEL" "$MC_RESET"

  while IFS=$'\t' read -r updated run_id agent status findings input_tokens; do
    color="$(mc_status_color "$status")"
    printf '%-24s  %-16s  %-8s  %s%-11s%s  %-9s  %s\n' \
      "$updated" "$run_id" "$agent" "$color" "$status" "$MC_RESET" "$findings" "$input_tokens"
  done <<< "$payload"

  sleep 5
done

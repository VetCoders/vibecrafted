#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

while :; do
  mc_header "Recent Sessions"

  payload=""
  mode_label="artifact fallback"

  if command -v aicx-mcp >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    payload="$(
      aicx-mcp search --query "recent agent sessions" --limit 8 2>/dev/null |
        jq -r '.items[]? | [(.date // "-"), (.agent // "-"), (.label // "-"), (.file // "-")] | @tsv' 2>/dev/null || true
    )"
    [[ -n "$payload" ]] && mode_label="aicx-mcp"
  fi

  if [[ -n "$payload" ]]; then
    printf '%ssource:%s %s\n' "$MC_STEEL" "$MC_RESET" "$mode_label"
    printf '%sdate                      agent     label                         file%s\n' "$MC_STEEL" "$MC_RESET"
    printf '%s------------------------  --------  ----------------------------  ----------------%s\n' "$MC_STEEL" "$MC_RESET"

    while IFS=$'\t' read -r date_value agent label file_path; do
      printf '%-24s  %-8s  %-28s  %s\n' "$date_value" "$agent" "$label" "$(basename "$file_path")"
    done <<< "$payload"

    sleep 10
    continue
  fi

  payload="$(
    find "$MC_ARTIFACT_ROOT" -path '*/reports/*.meta.json' -type f 2>/dev/null |
      while read -r file; do
        if command -v jq >/dev/null 2>&1; then
          jq -r '
            [(.updated_at // "-"), (.agent // "-"), (.status // "-"), (.report // .transcript // input_filename)]
            | @tsv
          ' "$file" 2>/dev/null || printf '%s\t-\t-\t%s\n' "$(basename "$file")" "$file"
        else
          printf '%s\t-\t-\t%s\n' "$(basename "$file")" "$file"
        fi
      done |
      sort -r |
      head -n 15
  )"

  if [[ -z "$payload" ]]; then
    mc_note "No recent session artifacts found."
    sleep 5
    continue
  fi

  printf '%ssource:%s %s\n' "$MC_STEEL" "$MC_RESET" "$mode_label"
  printf '%supdated_at                agent     status       artifact%s\n' "$MC_STEEL" "$MC_RESET"
  printf '%s------------------------  --------  -----------  ----------------%s\n' "$MC_STEEL" "$MC_RESET"

  while IFS=$'\t' read -r updated agent status artifact; do
    color="$(mc_status_color "$status")"
    printf '%-24s  %-8s  %s%-11s%s  %s\n' \
      "$updated" "$agent" "$color" "$status" "$MC_RESET" "$(basename "$artifact")"
  done <<< "$payload"

  sleep 10
done

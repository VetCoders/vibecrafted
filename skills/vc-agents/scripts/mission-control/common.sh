#!/usr/bin/env bash
set -euo pipefail

MC_ARTIFACT_ROOT="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/artifacts"

MC_COPPER=$'\033[38;5;173m'
MC_STEEL=$'\033[38;5;247m'
MC_GREEN=$'\033[32m'
MC_YELLOW=$'\033[33m'
MC_CYAN=$'\033[36m'
MC_RESET=$'\033[0m'

mc_clear() {
  printf '\033[H\033[2J'
}

mc_header() {
  local title="$1"
  mc_clear
  printf '%s𝓥𝓲𝓫𝓮𝓬𝓻𝓪𝓯𝓽𝓮𝓭.%s %s%s%s\n' "$MC_COPPER" "$MC_RESET" "$MC_STEEL" "$title" "$MC_RESET"
  printf '%sartifact root:%s %s\n\n' "$MC_STEEL" "$MC_RESET" "$MC_ARTIFACT_ROOT"
}

mc_note() {
  printf '%s%s%s\n' "$MC_STEEL" "$1" "$MC_RESET"
}

mc_status_color() {
  case "${1:-}" in
    completed|success|ok)
      printf '%s' "$MC_GREEN"
      ;;
    launching|running|in_progress|warn|warning)
      if [[ "${1:-}" == "launching" ]]; then
        printf '%s' "$MC_YELLOW"
      else
        printf '%s' "$MC_CYAN"
      fi
      ;;
    *)
      printf '%s' "$MC_STEEL"
      ;;
  esac
}

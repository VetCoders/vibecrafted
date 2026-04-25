#!/usr/bin/env bash
set -euo pipefail

apply=0
include_live=0
quiet=0
max_age_hours="${VIBECRAFTED_ZELLIJ_MAX_AGE_HOURS:-24}"

usage() {
  cat <<'EOF'
Usage:
  zellij-gc.sh [--apply] [--include-live] [--max-age-hours <hours>] [--quiet]

Default behavior is a dry-run over Zellij sessions:
  - always reports dead EXITED sessions
  - optionally targets detached live sessions older than the threshold

Flags:
  --apply                 Actually kill the selected sessions
  --include-live          Include detached live sessions older than the threshold
  --max-age-hours <n>     Age threshold for detached live sessions (default: 24)
  --quiet                 Suppress the summary when nothing actionable is found
  -h, --help              Show this help
EOF
}

while (($#)); do
  case "${1:-}" in
    --apply)
      apply=1
      ;;
    --include-live)
      include_live=1
      ;;
    --max-age-hours)
      shift || {
        echo "--max-age-hours requires a value" >&2
        exit 1
      }
      max_age_hours="${1:-}"
      ;;
    --quiet)
      quiet=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift || true
done

command -v zellij >/dev/null 2>&1 || {
  echo "zellij is required." >&2
  exit 1
}

listing="$(zellij list-sessions 2>/dev/null || true)"
[[ -n "$listing" ]] || {
  (( quiet )) || echo "zellij-gc: no sessions reported"
  exit 0
}

inventory="$(
  python3 - "$max_age_hours" "$listing" <<'PY'
import re
import sys

max_age = float(sys.argv[1])
listing = sys.argv[2]
ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
created_re = re.compile(r"\[Created ([^\]]+?) ago\]")
token_re = re.compile(
    r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|week|weeks|y|year|years)\b",
    re.IGNORECASE,
)

factors = {
    "s": 1 / 3600,
    "sec": 1 / 3600,
    "secs": 1 / 3600,
    "second": 1 / 3600,
    "seconds": 1 / 3600,
    "m": 1 / 60,
    "min": 1 / 60,
    "mins": 1 / 60,
    "minute": 1 / 60,
    "minutes": 1 / 60,
    "h": 1,
    "hr": 1,
    "hrs": 1,
    "hour": 1,
    "hours": 1,
    "d": 24,
    "day": 24,
    "days": 24,
    "w": 24 * 7,
    "week": 24 * 7,
    "weeks": 24 * 7,
    "y": 24 * 365,
    "year": 24 * 365,
    "years": 24 * 365,
}

def created_hours(line):
    match = created_re.search(line)
    if not match:
      return None
    text = match.group(1)
    total = 0.0
    found = False
    for value, unit in token_re.findall(text):
      total += float(value) * factors[unit.lower()]
      found = True
    return total if found else None

for raw in listing.splitlines():
    line = ansi.sub("", raw).strip()
    if not line:
        continue
    parts = line.split()
    if not parts:
        continue
    name = parts[0]
    dead = "(EXITED" in line
    attached = "(attached" in line or "(current" in line
    hours = created_hours(line)
    stale_live = (not dead) and (not attached) and (hours is not None) and (hours >= max_age)
    print(
        "\t".join(
            [
                name,
                "dead" if dead else "live",
                "attached" if attached else "detached",
                "" if hours is None else f"{hours:.2f}",
                "1" if stale_live else "0",
            ]
        )
    )
PY
)"

dead_sessions=()
stale_live_sessions=()
while IFS=$'\t' read -r name state attachment hours stale_flag; do
  [[ -n "$name" ]] || continue
  if [[ "$state" == "dead" ]]; then
    dead_sessions+=("$name")
  elif (( include_live )) && [[ "$attachment" == "detached" && "$stale_flag" == "1" ]]; then
    stale_live_sessions+=("$name")
  fi
done <<<"$inventory"

# Empty-array expansion under `set -u` is fatal on bash 3.2 (macOS system
# bash, which CI macOS runners use). Guard each append on array length.
targets=()
if (( ${#dead_sessions[@]} )); then
  targets+=("${dead_sessions[@]}")
fi
if (( include_live )) && (( ${#stale_live_sessions[@]} )); then
  targets+=("${stale_live_sessions[@]}")
fi

if (( ${#targets[@]} == 0 )); then
  (( quiet )) || echo "zellij-gc: nothing actionable"
  exit 0
fi

if (( apply )); then
  for session in "${targets[@]}"; do
    zellij kill-session "$session" >/dev/null 2>&1 || true
  done
fi

if (( ! quiet )); then
  mode_label="dry-run"
  (( apply )) && mode_label="applied"
  echo "zellij-gc: $mode_label"
  if (( ${#dead_sessions[@]} )); then
    echo "  dead: ${dead_sessions[*]}"
  fi
  if (( include_live )) && (( ${#stale_live_sessions[@]} )); then
    echo "  stale-live>=${max_age_hours}h: ${stale_live_sessions[*]}"
  fi
fi

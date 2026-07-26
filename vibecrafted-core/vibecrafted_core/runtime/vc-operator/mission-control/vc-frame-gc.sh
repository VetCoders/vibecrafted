#!/usr/bin/env bash
set -euo pipefail

apply=0
include_live=0
quiet=0
max_age_hours="${VIBECRAFTED_VC_FRAME_MAX_AGE_HOURS:-24}"
bucket_tab_limit="${VIBECRAFTED_VC_FRAME_BUCKET_TAB_LIMIT:-}"

vc_frame_bin() {
  command -v vc-frame 2>/dev/null || return 1
}

usage() {
  cat <<'EOF'
Usage:
  vc-frame-gc.sh [--apply] [--include-live] [--max-age-hours <hours>]
                 [--bucket-tab-limit <count>] [--quiet]

Default behavior is a dry-run over vc-frame sessions:
  - always reports dead EXITED sessions
  - optionally targets detached live sessions older than the threshold
  - reconciles redundant terminal origin tabs
  - preserves durable bucket viewer tabs unless a limit is explicitly configured

Flags:
  --apply                 Actually kill the selected sessions
  --include-live          Include detached live sessions older than the threshold
  --max-age-hours <n>     Age threshold for detached live sessions (default: 24)
  --bucket-tab-limit <n>   Durable viewer tabs retained per bucket (default: disabled)
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
    --bucket-tab-limit)
      if (($# < 2)); then
        echo "--bucket-tab-limit requires a value" >&2
        exit 1
      fi
      shift
      bucket_tab_limit="$1"
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

vc_frame_bin="$(vc_frame_bin)" || {
  echo "vc-frame is required." >&2
  exit 1
}

case "$bucket_tab_limit" in
  *[!0-9]*)
    echo "--bucket-tab-limit must be a non-negative integer" >&2
    exit 1
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
tab_gc="$script_dir/../../../vc_frame_tab_gc.py"
control_plane="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}/control_plane"
if [[ -f "$tab_gc" && "${VIBECRAFTED_TEST_MODE:-0}" != "1" ]]; then
  tab_args=(
    "$tab_gc"
    --vc-frame-bin "$vc_frame_bin"
    --control-plane "$control_plane"
  )
  [[ -z "$bucket_tab_limit" ]] || tab_args+=(--bucket-tab-limit "$bucket_tab_limit")
  (( apply )) && tab_args+=(--apply)
  (( quiet )) && tab_args+=(--quiet)
  python3 "${tab_args[@]}" || true
fi

listing="$("$vc_frame_bin" list-sessions 2>/dev/null || true)"
[[ -n "$listing" ]] || {
  (( quiet )) || echo "vc_frame-gc: no sessions reported"
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
    if " [Created " not in line:
        continue
    name = line.split(" [Created ", 1)[0].rstrip()
    if not name:
        continue
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
  (( quiet )) || echo "vc_frame-gc: nothing actionable"
  exit 0
fi

if (( apply )); then
  for session in "${targets[@]}"; do
    "$vc_frame_bin" kill-session "$session" >/dev/null 2>&1 || true
  done
fi

if (( ! quiet )); then
  mode_label="dry-run"
  (( apply )) && mode_label="applied"
  echo "vc_frame-gc: $mode_label"
  if (( ${#dead_sessions[@]} )); then
    echo "  dead: ${dead_sessions[*]}"
  fi
  if (( include_live )) && (( ${#stale_live_sessions[@]} )); then
    echo "  stale-live>=${max_age_hours}h: ${stale_live_sessions[*]}"
  fi
fi

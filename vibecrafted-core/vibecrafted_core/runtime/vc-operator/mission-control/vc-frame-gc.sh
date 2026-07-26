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

python_bin() {
  local candidate
  for candidate in \
    "${VIBECRAFTED_PYTHON:-}" \
    "${XDG_DATA_HOME:-$HOME/.local/share}/uv/tools/vibecrafted-core/bin/python3" \
    python3.14 python3.13 python3.12 python3.11 python3
  do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c \
      'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

usage() {
  cat <<'EOF'
Usage:
  vc-frame-gc.sh [--apply] [--include-live] [--max-age-hours <hours>]
                 [--bucket-tab-limit <count>] [--quiet]

Default behavior is a dry-run over proof-backed vc-frame tabs.
No session is selected from list-sessions and this command never calls the
untyped `kill-session` surface.

Flags:
  --apply                 Close exact proof-backed tab incarnations
  --include-live          Refused: live-session GC has no typed identity contract
  --max-age-hours <n>     Compatibility flag; no session-age selection is performed
  --bucket-tab-limit <n>  Durable viewer tabs retained per bucket (default: disabled)
  --quiet                 Suppress a successful empty summary
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
      if (($# < 2)); then
        echo "--max-age-hours requires a value" >&2
        exit 1
      fi
      shift
      max_age_hours="$1"
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
  shift
done

if (( include_live )); then
  echo "--include-live is unsafe: vc-frame kill-session has no typed incarnation selector" >&2
  exit 2
fi

if [[ ! "$max_age_hours" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "--max-age-hours must be a non-negative number" >&2
  exit 1
fi

case "$bucket_tab_limit" in
  *[!0-9]*)
    echo "--bucket-tab-limit must be a non-negative integer" >&2
    exit 1
    ;;
esac

vc_frame="$(vc_frame_bin)" || {
  echo "vc-frame is required." >&2
  exit 1
}
python="$(python_bin)" || {
  echo "Vibecrafted requires Python >=3.11 for proof-gated vc-frame GC." >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
package_root="$(cd "$script_dir/../../../.." && pwd -P)"
tab_gc="$script_dir/../../../vc_frame_tab_gc.py"
vibecrafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
control_plane="${VIBECRAFTED_CONTROL_PLANE:-$vibecrafted_home/control_plane}"

if [[ ! -f "$tab_gc" ]]; then
  echo "proof-gated vc-frame tab GC is unavailable: $tab_gc" >&2
  exit 1
fi

tab_args=(
  --vc-frame-bin "$vc_frame"
  --control-plane "$control_plane"
)
[[ -z "$bucket_tab_limit" ]] || tab_args+=(--bucket-tab-limit "$bucket_tab_limit")
(( apply )) && tab_args+=(--apply)
(( quiet )) && tab_args+=(--quiet)

PYTHONPATH="$package_root${PYTHONPATH:+:$PYTHONPATH}" \
  "$python" -m vibecrafted_core.vc_frame_tab_gc "${tab_args[@]}"

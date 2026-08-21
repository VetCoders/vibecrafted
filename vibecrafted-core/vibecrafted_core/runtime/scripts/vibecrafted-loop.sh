#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
core_dir="${VIBECRAFTED_CORE_DIR:-$(cd "$script_dir/../../.." && pwd)}"

PYTHONPATH="$core_dir${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m vibecrafted_core.loop "$@"

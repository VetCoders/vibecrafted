#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
core_dir="${VIBECRAFTED_CORE_DIR:-$repo_root/vibecrafted-core}"

PYTHONPATH="$core_dir${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m vibecrafted_core.compact_hooks postcompact

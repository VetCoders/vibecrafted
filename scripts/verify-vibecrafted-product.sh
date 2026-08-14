#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$repo_root/vibecrafted-core${PYTHONPATH:+:$PYTHONPATH}"

exec "$repo_root/scripts/project-python" \
  -m vibecrafted_core.product_contract "$@"

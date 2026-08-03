#!/usr/bin/env bash
# copy-scrollback.sh — Dump focused pane scrollback, copy to clipboard (pbcopy) and push to Paste Stack
set -euo pipefail

tmp=$(mktemp -t vc-pane-dump.XXXXXX)
trap 'rm -f "$tmp"' EXIT

current="${VC_FRAME_PANE_ID:-}"

pane_id=$(vc-frame action list-panes --json --all --state 2>/dev/null | python3 -c '
import json, os, sys
current = os.environ.get("VC_FRAME_PANE_ID", "")
try:
    panes = json.load(sys.stdin)
    # 1. Look for focused pane that is not the floating command script pane
    match = next((p for p in panes if p.get("is_focused") and str(p.get("id")) != current), None)
    # 2. Fallback to first non-plugin active terminal pane if floating pane stole focus
    if not match:
        match = next((p for p in panes if not p.get("is_plugin") and str(p.get("id")) != current), None)
    if match:
        prefix = "plugin_" if match.get("is_plugin") else ""
        print(f"{prefix}{match.get(\"id\")}")
except Exception:
    pass
' || true)

if [[ -n "$pane_id" ]]; then
    vc-frame action dump-screen --full --pane-id "$pane_id" --path "$tmp"
    pbcopy < "$tmp"
else
    vc-frame action dump-screen --full --path "$tmp"
    pbcopy < "$tmp"
fi

# Append to Paste Stack history (FIFO max 50 entries)
if [[ -s "$tmp" ]]; then
    cache_dir="${HOME}/.cache/vc-frame"
    mkdir -p "$cache_dir"
    stack_file="${cache_dir}/paste-stack.json"

    python3 -c '
import json, os, sys

tmp_file = sys.argv[1]
stack_file = sys.argv[2]

try:
    with open(tmp_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if not content.strip():
        sys.exit(0)

    stack = []
    if os.path.exists(stack_file):
        try:
            with open(stack_file, "r", encoding="utf-8") as f:
                stack = json.load(f)
        except Exception:
            stack = []

    # Filter out duplicate of most recent item
    if not stack or stack[0] != content:
        stack.insert(0, content)

    # Cap to max 50 items
    stack = stack[:50]

    with open(stack_file, "w", encoding="utf-8") as f:
        json.dump(stack, f, ensure_ascii=False, indent=2)
except Exception as e:
    pass
' "$tmp" "$stack_file" || true
fi

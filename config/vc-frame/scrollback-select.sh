#!/usr/bin/env bash
# scrollback-select.sh — mouseless scrollback selection (spec 1.2 §B)
#
# Dumps the focused pane's full scrollback into a read-only vim/nvim buffer.
# Visual modes work (v / V / Ctrl-v). After the editor exits, if the operator
# wrote a yank file via the `y` mapping, content is pbcopy'd and pushed onto
# the Paste Stack.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PASTE_STACK=""
for candidate in \
  "${SCRIPT_DIR}/paste-stack.sh" \
  "${HOME}/.config/vetcoders/frontier/vc-frame/paste-stack.sh" \
  "${HOME}/.config/vc-frame/paste-stack.sh"
do
  if [[ -x "$candidate" ]]; then
    PASTE_STACK="$candidate"
    break
  fi
done

tmp="$(mktemp "${TMPDIR:-/tmp}/vc-scrollback.XXXXXX")"
yank_file="$(mktemp "${TMPDIR:-/tmp}/vc-scroll-yank.XXXXXX")"
trap 'rm -f -- "$tmp" "$yank_file"' EXIT

current="${VC_FRAME_PANE_ID:-}"
pane_id="$(
  vc-frame action list-panes --json --all --state 2>/dev/null | python3 -c '
import json, os, sys
current = os.environ.get("VC_FRAME_PANE_ID", "")
try:
    panes = json.load(sys.stdin)
    match = next((p for p in panes if p.get("is_focused") and str(p.get("id")) != current), None)
    if not match:
        match = next((p for p in panes if not p.get("is_plugin") and str(p.get("id")) != current), None)
    if match:
        prefix = "plugin_" if match.get("is_plugin") else ""
        print(f"{prefix}{match.get(\"id\")}")
except Exception:
    pass
' || true
)"

if [[ -n "$pane_id" ]]; then
  vc-frame action dump-screen --full --pane-id "$pane_id" --path "$tmp" 2>/dev/null || true
else
  vc-frame action dump-screen --full --path "$tmp" 2>/dev/null || true
fi
if [[ ! -s "$tmp" ]]; then
  printf '(empty scrollback)\n' >"$tmp"
fi

editor_bin="vim"
if command -v nvim >/dev/null 2>&1; then
  editor_bin="nvim"
fi

# Read-only view with line numbers; `y` in visual mode writes the selection
# to $yank_file (vimscript is kept tiny and path-safe).
"$editor_bin" -R \
  -c 'set number' \
  -c 'set laststatus=0' \
  -c 'set nowrap' \
  -c 'set sidescroll=1' \
  -c "let g:vc_yank_file='${yank_file//\'/\'\'}'" \
  -c 'vnoremap <silent> y "zy:call writefile(split(@z, "\n", 1), g:vc_yank_file)<CR>:echo "yanked — quit to push paste-stack"<CR>' \
  -- "$tmp" || true

if [[ -s "$yank_file" ]]; then
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy <"$yank_file" || true
  fi
  if [[ -n "$PASTE_STACK" ]]; then
    "$PASTE_STACK" push "$yank_file" || true
  fi
fi

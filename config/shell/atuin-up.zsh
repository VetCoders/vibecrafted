#!/usr/bin/env zsh
# Atuin keyboard Up binding for host shells.

#
# Keyboard Up → Atuin search. Mouse wheel is handled by the Alacritty host
# preset (primary buffer = scrollback, alternate = arrows for TUIs), so Up
# no longer collides with scroll. Source of truth for the wheel split:
#   vc-frame/tools/alacritty/vc-frame.toml
#
# Usage in ~/.zshrc (after PATH is ready):
#   source /path/to/config/shell/atuin-up.zsh
# or paste the block. Also wired in vibecrafted-vm/zshrc.template.
#
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI

if command -v atuin >/dev/null 2>&1; then
  # Disable stock Up binding from atuin init, then re-bind with multiline guard.
  eval "$(atuin init zsh --disable-ctrl-r --disable-up-arrow)"
  atuin-up-or-history() {
    emulate -L zsh
    if [[ $BUFFER == *$'\n'* ]]; then
      zle up-line-or-history
    else
      _atuin_search --shell-up-key-binding "$@"
    fi
  }
  zle -N atuin-up-or-history atuin-up-or-history
  bindkey '^[[A' atuin-up-or-history
  bindkey '^[OA' atuin-up-or-history
  bindkey '^[[B' down-line-or-history
  bindkey '^[OB' down-line-or-history
  bindkey '^R' atuin-search
  bindkey -M viins '^R' atuin-search-viins
  bindkey -M vicmd '/' atuin-search-vicmd
fi

#!/usr/bin/env bash
# shellcheck shell=bash
# Host-shell entrypoint for Alacritty / vc-terminal.
# (zsh-compatible; written as bash for shellcheck + portable /bin/sh callers.)
#
# Keep the interactive shell on the PRIMARY buffer so Alacritty scrollback
# works and mouse-wheel (~Alt) browses output instead of sending Up/Down.
# TUIs (Atuin, less, vim, vc-frame panes) enter/leave the alternate buffer
# themselves — do not smcup the whole session.
#
# Install next to the host preset:
#   ~/.config/alacritty/launch-primary-shell.zsh
# and point alacritty.toml at it only when you want a plain login shell
# (the shipped vc-frame.toml launches `vc-frame attach` directly instead).
#
# Source of truth: vc-frame/tools/alacritty/launch-primary-shell.zsh
# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI

tty_path="/dev/tty"

leave_alt_screen() {
  if [[ -w "$tty_path" ]]; then
    if command -v tput >/dev/null 2>&1; then
      tput rmcup >"$tty_path" 2>/dev/null || printf '\e[?1049l' >"$tty_path"
    else
      printf '\e[?1049l' >"$tty_path"
    fi
  fi
}

# Ensure we start on the primary buffer (scrollback + ~Alt wheel bindings).
leave_alt_screen

if [[ "${1:-}" == "vc-start" ]]; then
  /bin/zsh -lic 'vc-start'
  # vc-frame owns its own alternate-buffer lifecycle; clean sticky smcup.
  leave_alt_screen
fi

exec /bin/zsh -l

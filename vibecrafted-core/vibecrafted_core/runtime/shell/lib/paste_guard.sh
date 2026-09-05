# shellcheck shell=bash
# NBSP paste guard. Clipboard managers and rich-text sources smuggle U+00A0
# into shell lines; the shell then reads ";<NBSP>aicx" as one word and fails
# with "command not found:  aicx" — the invisible byte renders as a doubled
# space (live incident: Paste.app snippet, 2026-09-05, identical NBSP offsets
# across two paste events). Scrub every bracketed paste down to plain spaces.
# zsh-only surface: ZLE exists only in interactive zsh; bash callers no-op.
if [[ -n "${ZSH_VERSION:-}" ]] && [[ -o interactive ]] 2>/dev/null; then
  autoload -Uz bracketed-paste-magic
  zle -N bracketed-paste bracketed-paste-magic
  vc_paste_scrub_nbsp() { PASTED=${PASTED//$'\u00A0'/ } }
  zstyle :bracketed-paste-magic paste-init vc_paste_scrub_nbsp
fi

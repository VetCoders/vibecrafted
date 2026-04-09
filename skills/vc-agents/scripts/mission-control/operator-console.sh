#!/usr/bin/env bash
set -euo pipefail

export VIBECRAFTED_OPERATOR_MODE=1
export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=down

shell_bin="${SHELL:-}"
if [[ -z "$shell_bin" || ! -x "$shell_bin" ]]; then
  if command -v zsh >/dev/null 2>&1; then
    shell_bin="$(command -v zsh)"
  else
    shell_bin="$(command -v bash)"
  fi
fi

printf '⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Operator Mode\n'
printf '──────────────────────────────────\n'
printf 'Start here:\n'
printf '  vibecrafted marbles codex --count 3 --depth 3\n'
printf '  vibecrafted workflow claude -p "Plan and implement auth"\n'
printf '  vibecrafted review codex -f /path/to/plan.md\n'
printf '\n'
printf 'Spawn policy:\n'
printf '  normal workflows -> launcher opens below this pane\n'
printf '  marbles -> state launcher opens below, loop panes grow to the right\n'
printf '\n'

exec "$shell_bin" -l

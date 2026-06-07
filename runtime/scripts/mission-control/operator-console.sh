#!/usr/bin/env bash
set -euo pipefail

export VIBECRAFTED_OPERATOR_MODE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

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
printf '  marbles -> worker panes stay stacked with their orchestrator\n'
printf '\n'

if [[ -x "$SCRIPT_DIR/zellij-gc.sh" ]]; then
  bash "$SCRIPT_DIR/zellij-gc.sh" --apply --quiet || true
fi

# restore-orphaned path retired 2026-04-22 — it reanimated zombie runs without
# PID validation and burned the laptop. Dead runs stay dead. Spawn-time GC in
# marbles_spawn.sh + watcher heartbeat keep the truth fresh without resurrection.

exec "$shell_bin" -l

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

printf 'Vibecrafted Operator\n'
printf '\n'
printf 'Session\n'
printf '  entrypoint: vc-start\n'
printf '  agent tabs: new runs open in this session and stay visible in the tab bar\n'
printf '\n'
printf 'Start here\n'
printf '  vibecrafted workflow codex --prompt "..."\n'
printf '  vibecrafted implement codex --file path/to/brief.md\n'
printf '  vibecrafted research --prompt "..."\n'
printf '\n'
printf 'Watch runs\n'
printf '  vibecrafted codex observe --run-id <run_id>\n'
printf '  vibecrafted codex await --run-id <run_id>\n'
printf '\n'
printf 'Artifacts\n'
printf '  ~/.vibecrafted/artifacts\n'
printf '  explorer pane opens beside this shell when the terminal is wide enough\n'
printf '\n'
printf 'Leaving\n'
printf '  close terminal: detach\n'
printf '  Ctrl+q: quit intentionally\n'
printf '\n'

if [[ -x "$SCRIPT_DIR/vc-frame-gc.sh" ]]; then
  bash "$SCRIPT_DIR/vc-frame-gc.sh" --apply --quiet || true
fi

# restore-orphaned path retired 2026-04-22 — it reanimated zombie runs without
# PID validation and burned the laptop. Dead runs stay dead. Spawn-time GC in
# marbles_spawn.sh + watcher heartbeat keep the truth fresh without resurrection.

exec "$shell_bin" -l

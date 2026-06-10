# vc-operator Runtime

Workflow-owned runtime for the `vc-operator` orchestration posture
(skill: `skills/vc-operator/`): the mission-control surface the operator
watches while a fleet runs.

## Layout

- `mission-control/operator-console.sh` — operator console pane.
- `mission-control/active-agents.sh` — live agent inventory watcher.
- `mission-control/recent-sessions.sh` — recent run/session watcher.
- `mission-control/convergence-trend.sh` — marbles convergence monitor.
- `mission-control/live-transcript.sh` — transcript tail pane.
- `mission-control/zellij-gc.sh` — dead zellij session garbage collector
  (resolved via `_vetcoders_workflow_script "vc-operator"
"mission-control/zellij-gc.sh"` in `runtime/shell/lib/zellij.sh`).
- `mission-control/common.sh` — helpers shared between the panes above;
  sourced relative to the script dir, internal to this workflow.

## Consumers

- `config/zellij/layouts/{dashboard,marbles,operator}.kdl` probe
  `<runtime-root>/vc-operator/mission-control/` first and fall back to the
  legacy `<runtime-root>/scripts/mission-control/` path for older installed
  runtimes.

## What stays shared (do not pull in here)

- `runtime/scripts/lib/` — launcher/meta/telemetry library.
- `runtime/scripts/await.sh` — fleet await is a shared surface, not an
  operator-only one.
- `runtime/shell/lib/operator.sh`, `operator_entrypoints.sh`,
  `dashboard.sh` — facade modules that mix operator entrypoints with the
  shared dispatch surface; extracting them needs its own ownership pass.

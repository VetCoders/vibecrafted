# Read-Write Cadence Runtime TODO

This note parks the next runtime direction after `vc-research uno`.
The canonical lifecycle this TODO implements toward now lives in
[`LIFECYCLE.md`](./LIFECYCLE.md) (operator-dictated canon, 2026-06-08).

## Target Rhythm

- Read phase: research, init, intents, review, audit, followup.
- Write phase: workflow, implement, ownership, marbles, polarize, release.
- The runtime should make the phase visible in launch receipts, control-plane state, reports, and dashboard views.
- Each workflow should eventually have one async launcher with a full lifecycle: launch, observe, await, stop/recover, report closure.

## Polarize Convergence Contract

- `vc-polarize` runtime should be isomorphic to `vc-marbles` where lifecycle mechanics are concerned.
- `vc-marbles` goal: add pressure and fill gaps, including deliberate excess when needed.
- `vc-polarize` goal: remove excess and shape the final form.
- Shared mechanics should include run state, await/observe behavior, report tracking, dashboard visibility, and recovery semantics.
- Divergence should live in objective, prompts, convergence criteria, and final report shape.

## Immediate Follow-Up Questions

- Which current marbles lifecycle pieces can be lifted without semantic leakage?
- Which polarize surfaces already pretend to be launcher-equivalent but are not?
- Where should phase metadata live so MCP, server, app, and shell see the same truth?

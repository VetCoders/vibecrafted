# Control status threads (vc-server)

Investigation + partial fix branch: `fix/control-status-threads`.

## Orthogonal threads (by design)

| Thread                   | Owner                                | Ends when                                                |
| ------------------------ | ------------------------------------ | -------------------------------------------------------- |
| Process `state` / health | merge of snapshots+meta+locks+events | FINAL_STATES / terminal liveness / exit_code (workers)   |
| Settlement f / x / n     | Python snapshot only                 | `finalized` / `failed` / `needs_attention` / `invalid`   |
| Delivery axes            | kernel receipt                       | never invented from `completed`                          |
| Lifecycle container      | lifecycle_runs state.json            | **overall workflow status** final (not stage exit alone) |

## Bugs fixed here

1. Lifecycle `to_run_status` no longer treats stage `exit_code` as process-terminal while status is still mid-flight.
2. `delivery_axes_for_receipt` no longer maps unknown mid-flight statuses to `ExecutionState::Failed`.
3. `/api/control/state` + dashboard export `stalled_runs`; cards show `settle:f|x|n` and last_error.

## Still open (next PRs)

- Single documented `TerminalKind` (process vs settlement).
- Disambiguate process state `"stalled"` vs health `stalled`.
- All Runs still snapshot-only (label now says so).
- Recompute health on pure snapshot load/lookup with `now`.

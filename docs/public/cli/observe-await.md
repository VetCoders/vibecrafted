---
title: "Following Runs: Observe and Await"
description: "How to follow dispatched runs with observe and await, where run truth lives on disk, and the three-signal rule for declaring a run finished."
section: cli
order: 40
---

# Following Runs: Observe and Await

Every dispatch creates a run in the control plane, identified by a run id
such as `impl-<timestamp>-<id>` or `scaf-<timestamp>-<id>`. The run — not the
terminal tab, not the process — is the unit of truth. Two verbs follow it:
`observe` reads what a run produced; `await` blocks until it lands.

## The two verbs

```bash
vibecrafted observe <agent> --last            # last report/transcript
vibecrafted observe <agent> --run-id <id>     # a specific run
vibecrafted await <agent> --last              # wait for the last run
vibecrafted await <agent> --run-id <id>       # wait for a specific run
```

Arm `await` immediately after dispatching — supervisor-side, before doing
anything else with the run:

```bash
vibecrafted implement codex --prompt "Ship <task>"
vibecrafted await codex --run-id impl-<timestamp>-<id>
```

`await` is liveness-aware: it aggregates child-run movement for looping
workflows (a marbles parent freezes between rounds while its children work),
and it returns `completed` with reason `report_delivered` as soon as a
non-empty report exists — a worker that wrote its report and exited is done
even if metadata lags.

Do not hedge `await` with manual sleep/poll/process monitors. If you feel the
need to double-guard it, that is a bug report against the runtime contract,
not a supervision pattern.

## Run ids, transcripts, and reports

On-disk truth, when the CLI is not enough:

| Path                                              | What it holds                                  |
| ------------------------------------------------- | ---------------------------------------------- |
| `~/.vibecrafted/control_plane/runs/<id>.json`     | run state, liveness, exit code                 |
| `~/.vibecrafted/control_plane/runs/archive/`      | settled runs                                   |
| `~/.vibecrafted/control_plane/runtime_runs/<id>/` | `transcript.log` and runtime artifacts         |
| `~/.vibecrafted/control_plane/launches/*.log`     | launcher stderr — first stop for silent deaths |
| `~/.vibecrafted/artifacts/<org>/<repo>/<date>/`   | plans, briefs, reports                         |

Reports carry YAML frontmatter (`run_id`, `agent`, `skill`, `status`, claim
fields) — the same contract documented in
[Briefs and reports](/docs/briefs-and-reports/).

## Liveness: the three-signal rule

Declaring a run finished is always a multi-signal decision, because any
single channel can lie: a worker can die without writing a report, metadata
can lag a completed worker, and an exit code alone proves nothing about
delivery.

Before declaring a run done, reconcile:

1. **The await verdict** — `await` returned success for the run id.
2. **Terminal state in run meta** — the run record shows a terminal state
   (`completed`, `failed`), not `active` or `stalled`.
3. **Worker process death** — the worker pid is gone.

When a report path was promised, add a fourth check: the report file exists
and is non-empty.

Two agreeing signals justify cautious next steps or recovery. Three are
required to declare done. Any disagreement means: treat the run as live and
re-arm `await`.

## Reading the signals

```bash
# 1. await verdict
vibecrafted await codex --run-id impl-<timestamp>-<id>

# 2. run meta terminal state
cat ~/.vibecrafted/control_plane/runs/impl-<timestamp>-<id>.json

# 3. report delivered and non-empty
vibecrafted observe codex --run-id impl-<timestamp>-<id>
```

Failure signatures worth knowing:

- **Startup death**: transcript under a few KB and silent for minutes — the
  worker died near launch. Check `launches/*.log`, then stop and refire the
  same brief; briefs are idempotent.
- **Mid-flight death**: transcript frozen, pid gone — stop and refire; the
  run record stays as evidence.
- **Meta lag**: report written but state stuck `active` — the delivered
  report wins; `await` recognizes it as `report_delivered`.

## Settled runs

Finished runs settle into the `f · x · n` ledger (finalized / failed /
needs-attention). Query it read-only:

```bash
vibecrafted settlements summary
vibecrafted settlements inspect <run_id>
```

A worker's own `status: completed` claim is triangulated against exit code,
report, and transcript — contradictions land in needs-attention rather than
being trusted. See [Commands](/docs/commands/) for the full `settlements`
surface and [vc-frame](/docs/vc-frame/) for the dashboard projection of the
same truth.

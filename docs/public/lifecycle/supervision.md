---
title: "Lifecycle Supervision"
description: "The human-controls verbs for lifecycle runs: status, approve, interrupt, fallback, force-audit, accept-dou, and dead-worker recovery."
section: lifecycle
order: 30
---

# Lifecycle Supervision

A lifecycle run is steerable, and every act of steering leaves a trace. The
human-controls verbs are real CLI verbs on every lifecycle command
(`vibecrafted ship`, `vibecrafted dou`, `vibecrafted audit`, …), validated
against the run's manifest and recorded as timestamped `operator_actions`
entries in `state.json`, the run report, and the transcript. There is no
side-channel steering: if it moved the run, it is in the record.

## Observability verbs

```bash
vibecrafted ship runs [--all] [--json]        # lifecycle runs, newest first
vibecrafted ship status [run_id] [--json]     # one run's truth
```

Omitting `run_id` targets the newest run of the invoking workflow. `status`
surfaces the current stage, the baton, the latest `dou_index` next to
`accepted_dou` (operator-accepted gaps), and — when the current stage's
worker died without writing its report — the actionable flag
`worker_dead_without_report`.

## Steering verbs

```bash
vibecrafted ship approve [run_id] [--force]
vibecrafted ship interrupt [run_id]
vibecrafted ship force-audit [run_id]
vibecrafted ship accept-dou [run_id] --finding "<text>"
vibecrafted ship fallback [run_id] --stage <stage-id>
```

| Verb          | Effect                                                                              |
| ------------- | ----------------------------------------------------------------------------------- |
| `approve`     | Fire the baton: launch the pending `next_stage` as a parent-linked continuation run |
| `interrupt`   | Stop the live stage run; the lifecycle run lands in `interrupted` state             |
| `force-audit` | Re-steer the baton to the audit stage when the evidence feels weak                  |
| `accept-dou`  | Mark a DoU finding as consciously accepted for this release                         |
| `fallback`    | Move the baton to a fallback or earlier stage (manifest-validated)                  |

`approve` first verifies the baton's report files exist and are non-empty —
in no-await mode the worker may still be writing — and refuses with the
missing paths otherwise. `--force` is the conscious override and is traced
as `forced_missing_reports`. Steering verbs (`force-audit`, `fallback`)
mutate the baton; `approve` fires it.

## Dead-worker recovery

When a stage worker dies without delivering (status shows
`worker_dead_without_report`, or the transcript is tiny and silent), recover
with the verb sequence — no manual state surgery:

```bash
vibecrafted ship interrupt life-ship-<timestamp>-<id>
vibecrafted ship fallback life-ship-<timestamp>-<id> --stage <stage-id>
vibecrafted ship approve life-ship-<timestamp>-<id> [--force]
```

The baton rewinds with its cargo intact: no stage reports are lost, and the
stage relaunches with the full report trail. Use `--force` only when the
report gate is correctly flagging the report the dead worker never wrote.

Never edit `state.json` by hand. Consumers and operators mutate lifecycle
state only through these verbs.

## Report frontmatter steering

Stage workers steer the lifecycle from inside their report YAML frontmatter;
the runner validates every value against the manifest:

| Key                      | Effect                                                                                   |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| `next_stage: <stage-id>` | Steer the umbrella forward or backward; unknown ids are ignored; no key = manifest order |
| `next_agent: <agent-id>` | Hand the baton: the named agent runs following stages until re-steered                   |
| `dou_index: <int>`       | Open Definition-of-Undone findings; `0` is launch-ready; absent/invalid reads as unknown |

The runner records the latest `dou_index` in `state.json`, on the baton, and
in the run report; in no-await mode `status` reads the live report
frontmatter. The full worker-side contract is in
[Briefs and reports](/docs/briefs-and-reports/).

## Traced operator actions

Every verb invocation appends a timestamped entry to `operator_actions` in
the run's `state.json` and mirrors it into `report.md` and the transcript.
This is the design rule of human participation: the project stays steerable
without manual intervention becoming invisible state mutation. When you read
a finished lifecycle run, you can reconstruct exactly which transitions were
earned by workers and which were pushed by an operator — and why.

## Supervision hygiene

- Arm `vibecrafted await <agent> --run-id <id>` for the active stage run and
  trust it; reconcile the three signals (await verdict, terminal run meta,
  worker pid) before declaring a stage done — see
  [Observe and await](/docs/observe-await/).
- Read stage reports between stages; do not steer from mid-stage transcript
  impressions.
- Prefer baton handoff through lifecycle state and reports over chat
  instructions to the next agent.

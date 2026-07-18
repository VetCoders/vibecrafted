# Continuity Capability — resume, fork, and lifecycle continuation

_Ground truth as of branch `fix/e2e-vc-ship-and-resume-runtime`. Every claim
below names its code owner; when the doc and the code disagree, trust the code
and fix this file._

A dispatched worker can die mid-stage — provider-side stream refusal, transport
failure, machine sleep. Continuity is the runtime's answer: the recorded agent
session, the run identity, and the lifecycle baton all survive the death, and
one public deck verb picks the work back up.

## The three lanes

| Lane                           | Verb                                                       | Identity kept                                                                              | Owner                                                                 |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| Session resume (raw)           | `vibecrafted resume <agent> --session <id>`                | agent session only                                                                         | shell deck (`runtime/shell/lib/marbles.sh`)                           |
| Session fork                   | `vibecrafted resume <agent> --session <id> --fork-session` | parent history → new session                                                               | shell deck; native flags per agent                                    |
| **Run resume (control plane)** | `vibecrafted resume [<agent>] --run-id <id>`               | run id · meta · transcript · **canonical report path** · agent session · lifecycle binding | core (`vibecrafted_core.cli._resume_run_cli` → `workflow.resume_run`) |

### Run resume — the continuity contract

`workflow.resume_run` (vibecrafted-core/vibecrafted_core/workflow.py) resumes a
**terminal** run in place through the same dispatcher lane that launched it:

- same `run_id`, same `runtime_runs/<id>/meta.json` and `transcript.log`
  (transcript appends), same canonical report path from the original contract;
- the recorded agent session is continued, not replaced:
  `spawn._resume_stdin_command` builds `codex exec resume <session> -`,
  `claude --resume <session>` (`--fork-session` optional), grok `--resume`;
  agents with no non-interactive resume contract fail closed;
- lineage lands in `meta.json` under `resume_history[]`
  (`parent_session_id`, `resumed_at`, `resume_prompt`, `resume_index`);
- the lifecycle binding is rediscovered from durable state
  (`workflow._lifecycle_state_for_run` scans
  `control_plane/lifecycle_runs/*/state.json` for the stage that launched the
  run) and passed to the dispatcher as `--lifecycle-state`;
- Foundation preflight runs again (read-only stages pass as `UNSEALED`; write
  stages need a sealed receipt — see below);
- `observe` / `await` keep reading the same run id, so they show the same
  truth the resumed worker writes.

Preconditions (fail-closed, event `audit:resume` records every rejection):
the run must exist, be terminal (`run_not_terminal` otherwise), and carry a
recorded agent session (`no_agent_session`). Codex `--fork-session` is
terminal-only (`codex exec` has no fork command) — headless codex fork is
rejected, never downgraded.

### Healing the lifecycle record

The dispatcher's push-side report-on-death (`dispatcher._maybe_record_lifecycle_worker_exit`)
writes failures back into the lifecycle `state.json`. Since the resume lane
landed it also writes a SUCCESS back — but only when the state already records
a failed `worker_exit` for that run. A resumed worker that delivers its report
replaces the stale `report_missing` failure with `report_validated`, so the
lifecycle state and the report never disagree. A healthy first-pass handoff
still writes nothing (the rare-write doctrine holds).

### Continuing the vc-ship lifecycle — no replay

Stage continuation is a separate, existing verb: once the interrupted stage's
report exists (delivered by resume), the operator approves the baton:

```bash
vibecrafted ship approve <lifecycle-run-id>
```

`lifecycle_control.approve_transition` launches ONLY the baton's
`next_stage` as a parent-linked continuation run (`parent_run_id` chains the
lineage); previous stages are never replayed and the baton carries the full
`previous_reports` trail — including the report the resumed worker wrote.

### Foundation binding for continuations

Write stages cannot launch without a Foundation receipt
(`foundation.service.preflight_launch`). The binding order is:

1. explicit `--foundation-receipt` / `spec.foundation_receipt_path`;
2. plan frontmatter bindings (`parse_plan_bindings`);
3. **fail-closed discovery**: the repo's `latest.json`
   (`~/.vibecrafted/foundation/<repo-key>/latest.json`) — `verify_receipt`
   still re-validates authority drift, hash, and root binding, so a stale or
   foreign receipt blocks.

Seal a receipt with the public verb:

```bash
vibecrafted foundation seal [--authority origin/main] [--run-id <id>]
```

## Read/Write Cadence — control-plane rules

The event stream (`control_plane/events.jsonl`) is an append-only tail, NOT
the durable projection. Run snapshots (`control_plane/runs/*.json` plus its
`archive/`) are the projection. Three rules keep the cadence honest
(`vibecrafted_core/control_plane.py`):

1. **Reads never load the whole stream.** `read_event_tail` reads a bounded
   tail (seek-based); `_merge_event_stream` streams line-by-line with a scoped
   substring prefilter. (Incident: a 4.6 GB / 7.5 M-line stream made every
   status lookup a >120 s, 8 GB-RSS scan.)
2. **Reads must not re-write history.** `_load_existing_snapshots` consults
   the GC archive so an archived terminal run never re-enters the stream as a
   fresh `entered <state>` transition. (Incident: a GC↔projection flip-flop
   appended ~35 duplicate terminal events per second, unbounded.)
3. **The stream rotates.** Past `VIBECRAFTED_EVENTS_MAX_BYTES` (default
   64 MiB) the full-board sync rotates `events.jsonl` into
   `control_plane/events_archive/` — only AFTER the projection pass has
   landed every event-derived run in a snapshot.

## Regression coverage

`vibecrafted-core/tests/test_resume_run.py` drives the full lane end-to-end
through the real dispatcher with a fake agent binary: continued session argv,
original report path, `resume_history` lineage, healed lifecycle
`worker_exit`, and a terminal-successful projection for the same run id —
plus the fail-closed rejections (live run, missing session, headless codex
fork).

## Incident record — why this exists

2026-07-17, vc-ship run `life-ship-260717-201751-44000`, stage `review`
(worker `revi-260717-201752-39000`, codex session `019f714c…`): the provider
flagged the worker's turn mid-review (`turn.failed`, exit 1,
`report_missing`). The deck of that day could resume a _session_ but not a
_run_: no lineage, no report-path reuse, no lifecycle heal — and every public
write launch was separately dead because no Foundation receipt existed and the
deck had no discovery path. The resume lane above closed the gap; the same run
was resumed publicly, delivered its report to the original path, healed the
lifecycle record, and the ship continued from `review` → `workflow` without
replay.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

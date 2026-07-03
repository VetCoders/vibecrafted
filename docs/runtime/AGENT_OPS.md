# Agent Ops — Runtime Failure Classes

The agent-ops canon: failure classes of multi-agent runtimes, observed in
anger, with confirmed remediations. This is runtime mechanics, not identity or
naming — it documents how agents fail _inside this machinery_ (dispatcher,
no-await lifecycle, subagents, watchers) and what actually fixes it.

Every class here earned its entry with at least two confirmed real-world
cases. Speculative classes do not belong in this file.

## The shared principle

> **Neither side may rely on a signal whose channel does not guarantee
> delivery.**

Both classes below are the same root cause seen from opposite ends of the
relay: a worker waiting for a wake-up that will never come, and a supervisor
assuming a death notice that is never sent. The cure is always the same shape:
replace passive waiting with active verification on the side that can act.

---

## Class 1 — Gate-nap („Drzemka na bramce")

_3 confirmed cases, prview-rs session 2026-07-02/03 (Monika). Canonical
description by Monika._

### Symptom

A worker-subagent gets a task with a quality gate (cargo test / build /
release gate, 2–8 min). Instead of waiting for the result, it launches the
gate in the background (`run_in_background` / monitor pattern) and ends its
turn with "waiting for the completion signal". The dispatcher receives
`task-notification: completed` with that "waiting" as the result — the work
hangs half-done (commits exist, but no report/push/replies), and the worker
never comes back on its own.

### Mechanism: wake asymmetry in the harness

The main loop is automatically re-invoked when its background task completes.
A subagent is NOT. For a subagent, end of turn = end of its decision process —
the signal from its own background task has nobody left to wake. The worker
imitates a pattern it sees the orchestrator use (and which is correct _for the
orchestrator_), not knowing that for a subagent it is a trap with no exit.

### Why a ban in the brief is not enough

Case #3 had the explicit ban ("gates synchronously, never in background") and
broke it anyway. Affordance beats prohibition: the flag is visible in the
tool, the gate is long, and the pattern looks like good practice.

### Confirmed remediation (3/3)

Resume the stopped agent with an EXPLANATION OF THE MECHANICS, not a bare
"continue":

> "The gate signal will NEVER reach you — you are a subagent, background
> notifications do not wake you. Read the result directly now (Read the
> output file / re-run the command in the foreground) and finish everything
> in this turn."

Context is preserved; the worker finishes without loss. A soft "finish up" is
too weak — case #2 fell asleep again after one; only the explanation of _why
waiting is futile_ worked.

### Prevention (strongest first)

1. **Harness/hook**: PreToolUse hook on subagents' `run_in_background=true` —
   preferably **auto-degrade to foreground with a message** ("degraded to
   foreground: you are a subagent"), not a hard block. A hard block on an
   8-minute gate can kill the worker on turn timeouts instead; degradation
   teaches the mechanics as a side effect (levels 1 and 3 in one shot).
2. **Dispatcher watchdog**: a `completed` notification whose result matches
   `/czekam|wait.*(monitor|event)/i` → automatic resume with the standard
   mechanics message.
3. **Template preamble** in dispatch/skill worker contracts: "You are a
   subagent: background completions will never wake you. Never end your turn
   waiting." Explanation of mechanics > bare prohibition (evidence: case #3
   vs. the effective resume).

**Implemented in this runtime**: level 3 is wired mechanically — every worker
prompt the runtime composes carries `WORKER_SIGNAL_DISCIPLINE`
(`workflow_runtime.py`, injected by both `workflow._runtime_prompt` and
`workflow_runtime._child_prompt`, so dispatched workers AND supervised
marbles/polarize/research children get the mechanics explanation in their
contract). Levels 1–2 remain harness-side proposals.

### Cost when it hits

~3 × 10–20 min delay per case plus manual intervention; zero lost work
(commits were always on disk — only the final leg hung: report/push/replies).

---

## Class 2 — Report-on-death gap

_3 confirmed cases, vibecrafted vc-ship flights 2026-07-02/03 (claude
supervising codex workers)._

### Symptom

A dispatched worker dies silently at or near startup; the dispatcher never
notices. In no-await lifecycle mode the run's meta stays in a live-looking
state and the supervisor (or its watcher) waits on a report that will never
be written. Observed death modes:

- `codex exec` dies right after `task_started` (rollout truncated at ~22 KB;
  transport failure, not disk) — dispatcher hung blind for 37 minutes.
- `codex` dies on `failed to refresh available models: timeout` (transcript
  ~244 bytes) — a 3-hour watcher budget expired on a corpse.

### Mechanism

In no-await mode nothing owns the child's death: the ephemeral spawn launcher
exits by design, the dispatcher tracks the report file, and process death
emits no report. The absence of a signal is indistinguishable from slow work
unless someone actively checks liveness.

### Confirmed remediation (3/3)

Operator-verb sequence, no manual state surgery:

```
vibecrafted ship interrupt <run_id>          # trace: stop_accepted
vibecrafted ship fallback <run_id> --stage <stage>   # baton rewinds WITH cargo
vibecrafted ship approve <run_id> [--force]  # --force only when the cargo gate
                                             # correctly flags the unwritten report
```

No baton cargo is lost; the stage relaunches with the full report trail.

### Prevention

1. **Supervisor-side watchers, never worker-side** (see patterns below) with
   explicit early-death detection: transcript < 5 KB and silent for 10 min =
   startup death; do not wait out the full stage budget.
2. **Terminal-state check** alongside the report poll: read `meta.json` state
   (`failed` / `process_dead` / `contract_failed` / `ghost`), don't infer from
   transcript growth alone.
3. **Systemic cut (implemented, on-read)**: `control_plane.run_liveness()`
   runs the dispatch reconciler for one run and answers with OS-level truth;
   `LifecycleSupervisor.status()` joins it for the current stage as
   `stage_worker` with the actionable flag `worker_dead_without_report` —
   surfaced by `vibecrafted ship status`, `vc_lifecycle_status` (MCP), and
   anything else reading the status projection. Still open: a push-side
   variant where the detached dispatcher writes the terminal state at death
   itself, so purely passive readers (raw `state.json` consumers) see it
   without any status call.

---

## Supervisor watcher patterns (battle-tested, two full vc-ship flights)

- Poll the stage **report file** (`[ -s "$REPORT" ]`), paired with the
  `meta.json` terminal-state check above. Report file appearing = stage done;
  terminal state = stage dead. Waiting on anything else is guesswork.
- **Marbles parent runs have NO transcript.log** — the loop spawns children
  with their own transcripts under `reports/marbles/<run>-children/`. Watch
  children-dir growth or the report file; a parent-transcript stall check is
  a false alarm (confirmed twice).
- Watchers live with the supervisor (main loop), never inside a subagent —
  that is Class 1 waiting to happen.
- Budget every watcher, and on silent expiry verify liveness before declaring
  a stall; on noisy expiry check for the early-death signature first.

## Provenance

- Class 1: prview-rs, session 2026-07-02/03, cases #1–#3, remediation and
  canonical description by Monika.
- Class 2: vibecrafted, vc-ship flights `life-ship-260702-123238-24000`
  (v3.3.0) and `life-ship-260702-202338-58000` (lifecycle.schema.v1),
  supervision by claude, session `2603026d-0c40-4ca9-af91-e2ab74256926`.

# vc-operator — AWAIT: Notify-Driven Orchestration

> The operator-agent's relationship to time. Dispatch is fire-and-await,
> not fire-and-forget and not fire-and-poll.

Read alongside [`SKILL.md`](SKILL.md), [`GUIDE.md`](GUIDE.md), [`DISPATCH.md`](DISPATCH.md).

---

## The doctrine

After dispatch, arm `vibecrafted <agent> await --run-id <id>` immediately,
supervisor-side. Control-plane JSON, report files, transcripts, panes, and
scheduled wakeups are diagnostic only, not wake signals. Hedging await with
ad-hoc pollers/watchers is a Class 3 violation; fix `control_plane.await_run`,
do not normalize the hedge.

Liveness is always 3-signal before declaring done: await verdict, terminal-state
run meta, and worker pid dead; if a report is promised, confirm it exists. Two
agreeing signals are enough to act, three to declare done; disagreement means
treat as live and re-arm await. Known skew: rc=0-on-live and meta stuck
`active`/`stalled` after real completion.

See `docs/runtime/AGENT_OPS.md` for the Class 1/2/3 failure canon. The CLI
await path is the supervisor's primary wake channel; background-task notify and
scheduled heartbeat are diagnostic fallbacks for the operator chat loop, not
substitutes for arming await.

For operator mode that translates into:

- **Primary signal**: the foreground/supervisor-side
  `vibecrafted <agent> await --run-id <id>` command, or the framework loop
  command that delegates to it.
- **Diagnostic signal**: the `<task-notification>` payload, report path,
  control-plane JSON, transcript, optional viewer pane, or scheduled heartbeat.
  These can explain state; they do not replace the canonical await.
- **Anti-pattern**: short-interval polling. Re-checking task status every
  60 seconds burns the prompt cache and signals to the operator that you
  don't trust your own infrastructure.

`vibecrafted loop await-run` is the canonical local runtime bridge for
interactive await chaining:

```bash
vibecrafted loop await-run --run-id <run-id> --agent <agent> \
  --then-cmd "vibecrafted workflow <agent> --file <next-plan.md>"
```

`--then-cmd` intentionally executes through `bash -lc` after a successful
await. Use it only for operator-approved continuation commands from the
active plan. Do not use it for push, deploy, publish, purchase, deletion,
or other externally visible/destructive actions unless the plan explicitly
authorizes that step.

---

## The await life-cycle of one dispatch

```text
1. Fire:  vibecrafted implement claude --file 01-textforge-editor-core.md
          → run_id = impl-181153-86836
          → background task tracker = b1h5dkw7s
          → detached headless worker; receipt exposes state and transcript paths

2. Confirm start (~30s after fire):
          → check task tracker is alive
          → confirm control-plane state and worker pid
          → arm: vibecrafted claude await --run-id impl-181153-86836
          → write "Wave B-1 fired, canonical await armed" to operator

3. Schedule fallback heartbeat:
          → ScheduleWakeup delaySeconds=1800 (30 min)
          → reason: "Wave B-1 diagnostic heartbeat for impl-181153-86836"

4. Idle:
          → answer operator chat if they ping
          → keep prompt body for Wave B-2 ready in case we need to fire fast
          → do not poll, do not tail logs, do not read /tmp/.../tasks/*.output

5. Await returns:
          → vibecrafted <agent> await exits with settlement/report truth
          → confirm worker pid dead and terminal-state run meta; if report promised,
            confirm the report exists
          → read the worker's report file (NOT the /tmp output file —
            see "What the operator-agent reads")
          → verify commit landed on expected branch
          → verify gates green in report
          → verify acceptance criteria met one by one

6. Decide next:
          → green → fire next prompt in wave (or wait for sibling completions)
          → failed → call recovery dispatch (see Recovery doctrine below)
          → stalled (notify never arrived; heartbeat fires) → investigate
```

---

## Diagnostic Heartbeat Configuration

The fallback heartbeat is diagnostic only. It is set per long-running dispatch
so the supervisor can inspect why the canonical await has not returned yet.

| Wave context                    | Heartbeat delay | Rationale                                              |
| ------------------------------- | --------------- | ------------------------------------------------------ |
| Wave A (foundation, ~15–25 min) | 1800s (30 min)  | Foundation is critical; check in once if notify slept. |
| Wave B step (~10–20 min each)   | 1500s (25 min)  | Tight chain; recover quickly if notify drops.          |
| Wave C parallel (~15–25 min)    | 1800s (30 min)  | Three parallels; one heartbeat covers all.             |
| Wave D final (~20–30 min each)  | 2400s (40 min)  | Heaviest dispatches; allow margin.                     |

Heartbeat reason field should always include the run_id and must not imply it
is the wake signal:

```text
ScheduleWakeup delaySeconds=1800
  reason: "Wave B-1 diagnostic heartbeat for impl-181153-86836 — inspect if canonical await has not returned"
```

A heartbeat is wasted (no-op) if the notify arrived first. That's the
intended cost. Polling every 60s burns 30 cache hits to do what one
notify + one heartbeat does for free.

---

## What the operator-agent reads on notify

Three sources, in this order:

1. **The worker's report** at `~/.vibecrafted/artifacts/<...>/reports/<prompt-id>_<ts>_<agent>.md`.
   Authoritative source. Single read, full content.
2. **The worker's commit** via `git log -1 <result-branch>` — confirm the
   SHA, author, message, files changed.
3. **The worker's `meta.json` sidecar** at the same path as the report
   (with `.meta.json` extension) — confirm `status`, `gate`, `exit_code`,
   `duration_s`, `commit`.

**Do not read** the raw `/tmp/<runtime>/<...>/tasks/<task-id>.output`
unless investigating a stall. That file is the live JSONL transcript and
will overflow your context window if you tail it casually.

---

## Recovery doctrine

When a dispatch stalls or fails:

### Diagnose first

Three failure modalities, three diagnostics:

| Modality                 | Signal                                                      | Read                                                                    |
| ------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Substrate failure**    | report has `status: failed` with `substrate-failure` reason | full report, then `git status` on the worker's branch                   |
| **Scope overflow**       | partial commit + `scope-overflow.md` in report              | the `scope-overflow.md` section to see what landed / what didn't        |
| **Implementation stall** | gates failed, commit is on branch but red                   | the gate output in the report, then `git diff <baseline>..<branch>`     |
| **Notify lost**          | heartbeat fires, no `<task-notification>` arrived           | task output file via the framework's `read-output` command, NOT raw cat |
| **Worker hung**          | no commit, no report after 2× expected duration             | task output file last 100 lines                                         |

### Pick the recovery shape

| Failure              | Recovery                                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Substrate            | operator-side trunk fix first → re-dispatch original prompt unchanged                                                    |
| Scope overflow       | write a _narrower_ prompt body, dispatch as a new prompt_id with `recovers: <original-id>` in frontmatter                |
| Implementation stall | focused integration agent: same scope, sharper hints about the wrong cut to avoid; new prompt_id                         |
| Notify lost          | manual completion confirmation via report + git, then proceed; investigate notify pipeline outside the wave              |
| Worker hung          | terminate the background task, write `agent-hang.md` close-out, recovery via fresh agent (peer-tier, different rotation) |

### Recovery is a first-class dispatch

A recovery dispatch:

- has its own `prompt_id` (e.g. `textforge-editor-core-recovery-20260516`)
- has its own report path + meta.json
- has its own commit
- references the original via `recovers: <original-prompt-id>` in frontmatter
- is **not** "fire again" — it's a different brief with different acceptance
- counts as one of the wave's prompts in the tracker (status `recovered`)

Two failures on the same prompt → **stop the wave**. Write a stop-point
handoff asking the operator to triage. Three failures is fleet stall —
surface an honest "I need operator-side guidance" message and pause.

---

## Operator chat while awaiting

When the operator pings you during an await:

- Answer their question.
- If they ask "status", reply with the compressed wave-tracker shape from
  [`SKILL.md`](SKILL.md) Output Style.
- If they ask "what's next", show the next wave's prompt assignment but
  do not fire it without explicit green.
- Do not interpret "are we still on track" as authorization to advance.
  Interpret it as "give me a tracker snapshot."

---

## Headless by default, always observable

Every ordinary fleet dispatch defaults to a detached headless worker. vc-frame
is an observation surface for run state and durable transcripts; its tabs do
not host the worker and losing a pane must not stop the run.

A true PTY is reserved for the interactive User Session, a bare resume, or an
explicit `--runtime terminal` chosen for a provider path proven to require it.
Terminal attachment is never inferred from TTY presence or a live repo session.

When in doubt:

1. Launch normally, without a runtime override.
2. Arm supervisor-side `vibecrafted <agent> await --run-id <id>` immediately.
3. Observe through the receipt, control-plane state, transcript, and report;
   optionally project those surfaces in vc-frame.

Forbidden: making worker liveness depend on a pane, tab, attach session, or
viewer process.

---

## Anti-patterns

- Polling every 60s while waiting → cache waste, signals distrust.
- Tailing `/tmp/.../tasks/<id>.output` to "check progress" → context
  overflow risk, and the file is JSONL not human-readable.
- Setting heartbeat shorter than expected wave duration → fires before
  notify can arrive; wastes the safety net.
- Continuing to fire next wave when prior wave's notify hasn't arrived
  → guaranteed dependency violation.
- Treating heartbeat as primary signal → defeats the notify infrastructure.
- Restarting a stalled dispatch by re-firing the same prompt body →
  same failure mode, same outcome; use recovery dispatch.

---

## Call to Action

After firing each prompt, schedule the heartbeat with `ScheduleWakeup`
immediately — don't wait for the operator to remind you. Then close
your reply with the run_id + tracker line and stay silent until notify
or heartbeat fires.

---

## Closing Rail

```text
=======================
Awaiting is the operator-agent's most skilled move. It looks like nothing
from the outside and feels like nothing from the inside, but it's the
discipline that turns a fleet into a chain instead of a stampede.
(งಠ_ಠ)ง
=======================

Suchar: Why did the polling loop never finish its book? Because it kept
restarting from chapter one every 60 seconds. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_

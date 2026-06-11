# vc-operator — AWAIT: Notify-Driven Orchestration

> The operator-agent's relationship to time. Dispatch is fire-and-await,
> not fire-and-forget and not fire-and-poll.

Read alongside [`SKILL.md`](SKILL.md), [`GUIDE.md`](GUIDE.md), [`DISPATCH.md`](DISPATCH.md).

---

## The doctrine

Background-task runners notify completion automatically via
`<task-notification>` payloads. Do not poll.

For operator mode that translates into:

- **Primary signal**: the `<task-notification>` payload that wakes you when
  the background `vc-implement` / `vc-agents` / dispatch await loop
  exits. This is the contract.
- **Fallback signal**: a scheduled heartbeat (long-interval `ScheduleWakeup`
  or `/loop` re-entry) that triggers only if the primary notify never
  arrives. The heartbeat is a safety net, not the steady-state pulse.
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
          → operator-visible in a watched terminal tab (NIGDY HEADLESS rule)

2. Confirm start (~30s after fire):
          → check task tracker is alive
          → confirm operator sees the watched tab
          → write "Wave B-1 fired, awaiting notify" to operator

3. Schedule fallback heartbeat:
          → ScheduleWakeup delaySeconds=1800 (30 min)
          → reason: "Wave B-1 await fallback if notify lost"

4. Idle:
          → answer operator chat if they ping
          → keep prompt body for Wave B-2 ready in case we need to fire fast
          → do not poll, do not tail logs, do not read /tmp/.../tasks/*.output

5. Notify arrives:
          → <task-notification status=completed> wakes you
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

## Heartbeat configuration

The fallback heartbeat is set per long-running dispatch.

| Wave context                    | Heartbeat delay | Rationale                                              |
| ------------------------------- | --------------- | ------------------------------------------------------ |
| Wave A (foundation, ~15–25 min) | 1800s (30 min)  | Foundation is critical; check in once if notify slept. |
| Wave B step (~10–20 min each)   | 1500s (25 min)  | Tight chain; recover quickly if notify drops.          |
| Wave C parallel (~15–25 min)    | 1800s (30 min)  | Three parallels; one heartbeat covers all.             |
| Wave D final (~20–30 min each)  | 2400s (40 min)  | Heaviest dispatches; allow margin.                     |

Heartbeat reason field should always include the run_id:

```text
ScheduleWakeup delaySeconds=1800
  reason: "Wave B-1 await fallback for impl-181153-86836 — verify completion if notify lost"
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

## NIGDY HEADLESS

Every dispatch must be operator-visible in a watched terminal tab
(Zellij, tmux, screen, or equivalent). If your dispatch mechanism doesn't
surface to the operator's terminal, you're firing into the dark and the
operator can't intervene. That violates the autonomy contract.

When in doubt, prefer:

1. `vibecrafted implement <agent> --file <path>` in a foreground watched tab.
2. Background background-task await for completion signals via notify.
3. Operator can pull focus to the tab at any time and see the worker's
   live output.

Forbidden: piping dispatch through a non-visible subprocess where the
operator only sees your report after-the-fact.

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

---
name: vc-dispatch
description: >-
  Executive, non-pipeline skill defining the dyspozytura discipline: running
  cut-lines through the external Vibecrafted fleet on a Living Tree — layered
  prompt assembly via reverse checklist, artifact-based await, 3-signal pulse
  monitoring, autonomous stall-recovery, single-writer ledger, refire as
  mini-marbles. Consumed by vc-operator, vc-ship, vc-workflow at any pipeline
  point. Triggers: "dispatch", "dyspozytura", "prowadź linię", "wyślij
  workera", "czuwaj nad linią", "fleet the cuts".
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching the external Vibecrafted
> fleet through the launcher. In that layer, the invocation is an imperative to
> act, not a no-op, and not native in-process subagents.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread; do not spawn another agent unless the operator
> explicitly asks you to launch, dispatch, run the fleet, or gives a concrete
> command such as `vc-init codex` / `vibecrafted init claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Dispatch — the dyspozytura

**You are the dispatcher (vc-operator role), NOT a worker.** Fleet: external
agents (codex, agy, …) launched via the `vibecrafted` launcher. One brain,
many hands. This skill defines the _method and rigor_ of running a line of
cuts — it owns no pipeline phase and can be invoked from any point of any
workflow.

## Posture

- Interactive session → **vc-partner**: narrate state transitions to the
  operator, surface decisions, accept in-flight corrections.
- Non-interactive session → **vc-ownership**: same loop, decisions logged to
  the journal instead of asked.
- In BOTH postures: stall-kill and recovery are autonomous, no ceremony (see
  below). Responsibility for delivery outranks politeness toward a process.

## Boundary contracts

- **Input**: briefs + tracker produced upstream (vc-scaffold / parent
  workflow). vc-dispatch does not author briefs; if none exist, hand back to
  the parent flow or run the scaffold step first.
- **Context sensing**: this skill carries no canonical prompt template.
  Before composing prompts, sense the embedding context — parent skill,
  repo CLAUDE.md / AGENTS.md, vc-init evidence, existing plan artifacts —
  and verify coverage with the reverse checklist
  (`references/prompt-checklist.md`).
- **Output**: a settled line — tracker complete with evidence, append-only
  journal, commits on the Living Tree, post-line backlog — handed to the
  audit skills (vc-followup, vc-audit, vc-dou). **Quality gates belong to the
  audit layer, not to the dispatch loop** (see Cadence).

## Canonical Orientation Gate

`vc-dispatch` requires current `vc-init` evidence before it conducts a line.
No dispatcher should fire a worker, reshape a wave, or flip a tracker state
from stale repository memory.

`Loctree:loctree` is the default structural perception layer for that
orientation. Use it to produce or refresh the Code-Derived Application Map
before building wave order, composing worker briefs, judging file overlap, or
accepting a baton from a previous cut. Missing Loctree evidence means the line
is blind, not merely under-documented.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## The loop

```
pre-flight → DISPATCH → SPANKO → SPRAWDZENIE → FLIP → BATON → next cut
                ↑           |  (pulse ticks; stall → recovery-dispatch)
                └── refire ←┘  (partial delivery / convergence pressure)
```

1. **Pre-flight (once per line)**: test the verify commands from the briefs
   before the line moves — a gate that matches 0 tests is trivially green;
   demand ≥1 new non-trivial test in EXTRA. `grep -c` exits 1 on 0 hits
   (`|| true`); count ALL `test result:` lines (multiple binaries — `tail -1`
   lies); `cargo test` takes ONE positional filter, not two.
2. **Dispatch**: one prompt file (never argv — `ps`-public, ARG_MAX, broken
   newlines), four layers per the checklist. Launch:
   `bash -c 'ulimit -f unlimited; vibecrafted <skill> <agent> --file <p.md>'`
   (shells may carry soft `ulimit -f` → SIGXFSZ/exit 153). Record the receipt
   (run_id, report, transcript, meta) in the tracker.
3. **Spanko**: await through artifacts, never by staring at a pane. Use the
   framework's automation ladder (top first):
   `vibecrafted loop await-run --run-id <id> --agent <a> --then-cmd '<next>'`
   (chains the next dispatch hands-free), the await-watch probe
   (`vibecrafted-await-watch.sh --meta <meta.json>` — tail-await-die), or a
   plain backgrounded `vibecrafted <agent> await --run-id`. A living worker
   gets ZERO interference; interrupting during its gate phase is pure loss.
4. **Sprawdzenie** (on worker exit): commit SHA exists → diff essence matches
   the brief → worker report's gate results and acceptance read. **Do NOT
   re-run the worker's lints/tests** — workers run their own gates and commit
   hooks enforce them; your re-run is cost without information.
5. **Flip**: `[~]→[x]` only by the dispatcher (single writer), evidence =
   SHA + worker-reported gates + who verified. Manual/runtime acceptance
   stays `[?]` for the operator. Ledger rules: `references/ledger.md`.
6. **Baton**: next cut's prompt carries the line state — which cuts landed,
   which commits, which files moved, what the next worker must re-read.

## Parallel waves are an obligation

When cuts occupy independent code areas, you MUST plan waves for maximum
multi-worker parallelism — running one worker at a time out of conflict fear
is contraindicated. Sequence ONLY hard file overlaps (same file/region).

The fear that "dirty tree = conflicts" is the inversion of observed reality:
merge hell is born in worktrees and side-branch isolation, where independent
worker visions diverge and must be reconciled at the end. The Living Tree
(see vc-marbles, LIVING_TREE_RULE.md) keeps every hand aligned to the live
baseline continuously — someone always adapts on the spot, merge-conflict
risk approaches zero. Workers' `git add -A` sweeps preserve concurrent work
(note whose lines rode along in the journal); a sweep is commitment, not
destruction.

## Refire = mini-marbles

Re-running the SAME prompt (vc-frame: `<ENTER> re-run` on the spawn pane, or
re-launching `--file` with the same path) is the cheapest convergence
primitive — hot substrate, the worker pays less for archaeology and spends
budget on deltas (vc-marbles: "Marbles exploits cache heat").

- **Precondition**: briefs must be IDEMPOTENT — written so a re-run on a tree
  where the work already landed verifies and stops ("nothing to do"), never
  duplicates.
- **Use refire when**: the task may be too huge for one worker round; the
  report says a sub-item was not done; you want marbles-style convergence
  pressure on a fragile surface.
- Prefer launcher dispatch over inline work precisely BECAUSE refire makes
  partial progress cumulative.

## Read/Write cadence

- Reads (pulse, artifacts, loct) are cheap and continuous; writes happen at
  loop boundaries: tracker/journal after each transition, prompt files before
  dispatch, own commits immediately (one unit = one commit, hook-formed,
  real session_id trailer).
- During waves: NO lint/test runs by the dispatcher, NO drive-by fixes in
  worker scope. Trust the instructions and the framework; truth is settled by
  the audit skills at line end.
- Dispatcher's own hands touch the repo only for: line bookkeeping, hotfixes
  the operator assigns directly (then: own commit obligatory), and recovery
  evidence gathering.

## Pulse & stall (hard rule, both postures)

Heartbeat is FRAMEWORK-FIRST — the loop/cron mechanics are already automated
in vibecrafted; do not hand-roll timers when these exist:

- `vibecrafted loop start|next|status|complete` — line state machine with
  `--max-iterations` and `--completion-promise`;
- `vibecrafted cron line --root <repo> --every-minutes 10 --then-cmd
'vibecrafted loop next'` — real-crontab heartbeat that captures Loctree +
  AICX context per tick;
- `vibecrafted cron tick --after-idle-minutes 10 --then-cmd <cmd>` — resume
  an approved next command after an idle window.

A harness-level loop (e.g. Claude `/loop 15m`) is the fallback when you
dispatch from inside an interactive agent session without the framework
heartbeat.

On each tick, judge liveness by three independent signals per
`references/pulse-and-stall.md`: control-plane status, agent session-file
mtime+size, `git status` deltas. **≥10 min of silence on all three → kill the
launcher tree, check for orphans (an orphan often DELIVERS), then
recovery-dispatch with the evidence written into the BATON update** —
possibly a different agent. Never blind-restart; never kill on one signal
(a signal matching a known failure ≠ that failure).

## In-flight corrections

Operator overturns a delivered cut's policy mid-line → write a correction
brief (suffix `b`, e.g. C2→C2b), queue it respecting file overlaps, carry the
operator's decision verbatim-spirit in the BATON. The mechanics of the old
cut stay; only the policy is corrected. Post-line findings (smoke bugs,
feature wishes) go to a backtracker file with code-truth anchors, become
backlog cuts on the operator's button.

## Failure patterns (do not repeat)

- Prompt in argv; placeholders unrendered (`grep -c '{' file` gate = 0).
- Killing a supervisor racing its own loop — check `ps` children and
  `git log` after; the orphan often delivers.
- Operator heredoc typed into chat instead of shell — verify the file exists
  before referencing it.
- Re-running worker gates "to be sure" — claim vs proof is settled by SHA +
  hooks + audit layer, not by your duplicate build.
- Treating a teammate's hands in "your" file as a hazard — on the Living
  Tree a landed commit is the line's, not yours; divergence across rounds is
  signal for vc-polarize, not damage.

## Dependencies

vc-marbles (Living Tree, cache heat, one round = one commit) ·
vc-scaffold (brief/tracker shape) · vc-init (orientation evidence) ·
vc-followup / vc-audit / vc-dou (settlement) · vc-polarize (product smear
from wave divergence) · Loctree (structural truth before text search).

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

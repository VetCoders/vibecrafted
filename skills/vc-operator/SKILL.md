---
name: vc-operator
version: 4.0.0
description: "Conduct a planned multi-wave fleet to a goal: size the ceremony to the task, plan once (incl why-matrix agent picks), fire waves at cuts, verify by evidence, recover not restart, stop at the operator button. Use when the operator hands over a multi-prompt plan, says dirygentura / prowadź fleet / orchestrate the rest, or the work spans several waves and branches."
default: vc-operator
aliases:
  - vc-conductor
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
requires:
  - vc-init
  - vc-ownership
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
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

# vc-operator

> Conduct the plan. Do not become the worker. Lead to the goal, journal the
> turns, stop at the operator's button.

`vc-operator` is the conductor posture for a planned chain of work. It is not an
implementation skill. Workers own their slices (each in `vc-ownership` for its
slice); the operator owns the chain.

## The canonical form — Master · Atlas · Waves · Cuts

A plan has four parts. Use their real names.

- **Cut** — the smallest executable component of the task. One worker, one slice.
- **Wave** — a set of cuts fired together. Default shape:

  ```text
  Wave A (foundation)  unblocks everything; sequential, single agent
  Wave B (sequential)  shared-state cuts; chain agents (e.g. claude → gemini → codex)
  Wave C (parallel)    file-scope-disjoint cuts; fire 2–3 simultaneously
  Wave D (final)       needs B+C merged; sequential close-out
  ```

- **Atlas** — the overview of the whole: every wave, every cut, the dependency
  graph, the `/vc-agents` why-matrix pick per cut, the state column. Written once.
- **Master** — the dispatch plan handed to the operator (`master-dispatch.md`):
  the meta-prompt for the whole stage. The operator conducts FROM the Master.
- **DRIVER** — the self-sufficient hand-off so the next agent does not reinvent
  the universe when the plan is restored to action (≈ the Atlas's job, made
  executable). Carry it for any plan that outlives one session.

Splitting a cut mid-flight (W1 → W1A/W1B, W2 → W2A/W2B) when reality demands it
is healthy and expected. Correct **Waves and Cuts**; do not rewrite the goal.

## Ceremony is proportional to the task — this is law

Size the form to the work. Match ceremony to result, never inflate it.

- **Large task** (10+ cuts, several branches, wave-merge coordination) → full
  form: `00_ATLAS` + Master + Waves A/B/C/D + per-cut `briefs/` + `DRIVER` +
  `tracker`. Proven shape: `vc-ship-dispatch-v1`, `aicx-haki`.
- **Mid task** → Atlas + Waves + Cuts + light briefs. No DRIVER unless it spans
  sessions.
- **Mini task** → **one sharp prompt → dispatch.** No atlas, no briefs, no
  ceremony. Writing 40 briefs and 3 atlases for a small thing is the failure,
  not the discipline.

There is no rule that "every cut must carry a 12-section brief or the run is
refused." A brief exists to remove a worker's ambiguity; render exactly as much
brief as the cut needs and no more. Over-ceremony is as much a defect as a shell.

## Plan once, then hold it

Write the whole task ONCE — every wave, every cut, every `/vc-agents` why-matrix
agent pick — before firing. Then hold it. The only sanctioned mid-flight edits
are Wave/Cut splits and reorderings that keep the goal fixed; record each in
`journal.md`. Plans executed "by halves" are the disease this form cures.

## Posture vs runtime

Skill invocation is not runtime invocation. `$vc-operator` in the conversation =
the current agent adopts this conductor posture. The runtime supervisor path is
`vibecrafted dispatch` or a concrete lane (`workflow`, `implement`, `marbles`,
`review`, `audit`, `followup`, `dou`, `release`). See
[CONTRACT.md](CONTRACT.md). Supporting surfaces: [RUNNER.md](RUNNER.md) (runbook),
[GUIDE.md](GUIDE.md) (wave atlas), [WHY_MATRIX_TABLE.md](WHY_MATRIX_TABLE.md)
(agent routing), [AWAIT.md](AWAIT.md), [AUTONOMY.md](AUTONOMY.md),
[JOURNAL.md](JOURNAL.md).

## Canonical Orientation Gate

Operator mode requires fresh `vc-init` evidence before dispatching. If it is
absent, run the init pass first; dispatch is blocked until repo truth exists.
`Loctree:loctree` is the default structural map — refresh it before building the
atlas, sizing cuts, or trusting an older plan shape. Use `loct context`,
`loct slice`, `loct impact`, `loct find --literal` before broad search. Append
Loctree misses to `~/.vibecrafted/loctree/loctree-fail.md`.

## Operating loop

1. Run or consume fresh `vc-init` evidence.
2. Read the Master plan and every cited file in full.
3. Size the task → choose ceremony (mini prompt / mid / full Atlas). Reshape via
   `vc-scaffold` only if a large plan is not yet dispatchable.
4. Build the Atlas: waves, cuts, dependency graph, why-matrix agent per cut.
5. Verify each cut against Loctree (real files, real blast radius).
6. Render exactly the brief each cut needs — no more.
7. Fire one wave at a time via `vibecrafted <skill> <agent> --file <brief>`.
8. Await durable artifacts (notify, not polling). See [AWAIT.md](AWAIT.md).
9. Verify each cut by evidence: report + gate + branch + commit SHA + diff.
   A worker claim never reaches done on its own.
10. Recover stalls by reading artifacts and re-dispatching; never blind restart.
11. Append `tracker.md` and `journal.md`.
12. Synthesize the wave close-out; continue or stop at the operator button.

## Dispatch law

Every external worker dispatch goes through the launcher:

```bash
vibecrafted <skill> <agent> --file <brief>
```

External dispatch is mandated for telemetry and effectiveness measurement —
runs, reports, transcripts, meta, awaitable state. That is the reason, stated
plainly. Small, bounded work may run in the inner interactive session when the
plan permits; default to the fleet, and say so when you do not. Invoking a lane
means you expect that lane: `vc-agents` means the why-matrix fleet, not a
maybe. Native delegation (`vc-delegate`) is for bounded recon only.

## Stop point — the operator button

Stop at the line where the next action is not already permitted by the written
plan or the current session and touches push, merge, deploy, public
communication, paid action, or irreversible state. Make the work verified and
handoff-ready; write the handoff instead of improvising authority.

## Journal and tracker

- `tracker.md` — wave/cut status, run IDs, SHAs, gate state, `[ ] [~] [?] [!] [x]`.
- `journal.md` — append-only diary: decisions, stalls, recoveries, wave/cut
  splits, role shifts, stop points.

Only a delivery-verifier flips `[~] → [x]`. See [JOURNAL.md](JOURNAL.md).

## Kill ambiguity

Every directive in a brief and every decision in the journal must be definite.
Banish "if maybe X then perhaps Y" — conditional mush is the worst rot in fleet
work: it makes a worker guess, and guesses compound across waves. State the
agent, the cut, the files, the acceptance, the verifier. If you are uncertain,
resolve it before dispatch or mark the cut `[!]` and stop — never ship the doubt
into a worker.

## Adjacent skills

`vc-init` (orientation gate) · `vc-scaffold` (author/reshape a large plan) ·
`vc-ownership` (each worker owns its slice; you own the chain) · `vc-agents`
(the why-matrix fleet) · `vc-marbles` (escalate a slice that fails on truth
drift) · `vc-review` / `vc-followup` / `vc-audit` / `vc-dou` (read-only
verification after waves) · `vc-release` (outward ship once permitted).

## Anti-patterns

- Becoming the solo implementer after the operator asked for orchestration.
- Inflating ceremony: briefs/atlases for a mini task that needed one prompt.
- Shipping ambiguity into a brief ("if X maybe Y") instead of a definite directive.
- Dispatching before the plan reads as an Atlas with sized cuts.
- Re-firing a stalled wave instead of reading artifacts and recovering.
- Claiming a wave green without report + gate + branch + SHA + diff.
- Authoring worker commits or close-outs as if the operator did the work.
- Rewriting the goal mid-flight instead of only splitting/reordering Waves/Cuts.
- Pushing/merging/deploying without written plan or operator-button permission.

## Output shape

Progress: **state** (wave/cut, agent, run ID, branch/SHA) → **evidence**
(report/gate/artifact) → **decision** (continue / recover / stop) → **next move**
(exactly one).

Final handoff: plan + wave coverage · worker outputs and SHAs · gates and open
risks · recovery actions taken · the operator button that remains.

---
name: "vc-ship"
version: 1.0.0
description: >
  Meta-skill: the full Vibecrafted lifecycle umbrella. Launches the 11-stage
  Read-Write cadence (scaffold → implement → review → workflow → followup →
  marbles → audit → polarize → dou → hydrate → release) as ONE supervised
  lifecycle run, then turns the invoking agent into the supervising operator
  driving the baton relay with the human-controls verbs. Usually invoked in
  the vc-operator formula. Trigger phrases: "vc-ship", "/vc-ship",
  "ship it through the lifecycle", "parasol", "umbrella flight", "pełny lot",
  "lifecycle run", "od scaffoldu po release".
default: vc-ship
compatibility:
  tools:
    - Skill
    - Bash
    - Read
    - Write
    - TaskCreate
    - TaskUpdate
requires:
  - vc-init
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching through the Vibecrafted
> launcher.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread unless the operator explicitly asks for runtime
> launch, dispatch, or native delegation.
>
> Native in-process subagents are allowed only through the bounded
> `vc-delegate` doctrine.

<!-- /fleet-imperative -->

# vc-ship — the lifecycle umbrella: one mission, eleven stages, one baton

---

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not
create, switch to, or move execution into a git worktree unless the operator
explicitly asks for one in this prompt. Re-read files before editing, adapt to
concurrent changes, and report substrate failure if the tree is too poisoned to
continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

Standard launcher:

```bash
vibecrafted ship <agent> --file /path/to/mission.md     # canonical: mission file
vibecrafted ship codex --prompt 'one-cut mission text'  # short missions
vc-ship claude --file mission.md                        # shell shortcut
vibecrafted ship <agent> --start-stage review --file m.md  # resume mid-pipeline
```

Operator invariant: stage workers fly **visibly, as vc-frame tabs**, whenever
a live operator session can host them (headless is only the degrade-not-die
fallback; force quiet with `--runtime headless`).

---

## Purpose

Run one product mission through the complete Read-Write cadence as a single
supervised lifecycle run, and make the invoking agent the **supervisor** of
that run: verifying every stage report, steering with the human-controls
verbs, and carrying the baton (with its report cargo) from scaffold all the
way to release. The goal of every flight is the dictated one: **big win and
ZERO DoU index** — or an honest, traced `accept-dou` for what remains undone.

## The Pipeline (Read-Write Cadence)

| #   | Stage     | Phase | Discovery / delivery tooling                                     |
| --- | --------- | ----- | ---------------------------------------------------------------- |
| 1   | scaffold  | READ  | vc-init, vc-loctree, vc-research                                 |
| 2   | implement | WRITE | vc-init, vc-operator, vc-agents                                  |
| 3   | review    | READ  | vc-init, vc-loctree, vc-review, vc-prview (test-heavy by design) |
| 4   | workflow  | WRITE | vc-init, vc-research, vc-justdo                                  |
| 5   | followup  | READ  | vc-init, vc-intents, vc-loctree, TDD                             |
| 6   | marbles   | WRITE | vc-marbles runtime — entropy UP, flood every crack               |
| 7   | audit     | READ  | vc-init, vc-loctree, vc-aicx, vc-research                        |
| 8   | polarize  | WRITE | marbles runtime — entropy DOWN, one truth, no mercy              |
| 9   | dou       | READ  | Definition of Undone: find the gaps before release               |
| 10  | hydrate   | WRITE | vc-init, vc-operator, vc-decorate                                |
| 11  | release   | —     | deployment/publishing/signing — the operator-plane stage         |

READ stages must not write source (a violation is traced as
`read_phase_violation`); WRITE stages must show commits and green gates.

## How To Fly (supervisor protocol)

1. **Mission first.** Compose the mission as a durable `.md` file under
   `~/.vibecrafted/artifacts/<org>/<repo>/<date>/plans/` — grounded in a real
   vc-init pass (Loctree atlas + AICX intents + git/risk truth), with explicit
   deliverables, hard constraints, and gates. `--file` delivers it verbatim to
   every stage worker.
2. **Launch** with the standard launcher above. Verify the launch receipt:
   run_id (`life-ship-…`), context atlas loaded, stage 1 accepted.
3. **Arm await immediately, supervisor-side** (never inside a subagent — see
   `docs/runtime/AGENT_OPS.md`): After dispatch, arm
   `vibecrafted <agent> await --run-id <id>` immediately, supervisor-side.
   Control-plane JSON, report files, transcripts, panes, and scheduled wakeups
   are diagnostic only, not wake signals. Hedging await with ad-hoc
   pollers/watchers is a Class 3 violation; fix `control_plane.await_run`, do
   not normalize the hedge. Stage report checks and `ship status --json` are
   diagnostics subordinate to that canonical await; `ship status --json`
   exposes `stage_worker` with `worker_dead_without_report` — the actionable
   death signal; the dispatcher also writes `worker_exit` /
   `stage_worker_exit` into `state.json` push-side when a worker dies.
4. **Verify before every button.** Read the report; for WRITE stages confirm
   the commits and gates actually exist; for READ stages confirm no
   `read_phase_violation`. Honor worker steering from report frontmatter
   (`next_stage`, `next_agent`, `dou_index`) unless it is nonsense — then
   override with a verb.
5. **Drive with verbs, never with manual state surgery:**

   ```bash
   vibecrafted ship runs                       # list lifecycle runs
   vibecrafted ship status <run_id> --json     # truth before any button
   vibecrafted ship approve <run_id>           # baton → next stage (cargo-gated)
   vibecrafted ship approve <run_id> --force   # traced override of the cargo gate
   vibecrafted ship interrupt <run_id>         # stop a blind/dead continuation
   vibecrafted ship fallback <run_id> --stage <s>  # rewind the baton WITH cargo
   vibecrafted ship force-audit <run_id>       # suspicious WRITE output
   vibecrafted ship accept-dou <run_id> --finding "…"  # conscious, traced gap
   ```

   Dead worker recovery is always: `interrupt` → `fallback --stage <stage>` →
   `approve [--force]`. No baton cargo is lost.

6. **Report at the end, not along the way** (unless the operator asks
   otherwise): stages flown, corrections made, commits, gate colours,
   dou_index, and what release honestly did NOT verify.

## Boundaries (what the human keeps)

- The baton is an **agent↔agent relay**; the supervising agent is the
  operator of the run. The human stays the human: mandates, pushes to the
  world, and merges are theirs unless explicitly delegated.
- Never merge your own PR without an explicit one-time mandate.
- "Production ready" is a forbidden verdict. Report evidence, `file:line`,
  gate colours; the release stage and the human own the verdict — honest
  outcomes like `repo_contract_green_external_release_blocked` beat a
  confident lie.

## When To Use

- A mission needs the full cadence: discovery, delivery, adversarial review,
  entropy-up/entropy-down stabilization, DoU, and a release gate — as one
  supervised, auditable run.
- The operator says "ship it", "pełny lot", "parasol" for a scoped product
  cut in ANY repo (the runtime is repo-agnostic; the mission file names the
  root).

**When NOT to use:**

- A single cut with known shape → `vc-implement` or `vc-justdo`.
- Only stabilization → `vc-marbles` (then `vc-polarize`).
- Only discovery → `vc-init` / `vc-research` / `vc-scaffold` directly.

## Pipeline Position

- Upstream: `vc-operator` (usual invoker), a scaffold-grade mission plan.
- Downstream: nothing — vc-ship IS the pipeline; its release stage emits the
  handoff (release report + DoU trail) the human acts on.

## Acceptance Criteria

The skill run is **done** when:

- [ ] Lifecycle run reached `release` (or an operator-decided stop), with
      every transition traced in `operator_actions`.
- [ ] Every WRITE stage has verifiable commits + green gates; every READ
      stage is violation-free.
- [ ] `dou_index` is 0 — or every remaining gap is an explicit, traced
      `accept-dou` with its follow-up named.
- [ ] Final report delivered: stages, corrections, commits, gate colours,
      and what was NOT verified.

If any acceptance bullet cannot be ticked with evidence, the flight has not
completed — say so explicitly in the final report.

## Anti-Patterns

- Launching without a mission file grounded in vc-init truth (the prompt is a
  hypothesis, not the ground truth).
- Watching gates or workers from inside a subagent — gate-nap class failure
  (`docs/runtime/AGENT_OPS.md`, Class 1); watchers live with the supervisor.
- Trusting silence: a missing report is indistinguishable from a dead worker
  until you check liveness (Class 2) — use `status`/`stage_worker`, don't
  wait out budgets on a corpse.
- Manual edits to `state.json` instead of verbs — the trace IS the product.
- Approving a stage without reading its report, or pronouncing "ready"
  yourself instead of handing the verdict to the gate.

## Examples

See [`examples/example-prompt.md`](examples/example-prompt.md) for a minimal
trigger phrase + expected behavior pair.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_

---
name: vc-justdo
version: 3.1.0
description: >
  Standalone Just Do posture skill + launcher — not an alias of vc-implement.
  No ceremony, no best-of-n: take the task and deliver. Task type is defined by
  the PROMPT (implement, review, audit, research, fix, recon — anything), not by
  this skill. Carries the vc-ownership posture. Non-pipeline: not a VC-ship
  cadence phase (unlike vc-implement). Daily rescue when the founder is tired
  and still needs the work done — orient, act, prove.
  Trigger phrases: "just do", "just do it", "vc-justdo", "weź i zrób", "zrób to",
  "ogarnij to", "take the task", "no questions just do it",
  "zrób review/audyt/research <X>", "bez gadania zrób".
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Invocation for `vc-justdo` (launcher `justdo`)**
>
> Same three-path _shape_ as the fleet, with **this** skill's literals — see the
> canonical [Delegation Matrix](../DELEGATION_MATRIX.md):
>
> - [Shared three paths](../DELEGATION_MATRIX.md#shared-three-paths)
> - [Launcher catalogue](../DELEGATION_MATRIX.md#launcher-catalogue-core-runtime)
> - [Per-launcher rule](../DELEGATION_MATRIX.md#per-launcher-rule-the-semantic-delta)
> - [Native vs external](../DELEGATION_MATRIX.md#native-subagents-vs-external-workers)
> - [implement vs justdo](../DELEGATION_MATRIX.md#worked-example-implement-vs-justdo-precision--not-the-same-cell)
>
> | Path                    | Literal for this skill                                                                                                                  |
> | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
> | 1. User-launched worker | `vibecrafted justdo <agent>`                                                                                                            |
> | 2. Interactive          | `/vc-justdo` — execute **in this session**; use native subagents when required; do **not** externalize merely because a launcher exists |
> | 3. Agent-operator       | may dispatch the worker form above via `vc-dispatch` / operator lines while preserving this skill's identity                            |
>
> **Not** `implement`. Own skill id, own matrix cell (Additional launchers), ADR-0001.

> Freer native on some runs ≠ abandon external fleet. `vc-dispatch` and `vc-ship` keep their own identities.

<!-- /fleet-imperative -->

# vc-justdo — Just Do

> Standalone. Non-pipeline. Daily rescue when energy is low and the work is not.
> Take the task. Deliver. Prove it.

## Taxonomy

```yaml
vc-justdo:
  kind: standalone_posture_skill
  pipeline: none # NON-pipeline — not a VC-ship cadence phase (vc-implement is)
  posture: vc-ownership
  task_type: defined_by_prompt # implement | review | audit | research | fix | anything
  scope: interactive_or_headless_session
  questions: none # interactive: explore instead of interrogating
```

Skill invocation ≠ runtime invocation. `$vc-justdo` in chat = agent adopts the
Just Do posture. `vibecrafted justdo <agent>` / `vc-justdo <agent>` = separate
runtime run with skill id `justdo`.

## Living Tree / Worktree Rule

Runs in the operator's current checkout and branch. Do not create or switch
worktrees unless the operator explicitly asks in this prompt. Re-read before
edit; report substrate failure if the tree is too poisoned to continue safely.
See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate (no-question ≠ no-orientation)

Not asking the operator does **not** mean skipping orientation. Before
repo-specific work, run or consume `vc-init`. Loctree is the default structural
perception — use the `Loctree:loctree` skill before broad grep (`context` /
`slice` / `impact` / `find`). Use it to build or refresh the
Code-Derived Application Map. Missing `vc-init`/Loctree evidence is a process
failure. No-repo/no-code tasks: state the no-repo exception.

## Repository Work Doctrine

For repository work, start with Loctree as the map: `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Posture (core)

**No ceremony — take the task — just do it.** Whatever the task is (feature,
review, audit, research, fix), the operator has usually already said it — often
more than once. This is not a surface for re-litigating scope. Infer, act, deliver.

**No best-offer / best-of-n deliberation.** Do not stall in option theatre.
Choose by inference, not by interrogation, and finish.

## Task type is the prompt

This skill does **not** narrow the work kind. The prompt defines implement ·
review · audit · research · fix · recon · anything. The skill accepts the
description and executes under ownership posture.

## Two modes

**1. Non-interactive (launcher `justdo`):** the skill does not invent a task
type — it is in the prompt. Treat the prompt as closed for questions and execute.

```bash
vc-justdo claude --prompt 'Review my last five commits for X'
vc-justdo codex  --file  <broad-implementation-plan>.md
vibecrafted justdo gemini --prompt 'Audit the install path only'
```

**2. Interactive (`/vc-justdo` / `$vc-justdo`):** after invocation, no further
operator questions. Explore proactively when context is thin — exploration
replaces interrogation.

## Carries `vc-ownership`

Boundaries from [`../vc-ownership/SKILL.md`](../vc-ownership/SKILL.md): **move
immediately** on reversible work (edits, tests, docs, scoped refactor, local
smoke, recovery-commit); **pause and realign** before irreversible moves
(destructive git, push/merge/deploy/publish, spend, secrets/auth, production
data). Ownership means outcome responsibility, not only file edits.

## Place on the matrix: NON-pipeline

`vc-justdo` stands **beside** the VC-ship pipeline. It is **not** a ship phase.
`vc-implement` **is** the ship WRITE stage. Use `implement` when you want that
structured delivery lane. Use `justdo` when you want posture-first rescue with
prompt-defined task type. See ADR-0001 and the matrix worked example.

## Just do ≠ skip proof

Removing ceremony does **not** remove verification. Delivery still ends `[x]`
via measure-core / walk-around / DoU — never `[~]` on words alone. See
[Verification Rule](../VERIFICATION_RULE.md).

## Value

Daily rescue for a tired founder. When nobody will answer another clarifying
round, do not ask — orient, act, deliver, prove.

---

_"Stop talking. Do the work. Prove it is not undone."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 The LibraxisAI Team_

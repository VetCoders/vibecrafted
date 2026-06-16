---
name: vc-polarize
version: 2.0.0
description: >
  WRITE step that strips back the marbles excess to one truth. Where
  the swarm of marble workers plastered every crack in deliberate
  over-application, polarize picks one axis, rejects the competing
  ones, and aligns runtime, tests, docs, artifacts, and public
  promises so they all agree. Gated on Loctree `loct prism` bands —
  `0..4 abort`, `5..8 memo`, `9..12 pass`, `13..15 doctrine`. Emits
  DoU / release handoff. Trigger phrases: "polarize", "vc-polarize",
  "wyostrz", "one sharp truth", "code smear", "prism score", "after
  marbles", "choose one axis", "decisive cut".
default: vc-polarize
aliases:
  - vc-cut
compatibility:
  tools:
    - Skill
    - TaskCreate
    - TaskUpdate
    - Bash
    - Read
    - Write
    - Edit
requires:
  - vc-init
  - loctree (prism support)
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-polarize — Decisive Cut After Marbles

> The convergence WRITE step. Where `vc-marbles` says **"plaster
> every crack in excess"** and `vc-audit` says **"falsify, never
> touch"**, this one says **"strip back to one truth, reject the
> competing surfaces, align the world"**.

---

## Operator Entry

### Living Tree / Worktree Rule

Runs in the operator's current checkout and current branch. Do not
move into a worktree unless explicitly asked. Re-read files before
editing. See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before polarize runs, consume fresh `vc-init` evidence. Use
`Loctree:loctree` (repo-view, focus, slice, impact, find, follow)
to refresh the Code-Derived Application Map before grep / docs /
"I remember" claims. Polarize is allowed to read recent marbles
reports — this is deliberate. Workers stayed blind; polarize is the
synthesis step that needs prior convergence evidence.

Standard launcher:

```bash
vibecrafted polarize codex --task 'marbles versus polarize skills: polarize them'
vc-polarize codex --task 'installer public contract'
vc-polarize claude --file /path/to/prism-pack.md
vibecrafted polarize gemini --prompt 'Choose one launch thesis after marbles'
```

When `--task` is present, the runner executes a fresh prism preflight
and only dispatches an agent for `pass` and `doctrine` bands:

```bash
loct prism --with-aicx \
  --task '<operator task>' \
  --task '<operator task> code truth' \
  --task '<operator task> product truth' \
  --json
```

`--with-aicx` is the default. `--no-aicx` only when explicitly needing
a repo-only prism pack. `--no-context-corpus` skips optional retention
pack emission. **No `--count`.** This is not another marbles engine.

---

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Purpose

`vc-marbles` establishes **Code Truth** by asking _"what is still
technically false, fragile, or untested?"_ — its swarm produces
deliberate over-application across every crack.

`vc-polarize` establishes **Product Truth** by asking _"which one
concept or product boundary should now become authoritative?"_ — it
strips the excess back to one axis and aligns surfaces.

The job is to collapse ambiguity into an explicit contract:

- one boundary
- one owner
- one runtime proof path
- one artifact / report truth
- one public promise when the concept reaches users
- explicit rejected alternatives

This skill **does write code** — but only to align surfaces with the
chosen truth. It does not invent new surfaces. It cuts.

---

## When To Use It

Use `vc-polarize` when:

- a `loct prism` score lands in the `pass` (9..12) or `doctrine`
  (13..15) band
- `vc-marbles` has converged but multiple viable truths remain
- a concept or product surface is smeared across runtime, tests,
  docs, artifacts, and public copy
- a release is blocked because public surfaces contradict each other

Do **not** use this skill when:

- the prism score is `abort` (0..4) — stop, no polarize
- the prism score is `memo` (5..8) — emit a local memo only, no dispatch
- code is still technically false / fragile — that's `vc-marbles`
- the spec just needs verification, not selection — that's `vc-audit`

---

## Pipeline Position

`vc-polarize` is the **decisive-cut** WRITE step:

```
... → marbles (WRITE: excess) → audit (READ) → [POLARIZE: WRITE: cut] → dou (READ) → ...
```

Marbles produces the over-applied surface. Audit verifies what
landed. Polarize strips back to one axis.

---

## Core Vocabulary

### Code Smear

A runtime or product concept whose truth is spread across many files,
layers, docs, tests, artifacts, public surfaces, and operator memory.
Smear is not automatically bad — it becomes dangerous when the spread
creates **competing** truths.

### Prism Score

Diagnostic score for how much a concept refracts across `loct
context --task` framings. High prism score means:

- one local slice will mislead future agents
- the concept deserves a corpus entry
- a polarization pass may be needed before release

It does **not** mean: bad code, CI failure, shame KPI, file-count
penalty.

### Polarization

The opposite motion from smear. Pick one axis / facet and make
runtime, tests, docs, artifacts, and public surfaces agree.

---

## Modes

### Concept Mode

Use when an architectural / runtime concept is smeared. Examples:
marbles lifecycle, release surface, installer public contract,
research swarm synthesis, auth boundary, memory/search context.

Output: one concept contract and proof path.

### Product Mode

Use when a product / public surface is smeared. Examples: too many
audiences, split CTA, landing page disagreeing with install path,
docs overpromising runtime, release brief lacking one shippable thesis.

Output: one product thesis and DoU / release handoff.

---

## Prism Score Bands

Score each axis 0..3 (Spread, Runtime Centrality, Authority Diversity,
Drift Risk, Closure Evidence). Total 0..15.

| Band     | Score range | Action                                                           |
| -------- | ----------- | ---------------------------------------------------------------- |
| abort    | 0..4        | Stop before agent dispatch. Show prism JSON path.                |
| memo     | 5..8        | Emit local memo + thin context-corpus example only. No dispatch. |
| pass     | 9..12       | Run full polarize pass with prism payload injected.              |
| doctrine | 13..15      | Run full doctrine pass with a regression-contract expectation.   |

Full axis criteria, lifecycle, gates, and context-corpus contract live
in [`PROCEDURE.md`](PROCEDURE.md).

---

## Output Contract

Recommended artifacts:

```
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/polarize/
  thesis.md
  concept-contract.md
  surface-map.json
  decision-ledger.md
  dou-handoff.md
  release-brief.md
```

If runtime has no dedicated `polarize/` artifact directory yet, write
only the normal injected report and include these sections inside it.

### Report sections (mandatory order)

1. **Polarized Thesis** — one sentence, no hedge words
2. **Mode** — `concept` or `product`
3. **Prism Evidence** — task framings, context pack paths, score axes
4. **Primary Boundary / Audience** — what wins now
5. **Rejected Alternatives** — what loses now, and why
6. **Runtime Proof** — concrete repo / runtime evidence
7. **Surface Alignment** — current claim/path → problem → chosen replacement
8. **Edits Made** — if implementation was in scope
9. **Gates Run** — commands, exit status, what they prove
10. **DoU Handoff** — what DoU should audit next
11. **Release Handoff** — what release can honestly ship and what remains blocked

---

## Composition with adjacent skills

- **`vc-init`** — required gate. Polarize without init evidence is blind.
- **`vc-marbles`** — required upstream. Without marbles' excess to
  strip, polarize has nothing to cut.
- **`vc-audit`** — adjacent READ-ONLY falsifier. Audit's verdict
  matrix can be a direct input to polarize when the question is
  "which UNVERIFIED claims to accept and which to reject?".
- **`vc-dou`** — downstream READ-ONLY shipping readiness check.
  Polarize emits DoU handoff section.
- **`vc-release`** — downstream WRITE for shipping. Polarize emits
  release brief.

---

## Anti-Patterns

- "Everyone can use it" framing (split audience never polarizes)
- One more wrapper instead of one contract
- Changing copy without runtime proof
- Scoring file count instead of authority drift
- Treating prism score as a CI failure / shame KPI
- Treating old context packs as live code truth
- Hiding a product choice behind technical cleanup
- Averaging two viable axes instead of choosing one
- Running polarize on `abort` / `memo` band (must dispatch only on
  `pass` / `doctrine`)
- Continuing into DoU / hydrate / decorate / release without operator ask
- Loading stale prism packs as authoritative

---

## Finish Condition

After the polarize pass:

- thesis written, single sentence
- rejected alternatives recorded with reasons
- surfaces aligned where runtime proof supports the chosen axis
- gates green for touched surfaces
- DoU + release handoffs written

Stop. Do not continue into DoU, hydrate, decorate, or release unless
the operator explicitly asked for that chain.

---

## Call to Action

Read [`PROCEDURE.md`](PROCEDURE.md) before your first polarize pass —
it carries the full lifecycle, the prism axis scoring detail, the
context-corpus contract, and the minimum-gates list. Then run a
prism preflight, check the band, and only dispatch for `pass` /
`doctrine`.

---

## Closing Rail

```text
=======================
Remember: polarize mode is permission to choose one truth, not
permission to invent new ones. The marbles flood is yours to strip,
not yours to extend. One thesis, rejected alternatives named, surfaces
aligned, gates green. Stop at the handoff.
( •̀ω•́ )✧
=======================

Suchar: Why does polarize never average two truths? Because the
average of two stars is dust.  (._.)
```

---

## Verify before the handoff

Before you report "done", walk around the truck — see [Verification Rule](../VERIFICATION_RULE.md): run the REAL artifact (launch the app/binary, not just `--version`), re-verify runtime, never trust upstream verification as proof, and check your own check. Gates green ≠ works.

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

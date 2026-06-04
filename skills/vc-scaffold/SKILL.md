---
name: vc-scaffold
version: 0.2.0
description: >
  Founder-first main brainstorm + planwriting — the armored lighthouse (pancerna
  latarnia) that carries a single cut, multiple cuts, or a whole project into the
  autonomous VC-ship pipeline. The WRITE entry of the read/write cadence: produces a
  measurable, self-sufficient plan a fleet executes with the operator absent mid-flight.
  This skill should be used when the user asks to "scaffold", "plan this", "architect
  this", "break this down", "I have an idea", "design the system", "vc-scaffold",
  "zaplanuj to", "rozrysuj architekturę", "mam pomysł".
---

# vc-scaffold: Founder-First Planning — Pancerna Latarnia

## What this is

Scaffold is the **main brainstorm + planwriting** surface: take a vague idea and produce
a scoped, **measurable** build plan. It scales across one gate: a **single cut**, **multiple
cuts**, or a **whole project**. It is the **WRITE entry of the VC-ship read/write cadence** —
the plan it emits must be **self-sufficient and falsifiable** because in autonomous delivery
the operator is absent mid-flight and sees only intermediate artifacts. Plan as if no one will
answer a question after dispatch. Front-load every decision here. See `references/cadence.md`.

The lighthouse orients before the fleet sails; the armor is the verification each cut carries.

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch
to, or move execution into a git worktree unless the operator explicitly asks. Generic words like
"isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to
concurrent changes, report a substrate failure if the tree is too poisoned to continue safely.
See [Living Tree Rule](../LIVING_TREE_RULE.md).

### Dispatch

Enter the framework session, then launch through the command deck (not raw `skills/.../*.sh`):

```bash
vibecrafted start            # or: vc-start
vibecrafted scaffold claude --prompt 'Design the payment system'
vc-scaffold gemini --prompt 'Plan migration from NextAuth to custom auth'
vibecrafted scaffold codex --file /path/to/idea-brief.md
```

Prefer `--file` for an existing plan/artifact and `--prompt` for inline intent.

## Canonical Orientation Gate (HARD-BLOCK — safety-critical)

Before any repo-specific analysis or planning, run or consume `vc-init` for the assigned repo.
**This is not a polish step — it is a safety bezpiecznik.** In autonomous VC-ship an agent that
composes from memory injects silent drift the operator cannot catch live. Therefore: **no plan
until repo/runtime truth exists.** Missing `vc-init`/Loctree evidence is a process failure, not a
warning.

`Loctree:loctree` is the default structural perception. Use it before grep or docs-driven claims:
`repo-view`, `focus`, `slice` (before edit), `impact` (before delete), `find` / `find --literal`
(before create), `follow` (dead/cycles/twins/hotspots). Find load-bearing hubs, twins, dead code,
drift, runtime entrypoints, blast-radius traps. If the task is explicitly non-repo/greenfield,
declare the **no-repo exception** in the report and name the orientation source used instead.

## Pipeline Position

```
[SCAFFOLD] → init → implement → review → workflow → followup → marbles → audit → polarize → dou → hydrate → release
^^^^^^^^^^   WRITE entry of the read/write cadence (WRITE produces an artifact, READ falsifies it)
```

Scaffold is the WRITE entry. If the task is already clear and bounded, skip scaffold and start at
`vc-init`. The full cadence and the WRITE/READ classification live in `references/cadence.md`.

## The Five Phases

Run these in order. Each phase produces the input the next consumes.

### 1. Orient (research-first)

Pass the Canonical Orientation Gate above. Map the existing landscape: `repo-view` for size/health,
`focus` on suspect modules, `slice` critical files, `tree` for hotspots, `follow` for dead/cycles.
Capture the **constraint space** — tech (stack/versions/infra), team (who builds, which languages),
business (time budget, deadline), scope (MVP vs full vision). Constraints shape everything.

### 2. Falsify (adversarial premise check)

Before committing to a shape, try to **break** the founding assumption. Ask "how would I know this
is a lie?" The 0-byte-passes-exit-0 lesson: every "it works" must survive a real probe, never a
green checkmark alone. Surface the failure modes the plan must defend against.

### 3. Shape (scale-adaptive)

Decide architecture by **boundaries and decisions** (3-5 that matter, not a thousand details), set
**scope** (in / out / explicitly out — be ruthless), and define **product identity** (material
metaphor, color roles, typography, tone, dark/light) — identity is an architectural decision that
feeds DoU and Decorate later. Then pick the **output shape by scale**: single-cut brief · wave-atlas+tracker · project read/write pipeline. See `references/output-shapes.md`.

### 4. Defend (gates first-class)

Break work into agent-sized cuts (30-120 min). **Every cut carries the measure-core**: a `Vector`
(stabilize/implement/recon/e2e), the four-term delta (`intent | baseline | claim | delivery`), a
`state` marker `[ ] [~] [?] [!] [x]`, and a **delivery-verifier** — the non-fakeable test that flips
`[~]→[x]`. A cut without a verifier ships as `[?]`, never `[x]`. See `references/measure-core.md`.

### 5. Handoff

Produce the plan from `references/plan-template.md`. **Scaffold owns brainstorm→plan (WRITE);
vc-operator reads the `state` column for trigger/stop (dispatch).** The plan must speak for itself:
what is `[x]` vs `[?]`/runtime-pending, with an exact recipe. Save to the task output directory.

## Measurement (the armor)

Every plan unit is claim/outcome-addressable. **Only a verifier flips `[~]→[x]`; a claim never
reaches `[x]` on its own** — that invariant is what makes the plan measurable instead of optimistic.
`dou-index = |[x]| / total`; `delta = {[ ],[~],[?],[!]}`; trigger/stop reads the `state` column
(`[!]`/`[?]` → STOP → recovery-vector; full `[x]` wave → TRIGGER next). **STOP is never surrender —
it triggers a recovery-vector** (fallback/failover/handsoff). Full alphabet + markers:
`references/measure-core.md`.

## Critical Rules

- **Research-first is hard-block, not polish.** No plan from memory; derive from repo/runtime truth.
- **Measure, don't claim.** A cut is done when its verifier is green, never when an agent says so.
- **Map before designing.** Respect the grain of the existing system; loctree before assumptions.
- **Scope is your best friend.** Tight scope + great execution beats loose scope every time.
- **Write for an absent operator.** The artifact speaks for itself; the next READ falsifies it
  without a human on the other side.
- **Keep dependencies shallow.** Prefer independent workstreams; sequential A→B→C kills parallelism.
- **No premature optimization / no invented patterns.** The best architecture is the one that ships.

## What Success Looks Like

- A cold fleet (or human) executes the plan **without asking a question** mid-flight.
- Every cut has a `Vector` and a `delivery-verifier`; the `state` column is machine-readable.
- Scope boundaries are crystal clear; 3-5 architectural decisions explicit with trade-offs.
- The plan survives an absent operator: `[x]` is earned, `[?]` is honest, nothing is faked.

## Cross-References

- **vc-init** — bootstraps agent context after scaffolding (the orientation gate).
- **vc-implement** (alias **vc-justdo**) / **vc-workflow** — WRITE phases that consume scaffold plans.
- **vc-review · vc-followup · vc-audit · vc-dou** — the READ phases that falsify each WRITE artifact.
- **vc-operator** — reads the plan's `state` column and conducts the dispatch (trigger/stop).
- **vc-research** — triple-agent research for unknowns found during Orient/Falsify.

## Anti-Patterns

- Planning before the orientation gate (composing architecture from memory = silent drift).
- A 50-page design doc instead of a sharp, measurable plan.
- Prose instead of a `state` column — the operator can't trigger/stop on prose.
- Treating an agent's `[~]` claim as `[x]` without a verifier (the optimism trap).
- STOP-as-surrender (502-and-die) instead of STOP-as-recovery-vector.
- Breaking all work into sequential dependencies; skipping product identity.

## Additional Resources

- **`references/measure-core.md`** — `[ ][~][?][!][x]` alphabet, invariant, Vector→Δ, marker taxonomy.
- **`references/cadence.md`** — VC-ship read/write cadence (order, WRITE/READ, handoff, planning rules).
- **`references/output-shapes.md`** — the three scale shapes + 12-section dispatch template + tracker.
- **`references/plan-template.md`** — the SCAFFOLD.md output format (now with Vector + state + verifier).

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

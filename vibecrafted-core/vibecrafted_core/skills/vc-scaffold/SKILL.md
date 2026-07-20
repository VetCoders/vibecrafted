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
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
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
vc-scaffold agy --prompt 'Plan migration from NextAuth to custom auth'
vibecrafted scaffold codex --file /path/to/idea-brief.md
```

Prefer `--file` for an existing plan/artifact and `--prompt` for inline intent.

## Canonical Orientation Gate (HARD-BLOCK — safety-critical)

Before any repo-specific analysis or planning, run or consume `vc-init` for the assigned repo.
**This is not a polish step — it is a safety bezpiecznik.** In autonomous VC-ship an agent that
composes from memory injects silent drift the operator cannot catch live. Therefore: **no plan
until repo/runtime truth exists.** Missing `vc-init`/Loctree evidence is a process failure, not a
warning.

`Loctree:loctree` is the default structural perception. Use it before grep or docs-driven claims
to produce or refresh the **Code-Derived Application Map**:
`repo-view`, `focus`, `slice` (before edit), `impact` (before delete), `find` / `find --literal`
(before create), `follow` (dead/cycles/twins/hotspots). Find load-bearing hubs, twins, dead code,
drift, runtime entrypoints, blast-radius traps. If the task is explicitly non-repo/greenfield,
declare the **no-repo exception** in the report and name the orientation source used instead.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Pipeline Position

```
[SCAFFOLD] → init → implement → review → workflow → followup → marbles → audit → polarize → dou → hydrate → release
^^^^^^^^^^   WRITE entry of the read/write cadence (WRITE produces an artifact, READ falsifies it)
```

Scaffold is the WRITE entry. If the task is already clear and bounded, skip scaffold and start at
`vc-init`. The full cadence and the WRITE/READ classification live in `references/cadence.md`.

## The Six Phases

Run these in order. Each phase produces the input the next consumes. Phases 5–6 are the
**delivery mechanism**: every cut gets a brief (hard-gate) and the artifacts are served for
operator review — not narrated as prose and not gated on the agent's good intentions.

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

### 5. Brief every cut (HARD-GATE — this is the delivery mechanism)

Produce the plan from `references/plan-template.md` (master-dispatch: wave atlas + dependency
graph + the `state` column). **Then — non-negotiable — render a brief for EVERY cut.** A cut
without a rendered, well-formed brief does not exist as far as the plan is concerned. This is the
rule that turns a plan from a shell (wydmuszka) into something a fleet can execute.

For each cut, write `briefs/<wave>-<slot>_<slug>.md` from the 12-section dispatch template
(`references/output-shapes.md`): mission · context · files · acceptance · gates · out-of-scope ·
Living Tree etiquette (verbatim) · Loctree-first · recovery hint · branch+commit · report path.

**Enforcement (ported from `/brainstorming`, the flow that leads the agent by the hand):**

- **Checklist→TODOs:** create one TodoWrite item per cut-brief; complete them in order. The
  scaffold is not "done" while any cut-brief todo is open.
- **Hard-gate:** do NOT hand off to `vc-operator`, dispatch, or claim the scaffold complete until
  EVERY cut in the wave atlas has a matching brief with all 12 sections present.
- **Loop to green:** missing or malformed brief → loop back and render it. Single terminal state:
  all briefs rendered AND the scaffold-doctor gate passes.
- **Anti-pattern pre-emption (FORBIDDEN rationalizations):** "this cut is too small to need a
  brief", "we are 1:1 so no briefs needed", "the master-dispatch table is enough". A plan without
  per-cut briefs is a shell, not a plan. No exceptions, regardless of perceived simplicity.

### 5.5 DRIVER.md (HARD-GATE — the operator's hand-off driver)

Alongside the briefs, render **one `DRIVER.md`** co-located with `briefs/`. It is the single
self-sufficient artifact a human operator (or a cold fleet) drives the whole plan from **when the
in-thread loop dies**. NOT optional, NOT a re-skin of the atlas — it is the executable hand-off.
It MUST contain all five:

1. **Full absolute paths** — every plan artifact, brief, orient evidence, and input/fixture, as
   copy-pasteable absolute paths.
2. **Dependency graph WITH a `why` on every edge** — what-after-what AND why: why each cut precedes
   the next; why a pair is **SEQUENCE** (shared file domain → Living Tree conflict) vs **PARALLEL**
   (disjoint domains → safe concurrent); and where every **⛔ operator-button STOP** sits (push/merge,
   product decisions). A graph without `why` is a diagram, not a driver.
3. **Ready commands** — the exact launcher line (`vibecrafted <workflow> <agent> --file <brief>`) for
   EVERY remaining cut, in dispatch order, tagged SEQUENCE / PARALLEL / STOP, each followed by its
   per-cut verify command. A human pastes these verbatim if the loop fails.
4. **The state alphabet + the `[ ]→[x]` rule, reproduced verbatim** (mirrors Measurement):
   `[ ]` todo · `[~]` running · `[?]` done-unverified · `[!]` blocked · `[x]` verifier-green.
   **Only a delivery-verifier flips `[~]→[x]`; an agent's claim NEVER reaches `[x]` on its own.**
   The rule lives IN the DRIVER on purpose — so that mid-dispatch nobody promotes a claim to done
   without re-running the verifier. That promotion-without-proof is the single failure mode that
   wrecks an operator run ("się zajebiemy"). Encode it where the dispatcher's eyes are.
5. **Live status snapshot** + `dou-index = |[x]| / total`.

### 5.6 manifest.json (HARD-GATE — canonical artifact inventory)

Create one plan root at
`~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<plan_id>/` and write
`manifest.json` there as mandatory output. Schema version `"1"` declares `plan_id`, `org`, `repo`,
`day`, and an ordered `artifacts` array. Every artifact entry declares a stable `id`, explicit
`role`, relative `path`, `editable`, and `required`; optional `dependencies` contain artifact IDs.
Supported roles are `driver`, `wave-atlas`, `brief`, `design-doc`, `traceability`, `tracker`,
`falsification`, `report`, and `other`. Register every generated artifact before handoff. Filenames
never imply roles. Do not create an `operator/` mirror, compatibility copy, naming alias, or symlink.

### 6. Serve & review (editable artifacts via vibecrafted-server)

The plan + briefs are **editable artifacts**, not a wall of inline questions. The flow is:
research → present findings + effort estimate → propose the first cut/wave shape → render the
briefs → **serve them for operator review through `vibecrafted-server`** (the natural home of this
phase's tooling: it reads the typed control-plane contract and renders the wave atlas + briefs as a
**multi-tab, editable** HTML surface — one tab per artifact (atlas · each brief · each design doc),
edited in place). The operator steers by editing the rendered plan in the browser, not by answering
twenty questions mid-scaffold. Refine WITH the operator on the served artifacts.

**Transplant the surface — do not reinvent it.** Proven sources to lift from: `../pensieve`
(multi-tab editable workspace dashboard), `../unicode-puzzles-portal` (portal generators), and
`/brainstorming`'s visual-companion (proven HTML mockup/diagram generators). The server-review tab
must be multi-tab + editable from day one, not a static dump.

**scaffold-doctor (the gate, machine-checked):** a deterministic validator in
`vibecrafted-server/control-core` that loads the same typed `manifest.json` used by the server and
refuses the scaffold→implement baton until: the manifest identity matches its canonical plan root;
all declared required artifacts exist; IDs and paths are unique; dependencies resolve; editable
paths are non-symlinked and remain inside the plan root; briefs on disk are declared; and the atlas
has a wave atlas + dependency graph; every cut has a `briefs/<wave>-<slot>_<slug>.md` with all 12
sections; acceptance bullets are atomic + verifier-backed; a design doc exists for every cut flagged
`needs_design`; **a `DRIVER.md` exists and carries all five (full paths · why-annotated graph ·
ready commands · the `[ ]→[x]` rule verbatim · status snapshot)**. The gate is **machine-checked, not
agent-promised** — it is the same artifact-as-truth gate the async runtime uses between every
read-write cadence handoff.

## Measurement (the armor)

Every plan unit is claim/outcome-addressable. **Only a verifier flips `[~]→[x]`; a claim never
reaches `[x]` on its own** — that invariant is what makes the plan measurable instead of optimistic.
`dou-index = |[x]| / total`; `delta = {[ ],[~],[?],[!]}`; trigger/stop reads the `state` column
(`[!]`/`[?]` → STOP → recovery-vector; full `[x]` wave → TRIGGER next). **STOP is never surrender —
it triggers a recovery-vector** (fallback/failover/handsoff). Full alphabet + markers:
`references/measure-core.md`.

## Critical Rules

- **Research-first is hard-block, not polish.** No plan from memory; derive from repo/runtime truth.
- **A brief for every cut — no exceptions.** Per-cut briefs are the hard-gate (Phase 5). A plan
  whose cuts lack briefs is a shell; the scaffold-doctor refuses to hand it off.
- **A DRIVER.md — no exceptions (Phase 5.5).** The operator hand-off driver (full paths · why-annotated
  graph · ready commands · the `[ ]→[x]` rule verbatim · status snapshot) is part of the scaffold-doctor
  gate. A plan a human can't drive from one file when the loop dies is not handoff-ready.
- **Durable artifacts NEVER go to `/tmp`.** `/tmp` is ephemeral scratch only — it is wiped, untracked,
  and invisible to the operator's tooling and sync. Every plan, brief, DRIVER, tracker, journal, report,
  and design doc lands in the **canonical plan root**:
  `~/.vibecrafted/artifacts/<org>/<repo>/<DATE>/plans/<plan_id>/`
  (mirrors the reports layout). Writing a durable artifact to `/tmp` is a process failure, not a shortcut.
- **manifest.json is mandatory.** It is the only artifact inventory and role contract. No `operator/`
  mirror, duplicate, filename-role inference, or compatibility symlink may become a second writable truth.
- **Serve, don't interrogate.** Render editable artifacts and review them through `vibecrafted-server`;
  the operator edits the plan, not answers twenty mid-scaffold questions.
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

## Verification carries into the prompt

Every prompt this skill composes must carry the [Verification Rule](../VERIFICATION_RULE.md) into the worker's dispatch: walk-around verification (gates green ≠ works) + loct literal-vs-semantic. See `vc-operator/DISPATCH_TEMPLATE.md` Sections 6 + 9.

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_

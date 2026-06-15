---
name: vc-scaffold
version: 1.0.0
description: "Founder-first brainstorming and planwriting that produces measurable, fleet-executable plans — sized to the task. A big plan earns the full form (Atlas + Master + Waves + Cuts + briefs + DRIVER); a mini task earns one sharp prompt. Use when turning a vague idea into a build plan, shaping a feature, or preparing work for dispatch."
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

# vc-scaffold — Founder-First Planning

Scaffold is the **WRITE entry** of the VC-ship read/write cadence: take a vague
idea and produce a scoped, **measurable** plan the fleet can execute. The plan
must be self-sufficient and falsifiable — in autonomous delivery the operator is
absent mid-flight and sees only the artifacts. Front-load every decision.

## The form is a scale, not a mandate — this is law

The plan has four named parts. Use their real names.

- **Cut** — the smallest executable component. One worker, one slice.
- **Wave** — cuts fired together: A (foundation, sequential) · B (shared-state,
  chained agents) · C (disjoint, parallel) · D (final, after B+C merge).
- **Atlas** — the overview of the whole: waves, cuts, dependency graph, the
  `/vc-agents` why-matrix pick per cut, the `state` column. Written once.
- **Master** — the dispatch plan handed to the operator (`master-dispatch.md`).

**Match the ceremony to the task. Inflating it is as much a defect as a shell.**

- **Large** (10+ cuts / several branches / wave-merge) → full form: `00_ATLAS`
  - Master + Waves A/B/C/D + per-cut `briefs/` + `DRIVER` + `tracker`. Proven
    shape: `vc-ship-dispatch-v1`, `aicx-haki`.
- **Mid** → Atlas + Waves + Cuts + light briefs.
- **Mini** → **one sharp prompt → dispatch.** No atlas, no briefs, no DRIVER.

A brief exists to remove a worker's ambiguity. Render exactly as much brief as a
cut needs and no more. There is no rule that "every cut must carry a 12-section
brief"; a mini task that gets 40 briefs and 3 atlases is the failure.

## Operator Entry

```bash
vibecrafted start            # or: vc-start
vibecrafted scaffold codex --prompt 'Design the payment system'
vibecrafted scaffold claude --file /path/to/idea-brief.md
```

Runs in the operator's current checkout and branch. Do not create/switch
branches or worktrees unless the operator says "worktree". Re-read before
editing; report a substrate failure if the tree is too poisoned.
See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate (HARD-BLOCK — safety-critical)

Before any planning, run or consume `vc-init` for the repo. No plan from memory —
composing from memory injects silent drift the operator cannot catch live.
`Loctree:loctree` is the default map: `loct context`, `focus`, `slice` (before
edit), `impact` (before delete), `find --literal` (before create), `follow`
(dead/cycles/twins/hotspots). If the task is explicitly non-repo/greenfield,
declare the no-repo exception and name the orientation source used.

## Pipeline Position

```
[SCAFFOLD] → init → implement → review → workflow → followup → marbles → audit → polarize → dou → hydrate → release
^^^^^^^^^^   WRITE entry (WRITE produces an artifact; READ falsifies it)
```

If the task is already clear and bounded, skip scaffold and start at `vc-init`.
Cadence detail: `references/cadence.md`.

## The Phases

Phases 1–4 always run (sized to the task). Phases 5–6 are the delivery mechanism
for **mid/large** plans; a mini task collapses 5–6 into "write one sharp prompt".

### 1. Orient (research-first)

Map the landscape: `repo-view` for size/health, `focus`/`slice` on suspects,
`follow` for dead/cycles. Capture the constraint space — tech, team, business,
scope (MVP vs full). Constraints shape everything.

### 2. Falsify (adversarial premise check)

Try to break the founding assumption: "how would I know this is a lie?" The
0-byte-passes-exit-0 lesson — every "it works" must survive a real probe, never a
green checkmark alone. Surface the failure modes the plan must defend against.

### 3. Shape (scale-adaptive)

Decide architecture by **boundaries and decisions** (3–5 that matter), set
**scope** (in / out / explicitly out — be ruthless), define **product identity**
(material metaphor, color roles, typography, tone) — identity feeds DoU and
Decorate later. **Pick the output shape by scale**: mini prompt · single-cut
brief · wave-atlas+tracker · project pipeline. See `references/output-shapes.md`.

### 4. Defend (gates first-class)

Break work into agent-sized cuts (30–120 min). **Every cut carries the
measure-core**: a `Vector` (stabilize/implement/recon/e2e), the four-term delta
(`intent | baseline | claim | delivery`), a `state` marker `[ ] [~] [?] [!] [x]`,
and a **delivery-verifier** — the non-fakeable test that flips `[~]→[x]`. A cut
without a verifier ships as `[?]`, never `[x]`. See `references/measure-core.md`.

### 5. Brief each cut that needs one (mid/large)

Produce the plan from `references/plan-template.md` (Master/master-dispatch: wave
atlas + dependency graph + `state` column). Then render a brief for each cut
**proportional to its risk** — write `briefs/<wave>-<slot>_<slug>.md` from the
dispatch template (`references/output-shapes.md`): mission · context · files ·
acceptance · gates · out-of-scope · Living Tree etiquette · Loctree-first ·
recovery hint · branch+commit · report path.

A large plan handed off as a bare table with no briefs is a shell (wydmuszka) —
render the briefs. A mini task handed off as 40 briefs is over-ceremony — write
one sharp prompt instead. Size the briefing to the work.

### 5.5 DRIVER.md (for plans that outlive one session)

For a large or cross-session plan, render one `DRIVER.md` beside `briefs/` — the
self-sufficient artifact a human or cold fleet drives the whole plan from when
the in-thread loop dies (≈ an executable Atlas). It carries: full absolute paths;
dependency graph with a `why` on every edge (SEQUENCE vs PARALLEL, and every ⛔
operator-button STOP); ready launcher commands per remaining cut in order, each
with its verify command; the `[ ]→[x]` rule verbatim; a live status snapshot +
`dou-index = |[x]| / total`. Skip it for a mini task that finishes in one go.

### 6. Serve & review (mid/large)

The plan + briefs are **editable artifacts**, not a wall of inline questions:
research → present findings + effort estimate → propose the first wave → render
briefs → serve through `vibecrafted-server` (reads the typed control-plane
contract, renders the atlas + briefs as a multi-tab editable HTML surface). The
operator steers by editing the rendered plan, not by answering twenty questions.
Transplant the surface (`../pensieve`, `/brainstorming` visual-companion) — do
not reinvent it.

**scaffold-doctor (gate for the full-form path):** a deterministic validator in
`vibecrafted-server/control-core` that refuses the scaffold→implement baton for a
**large** plan until: Master has a wave atlas + dependency graph; each cut has a
proportional brief; acceptance bullets are atomic + verifier-backed; a design doc
exists for every `needs_design` cut; a `DRIVER.md` carries the five fields above.
Machine-checked, not agent-promised. It gates the heavy form — it does not force
heavy form onto a mini task.

## Measurement (the armor)

Every plan unit is claim/outcome-addressable. **Only a verifier flips `[~]→[x]`;
a claim never reaches `[x]` on its own.** `dou-index = |[x]| / total`; trigger/stop
reads the `state` column (`[!]`/`[?]` → STOP → recovery-vector; full `[x]` wave →
TRIGGER next). STOP is never surrender — it triggers a recovery-vector. Full
alphabet: `references/measure-core.md`.

## Plan once, then hold it

Write the whole task ONCE — every wave, cut, and `/vc-agents` why-matrix pick —
then hold it. The only sanctioned mid-flight edits are Wave/Cut splits and
reorderings (W1→W1A/W1B) that keep the goal fixed. Plans executed by halves are
the disease this form cures.

## Kill ambiguity

Every directive in a brief must be definite. Banish "if maybe X then perhaps Y" —
conditional mush makes a worker guess, and guesses compound across waves. State
the agent, the cut, the files, the acceptance, the verifier. Resolve uncertainty
before dispatch or mark the cut `[!]` and stop. Never ship doubt into a worker.

## Critical Rules

- **Research-first is hard-block.** No plan from memory; derive from repo truth.
- **Ceremony proportional to task.** Large → full form; mini → one sharp prompt.
  Briefs/DRIVER scale with size; do not mandate them onto small work.
- **Durable artifacts NEVER go to `/tmp`.** Plans, briefs, DRIVER, tracker, reports
  land in `~/.vibecrafted/artifacts/<org>/<repo>/<DATE>/plans/`. `/tmp` is wiped,
  untracked, invisible to operator tooling — writing there is a process failure.
- **Serve, don't interrogate.** Render editable artifacts; the operator edits them.
- **Measure, don't claim.** A cut is done when its verifier is green, not on a say-so.
- **Map before designing.** Loctree before assumptions.
- **Write for an absent operator.** The artifact speaks for itself; the READ falsifies it.

## Cross-References

- **vc-operator** — conducts the dispatch from the Master/Atlas this skill writes;
  shares this canon (Master·Atlas·Waves·Cuts, size-proportional).
- **vc-init** — orientation gate. **vc-implement** / **vc-workflow** — WRITE phases
  that consume the plan. **vc-review · vc-followup · vc-audit · vc-dou** — READ
  phases that falsify it. **vc-research** — unknowns found during Orient/Falsify.

## Anti-Patterns

- Planning before the orientation gate (architecture from memory = silent drift).
- Inflating ceremony: briefs/atlases/DRIVER for a mini task that needed one prompt.
- Shipping ambiguity into a brief ("if X maybe Y") instead of a definite directive.
- A 50-page design doc instead of a sharp, measurable plan.
- Prose instead of a `state` column — the operator can't trigger/stop on prose.
- Treating an agent's `[~]` claim as `[x]` without a verifier.
- Rewriting the goal mid-flight instead of only splitting/reordering Waves/Cuts.

## Additional Resources

- `references/measure-core.md` — `[ ][~][?][!][x]` alphabet, invariant, Vector→Δ.
- `references/cadence.md` — VC-ship read/write cadence.
- `references/output-shapes.md` — the scale shapes + dispatch template + tracker.
- `references/plan-template.md` — the SCAFFOLD.md output format.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

# vc-operator — DISPATCH: Iter-3 Prompt Body Shape

> Canonical prompt-body shape for `/vc-agents` / `vc-justdo` / `vc-implement`
> dispatch. Refined through three iterations: Iter-1 (one-liner checklist,
> too thin), Iter-2 (ad-hoc paragraph, too soft), Iter-3 (twelve-section
> ownership-grade brief, current). Honours the [`EMIL.md`](EMIL.md) plan
> shape and the Emil voice-prompt rail format from `~/.codescribe/transcriptions/`
> (Jan 2026, where the convention was first lived before being codified).

Read alongside [`SKILL.md`](SKILL.md), [`GUIDE.md`](GUIDE.md), [`EMIL.md`](EMIL.md).

---

## Why Iter-3 shape

A dispatched agent has **no shared memory** with you. The prompt body is
the complete contract. Iter-1 underspecified scope (workers improvised);
Iter-2 over-described intent but underspecified gates (workers committed
half-broken work). Iter-3 fixes both by treating the prompt body as the
worker's **exit contract** — explicit acceptance, explicit gates, explicit
out-of-scope, explicit recovery hint, and an explicit closing rail that
sets the emotional contract (stakes + wink) the worker must honour.

A well-shaped Iter-3 brief takes ~20 minutes to author and saves ~3 hours
of recovery dispatch per wave.

---

## The twelve sections

Every dispatch body has these in this order:

### 1. YAML frontmatter

```yaml
---
prompt_id: textforge-editor-core-20260516
wave: B
position: 1
mandate: /vc-ownership
recommended_agent: claude
parent_branch: feat/text-context-menu@f6b02744
result_branch: feat/textforge-editor-core
depends_on: [textforge-shell-20260516]
parallel_with: []
blocks:
  [
    textforge-tool-rail-20260516,
    textforge-stylize-20260516,
    textforge-inspectors-20260516,
  ]
report_path: ~/.vibecrafted/artifacts/<...>/reports/textforge-editor-core_<ts>_claude.md
authored_by: claude <agents@vetcoders.io>
---
```

`prompt_id` is the cross-walk key into session retrieval; `wave` + `position`
locate it in the atlas; `recommended_agent` is enforced by AGENT MODEL
PARITY; `parent_branch` is the precise SHA the worker branches off;
`depends_on` / `parallel_with` / `blocks` close the dependency graph.

### 2. Mission

One paragraph (3–5 sentences) opening with the Emil-default imperative
`You're tasked with...` / `Your job is to...`. State what lands when this
prompt succeeds — the "after-this-lands acceptance" in plain language.

Example:

> _"You're tasked with replacing the canvas placeholder with a real
> multi-line editor surface. Buffer + selection + cursor live on the
> provider. Undo/redo with a 200-step ring buffer. Selection-aware so
> transforms later can read the current span without re-querying the DOM.
> After this lands, Waves B-2 through B-4 can plug their tool-specific
> reads/writes against `buffer` and `selection` signals without further
> provider extensions."_

### 3. Context

Bullets pointing to what the worker should read before editing:

- existing provider / shell / canvas file paths (with `loct slice` hints)
- prior wave's commit SHA + what it landed (so the worker knows the baseline)
- design tokens / theme files that constrain visual output
- relevant tests that pin contracts

Do not paste content here — paths only. The worker reads files themselves.

### 4. Files to create / edit

Explicit list, grouped:

```text
Create:
  studio/src/components/textforge/TextForgeCanvas.tsx
  studio/src/components/textforge/__tests__/TextForgeCanvas.test.tsx

Modify (append-only fields where marked):
  studio/src/components/textforge/TextForgeProvider.tsx
    + APPEND-ONLY: buffer / selectionStart / selectionEnd signals
    + APPEND-ONLY: history stack (push debounced 150ms)
    DO NOT delete or rename existing exports — Wave B-2..B-4 depend on them

  studio/src/styles/textforge.css
    + canvas typography rules in the dedicated section
```

The append-only markers + "do not delete" lines are **Living Tree warnings
VERBATIM** — see Section 8 below.

### 5. Acceptance

GitHub-flavored checkbox list, atomic, testable (per [`EMIL.md`](EMIL.md)
Rule 1):

```markdown
- [ ] Typing in the canvas updates the provider's buffer signal in real time.
- [ ] Selection changes inside the textarea propagate to selectionStart/End
      signals observable from outside the component.
- [ ] Cmd/Ctrl+Z undoes the last 150ms-debounced edit; Shift+Cmd/Ctrl+Z redoes.
- [ ] Ring buffer caps at 200 steps; earlier steps are silently dropped.
- [ ] Existing tests in `sidebar-state.test.ts` and `TextForgeProvider.test.ts`
      stay green.
- [ ] New tests in `TextForgeCanvas.test.tsx` cover typing flow, selection
      propagation, and undo/redo wiring.
```

The worker flips items `[ ]` → `[x]` as they complete and pastes the
final checkbox state into their report.

### 6. Gates

Explicit commands:

```bash
pnpm -C studio run check   # typecheck + lint + format
pnpm -C studio run test    # Vitest
pnpm run check             # root: lint + format + Jest + studio check
```

All green is the gate. Workers must run gates locally before committing.

### 7. Out of scope

Explicit anti-scope-creep:

```text
Out of scope (DO NOT touch):
- Tool rail behaviour beyond exposing `activeTool` signal as a placeholder
  (that's Wave B-2's surface)
- Inspector content (Wave B-4)
- TopBar actions / workspace tabs (Wave C topbar)
- StatusBar wiring (Wave C statusbar)
- Right-click context menu (already exists; Wave D input-parity rewires it)
```

Two-line out-of-scope per dispatch is the minimum. Workers love this section
because it tells them what to _not_ implement when "it would only take 5
minutes".

### 8. Living Tree etiquette

**Verbatim**, no paraphrase:

```text
Living Tree etiquette (NON-NEGOTIABLE):
- Re-read every file in `Files to modify` IMMEDIATELY before editing it.
  Another agent in a sibling wave or this wave's prior step may have
  pushed between your dispatch start and your first edit.
- For files marked APPEND-ONLY, never delete or rename existing exports.
  Append new signals / methods at the end of the export block.
- For shared CSS files, add new rules in a dedicated section with a
  comment block stating which prompt added them.
- If you detect that another agent's work is incompatible with your
  acceptance, halt and write a "substrate failure" report instead of
  attempting a merge. The operator-agent decides next move.
```

This block is identical across every dispatched prompt in a wave — the
operator-agent doesn't customize the wording, only the file list above.

### 9. Loctree first

Explicit `mcp__loctree-mcp__*` directives:

```text
Loctree first (perception over memory):
1. `mcp__loctree-mcp__context` on project root before any edit
2. `mcp__loctree-mcp__slice` on each file in `Files to modify` before editing
3. `mcp__loctree-mcp__impact` on files in `Files to modify` if your change
   could affect importers
4. `mcp__loctree-mcp__find name=TEXTFORGE_TOOLS mode=where-symbol` to
   confirm where shared types live

Grep fallback (only if loctree fails):
- Acceptable: `grep -RIln 'TextForgeProvider' studio/src/`
- Log a hook entry to `~/.vibecrafted/loctree/loctree-fail.md` describing
  why loctree was insufficient, so the loctree team can improve it.
```

### 10. Recovery hint

```text
Recovery hint (if your dispatch stalls):
- Substrate stall (Living Tree poisoned, prior wave's commit doesn't
  exist on parent_branch): halt, write `substrate-failure.md`, exit
  non-zero. Operator-agent dispatches a fix.
- Scope stall (acceptance #N is wider than 1 commit can satisfy): write
  a `scope-overflow.md` listing what landed + what didn't, exit 0 with
  partial commit. Operator-agent narrows the next dispatch.
- Implementation stall (you took the wrong cut, gates fail at >30 min):
  revert your branch to parent_branch, write `wrong-cut.md` describing
  what you tried, exit 1. Operator-agent dispatches a focused integration
  agent with hints.
```

### 11. Branch + commit convention

```text
Branch + commit:
- Branch: `feat/textforge-editor-core` off `feat/text-context-menu@f6b02744`
- Cadence: ONE commit per round (marbles — one round = one commit); a dispatch that delivers multiple rounds/units is EXPECTED to produce multiple commits, each committed locally as its round completes. Never leave delivered work uncommitted.
- Commit subject: `[claude/vc-implement] feat(textforge): wire editor canvas to provider`
- Commit body: explain the change, then include the full runtime footer:
  `Authored-By: claude <agents@vetcoders.io>`, `session_id: <uuid>`,
  `time: YYYY-MM-DDTHH:MM:SS±HH:MM`, and `runtime: <runtime>`.
- Do not use `Co-Authored-By:`, vendor noreply addresses, or personal signatures.
- DO NOT `git push`. Operator publishes after wave green.
- DO NOT create PR. Operator does that operator-side.
```

### 12. Report path + Call to Action + Closing rail

```text
Report path (mandatory):
~/.vibecrafted/artifacts/<...>/reports/textforge-editor-core_<ts>_claude.md

Report sections:
- Frontmatter (mirror this prompt's YAML, set `status: completed | failed`)
- Current state, Proposal, Execution, Open risks, Next move (per ownership)
- Gate results (paste the last 10 lines of each gate command)
- Files changed (paste `git diff --stat HEAD~1`)
- Acceptance verification (paste the Section 5 checkbox state, flipped)
```

Then the **Call to Action** + **Closing rail** — see default block below.

---

## Closing rail — the Emil default block

Every Iter-3 dispatch body closes with a rail-fenced block carrying three
elements: **anti-debt one-liner + signature kaomoji + suchar punchline**.
The shape was lived in `~/.codescribe/transcriptions/` Jan 2026 (Emil
voice prompts) and is now canon.

```text
=======================
[Anti-debt one-liner that personifies the bug as folk-horror, bureaucracy,
or domain absurdity — e.g. "If state silently overwrites itself, that's
not a bug, it's a poltergeist in the codebase — and the cure for
ghosts is a proper unit test."]  (งಠ_ಠ)ง
=======================

Call to Action: [Sequential imperative — "Start with X, then Y → Z". Be
specific. End with the report.]

Suchar: [Domain pun in dad-joke shape — "Why does the pipeline never go
to the forest? Because it's afraid of losing its path without loctree."]
(._.)
```

**Three required pieces**:

1. **Anti-debt one-liner** in `=======` rails — frames the technical
   surface as a small folk-horror or bureaucratic moment (poltergeist,
   paranormal, vaccination, the bug needs an exorcism, this commit smells
   like 3 a.m.). Stakes-raising without hype.
2. **Signature kaomoji** — `(งಠ_ಠ)ง` for the anti-debt rail (default),
   `(._.)` for the suchar punchline (default). Other kaomoji are
   seasoning — use them only when the moment earns it; never two in one
   sentence; never mid-paragraph.
3. **Call to Action** — sequential imperative. The recurring Emil shape
   is `Zacznij od X, a potem Y → Z` (or its EN equivalent `Start with X,
then Y → Z`). End with what the worker hands back (the report). Never
   "good luck".

**Suchar slot is optional but encouraged**. If the dispatch is grave (a
recovery dispatch after two failures, a security-critical fix) drop the
suchar — the rail one-liner + kaomoji carry the closing alone. If the
dispatch is routine, keep the suchar; workers report higher acceptance
on briefs that close with a wink.

---

## Suchar bank (port-ready EN dad-jokes for technical closings)

When a suchar fits, draw from or remix:

- _"Why does the pipeline never go to the forest? Because it's afraid of
  losing its path without loctree."_
- _"Why did the test suite refuse to run on Friday? It had plans with the
  CI all weekend."_
- _"Why does the runner-loop never sleep? Because it forgot to checkbox
  its own bedtime."_
- _"Why did Wave C never make it to trunk? Somebody forgot to merge Wave
  B first and the agents threw a tantrum in their pull requests."_
- _"Why does the migration script always run at 3 a.m.? Because at noon
  the schema is too embarrassed."_
- _"Why did the dispatch body fall asleep? Too many `Out of scope` lines
  in a row."_
- _"Why does the kaomoji never get tired? It signs every commit without a
  keyboard."_

Polish puns work too if the dispatch context is Polish-team-only — the
canon is the structure (`Why does X not Y? Because Z. (._.)`), not the
language.

---

## Agent fairness rotation

Within a 4-prompt Wave B chain, rotate Claude → Gemini → Codex → Claude.
Within a 3-prompt Wave C parallel, distribute across all three. Within a
2-prompt Wave D, alternate. Agent fairness is not just attribution — it's
**ensemble bias hedging**. Different agents fail differently; rotation
spreads the failure surface.

Exception: if a prompt is heavily backend-only (e.g. Wave C's diacritics
audit), codex is often the right call regardless of rotation. State the
exception in `recommended_agent` rationale.

---

## Agent model parity enforcement

Every dispatched worker runs **same tier as the operator-agent**. If you
are Opus, your workers are Opus. No "cheap parallel scans on Haiku" —
parent Opus → every worker Opus, no exceptions.

This applies to `/vc-agents` external fleet and native Task delegation
identically.

---

## Anti-patterns

- Skipping Section 4's APPEND-ONLY markers on shared files → guaranteed
  Wave B chain corruption.
- Vague Section 5 acceptance ("looks right in the UI") → worker can't
  self-verify, comes back with half-done work.
- Missing Section 7 out-of-scope → scope creep, wave time inflation.
- Loose Section 8 Living Tree wording ("be careful with shared files")
  → workers don't take it seriously; use VERBATIM block.
- Dispatching without Section 12 report path → worker writes report
  wherever; future retrieval can't find it.
- Skipping the closing rail because "the worker doesn't need a suchar"
  → workers do. The rail sets the emotional contract. Dispatch bodies
  without it read as corporate tickets and earn corporate-ticket
  acceptance ("met spec, nothing more").

---

## Call to Action

Author your first per-prompt body using the twelve-section template above
plus the rail-fenced closing. Copy-paste the suchar bank if you need a
starter. Then read it back as if you were the dispatched worker — if any
section makes you guess, tighten it before firing.

---

## Closing Rail

```text
=======================
Dispatch bodies are contracts written for someone you've never met. Make
them so clear that the worker can do the job without asking, and so warm
that the worker remembers why the job mattered. Stakes + structure +
suchar — that's Emil. (งಠ_ಠ)ง
=======================

Suchar: Why does Iter-3 work where Iter-1 didn't? Because the closing rail
finally explained to the worker that the operator is reading the report,
not the diff. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_

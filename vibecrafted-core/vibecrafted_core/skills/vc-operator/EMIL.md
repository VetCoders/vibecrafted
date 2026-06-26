# vc-operator — Plan-shape Style Guide

> The operator's signature plan-shape. Every plan, every dispatch body, every tracker, every backlog entry under operator mode follows this style.  
> Operator declaration (2026-05-16): _"Let's establish my rule that plans ALWAYS go from [ ] → [x]"_.

Read alongside: SKILL.md, DISPATCH.md, GUIDE.md, AUTONOMY.md.

---

## Executive Summary

This guide defines the one default shape for operator plans and dispatches:

- GitHub-flavored Markdown checkboxes only for work items.
- Numbered top-level sections with a consistent phase structure.
- A decisive, warm operator voice (founder-at-9pm vibe).
- Optional scan-friendly `[signals]` preface for long plans.
- A clear “ready to paste” framing for execution agents.

---

## 1) The Signature in One Box

- [ ] Pending work item
- [x] Completed work item

GitHub-flavored Markdown checkboxes. No prose status, no numbered TODO, no “(done)” suffixes.  
The operator scans for the binary [ ] / [x]; anything else burns scan time.

---

## 2) The Five Rules

### Rule 1 — Checkboxes

Every plan, every dispatch body, every wave tracker, every stop-point handoff, every forward-plan backlog entry.  
If it's a list of work items, it's a checkbox list.

#### Acceptance (example)

- [ ] Typing in the canvas updates the provider's buffer signal.
- [ ] Selection changes propagate to selectionStart/End signals.
- [ ] Cmd/Ctrl+Z undoes 150ms-debounced edits; Shift+Cmd/Ctrl+Z redoes.
- [ ] Ring buffer caps at 200 steps; earlier steps silently dropped.
- [ ] Existing tests stay green.
- [ ] New tests cover typing flow, selection propagation, undo/redo wiring.

#### Wave tracker example

Wave B (sequential, shared canvas/provider)

- [x] B-1 editor-core — 304791be on feat/textforge-editor-core
- [x] B-2 tool-rail — ba60ef66 on feat/textforge-tool-rail
- [x] B-3 stylize — ab32a848 on feat/textforge-stylize
- [ ] B-4 inspectors — firing now, await bc2zb970r

---

### Rule 2 — Numbered Top-Level Sections

Plans begin with `## Executive Summary` followed by numbered headlines.  
The plan itself does not consist of free-form prose.

Template:

#### 1) Main Goal (1:1)

[One paragraph — what the plan delivers]

#### 2) Initial Context

[Bullets pointing to relevant repo state, prior commits, continuity]

#### 3) Actionable TODO (Checklist — Execute Sequentially)

[Phased checklist — see Rule 3]

(1:1) is a seal — used when the plan preserves source intent verbatim. Remove it if you've editorialized.

---

### Rule 3 — Sub-Headers Per Phase

Inside a numbered TODO section, use level-4 sub-headers (`####`) to mark phase transitions. The four default phases:

- Examine the Code — recon before edit (Loctree, slice, impact, find)
- Implement Changes — the actual edits
- Verify Integrity (format, lint) — local gates
- Tests (Add If Missing) — tests + smoke

Each sub-header gets its own checkbox cluster. Workers scan vertically through phases — they should see the phase boundary, not infer it.

---

### Rule 4 — Conversational Operator Voice

Decisive but warm. Like a founder typing into a chat at 9 pm, not like a corporate ticket.

Examples:

> "Don't guess: if something is not visible in code, find and confirm in the repo first."

> "Work iteratively: implement minimally but correctly; don't lose the sense of the existing runner."

> "Paste the following prompt into the execution agent. This is a ready prompt."

What this is not:

- Not corporate ("The following deliverables are required:")
- Not bullet-list-only (some lines are full sentences — let the voice land)
- Not academic ("It would be beneficial to consider...")
- Not exclamation-heavy (no hype)

The voice is the operator's own.

---

### Rule 5 — Minimal Expressive Markers

Light expressive markers (kaomoji or similar) may be used sparingly in status outputs, but never in dispatch prompt bodies.  
Used only to accent emotional tone. Avoid heavy or inappropriate usage.

---

## 3) [signals] Block (Optional but Recommended)

Long plans (>20 checklist items) open with a `[signals]` block that auto-summarizes scan-state.

Example:

    [signals]
    RED LIGHT: checklist detected (open: 17, done: 0)
    - [ ] (first 4 unchecked items pulled forward)
    - [ ] ...
    Results (when partial done):
    - [x] (first 2 checked items pulled forward — proof of progress)
    [/signals]

For plans under 20 items, skip `[signals]` — it adds noise.

---

## 4) The “READY TO COPY-PASTE” Framing

Every dispatch prompt body opens with framing that signals: ready to paste verbatim into another agent's CLI:

    Paste the following prompt into the execution agent. This is a ready prompt. Do not ask the user for missing details — take initiative, examine the repo, and propose specific changes. Preserve the 1:1 intent from the brief above.

PROMPT FOR AGENT (For Copy-Paste)

1. Task Description  
   [...]

---

## 5) The (1:1) Seal

When a plan is derived from source voice or notes without editorializing, mark sections with (1:1).

Example:

#### 1) Main Goal (1:1)

Unify the storage location for all artifacts into a single folder: .aiContext/. Implement it consistent with the current logic in runner.sh. Separate "models" from "agents".

Drop the seal when you've added inference, narrowing, or extension.

---

## 6) Anti-Patterns

- Prose status instead of checkboxes
- Numbered TODO instead of checkboxes
- Mixing checkboxes with numbered prose
- Heavy or inappropriate expressive markers
- Corporate voice
- (1:1) seal on synthesized content
- Skipping [signals] on a 30-item plan

---

## 7) Example Skeleton (Paste-Ready)

    [signals]
    RED LIGHT: checklist detected (open: 12, done: 0)
    - [ ] [first 3–4 most important pending items pulled forward]
    [/signals]

    ## Executive Summary
    [1–3 sentences: what this plan does and why now.]

    ## 1) Main Goal (1:1)
    [Source intent in one paragraph.]

    ## 2) Initial Context
    - Repo state: [current branch, SHA, last known landings]
    - Continuity: [which prior session authored this plan; which agent]
    - Reusable surfaces: [files / contracts to plug into]

    ## 3) Actionable TODO (Checklist — Execute Sequentially)

    #### Examine the Code
    - [ ] [loctree slice / find / impact directive 1]
    - [ ] [recon directive 2]

    #### Implement Changes
    - [ ] [edit / create directive 1]
    - [ ] [edit / create directive 2]

    #### Verify Integrity (format, lint)
    - [ ] Run [project-specific gate command]
    - [ ] [format / lint commands]

    #### Tests (Add If Missing)
    - [ ] [test directive 1]
    - [ ] [test directive 2]

    ## 4) Acceptance
    - [ ] [observable outcome 1]
    - [ ] [observable outcome 2]
    - [ ] All existing tests stay green.

    ## 5) Out of Scope
    - [things explicitly NOT touched in this prompt]

    ## 6) Branch + Commit + Report
    - Branch: feat/<slug> off <parent-sha>
    - Commit title: [<agent>/<workflow>] <imperative description>
    - Report: ~/artifacts/<...>/reports/<prompt-id>_<ts>_<agent>.md

    Paste the above prompt into the execution agent. This is a ready prompt. Do not ask — take initiative, examine the repo, and propose specific changes.

---

Plan [ ] → [x], numbered, voiced, sealed (1:1).

Vibecrafted. with AI Agents (c)2024–2026

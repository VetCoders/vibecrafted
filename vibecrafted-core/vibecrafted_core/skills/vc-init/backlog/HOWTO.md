# vc-init — `backlog/HOWTO.md`: `docs/backlog/` as the Fourth Perception Sense

> `vc-init` already runs three perception passes — Loctree (structure),
> session history (intentions), Ground Truth (git + .env hygiene). This
> HOWTO adds the **fourth sense**: reading `docs/backlog/` as the
> default team-readable surface for _why we chose this shape, what's
> left, where else the pattern matters_.

Read alongside the [vc-init SKILL](../SKILL.md), [vc-operator EMIL](../../vc-operator/EMIL.md),
[vc-scaffold plans HOWTO](../../vc-scaffold/plans/HOWTO.md).

---

## 1) Why the fourth sense

Loctree shows you the **what** (files, edges, hubs). Session history
shows you the **who** (which agent decided what, when). Git shows you
the **how** (diffs, commits, branches). None of them answer:

- _"Why did we pick this shape instead of the obvious alternative?"_
- _"Which adjacent surfaces benefit from the same fix?"_
- _"What's the operator's plan for the next horizon?"_

The `docs/backlog/` directory answers these. Each entry is a
**team-readable + retrieval-friendly** document that turns commit-message
"what" into pattern "why, what's next, where else this matters".

Read backlog as part of init. It's where future-you's decisions are
already documented.

---

## 2) Where the backlog lives

Repo-local under `docs/backlog/`. Each entry is its own file:

```text
<repo-root>/docs/backlog/
├── README.md                                      ← convention guide
├── 2026-05-12-executetool-file-uri-sandbox.md
├── 2026-05-12-sidebar-line-art-icon-language.md
├── 2026-05-14-global-text-input-context-menu.md
├── 2026-05-14-stylizer-pl-diacritics-pattern.md
├── 2026-05-15-text-editor-portal-plan.md           ← forward plan
└── 2026-05-16-agent-operator-dashboard.md          ← forward plan
```

Filename: `YYYY-MM-DD-<slug>.md`. One file per **pattern**, **decision**,
or **follow-up cluster** — not one file per commit.

---

## 3) Two entry shapes

### 3.a) Retro pattern (default — after a feature lands)

Captured _after_ a commit lands. Anchors to the SHA that delivered it.
Reusable: the same pattern applied to a future surface.

```markdown
# <Lesson, not symptom>

> Captured <YYYY-MM-DD> after `<branch>` <one-sentence trigger>.

Reference commit: `<short-sha>` on `<branch>`.

## Pattern delivered

- **`<file-path-1>`** — <concrete, function-level summary>.
- **`<file-path-2>`** — <concrete summary>.

## Why the pattern matters

[The principle — what general problem class this solves, beyond the
specific commit that delivered it.]

## Follow-ups worth surfacing

- **<Adjacent surface 1>**: <bulleted action items that could become
  future prompts>.
  _Scoped into [`<plan-file>`](./<plan-file>) Prompt N_ (when applicable).
- **<Adjacent surface 2>**: <bullets>.
  _Not yet scoped_ (italic note when explicitly left for later).

## Provenance

<What conversation / external reference / incident triggered the entry.>
```

### 3.b) Forward plan (before a coordinated multi-prompt rollout)

Captured _before_ a wave-shaped dispatch fires. Anchors to the
**baseline** commit the plan starts from. Still lives in
`docs/backlog/` so retrieval finds it when an agent asks _"what was the
intended end state of X?"_.

```markdown
# Plan: <Title>

> Captured <YYYY-MM-DD>. <Operator-voice paragraph: why current shape
> fails.>

Reference baseline branch: `<branch>@<sha>`.
Dispatch target: `vc-operator` on `<host>`.
Mandate: `<skill>` for every prompt.

## 1) Why the current shape fails (1:1)

[Operator's diagnosis verbatim.]

## 2) Target shape

[Diagram + structural description.]

## 3) Reusable pieces from the existing tree

[Table mapping new surface to reused surfaces.]

## 4) Out of scope for this plan

- [ ] [explicit non-goals]

## 5) N prompts for `vc-operator`

[Per-prompt outline pointing at `<artifact-root>/<plan-id>.md`.]

## 6) Dispatch order + dependencies

[Wave structure, mermaid or ASCII.]

## 7) Operator handoff

[How the plan reaches the operator-agent.]

## Close-out (added when plan lands)

Final retrospective bullet listing:

- [x] Prompt 1 → `<sha>`
- [x] Prompt 2 → `<sha>`
- ...
  Plus link to any retro entries written from the plan's discoveries.
```

Both shapes share the default `Reference commit:` (or
`Reference baseline branch:`) line so retrieval works identically
across them.

---

## 4) Canonical `Reference commit:` phrasing

The exact line:

```text
Reference commit: `<short-sha>` on `<branch>`.
```

or for forward plans:

```text
Reference baseline branch: `<branch>@<sha>`.
```

Do **not** use variants like _"Branch: x"_, _"Initial commit: y"_,
_"Based on: z"_. Retrieval grep matches the default phrasing verbatim.
Spell out the SHA on a dedicated line for the same reason.

---

## 5) Cross-linking

When a follow-up bullet in one entry has been scoped into a prompt in
a later plan entry, annotate the bullet with **"Scoped into …"** plus
a relative link to the plan file:

```markdown
- **Curate Stylize submenu**: 62 entries surface every style including
  bugs and archaeological scripts. Triage to ~15 readable defaults; move
  historical scripts behind a "Stylize · All" toggle.
  _Scoped into [`2026-05-15-text-editor-portal-plan.md`](./2026-05-15-text-editor-portal-plan.md)
  Prompt 4 (`textforge-stylize`)_.
```

For follow-ups explicitly **not** yet scoped, mark with italics:

```markdown
- **Diacritics outside Polish/Latin-1**: verify the round-trip for
  Vietnamese (`ế`, `ư̛`), Czech (`ř`, `š`), Spanish (`ñ`).
  _Not yet scoped_.
```

Silence is ambiguous; explicit notes are not.

---

## 6) How `vc-init` consumes the backlog (the fourth sense)

After Loctree + session history + Ground Truth, add a fourth pass:

```bash
# 1. Inventory the backlog
ls -la <repo-root>/docs/backlog/

# 2. Read every entry from the last 14 days
find <repo-root>/docs/backlog/ -name '*.md' -newer <14-days-ago> | \
  xargs -I{} bash -c 'echo "=== {} ===" && cat {}'

# 3. Note which entries reference the surface you're about to touch
grep -l '<file-path-or-symbol-you-need-to-edit>' <repo-root>/docs/backlog/*.md

# 4. Read the README convention guide once per session
cat <repo-root>/docs/backlog/README.md
```

If a backlog entry references the surface you're about to edit, **read
the entry before editing**. If you ignore it and re-derive a decision
the entry already settled, you've violated the convention's purpose.

---

## 7) When to write a new entry

Write a retro entry when:

- A commit landed that revealed a **pattern** you'd want to apply
  elsewhere (e.g. NFD-split-and-reattach, sandbox pre-routing).
- A commit closed a **decision** whose rationale would otherwise be lost
  (why we picked one library over another, why we kept a deprecated
  skill instead of retiring it).
- A wave or PR generated **follow-up clusters** that won't fit in the
  current PR but shouldn't be lost.

Write a forward plan entry when:

- The operator hands you a multi-prompt mandate that won't fit in one
  dispatch.
- A retro entry's follow-up clusters have aggregated enough mass to
  warrant a coordinated rollout.

Do **not** write an entry per commit. The backlog is concept-grained,
not commit-grained.

---

## 8) Anti-patterns

- **Per-commit entries**: dilutes retrieval. One concept per file.
- **Wrong filename format**: retrieval cross-walks via
  `YYYY-MM-DD-<slug>.md`; deviations get missed.
- **Editorializing in retro `Provenance` section**: that section is
  the retrieval-friendly trace of _what triggered the entry_ — keep it
  factual.
- **Forward plan without baseline commit**: workers don't know where
  to branch off.
- **Skipping the README convention guide in init**: future agents
  guess at the shape and drift from default phrasing.
- **Backlog as TODO list**: it's not. TODOs live in worker reports
  and stop-point handoffs. Backlog is for patterns + decisions + plans.

---

## 9) Why this is the fourth sense, not a separate skill

The convention is light — one directory, two shapes, one default
SHA line. It doesn't need its own skill mandate. But it **is** a
distinct perception channel from Loctree (structure), session history
(intentions), Ground Truth (state). It answers _"what did we learn
that wouldn't otherwise survive?"_ — which is exactly the question
init is supposed to answer before any edit.

Honouring the fourth sense closes the loop: every session reads the
backlog, every meaningful commit considers writing one, every plan
lands as one. The backlog becomes the **transmission belt** between
sessions, between hosts, between operators.

---

## Call to Action

After completing the first three init passes, scan `docs/backlog/`
for entries dated within the last 14 days or referencing files in
your edit scope. Read those entries before your first edit. If your
edit will land a reusable pattern, draft the retro entry in your
head before writing the code — it will tighten the implementation.

---

## Closing Rail

```text
=======================
Loctree shows what. Session history shows who. Git shows how. The backlog
shows why. Skip the backlog and you re-derive yesterday's decision in
tomorrow's wrong direction. (งಠ_ಠ)ง
=======================

Suchar: Why does the fourth sense feel like cheating? Because the previous
session already did half the work, and you just have to read it. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024–2026_

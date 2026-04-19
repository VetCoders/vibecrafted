---
name: vc-research
version: 1.3.0
description: >
  Standalone triple-agent research skill. Co-define the problem with the user,
  write a research plan, then spawn claude + codex + gemini simultaneously on the
  same questions. Three independent reports come back. Synthesize into one
  gap-free research document ready for implementation. Use whenever the team
  needs ground truth before coding: unknown APIs, architecture decisions, library
  assessment, protocol research, best-practice survey, competitive analysis,
  or any situation where one agent's perspective is not enough. Trigger phrases:
  "research this", "zbadaj to", "triple research", "research swarm", "3 agenty
  research", "gap-free research", "zbadaj przed implementacją", "co mówi
  dokumentacja", "state of the art", "SoTA research", "porównaj podejścia",
  "analyze options", "research plan", "plan researchu".
compatibility:
  tools:
    - Bash
    - Read
    - Write
    - Agent
---

# vc-research — Triple-Agent Research Swarm

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

Then launch this workflow through the command deck, not raw `skills/.../*.sh` paths:

```bash
vibecrafted <workflow> \
  --<options> <values> \
  --<parameters> <values> \
  --file '/path/to/plan.md'
```

```bash
vc-<workflow> \
  --<options> <values> \
  --<parameters> <values> \
  --prompt '<prompt>'
```

If `vc-<workflow>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab. Replace
`<workflow>` with this skill's name. Prefer `--file` for an existing plan or
artifact and `--prompt` for inline intent.

### Concrete dispatch examples

```bash
vibecrafted research --prompt 'Compare auth libraries for Tauri desktop'
vc-research --prompt 'State of the art for MCP streaming transports'
vibecrafted research --file /path/to/research-plan.md
```

<details>
<summary>Foundation Dependencies (Loaded with framework)</summary>

- [vc-loctree](../foundations/vc-loctree/SKILL.md) — primary map and structural awareness.
- [vc-aicx](../foundations/vc-aicx/SKILL.md) — primary memory and steerability index.
</details>

> One perspective is an opinion. Three perspectives are evidence.

## Purpose

Research a problem from three independent angles before writing a single line of
code. The orchestrating agent (you) co-defines the problem with the user, writes
a plan, spawns claude + codex + gemini on the same questions, then synthesizes
their findings into one gap-free research document.

This is the Research phase from vc-workflow, extracted as a standalone
skill and upgraded with triple-agent triangulation.

## When To Use

- Unknown API, protocol, or library
- Architecture decision with multiple valid approaches
- "What is the current best practice for X?"
- Library assessment (A vs B vs C)
- Integration research (how does X talk to Y?)
- Any moment where guessing would be cheaper than being wrong

Do NOT use for:

- Questions answerable by reading one file in the repo
- Problems where loctree slice + grep gives the answer in 30 seconds
- Pure implementation tasks (use vc-workflow, usually through vc-agents; use vc-delegate only for small model-agnostic
  work)

## The 6-Step Research Flow

### Step 1 — Co-define the problem

Talk with the user. Do not write a plan yet. Establish:

- **What we need to know** — the actual question, not the symptom
- **Why we need to know it** — what decision depends on this answer
- **What we already know** — priors, assumptions, prior art in the repo
- **Boundaries** — what is out of scope for this research

Output: a short problem statement (3-5 sentences) agreed with the user.

### Step 2 — Write the research plan

Create one plan file. The plan is what every agent receives. It contains:

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: vc-research
project: <repo-name>
status: in-progress
---

# Research Plan: <title>

## Problem

<the co-defined problem statement from Step 1>

## Questions

1. <specific, answerable question>
2. <specific, answerable question>
3. ...

## Mandatory tools

- loctree MCP (repo-view, slice, find, impact) — for any codebase-related questions
- Brave Search or WebSearch — for external ground truth

## Encouraged tools (agent's choice)

- Context7 (resolve-library-id → query-docs) — for library documentation
- WebFetch — for specific URLs found via search
- Codebase grep — for internal patterns (only after loctree mapping)

## Report format

Write your findings to the report file as markdown with this structure:

### Q1: <question>

**Sources**: <URLs, docs, file refs>
**Finding**: <concise answer>
**Confidence**: high / medium / low
**Evidence**: <code snippet, quote, or data>

### Q2: ...

### Synthesis

- Recommended approach: <your recommendation>
- Alternatives considered: <with tradeoffs>
- Open questions: <what you could not answer>
- Implementation notes: <concrete guidance>

## Constraints

- Append current year to search queries for freshness
- Prefer primary sources (official docs, RFCs, source code) over blog posts
- If two sources disagree, note the disagreement explicitly
- Do not hallucinate API signatures — verify them
```

Save to
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_research-plan.md`.

Plans can be split if the problem has clearly separable domains. Each agent
gets ALL plans — they are independent researchers, not specialists.

### Step 3 — Spawn triple research swarm

Canonical operator-facing launch path goes through the command deck:

```bash
PLAN="$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_research-plan.md"

vc-research --file "$PLAN"
```

The repo-owned spawn scripts remain the internal engine behind that surface. Do
not document raw `bash skills/...spawn.sh` paths as the operator entrypoint.

The launcher opens one shared Zellij research tab using `vc-research.kdl`,
keeps a common `run_id`, and starts claude + codex + gemini against the same
plan. This is intentional — divergence between reports reveals blind spots.

Research observability is mandatory.
`vc-research` is not "running" just because three panes appeared.
Immediately after spawn, the operator should get a launch card with the shared
`run_id`, plan path, report/meta paths, and the exact await command.

That launch card is the default surface.
`observe --last` is a drilldown tool, not the primary source of truth.

### Step 4 — Collect reports

Reports land in:

```
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_claude.md
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_codex.md
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_gemini.md
```

Wait for all three through the dedicated runtime helper, not by hand-rolled
snippets.
The standard operator move is:

```bash
vc-research-await --run-id <run_id>
```

If you just launched the latest research swarm and want the newest one, this is
also valid:

```bash
vc-research-await --last
```

If you need transcript-level inspection while the swarm is still running, use
the observer helpers:

```bash
vibecrafted claude observe --last
vibecrafted codex observe --last
vibecrafted gemini observe --last
```

Do not treat manual `observe --last` calls as sufficient observability for the
workflow itself. The workflow should expose its state through launch metadata,
the await helper, and durable report paths by default.

### Step 5 — Synthesize

Read all three reports. For each research question, build a truth table:

| Question | Claude | Codex | Gemini | Consensus                          |
| -------- | ------ | ----- | ------ | ---------------------------------- |
| Q1       | X      | X     | X      | agreed                             |
| Q2       | A      | A     | B      | 2:1 → A, investigate B's reasoning |
| Q3       | X      | —     | X      | gap in Codex, cross-check          |

Rules for synthesis:

- **3/3 agree** → high confidence, use as ground truth
- **2/3 agree** → likely correct, but read the dissenting report carefully — it
  may have found an edge case the others missed
- **All disagree** → the question needs refinement or the domain is genuinely
  ambiguous. Flag for user decision.
- **One agent found nothing** → gap. Check if the question was answerable.
  If yes, that agent's search strategy was weak — use the others.

### Step 6 — Produce gap-free research document

Write the final document to
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_RESEARCH.md`:

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: vc-research
project: <repo-name>
status: completed
---

# Research: <title>

## Problem

<from Step 1>

## Findings

### Q1: <question>

**Answer**: <synthesized from 3 reports>
**Confidence**: high / medium / low
**Sources**: <merged, deduplicated>
**Dissent**: <if any agent disagreed, note why>

### Q2: ...

## Architecture Decision

- **Chosen approach**: <decision>
- **Why**: <based on triangulated evidence>
- **Alternatives rejected**: <with reasons from multiple agents>

## Implementation Notes

- <concrete guidance, merged from all three reports>
- <API signatures verified across sources>
- <edge cases noted by any agent>

## Remaining Gaps

- <questions none of the three could answer>
- <areas needing hands-on experimentation>
```

Present the summary to the user. This document is the input for
vc-workflow Phase 3 (Implement) or standalone implementation.

## Pipeline Integration

vc-research can be used:

- **Standalone** — when you need research without a full ERi pipeline
- **As workflow Phase 2** — vc-workflow can delegate here instead of
  doing single-agent research
- **Before vc-partner** — when partner mode needs ground truth before
  debug session
- **Before vc-agents/vc-delegate** — research feeds implementation plans

```
         ┌─── claude ──→ report ───┐
research │                         │
  plan ──├─── codex  ──→ report ───├──→ plans/<ts>_<slug>_RESEARCH.md
         │                         │
         └─── gemini ──→ report ───┘
```

## Anti-Patterns

- Passing `claude|codex|gemini` to `vc-research` (defeats the purpose — the launcher is the swarm)
- Giving each agent different questions (they must answer the SAME questions
  independently for triangulation to work)
- Skipping synthesis and just concatenating reports (the value is in the delta)
- Researching things you can verify by reading one file (use loctree slice)
- Writing the research plan without the user (Step 1 is collaborative)
- Trusting blog posts over official documentation
- Letting agents research without loctree context (they ask wrong questions)
- Jumping straight to raw `*_spawn.sh` invocations when `*-research` already
  exists in the real shell helper surface

---

_Created by M&K (c)2024-2026 VetCoders_

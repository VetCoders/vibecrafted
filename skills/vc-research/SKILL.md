---
name: vc-research
version: 1.2.0
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
`$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_research-plan.md`.

Plans can be split if the problem has clearly separable domains. Each agent
gets ALL plans — they are independent researchers, not specialists.

### Step 3 — Spawn triple research swarm

Canonical launch path is through the portable spawn scripts:

```bash
PLAN="$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_research-plan.md"

bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/claude_spawn.sh "$PLAN" --mode research
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/codex_spawn.sh "$PLAN" --mode research
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/gemini_spawn.sh "$PLAN" --mode research
```

If your environment has the shell aliases (e.g. `claude-research`), those are convenience wrappers that point to these
exact scripts.

All three get the same plan. All three work independently. This is intentional —
divergence between reports reveals blind spots.

### Step 4 — Collect reports

Reports land in:

```
$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_claude.md
$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_codex.md
$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_research-plan_gemini.md
```

Wait for all three. Use the observe scripts:

```bash
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/observe.sh claude --last
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/observe.sh codex --last
bash $VIBECRAFTED_ROOT/skills/vc-agents/scripts/observe.sh gemini --last
```

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
`$VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_RESEARCH.md`:

```markdown
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

- Spawning only one agent (defeats the purpose — use workflow Phase 2 instead)
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

---
name: vc-workflow
version: 1.0.0
description: >
  This skill should be used when the user asks to "examine and implement",
  "research then implement", "zbadaj i zaimplementuj", "workflow", "pipeline",
  "examine → research → implement", "full workflow", "ERi pipeline", "ERi",
  "plan and implement", "analyze then build", "structured implementation",
  "przebadaj repo i zaimplementuj", or describes a task that requires
  understanding code structure before making changes. Orchestrates a
  three-phase pipeline: Examine (loctree), Research (Brave Search / web),
  Implement (subagents). Each phase feeds context to the next.
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Workflow — ERi Pipeline

## Operator Entry

Standard launcher (`vibecrafted start` / `vc-start`, then `vc-<workflow> <agent> [--prompt|--file ...]`).

```bash
vibecrafted workflow claude --prompt 'Examine auth surface and implement fixes'
vc-workflow codex --prompt 'Research SSO options then implement the best fit'
vibecrafted workflow gemini --file /path/to/research-plan.md
```

Foundation deps (loaded with framework): `vc-loctree`, `vc-aicx`.

**Examine. Research. Implement.** Three-phase pipeline that chains structural
code intelligence, ground truth research, and parallel agent delegation. Each
phase accumulates context for the next — no blind implementation.

## Pipeline Position

```
scaffold → init → [WORKFLOW] → followup → marbles → dou → decorate → hydrate → release
```

## Pipeline Overview

```
 EXAMINE (loctree)         RESEARCH (web)          IMPLEMENT (agents)
 ┌────────────────┐        ┌────────────────┐      ┌────────────────┐
 │ repo-view      │        │ Brave Search   │      │ write plans    │
 │ focus 1-3 dirs │ ─────▸ │ WebFetch docs  │ ───▸ │ spawn agents   │
 │ slice + impact │        │ Context7 libs  │      │ collect reports│
 │ find symbols   │        │ curate         │      │ review + merge │
 └────────────────┘        └────────────────┘      └────────────────┘
        ↓                          ↓                       ↓
   CONTEXT.md                 RESEARCH.md             REPORTS/*.md
```

Canonical artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/{plans,reports,tmp}/`.
`CONTEXT.md` and `RESEARCH.md` live in `plans/` as `<ts>_<slug>_CONTEXT.md` and
`<ts>_<slug>_RESEARCH.md`. `skills/vc-agents/scripts/common.sh`
`spawn_prepare_paths()` is the source of truth for day-root resolution.
Repo-local `.vibecrafted/plans` and `.vibecrafted/reports` are convenience
symlinks only.

## Phase 1 — EXAMINE

Map the codebase before touching anything. Foundation skills are the primary
sensory layer.

1. **Consume `vc-init` outputs** — read `.vibecrafted/GUIDELINES.md` and the
   situational report. If `vc-init` was not run, run it first.
2. **Deepen the map (loctree)** beyond init baseline:
   - `slice(file)` for every file likely to change (deps + consumers)
   - `impact(file)` for high-hub or deletion-candidate files
   - `find(name)` before creating any new types/functions
3. **AICX (intentions)** — `aicx extract` if previous session output is too large
   or in raw JSONL.
4. **PRView** — generate artifacts first if the workflow is part of a PR review.
5. **ScreenScribe** — consume findings if the task originated from a visual demo.

### Output: CONTEXT.md

Write to `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_CONTEXT.md`:

```markdown
---
run_id: <id>
agent: <claude|codex|gemini>
skill: vc-workflow
project: <repo>
status: completed
created: <ISO-8601>
---

# Examination: <slug>

## Repo Health

- <3-5 bullets from repo-view>

## Scope

- Target dirs: <list>
- Why: <rationale>

## Critical Files

| File | Consumers | Risk | Notes |

## Symbols Found

- <existing symbols relevant to task>

## Risk Map

- <high-impact files + mitigation>

## Decision

- [ ] Research needed (unknown APIs/patterns)
- [ ] Skip to Implement (well-understood domain)
```

### Phase Gate

Present CONTEXT.md summary. Ask: **Research or Implement?** If domain is
well-understood, skip Phase 2.

## Phase 2 — RESEARCH

For deep architectural unknowns or major investigations, **DO NOT run ad-hoc
research yourself.** Hand the questions derived from Examination off to
`vc-research` (triple-agent swarm) and consume its report.

For simple lookups (single API param, file syntax) use Brave Search / Context7 /
WebFetch directly: query `"<API> usage example <year>"`, fetch standard docs.

### Output: RESEARCH.md

```markdown
---
run_id: <id>
agent: <claude|codex|gemini>
skill: vc-workflow
project: <repo>
status: completed
created: <ISO-8601>
---

# Research: <slug>

## Questions (from Examination)

1. <question>

## Findings

### Q1: <question>

- **Source**: <URL or Context7 lib>
- **Answer**: <concise>
- **Code example**: <if applicable>

## Architectural Decision

- Chosen: <decision>
- Why: <findings-based>
- Alternatives rejected: <reasons>

## Implementation Notes

- <concrete guidance for agents>
```

### Phase Gate

Present RESEARCH.md summary. Ask: **Proceed to Implement?**

## Phase 3 — IMPLEMENT

Armed with CONTEXT.md + RESEARCH.md, delegate to parallel agents.

### Agent Plan Template

Every plan MUST include:

1. **Mandatory frontmatter** — `run_id`, `agent`, `skill (vc-workflow/vc-agents)`, etc.
2. **Pipeline context** — paste relevant sections from CONTEXT.md + RESEARCH.md.
3. **Loctree instruction preamble** (proven 98% vs 85% completeness):
   ```
   Use loctree MCP tools as your primary exploration layer:
   - repo-view(project) first for overview
   - slice(file) before modifying any file
   - find(name) before creating new symbols
   - impact(file) before deleting
   Never edit code without mapping it first.
   ```
4. **Living tree rule** — standard 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. preamble.
5. **Quality gate** — repo-specific test/lint commands.

### Spawn Pattern

Follow `vc-agents` for spawn commands (portable scripts preferred). Plans →
canonical `plans/`, reports → canonical `reports/` under
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`. Repo-local
`.vibecrafted/plans` and `.vibecrafted/reports` are convenience symlinks only.

### Review & Mandatory Marbles Escalation

After implementation agents complete:

1. Read all reports.
2. Run quality gate (`make check` or equivalent).
3. Verify against `CONTEXT.md` risk map.
4. **MANDATORY ESCALATION** — if quality gate fails or there are gaps/regressions:
   - **DO NOT STOP.** Do not present a diff summary with broken tests or known gaps.
   - Explain the gaps and immediately invoke `vc-marbles`.
   - Loop until gates are green.
5. Once converged (or if gates passed initially), present the final diff summary.

## Quick Reference

| Phase     | Tool                               | Output                          |
| --------- | ---------------------------------- | ------------------------------- |
| Examine   | loctree MCP                        | `plans/<ts>_<slug>_CONTEXT.md`  |
| Research  | brave-search + Context7 + WebFetch | `plans/<ts>_<slug>_RESEARCH.md` |
| Implement | vc-agents (portable scripts)       | `reports/*.md`                  |

## Phase Skipping

- Small fix, known domain → Examine only, implement directly
- New API/library integration → all three phases
- Refactor → Examine + Implement (no external research)
- Research only → Examine + Research (no implementation yet)

State which phases apply at pipeline start.

## Notes

- Mandatory for non-trivial multi-file feature work.
- If loctree MCP unavailable, see `references/phase-examine.md` for grep fallback.
- Brave Search comes from runtime tool surface or web search fallback, not a local wrapper directory.

## Anti-Patterns

- Implementing without Examine (blind coding)
- Researching without structural context (asking wrong questions)
- Spawning agents without loctree instruction (proven 37% less complete)
- Skipping phase gates (user must approve transitions)
- Not writing CONTEXT.md/RESEARCH.md to canonical `plans/` (context lost between phases)

## Additional Resources

- `references/phase-examine.md` — deep loctree examination patterns
- `references/phase-research.md` — research methodology, source ranking
- `references/phase-implement.md` — agent delegation with accumulated context
- `scripts/pipeline-init.sh` — initialize canonical artifact paths

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

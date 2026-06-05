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

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps. If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`/Loctree evidence is a process failure.

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
 EXAMINE (loctree)         RESEARCH (web)          IMPLEMENT (agents)      CONVERGE (marbles+polarize)
 ┌────────────────┐        ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
 │ repo-view      │        │ Brave Search   │      │ write plans    │      │ marbles: fix   │
 │ focus 1-3 dirs │ ─────▸ │ WebFetch docs  │ ───▸ │ spawn agents   │ ───▸ │ gates (P0=0)   │
 │ slice + impact │        │ Context7 libs  │      │ collect reports│      │ polarize: align│
 │ find symbols   │        │ curate         │      │ review + merge │      │ docs & product │
 └────────────────┘        └────────────────┘      └────────────────┘      └────────────────┘
        ↓                          ↓                       ↓                       ↓
   CONTEXT.md                 RESEARCH.md             REPORTS/*.md            THESIS.md
```

Canonical artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/{plans,reports,tmp}/`.
Final Markdown artifacts use `%Y-%m-%d_<org>_<repo>_<full_session_id>-<kind>.md`
(`kind=report,plan,tracker,research,...`) with matching `.transcript.log` and
`.meta.json` sidecars. `CONTEXT.md` and `RESEARCH.md` live in `plans/` as
`<ts>_<slug>_CONTEXT.md` and `<ts>_<slug>_RESEARCH.md`. `agents/scripts/common.sh`
`spawn_prepare_paths()` is the source of truth for day-root resolution.
Repo-local `.vibecrafted/plans` and `.vibecrafted/reports` are convenience
symlinks only.

## Phase 1 — EXAMINE

Map the codebase before touching anything. Foundation skills are the primary
sensory layer.

1. **Consume `vc-init` outputs** — read `AGENTS.md` and the
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
default `plans/`, reports → default `reports/` under
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`. Repo-local
`.vibecrafted/plans` and `.vibecrafted/reports` are convenience symlinks only.

### Phase 4 — CONVERGE (Marbles & Polarize)

After implementation agents complete, the code exists but may not be true or shippable.
Do not stop at implementation. Proceed through the convergence boundary:

1. **Gate Check** — Read all reports, run quality gates (`make check`), verify risk map.
2. **Code Truth (`vc-marbles`)** — If gates fail, tests are red, or the runtime path is fragile:
   - **DO NOT STOP.** Do not present a diff summary with broken tests or known gaps.
   - Invoke `vc-marbles` to loop until gates are green (P0=0) and the codebase stops lying.
3. **Product Truth (`vc-polarize`)** — Once the code is stable (gates pass), check for "conceptual smear" (e.g., conflicting docs, ambiguous public interfaces, or architectural "split brains" where two valid paths compete).
   - If the concept is smeared, run `vc-polarize --task <concept>` and let the prism band-action contract decide: `0..4 abort`, `5..8 memo`, `9..12 full pass`, `13..15 doctrine pass with regression contract`.
4. **Handoff** — Present the final diff summary and/or `THESIS.md` ready for `dou` and Release.

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

## Additional Resources

- `references/phase-examine.md` — deep loctree examination patterns
- `references/phase-research.md` — research methodology, source ranking
- `references/phase-implement.md` — agent delegation with accumulated context
- `scripts/pipeline-init.sh` — initialize default artifact paths

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

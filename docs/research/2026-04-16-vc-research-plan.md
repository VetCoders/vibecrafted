---
run_id: rsch-183346
agent: codex
skill: vc-research
project: vibecrafted
status: in-progress
---

# Research Plan: Vibecrafted Repository Ground Truth

## Problem

We need an implementation-ready understanding of what `vibecrafted` actually is today, not just what the README says it is. The repo mixes a shell/bootstrap surface, Python installer/control-plane code, and skill-driven workflow orchestration, so the key question is where the real runtime center of gravity lives and where the current shape is likely to create drag or drift. This research should separate public claims from repo truth, identify the highest-leverage structural risks, and recommend the strongest next architectural move for the current Bash/Python/Zellij-based system. Out of scope: implementing fixes, redesigning the public site, or rewriting the workflow fleet.

## Questions

1. What is the real end-to-end operator architecture of this repository from bootstrap install through command-deck usage and workflow execution?
2. Which structural risks or duplicated surfaces in the current implementation are most likely to create maintenance drag, operator confusion, or product drift?
3. Which external best practices are most relevant to the install and CLI-distribution surface here, and how well does the current repo align with them?
4. Based on repo truth plus external guidance, what target architecture should the next implementation cycle converge toward?

## Mandatory tools

- loctree MCP (`repo-view`, `tree`, `focus`, `slice`, `follow`) for structure-first repo mapping
- repo file reads for command surfaces, installer flow, tests, and docs
- web search for current external guidance and official documentation

## Encouraged tools

- targeted grep after loctree mapping
- pytest / project verification commands for runtime truth
- prior local artifacts only if they directly sharpen the current questions

## Report format

### Q1: <question>

**Sources**: <URLs, docs, file refs>
**Finding**: <concise answer>
**Confidence**: high / medium / low
**Evidence**: <code snippet, behavior, or data>

### Q2: ...

### Synthesis

- Recommended approach: <your recommendation>
- Alternatives considered: <with tradeoffs>
- Open questions: <what remains uncertain>
- Implementation notes: <concrete guidance>

## Constraints

- Append the current year to external searches for freshness
- Prefer primary sources and repo truth over secondary commentary
- If docs and implementation disagree, call that out explicitly
- Do not invent command flows or API signatures; verify them in the repo or official docs

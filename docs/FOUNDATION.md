# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Foundation

Foundation packages are infrastructure that all skills depend on.
They are not skills — they are the senses and memory of the agent layer.

## The Stack

```
 Skills (vc-workflow, vc-marbles, vc-followup, ...)
    |           |           |            |
    v           v           v            v
 Loctree     AICX      PRView     ScreenScribe
  (eyes)    (memory)   (review)     (ears)
    |           |           |            |
    +--------- Foundation Layer ---------+
```

## Loctree — Eyes

**What it does**: Structural code intelligence. Maps files, imports,
dependencies, hubs, dead code, and blast radius.

**Why it matters**: Without loctree, agents guess based on filenames.
With it, they see the dependency graph before touching anything.

**Tools**: `loct` CLI, `loctree-mcp` server

**Used by**: Every skill that reads or modifies code. `vc-init` runs
`repo-view` as its first action. `vc-workflow` runs `slice` before editing.
`vc-followup` runs `impact` before deleting.

**Install**: `make foundations` (auto-downloads v0.8.16 binary) or
[Loctree/Loctree releases](https://github.com/Loctree/Loctree/releases)

## AICX — Memory

**What it does**: Deterministic decision retrieval. Stores and indexes
prior agent sessions, decisions, and context chunks by project and time.

**Why it matters**: Agents are ephemeral. AICX gives them access to what
happened in previous sessions without relying on fuzzy recall or
multi-gigabyte context windows.

**Tools**: `aicx` CLI, `aicx-mcp` server

**Used by**: `vc-init` (history baseline), `vc-followup` (prior decisions),
`vc-research` (what was already researched), `vc-partner` (session context).

**Install**: `make foundations` (binary or cargo fallback) or
[VetCoders/ai-contexters releases](https://github.com/VetCoders/ai-contexters/releases)

## PRView — Review

**What it does**: Generates structured review artifacts from code changes.
Produces findings as JSON/markdown that other agents can consume.

**Why it matters**: Terminal output is lost. PRView creates persistent
reports that feed into followup agents and convergence loops.

**Tools**: `prview` CLI

**Used by**: `vc-review`, `vc-followup`, `vc-marbles` (as review gate).

**Install**: Binary from
[VetCoders/prview releases](https://github.com/VetCoders/prview/releases)

## ScreenScribe — Ears

**What it does**: Turns screen recordings with narration into structured
engineering findings. Bridges the gap between "it's broken" shown on
screen and a formal bug report.

**Why it matters**: Some bugs are easier to show than to type. ScreenScribe
converts narrated demos into actionable input for agent workflows.

**Tools**: `screenscribe` CLI

**Used by**: `vc-decorate` (visual verification), `vc-followup` (UI audit),
`vc-dou` (product surface check).

**Install**: `pip install screenscribe` (not yet on PyPI — install from source)

## Foundation in the Installer

`make doctor` checks foundation binaries and reports their status.
Foundation packages are optional — skills degrade gracefully without them,
but lose structural awareness (loctree), session memory (aicx),
persistent review artifacts (prview), or visual input (screenscribe).

The recommended install order:

1. 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework (`make install`)
2. Foundation binaries (`make foundations` — installs loctree + aicx)
3. Agent CLIs (claude, codex, gemini)
4. PRView (recommended for review workflows)
5. ScreenScribe (optional, for visual verification)

## Foundation vs Skills

|                | Foundation            | Skills                                   |
| -------------- | --------------------- | ---------------------------------------- |
| **What**       | Infrastructure binary | Instruction set (SKILL.md)               |
| **Where**      | System PATH           | `$VIBECRAFTED_ROOT/.vibecrafted/skills/` |
| **Updates**    | Binary releases       | `make install` or `skills-sync`          |
| **Without it** | Skill degrades        | Agent doesn't know the workflow          |
| **Example**    | loctree-mcp           | vc-workflow                              |

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. by VetCoders_

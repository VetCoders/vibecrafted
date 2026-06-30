# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Foundation

Foundation packages are infrastructure that all skills depend on.
They are not skills — they are the senses and memory of the agent layer.

## The Stack

```
 Skills (vc-workflow, vc-marbles, vc-followup, ...)
    |           |           |            |
    v           v           v            v
 Loctree     AICX      PRView     Screenscribe
  (eyes)    (intentions)   (review)     (ears)
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

**Install**: `make foundations` or the current
[Loctree/Loctree release](https://github.com/Loctree/Loctree/releases). Do not
copy a pinned version from this page; `make doctor` and the installer are the
runtime truth.

## AICX — intentions

**What it does**: Deterministic decision retrieval. Stores and indexes
prior agent sessions, decisions, and context chunks by project and time.

**Why it matters**: Agents are ephemeral. AICX gives them access to what
happened in previous sessions without relying on fuzzy recall or
multi-gigabyte context windows.

**Tools**: `aicx` CLI, `aicx-mcp` server

**Used by**: `vc-init` (history baseline), `vc-followup` (prior decisions),
`vc-research` (what was already researched), `vc-partner` (session context).

**Install**: `make foundations` (binary or cargo fallback) or
[Loctree/aicx releases](https://github.com/Loctree/aicx/releases)

## PRView — Review

**What it does**: Generates structured review artifacts from code changes.
Produces findings as JSON/markdown that other agents can consume.

**Why it matters**: Terminal output is lost. PRView creates persistent
reports that feed into followup agents and convergence loops.

**Tools**: `prview` CLI

**Used by**: `vc-review`, `vc-followup`, `vc-marbles` (as review gate).

**Install**: Binary from
[Vetcoders/prview releases](https://github.com/Vetcoders/prview/releases)

## Screenscribe — Ears

**What it does**: Turns screen recordings with narration into structured
engineering findings. Bridges the gap between "it's broken" shown on
screen and a formal bug report.

**Why it matters**: Some bugs are easier to show than to type. Screenscribe
converts narrated demos into actionable input for agent workflows.

**Tools**: `screenscribe` CLI

**Used by**: `vc-decorate` (visual verification), `vc-followup` (UI audit),
`vc-dou` (product surface check).

**Install**: use the current Screenscribe release or source install path checked
by `make doctor`. Treat this document as role guidance, not a package registry.

## Foundation in the Installer

`make doctor` checks foundation binaries and reports their status.
`loctree` and `aicx` are required foundations. Skills may still be readable
without them, but the framework is not operating in its intended mode: it has
no structural perception and no durable intention recovery.

`prview` and Screenscribe are evidence layers. They are strongly recommended
for review and runtime proof, but they do not replace the required foundation
pair: `loctree-mcp` plus `aicx-mcp`.

The recommended install order:

1. 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework (`make install`)
2. Foundation binaries (`make foundations` — installs loctree + aicx)
3. Agent CLIs (claude, codex, gemini)
4. PRView (recommended for review workflows)
5. Screenscribe (recommended for visual verification)

## Foundation vs Skills

|                | Foundation            | Skills                                   |
| -------------- | --------------------- | ---------------------------------------- |
| **What**       | Infrastructure binary | Instruction set (SKILL.md)               |
| **Where**      | System PATH           | `$VIBECRAFTED_ROOT/.vibecrafted/skills/` |
| **Updates**    | Binary releases       | `make install` or `skills-sync`          |
| **Without it** | Runtime truth is weak | Agent doesn't know the workflow          |
| **Example**    | loctree-mcp           | vc-workflow                              |

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. by Vetcoders_

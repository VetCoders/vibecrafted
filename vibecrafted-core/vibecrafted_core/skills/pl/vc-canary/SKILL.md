---
name: canary
version: 0.1.0
description: >
  Ownership catalog of a repo: sense planes via loctree, one agent per dynamic
  scope, add missing docstrings without logic changes, one supervisor commit,
  then findings report for discussion. Use when the user asks to "canary",
  "ownership catalog", "docstring sweep", "skataloguj repo", "repo atlas", or
  runs /vc-canary / vibecrafted canary.
---

<!-- fleet-imperative: v3 -->

> **Invocation for `vc-canary` (launcher `canary`)**
>
> Same three-path _shape_ as the fleet — see
> [DELEGATION_MATRIX.md](../DELEGATION_MATRIX.md):
>
> | Path                    | Literal                                    |
> | ----------------------- | ------------------------------------------ |
> | 1. User-launched worker | `vibecrafted canary <agent>`               |
> | 2. Interactive          | `/vc-canary` — execute **in this session** |
> | 3. Agent-operator       | `vibecrafted canary <agent>` via dispatch  |
>
> Root defaults to **`$PWD`**. Do not invent `vibecrafted workflow` as a stand-in.

<!-- /fleet-imperative -->

# vc-canary — ownership catalog

## Overview

Canary answers: _this repo needs a proper catalog, but first I must know
**what** to catalog._ It builds a **repo-atlas** from loctree organs (not from
`context --full`), spawns **one agent per scope** (variable N), adds missing
docstrings only, commits once, then reports findings for discussion.

## Canonical Orientation Gate

Before building the repo-atlas, consume fresh `vc-init` evidence for
the repo. If absent, run `vc-init` first — canary's ownership catalog
is only as sound as the orientation it starts from. Use
`Loctree:loctree` (repo-view, focus, slice, impact, find, follow) to
materialize the Code-Derived Application Map that seeds `scopes.json`
and the per-scope briefs. Sensing planes via raw grep, docs, or
"I remember this repo" instead of Loctree organs is a process failure —
it is exactly the `loct context --full` / `structural.files` shortcut
this skill already forbids as inventory (see Sense organ below).

## Sense organ (mandatory)

| Question                     | Organ                      | How                                    |
| ---------------------------- | -------------------------- | -------------------------------------- |
| What planes exist?           | **repo-view / agent.json** | `canary_cli repo-view` / `atlas`       |
| What files/units live there? | **snapshot** via stream    | `canary_cli atlas` → `inventory.jsonl` |
| What hurts after?            | **findings**               | atlas copies `signals.json`            |

**Forbidden as inventory:** `loct context --full` `structural.files` (hub ranking only).
**Forbidden:** loading raw multi‑MB `snapshot.json` into the model context.

## Quick Start

```bash
cd /path/to/repo
uv run --python 3.12 path/to/vc-canary/scripts/canary_cli.py atlas --refresh
# → ./.loctree/atlas/repo-atlas.json + inventory.jsonl + coverage.json
```

Interactive:

```text
/vc-canary
```

Worker:

```bash
vibecrafted canary claude --prompt 'Catalog this repo; agent pin default if unset'
```

## Pipeline

1. **ORIENT** — `loct auto` (via `atlas --refresh`); coverage receipt.
2. **SENSE** — read `repo-atlas.json` + `planes_hint` + hubs; **you** write
   `./.loctree/canary/scopes.json` and one brief per scope
   (`scopes/<id>.brief.md`). N is **not fixed** — e.g. `core`, `macos`,
   `Makefile`, `scripts`. **Scale-adaptive:** when one plane dwarfs the rest
   (loctree-suite 2026-08-20: one crate held 73% of LOC), split it along its
   own substructure into agent-honest budgets and declare what stays out as an
   explicit deferred wave (`wave` field in `scopes.json`) — deferral is a
   recorded decision, not an omission.
3. **FLEET** — 1 agent = 1 scope. Hybrid: N≤8 native; N>8 external.
   **Substrate is mechanics, not judgement:** N=1 → Living Tree; N>1 → Fleet
   Worktrees (Living Tree Rule, Mode B) — one worktree per scope branched from
   the integration base, the agent commits inside its own worktree, a
   single-thread integrator merges scope branches sequentially. Never park a
   parallel fleet in one shared checkout.
   Native subagents inherit the **parent model** (agent model parity); the
   session defaults below pin external workers only. Every scope gets its
   **own scratchpad subdirectory**, named in the brief — flat shared tmp
   filenames collided between parallel scopes (loctree-suite, 2026-08-20).
   Agent pin: user; else session defaults (claude Sonnet 5 / codex gpt-5.6-terra /
   grok-4.5). Await = **session wake** ([await-arming](../vc-dispatch/references/await-arming.md)).
4. **SETTLE** — strict merge validates every catalog unit against the language
   plugin resolved from its `file`; `diff-audit` (**no auto-revert** — examine
   why, ask operator); compile/lint via plugin; **one** commit (solo) or a
   single-thread integration of scope branches with `diff-audit` re-run on the
   integrated tree (fleet).
5. **FINDINGS** — only after the fleet fully settles: fleet edits shift line
   numbers and re-trigger incremental scans, so `loct follow` counts drift
   mid-flight (observed 4→9 dead exports inside one wave). Pin the snapshot
   fingerprint next to every quoted count. Then: notes signals × `loct follow`
   / findings.json; only confirmed.
6. **REPORT → DISCUSS → DECIDE** — no silent memex/aicx seed.

## Utility scripts

```bash
CLI="uv run --python 3.12 …/vc-canary/scripts/canary_cli.py"

$CLI snapshot-path --root .
$CLI repo-view --root .
$CLI atlas --root . --refresh
$CLI merge-catalog --root . --strict
$CLI diff-audit --root .
$CLI coverage --root .
```

All writes go under `./.loctree/` (atlas + canary). Status on stdout; data in files.

## Catalog contract at settle

`merge-catalog` loads every `plugins/*.py` contract, resolves the plugin from
each unit's `file` glob, and by default rejects the first unit that is missing a
plugin `REQUIRED_FIELDS` value or has a `kind` outside `KIND_ENUM`. Files whose
language ships no plugin (swift, make, go, java, …) validate fail-closed against
the shared required-field contract with the kind enum waived — never silently
skipped. It names the catalog file, unit index, source file, and plugin
in the error, and writes no merged output on failure. `--no-strict` is an
explicit compatibility escape hatch and prints a warning; it is never implicit.

## Dependencies

| Skill / tool                | Why                             |
| --------------------------- | ------------------------------- |
| `loct` / loctree            | snapshot + repo-view + findings |
| `vc-loctree`                | structural doctrine             |
| `vc-dispatch` await-arming  | fleet wake, not log files       |
| `vc-delegate` / `vc-agents` | hybrid native vs external       |

## Agent pin defaults (when user silent)

Prefer whichever launcher is live in the session, in order:
`claude` (Sonnet 5 class) · `codex` (gpt-5.6-terra class) · `grok` (grok-4.5).

## Common mistakes

- Using `loct-context-full.json` as the file inventory
- Fixed agent count instead of scopes from sense
- `( await > file ) &` false-armed await
- Auto-revert on bad canary diff
- Using `--no-strict` without an operator-approved compatibility reason
- Parking a parallel fleet in one shared checkout (concurrency ⇒ worktrees)
- Returning the catalog under any top-level key other than `catalog`
- Flat shared scratchpad filenames across parallel scopes
- Running FINDINGS while the fleet still edits (drifting `loct follow` counts)
- Docstringing generated / SRI-pinned / vendored artifacts — catalog, never edit

## Verify before the handoff

See [VERIFICATION_RULE.md](../VERIFICATION_RULE.md). Green gates ≠ useful catalog.
Coverage `pass: true` and non-empty inventory required before fleet.

---

_Playbook evidence: canary-sweep rev2 + codescribe/vibecrafted field runs 2026-08-09.
Skill-first atlas dogfoods loctree organs before native `loct atlas`._

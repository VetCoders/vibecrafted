---
name: vc-init
version: 4.1.0
description: >-
  Technical due diligence before stabilization. The vibe-coding weekend 
  got the app to launch. Now we find the taped-together auth, god tables, and silent 
  failures. Init equips the agent with Perception, Intentions, and Security/Stability Ground Truth.
  Trigger: "init", "initialize", "bootstrap", "daj kontekst", "zainicjuj",
  "przygotuj agenta", "start fresh with context".
---

# vc-init — Technical Due Diligence

> 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 is the ansfwer for the failure of vibe coding
> and vibe coders community (that newer grew up unfortunately)
> stuck in the 80/20 <-> 20/80 trap; look the reference:
> [VIBECRAFTED.md](https://raw.githubusercontent.com/VetCoders/vibecrafted/refs/heads/main/docs/VIBECRAFTED.md)
> "Not hating on vibe coding. It got you to launch and that matters more than most
> people admit. But I keep getting the same call from founders who built their
> product in a weekend with Cursor... and now they're stuck.
> They can't close enterprise deals. They can't pass a security review. Their Stripe
> integration works until it doesn't."

Init is **Technical Due Diligence**. We are here to stabilize. An agent sent to "fix".
Nowadays when vibe-coded codebases can overgrow the half of the google's login agent
in complexity acting without the complete initial overview is a quick way to
catastrophic failures.
Fortunately if you are opt in to use this skill with very big propability you work in
the repository where 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. methods have already overtaken the
guards of the quality.

We apply the VetCoders Axioms here: **Perception over memory** and **Intentions
retrieval over RAG**. We don't blindly load a million tokens of historical context—we
need to see what the code is _now_. We need to find what's broken on the critical
path before we touch a single line of code.

## Pipeline Position

```
scaffold → [INIT] → workflow → followup → marbles → dou → decorate → hydrate → release
           ^^^^^^
```

Init is the first real act of every session. Everything downstream depends on the quality of due diligence achieved here.

## When To Use

Execute at the start of every session, **before any implementation work**:

- **Cold start**: First session on a repo (zero prior context)
- **Resuming after break**: Stale context after 24+ hours away
- **Subagent delegation**: Agents inherit structured context
- **Structural drift**: Major changes by others since last session

If you are tempted to skip init because "it's a small task" — that is exactly when init prevents the most damage.

---

## The Triad of Diligence

### Sense 1: Intentions (over RAG)

Pull historical context from previous AI sessions for this project. We are looking
for the _why_, not just a blind dump of _how_. Understand:

- What was the original intention behind the architecture?
- What duct-tape was applied late at night to "just make it work"?

**Discipline:** AICX is an intention-retrieval engine, not a blind RAG cannon.
Retrieve the context of the decisions, then verify their current truth in Sense 2.

You have access to both `aicx` (cli) and `aicx-mcp` (stdio and streamable-http):
a) the dual mode (stdio + streamable-http) allows for flexible and versatile
integration with various AI frameworks - the streamable-http mode is particularly useful for session retrieval from remote
sources (e.g. other workstations or users' remote agents) so do not rely only on
your local retrieval having configured the remote aicx-mcp http endpoint
b) the mcp reference: - `mcp_aicx_aicx_rank`
Rank stored AI session chunks by content quality. Shows signal density, noise ratio, and quality labels (HIGH/MEDIUM/LOW/NOISE) per chunk. Use --strict
to filter noise. - `mcp_aicx_aicx_search`
Fuzzy search across stored AI session chunks. Returns quality-scored results
with matched lines. Supports Polish diacritics normalization and optional
project filtering. - `mcp_aicx_aicx_steer`
Retrieve stored chunks by steering metadata (frontmatter fields).
Filters by run_id, prompt_id, agent, kind, project, and/or date range using
sidecar metadata — no filesystem grep needed.

The full reference for the binaries can be found in the `vc-aicx` SKILL which offers
a detailed information and use-cases or simply by calling `aicx --help`.

### Sense 2: Perception (over memory)

`loctree` v0.8.16 Features

Shipping maps, reports, and runtime truth for living codebases.
Loctree is no longer just dead-code detection. It is context
extraction, structural analysis, Tauri contract verification, bundle
intelligence, artifact generation, and MCP-native codebase perception.

`loct` (cli) and `loctree-mcp` (stdio) — the primary tool for structural analysis
Each tool is a different fidelity. Use them in order of breadth:

1. The look from step back and get the thorough structural overview:

- `mcp_loctree-mcp_repo-view`
  Get repository overview: file count, LOC, languages, health
  summary, top hubs. USE THIS FIRST at the start of any AI session to
  understand the codebase.

2. The directory structure overview without noise - use when u need to
   get the overview of the project architecture:

- `mcp_loctree-mcp_tree`
  Get directory structure with LOC (lines of code) counts. Helps
  understand project layout and find large files/directories.

3. The first look into module overview:

- `mcp_loctree-mcp_focus`
  Focus on a specific directory: list files, their LOC, exports, and
  dependencies within that directory. Great for understanding a
  module or subsystem.

4. The complete holographic dependency graph for a file:

- `mcp_loctree-mcp_slice`
  Get file context: the file + all its imports + all files that
  depend on it. USE THIS BEFORE modifying any file. One call = complete
  understanding of a file's role.

5. The microscope - find the symbols, parameters, functions, types, etc.
   in the codebase (first choice before grep):

- `mcp_loctree-mcp_find`
  Find symbols, trace imports, or explore features. Modes: 'symbols'
  (default) — symbol/param search with regex. 'who-imports' — what files
  import this file (reverse deps). 'where-symbol' — where is this symbol
  defined. 'tagmap' — unified keyword search (files + crowd + dead).
  'crowd' — functional clustering around a keyword.

6. The structural signals - dead code, cycles, twins, hotspots, trace,
   commands, events, pipelines:

- `mcp_loctree-mcp_follow`
  Pursue structural signals at field level. Scopes: 'dead' — unused exports
  with nearest consumers. 'cycles' — circular imports with weakest link.
  'twins' — duplicate exports. 'hotspots' — high-importer files. 'trace' —
  trace a Tauri/IPC handler end-to-end (requires handler param).
  'commands' — Tauri FE<->BE handler coverage. 'events' — event emit/listen
  flow analysis. 'pipelines' — pipeline summary (events + commands + risks).
  'all' — dead + cycles + twins + hotspots.

7. The refactor handy tool:

- `mcp_loctree-mcp_impact`
  What breaks if you change or delete this file? Shows direct and transitive
  consumers. USE THIS BEFORE deleting or major refactor.

The cli reference:

- the full reference can be retrieved by calling `loct --help`
  and `loct [subcommand] --help`.

All tools accept `project` parameter (default: current dir).
First use auto-scans if no snapshot exists. Subsequent calls use cache.

### Sense 3: Ground Truth over intuition

- taking the previous steps as the base, we now reason about the project

#### 3a. Derive Conventions from Git History

Run 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.'s canonical git retrieval helper:

```bash
zsh -ic repo-full
```

It provides deep dive into the current repo state far beyond what
`git log` and `git status` can provide.

Fallback: `git log --oneline --decorate --graph -n 15` and `git status -sb`. Observe actual commit style.

**Due Diligence Focus:**

- Are we looking at a Prisma/SQL schema with a 35-column "User" God Table and zero indexes?
- Is there a NextAuth/Clerk setup where everyone is either "admin" or "user" with no real row-level security?
- Are `.env` files tracked in git?

#### 3b. Absorb Existing Agent Configs

- Check for and read `.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENTS.md`
- Read (if exists) `.vibecrafted/GUIDELINES.md` — the canonical cross-tool reference.
- Verify it against code. If a config file claims a command that contradicts current
  code, trust the code and update other agents' files accordingly.

---

### Sense 4: Quality Gates (optional)

While 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 methodology highly care about the best
possible standards in quality gates, there is no need to run any of them on session
init if not explicitly requested.
The `vc-init` is an entry point for upcoming tasks and the quality gates will be run
as a part of the task execution.
Running the gates in the initial session bootstrap is a waste of time and resources.

> **Future reference (coming soon):**
> Refer to **𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.'s:**
>
> - `vc-gates` foundation skill which is the main reference for the VetCoders
>   quality gates.
> - `vc-tdd` foundation skill which is the main reference for the VetCoders test
>   driven development.

**The below steps are optional. Test whether your instruments work before you start cutting.**
A green test suite on a completely broken architecture is just a faster train on the wrong tracks. We value structural truth over synthetic checks.

Locate the project's quality gate commands (tests, lints, builds).
Run each quality gate command and record the result:

```bash
# Example:
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
cargo clippy --workspace -- -D warnings 2>&1 | tail -5
```

## `.env` vars policy

- in VetCoders we never commit `.env` files to version control.
- we always add the `.env` files with variants like `.env.*`, `.env.local`, etc.
  to `.gitignore`
- we use the hardened pre-commit and pre-push hooks configurations to avoid
  commiting the `.env` files to version control by accident.
- we always appreciate direct and open reporting on env vars leaks which gives us
  the opportunity to revoke them or take any reasonable actions immediately.
- This is why we are confident that **we can** work with `.env` files locally without
  any security risks while hesitating on working with them is a potential serius
  vulnerability for security workflows in the future.

---

## Anti-Patterns

- Starting implementation without running init (blind coding)
- Claiming your's or someone else's weekend MVP architecture as "production-ready"
  without verifying.
- Assuming the Auth handles edge cases like token expiration.
- Writing "run pytest" without actually running pytest (unverified claims).
- Commiting the `.env` file in version control and the same time hesitating on
  working with it locally because "it's security risk."

---

_"Perception. Intentions. Ground truth. Then — and only then — stabilize."_

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_

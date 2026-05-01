---
name: vc-init
version: 4.2.0
description: >
  Technical due diligence before stabilization. The vibe-coding weekend
  got the app to launch. Now we find the taped-together auth, god tables, and silent
  failures. Init equips the agent with Perception, Intentions, and Security/Stability Ground Truth.
  Trigger: "init", "initialize", "bootstrap", "daj kontekst", "zainicjuj",
  "przygotuj agenta", "start fresh with context".
---

# vc-init — Technical Due Diligence

## Operator Entry

Standard launcher (`vibecrafted start` / `vc-start`, then `vc-<workflow> <agent> [--prompt|--file ...]`).
`vc-init` usually needs no extra task input — omit `--file`/`--prompt` when not
needed. Launches in native interactive mode, not headless `-p` / `exec`.

```bash
vibecrafted init claude
vc-init codex
vibecrafted init gemini --prompt 'Bootstrap context for the payments module'
```

Foundation deps (loaded with framework): `vc-loctree`, `vc-aicx`.

> 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 is the answer for the failure of vibe coding stuck in
> the 80/20 ↔ 20/80 trap. See [MANIFESTO_EN.md](https://raw.githubusercontent.com/VetCoders/vibecrafted/refs/heads/main/docs/runtime/MANIFESTO_EN.md).
> "Not hating on vibe coding. It got you to launch... but founders who built in
> a weekend with Cursor are stuck. Can't close enterprise deals. Can't pass
> security review. Their Stripe integration works until it doesn't."

Init is **Technical Due Diligence**. We are here to stabilize. Acting without a
complete initial overview on a vibe-coded codebase that overgrew half of Google's
login agent in complexity is a quick way to catastrophic failure.

We apply the VetCoders Axioms: **Perception over memory** and **Intentions
retrieval over RAG**. We don't blindly load a million tokens of historical
context — we see what the code is _now_ and find what's broken on the critical
path before touching a line.

## Pipeline Position

Init is the first important action in every session. The quality of the work
done here affects everything that follows.

## When To Use

Execute at the start of every session, **before any implementation work**:

- **Cold start** — first session on a repo (zero prior context)
- **Resume after break** — stale context after 24+ hours away
- **Subagent delegation** — agents inherit structured context
- **Structural drift** — major changes by others since last session

If tempted to skip init because "it's a small task" — that is exactly when init
prevents the most damage.

---

## The Triad of Diligence

### Sense 1 — Intentions (`aicx intents` retrieval)

Pull historical context from previous AI sessions. We seek the _why_, not a blind
dump of _how_:

- What was the original intention behind the architecture?
- What duct-tape was applied late at night to "just make it work"?

**Discipline:** AICX is an intention-retrieval engine, not a blind RAG cannon.
Retrieve the context of decisions, then verify their current truth in Sense 2.

You have access to `aicx` (CLI) and `aicx-mcp` (stdio + streamable-http). The
HTTP mode enables session retrieval from remote sources (other workstations,
remote agents) — do not rely only on local retrieval if a remote `aicx-mcp`
endpoint is configured.

Key MCP tools: `aicx_rank` (rank chunks by quality), `aicx_search` (fuzzy search
with Polish diacritics normalization), `aicx_steer` (frontmatter-filtered
retrieval by run_id/prompt_id/agent/kind/project/date).

CLI: `aicx intents -p <project> --emit json | tee intents.json`, then `jq` to
summarize. Full reference in `vc-intents` and `vc-aicx` skills, or `aicx --help`.

### Sense 2 — Perception (over memory)

`loctree-mcp` (stdio) is the primary structural tool. Use broad → specific:

1. **`repo-view`** — overview: file count, LOC, languages, health, top hubs.
   USE FIRST at start of any session.
2. **`tree`** — directory structure with LOC counts. Project layout, large files.
3. **`focus`** — directory deep-dive: files, LOC, exports, internal deps.
4. **`slice`** — file context: file + imports + dependents. USE BEFORE modifying
   any file.
5. **`find`** — symbols/imports/features. Modes: `symbols` (regex), `who-imports`
   (reverse deps), `where-symbol`, `tagmap` (files+crowd+dead), `crowd`
   (functional clustering). First choice before grep.
6. **`follow`** — structural signals: `dead`, `cycles`, `twins`, `hotspots`,
   `trace` (Tauri/IPC end-to-end), `commands` (Tauri FE↔BE), `events`,
   `pipelines`, `all`.
7. **`impact`** — what breaks if you change/delete this file (direct + transitive
   consumers). USE BEFORE deleting or major refactor.

CLI reference: `loct --help` and `loct <subcommand> --help`. All tools accept
`project` (default: cwd); first use auto-scans, subsequent calls use cache.

### Sense 3 — Ground Truth over intuition

#### 3a. Derive conventions from git history

Run the canonical helper:

```bash
zsh -ic repo-full
```

Provides deep state beyond `git log` / `git status`. Fallback:
`git log --oneline --decorate --graph -n 15` and `git status -sb`.

**Due diligence focus:**

- Prisma/SQL schema with a 35-column "User" God Table and zero indexes?
- NextAuth/Clerk where everyone is "admin" or "user" with no row-level security?
- `.env` files tracked in git?

#### 3b. Absorb existing agent configs

- Read `.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENTS.md`.
- Read `.vibecrafted/GUIDELINES.md` — canonical cross-tool reference.
- Verify against code. If a config claims a command that contradicts current
  code, trust the code and update the agent files.

#### 3c. Hunt for myliki before updating docs

A **mylik** is a plausible misread that causes documentation drift: copying a
true statement from one actor/layer/runtime into a place where it is no longer
true.

Before changing docs, topology notes, runbooks, or `.vibecrafted/GUIDELINES.md`,
separate:

- **actor** — operator, spawned agent, application user, CI, installer, runtime
- **function** — admin UI, DSN/event ingestion, local helper, deploy path, fallback
- **scope** — public Internet, tailnet, local machine, source checkout, staged install
- **truth source** — code, generated template, deployed env, live endpoint, runtime artifact

Same URL/command/file in two roles → do not merge. Operator fallback paths are
not application runtime paths. Template placeholders are not deployed values.
A code path is not a topology claim until live/runtime confirms it.

### Sense 4 — Quality Gates (optional)

Vibecraftsmanship cares deeply about quality gates, but they do **not** run at
init. Init is the entry point for upcoming tasks; gates run as part of task
execution. Running them at bootstrap wastes time and resources.

Future reference (coming soon): `vc-gates` and `vc-tdd` foundation skills.

If you do test instruments before cutting, locate the project's gate commands
and record results:

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
cargo clippy --workspace -- -D warnings 2>&1 | tail -5
```

A green test suite on a broken architecture is just a faster train on the wrong
tracks. Structural truth beats synthetic checks.

## `.env` policy

- Never commit `.env` files to version control.
- `.env*` variants (`.env.local`, `.env.production`, ...) added to `.gitignore`.
- Hardened pre-commit / pre-push hooks block accidental `.env` commits.
- Direct, open reporting on env-var leaks → fast revoke / mitigation.
- We work with `.env` files **locally** without anxiety; hesitating on local
  use is itself a future-security vulnerability (workflows degrade around it).

---

## Anti-Patterns

- Starting implementation without running init (blind coding)
- Claiming weekend MVP architecture as "production-ready" without verification
- Assuming Auth handles edge cases like token expiration
- Writing "run pytest" without actually running pytest (unverified claims)
- Committing `.env` while hesitating to work with it locally because "security risk"

---

_"Perception. Intentions. Ground truth. Then — and only then — stabilize."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

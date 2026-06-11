---
name: vc-init
version: 4.4.0
description: >
  Technical due diligence before stabilization. The vibe-coding weekend
  got the app to launch. Now we find the taped-together auth, god tables, and silent
  failures. Init equips the agent with Perception (via the MCP-first loctree
  context engine), Intentions (AICX), and Security/Stability Ground Truth.
  Trigger: "init", "initialize", "bootstrap", "daj kontekst", "zainicjuj",
  "przygotuj agenta", "start fresh with context".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching the external Vibecrafted
> fleet through the launcher. In that layer, the invocation is an imperative to
> act, not a no-op, and not native in-process subagents.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread; do not spawn another agent unless the operator
> explicitly asks you to launch, dispatch, run the fleet, or gives a concrete
> command such as `vc-init codex` / `vibecrafted init claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# vc-init — Technical Due Diligence

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Structural Gate

`vc-init` is the orientation procedure every other repo-bound workflow consumes.
It does not recurse into another init pass; it produces the repo truth that
unblocks `vc-workflow`, `vc-marbles`, `vc-review`, `vc-dou`, `vc-release`, and
delegated agent work.

`Loctree:loctree` is default for this procedure. Start from structural truth,
not README claims: repo-view, focus, slice, impact, find, and follow as relevant.
Use it to produce or refresh the Code-Derived Application Map before tests,
lint, Semgrep, release checks, docs comparison, or intent classification.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift,
runtime entrypoints, and blast-radius traps. If Loctree MCP is unavailable,
declare the degradation and fall back to `loct` CLI or manual tracing; do not
pretend grep-only discovery is the default map.

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

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

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

**MCP-first, atlas-shaped.** `loctree-mcp` is the agent's primary discovery
channel. A single `context()` call materializes the Context Atlas
(`loctree.context_atlas.v1`) — structural + runtime + risk + next-moves +
AICX overlay — into a versioned on-disk cache. Subsequent calls are instant
reads. The CLI (`loct ...`) is the **operator** surface (markdown pill,
shell pipes, interactive debugging); agents share the same engine through
MCP and are allowed to use the CLI **only if the MCP server is not**
**available**.

#### Primary call

```jsonc
// Single first move — every session
{ "tool": "context", "project": "<repo-root>", "with_aicx": true }
```

MCP **fails-fast** if `<repo-root>` lacks `.git`. The atlas materializes
seven sections (six cards + `receipt`): core, structural, runtime,
memory-trail, verification-gates, risk-register, receipt. A repo-level
answer is incomplete until **core + structural + runtime** have been read.

Scope by passing `file: "<path>"` (before edit), `task: "<text>"` (semantic
relevance), or `changed: true` (Living Tree WIP). CI guards: `no_scan`,
`fail_stale`, `fresh`. Full parameter map and atlas card index live in
[`references/loct-context-engine.md`](references/loct-context-engine.md).

#### Authority labels — read before acting

`repo_verified` (snapshot fact, top trust) · `loctree_derived` (analyzer
inference) · `aicx_operator` (sticky operator intent) · `aicx_agent` (prior
agent outcome) · `aicx_failure` (prior failed path — don't repeat) ·
`semantic_guess` (heuristic — verify) · `stale_or_unknown` (re-check).

#### Drill-down (after the atlas, when scope is known)

- `slice(file)` before edit · `impact(file)` before delete/rename ·
  `find(pattern)` instead of grep · `follow(scope)` for dead/cycles/twins/
  hotspots/trace · `focus(directory)` for module deep-dive · `query(kind,
target)` for graph queries.
- Analysis (signal, not orientation): `health` · `findings` · `audit` ·
  `doctor` · `coverage` · `manifests` · `dist` · `insights`.
- Atlas paging: `context_manifest` · `context_section` · `context_next`.

**Living Tree reflex:** before any edit window longer than a few minutes,
call `doctor()` to compare fingerprint against your last call. If it
moved, re-issue `context(fresh: true)` — that's how concurrent agents
avoid silent drift.

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
- Read `AGENTS.md` — default cross-tool reference.
- Verify against code. If a config claims a command that contradicts current
  code, trust the code and update the agent files.

#### 3c. Hunt for myliki before updating docs

A **mylik** is a plausible misread that causes documentation drift: copying a
true statement from one actor/layer/runtime into a place where it is no longer
true.

Before changing docs, topology notes, runbooks, or `AGENTS.md`,
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
- Reaching for `repo-view` + `tree` + `focus` cascade when one `context()` call
  materializes the same atlas plus risk, action, authority, and AICX overlay
- Grepping or `find -name` before calling `context()` / `find()` —
  authority labels and reverse deps are lost the moment you bypass the atlas
- Treating empty `structural` / `runtime` cards as broken — that's the atlas
  telling you to scope with `file:` or `task:`
- Skipping `doctor()` / fingerprint check during long Living Tree edits —
  multi-agent coordination silently fails when fingerprints diverge under you
- Shelling out to `loct ...` from an agent for capabilities MCP already
  exposes — split-brain between agent and operator surfaces, lost provenance

---

_"Perception. Intentions. Ground truth. Then — and only then — stabilize."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

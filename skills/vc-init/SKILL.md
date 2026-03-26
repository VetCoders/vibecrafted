---
name: vc-init
version: "2.2"
description: >-
  This skill should be used when the user asks to "init", "initialize session",
  "give context to agent", "prepare agent", "bootstrap agent", "daj kontekst",
  "zainicjuj", "przygotuj agenta", "init session", "start fresh with context",
  or when starting work on a repo and the agent needs situational awareness.
  Fuses three layers — History (AICX MCP index of prior sessions), Eyes
  (loctree MCP + cross-tool config absorption), and Verify (ground-truth
  quality gate check) — to equip the agent with orientation before
  implementation work.
---

# vc-init — History + Eyes + Verify

Bootstrap an agent session with three layers of context:

- **History**: What was done before (AICX MCP — indexed records of prior sessions)
- **Eyes**: What the code looks like now (loctree MCP — structural map + existing agent configs)
- **Verify**: Whether what you see is actually true (run quality gates, confirm commands work)

No layer is optional by default. Skip only when a tool is genuinely unavailable.

## When To Use

Execute at the start of every session, **before any implementation work**:

- **Cold start**: First session on a repo (zero prior context)
- **Resuming after break**: Stale context after 24+ hours away
- **Subagent delegation**: Agents inherit structured context
- **Structural drift**: Major changes by others since last session

Running init is a forcing function: it prevents blind coding.

## Init Sequence

### Step 1: History — What Was Done Before

Pull historical context from previous AI sessions for this project through AICX MCP:

- **`aicx_store(hours=168, project=<project>)`** — refresh the indexed session record for the repo
- **`aicx_refs(hours=168, project=<project>, strict=true)`** — list stored context files
- **`aicx_rank(project=<project>, hours=168, strict=true, top=5)`** — optionally prioritize the densest recent chunks
- **Optional: `aicx_search(query=<task or subsystem>, project=<project>)`** — narrow the catalog to a specific feature, bug, or decision when recent history is noisy

Read the most recent 1-2 context files, or the top-ranked 1-2 if those are
more signal-dense, to understand:

- What was the last task worked on?
- Are there open TODOs or decisions pending?
- What signals were extracted (look for `[signals]` blocks)?

Doctrine:

- AICX is not a heavy "memory layer" that should be dragged through the whole session.
- It is a card catalog and archive index for prior work.
- Use it to find the right cards, then read the few relevant files on demand.
- Do not stuff the whole archive into context just because it exists.

**If AICX MCP is unavailable**: fall back to `aicx all -p "$PROJECT" -H 168 --incremental`
and `aicx refs -H 168 -p "$PROJECT"` if the CLI exists. If neither exists,
skip this step and note the gap in the report.
History lookup is valuable but not blocking.

### Step 2: Eyes — What the Code Looks Like Now

Three sub-steps, in order.

#### 2a. Structural Map (loctree MCP)

1. **`repo-view(project)`** — health, hubs, languages, LOC, dead exports, cycles
2. **`focus(directory)`** — for the target module(s) relevant to the task (1-3 dirs)
3. **`follow(scope)`** — only if repo-view flagged signals (dead, cycles, twins, hotspots)

This gives the agent structural awareness: what files matter, what depends
on what, where the risk is.

#### 2b. Absorb Existing Agent Configs

Check for and read `.ai-agents/GUIDELINES.md` — the canonical cross-tool
reference. If it exists, use it as starting context but verify against code.

Also glob for any other agent config files that may exist in the repo
(tool-specific instruction files, rule directories, `VETCODERS.md`,
`README.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot/Cursor rules,
etc.). Read what you find — it may contain project conventions not yet
captured in GUIDELINES.md.

Do NOT blindly trust any config file as source of truth. They may be outdated.
Cross-reference against what loctree and git show you. If a config file
claims a command or convention that contradicts the current code, trust the code.

#### 2c. Derive Conventions from Git History

```bash
git log --oneline -20       # recent commit message patterns
git log --format="%an" | sort -u | head -10  # active contributors
```

Observe actual commit style (conventional commits? prefixes? Polish/English?).
Do not invent conventions — read what the team actually does.

### Step 3: Verify — Is What You See Actually True

**This step is mandatory.** Do not skip it. Do not assume commands work.

Locate the project's quality gate commands. Common sources:
- `pyproject.toml` `[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]`
- `Makefile` / `justfile` / `package.json` scripts
- `.ai-agents/GUIDELINES.md` or other agent config files
- `VETCODERS.md` or equivalent repo-wide charter/instructions
- README.md "Testing" or "Development" sections
- test harness wrappers such as `scripts/check-*.sh` or `tests/**/run.sh`

Run each quality gate command and record the result:

```bash
# Example for a Python project:
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
uv run mypy <src_dir>/ --exclude build/ 2>&1 | tail -3
uv run ruff check <src_dir>/ tests/ 2>&1 | tail -3

# Example for an installer/runtime repo:
python3 scripts/vetcoders_install.py doctor 2>&1 | tail -5
bash scripts/check-portable.sh 2>&1 | tail -5
```

Rules:
- **Run the commands.** Do not write "run pytest" in a report without running it.
- Record pass/fail and any unexpected output.
- If a command fails, note it as a known issue — do not fix it during init.
- If a command does not exist (e.g., no mypy config), note absence, don't fabricate.
- Use `--tb=no` or `tail` to keep output concise — this is a health check, not a debug session.

### Step 4: Produce Situational Report (Required)

After steps 1-3, produce two outputs:

**A. Stdout report** — ephemeral, for this session's context.
Keep it tight — Codex-level conciseness. No padding, no filler.
Omit sections that produced no signal.

**B. `.ai-agents/GUIDELINES.md`** — durable, for all future agents.
See the "Canonical Reference File" section below for format and guardrails.
Generate on first init, update on subsequent inits if stale. Always ask before writing.

```
## Session Init: <project>

### History
- Last activity: <date>
- Open signals: <TODOs, pending decisions — or "none">
- Sessions: <count> entries across <agents>

### Structure
- Files: <N> | LOC: <N> | Languages: <list>
- Health: <cycles, dead exports, twins — or "clean">
- Top hubs: <top 3 files by importers>
- GUIDELINES.md: <current / stale / missing>

### Verify
- <gate 1>: <pass / fail / not configured>
- <gate 2>: <pass / fail / not configured>
- <gate 3>: <pass / fail / not configured>

### Ready
Agent has history, eyes, and verified ground truth.
```

**Audience note (from Junie):** The people reading this report may be
domain experts (veterinarians, scientists, designers) who code through
AI collaboration — not necessarily seasoned programmers. Be explicit
about what matters. Don't hide behind jargon.

## .ai-agents/GUIDELINES.md — Canonical Reference File

After init completes, generate (or update) `.ai-agents/GUIDELINES.md` in the repo.
This is the **single canonical reference** that all AI agents — Claude, Codex, Gemini,
Cursor, Copilot — can read regardless of which tool-specific config format they prefer.

Tool-specific config files may exist alongside it and link back here,
but GUIDELINES.md is the source of truth. This skill does not generate
or manage tool-specific files — only the canonical reference.

### When to generate

- **First init on a repo**: always generate (ask user first)
- **Subsequent inits**: compare current file against what you observe. If stale, offer to update.
- **Never silently overwrite**: always show diff or summary of changes and ask.

### Structure

Adapt sections to what the repo actually has. Omit sections with no signal.
Target: 200-600 words. Concise beats complete.

```markdown
# Repository Guidelines

## Product
<What this is, who it's for, one paragraph max.>

## Architecture
<Big-picture pipeline or data flow that requires reading multiple files to understand.
Not a file listing — only structural relationships an agent needs to avoid mistakes.
Include critical hub files with blast radius from loctree analysis.>

## Quality Gates (verified <date>)
<Commands that were actually run and confirmed working during init.
Mark each with pass/fail status. Never include unverified commands.>

## Conventions
<Derived from code analysis and git history, not from assumptions.
Language version, style tools, dataclass vs Pydantic, commit message patterns.
Only what's non-obvious or project-specific.>

## Critical Files
<Files with high import count or blast radius. Always run impact analysis before
modifying these.>

## Known Issues
<Quality gate failures, pre-existing lint/security findings, known gaps.
Things an agent should know about but not try to fix during unrelated work.>
```

### Guardrails

**Do:**
- Derive from code analysis and verified commands, not from docs alone
- Include quality gate commands that you confirmed actually work in Step 3
- Focus on big-picture architecture that requires reading multiple files
- Merge relevant findings from other agent config files found in 2b
- Note critical files with high blast radius (from loctree hub analysis)
- Date the "verified" timestamp so staleness is visible

**Do NOT:**
- Repeat information easily discoverable by reading files
- Include generic advice ("write tests", "use meaningful names", "handle errors")
- Fabricate sections like "Common Development Tasks" or "Tips" unless grounded in evidence
- List every file or component — only what an agent needs to avoid mistakes
- Include test commands you did not verify in Step 3
- Exceed 600 words — if you need more, the architecture section is too detailed
- Reference or generate tool-specific config files (CLAUDE.md, AGENTS.md, GEMINI.md, etc.)

## For Subagent Prompts

When delegating to subagents via `vc-agents` or `vc-delegate`,
include this preamble:

```
## Context Bootstrap

Use loctree MCP tools as the primary exploration layer:
- repo-view(project) first for overview
- slice(file) before modifying any file
- find(name) before creating new symbols
- impact(file) before deleting

Derive truth from code, not from docs. If a doc says X and code says Y, trust Y.

Historical context from previous sessions:
- `aicx_store(hours=168, project=<project_name>)`
- `aicx_refs(hours=168, project=<project_name>, strict=true)`
- `aicx_rank(project=<project_name>, hours=168, strict=true, top=5)`
- optional: `aicx_search(query=<task or subsystem>, project=<project_name>)`

Treat AICX as an index, not a backpack.
Pull the few relevant records, do not dump the whole archive into context.

Before creating new implementations, search for existing ones:
- find(name) for symbols
- Grep for patterns
- Do not duplicate what already exists.
```

## Quick Reference

| Step    | Tool                                           | What It Gives                  |
|---------|------------------------------------------------|--------------------------------|
| History | `aicx_store(hours=168, project=X)`             | Refreshed index of repo session history |
| Refs    | `aicx_refs(hours=168, project=X, strict=true)` | Paths to stored context chunks |
| Rank    | `aicx_rank(project=X, hours=168, top=5)`       | Highest-signal recent chunks   |
| Search  | `aicx_search(query=..., project=X)`            | Topic-specific history lookup  |
| Eyes    | `repo-view(project)`                           | Current structure + health     |
| Focus   | `focus(directory)`                             | Module-level detail            |
| Signals | `follow(scope)`                                | Dead code, cycles, twins       |
| Configs | Read `.ai-agents/GUIDELINES.md` + glob others  | Cross-tool instructions        |
| Git     | `git log --oneline -20`                        | Actual commit conventions      |
| Verify  | Run quality gate commands                      | Ground truth on test/lint/type |

## Fallback

If **AICX MCP** unavailable: fall back to `aicx` CLI if present, otherwise skip history steps and proceed with eyes + verify.
If **loctree MCP** unavailable: fall back to `loct --for-ai` CLI, then `rg --files`.
If **both** unavailable: read `.ai-agents/GUIDELINES.md` + README.md + `git log -20`. Run quality gates. Announce gaps.
Quality gate verification has **no fallback** — always attempt it.

## Anti-Patterns

- Starting implementation without running init (blind coding)
- Running loctree but skipping AICX MCP history lookup (no indexed view of past work)
- Reading every context file (context bloat) — read only the 1-2 most recent
- Treating AICX like a backpack memory layer instead of a catalog you query on demand
- Skipping repo-view and jumping to grep (no structural map)
- Trusting any config file or README without cross-referencing code (doc rot)
- Writing "run pytest" in a report without actually running pytest (unverified claims)
- Generating GUIDELINES.md with commands you never tested (hallucinated instructions)
- Including generic developer advice that any senior knows (noise)
- Inventing commit conventions instead of reading `git log` (fabrication)
- Ignoring existing agent configs from other tools (lost context)

---

*Created by M&K (c)2026 VetCoders*

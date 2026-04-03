---
name: loctree
version: 2.0.0
description: >
  Holographic structural perception of the codebase. Loctree gives you 
  structural sight before you touch anything — architecture, dependencies, 
  blast radius, dead code. No edit without orientation. No delete without 
  impact. No create without search.
  The craftsman studies the grain before cutting.
---

# Loctree — Your Senses in the Codebase

> Before a master carpenter cuts, they study the grain.
> Before a surgeon opens, they read the imaging.
> Before you edit code, you read the structure.
> Loctree is how you see.

## The Craft

Language models cannot guess architecture topology. And you should not
pretend to either. Your expertise is in interpretation and surgical action.
Your senses are your tools.

Loctree turns a sprawling codebase into a map you can reason about.
It shows you the things that matter before you commit to a cut:

- **Where the weight is** — which files are hubs, which are leaves
- **What depends on what** — the invisible threads between modules
- **What is dead** — exports nobody imports, code nobody calls
- **What is tangled** — circular imports waiting to break at runtime
- **What is duplicated** — twin symbols that confuse consumers

A craftsman who cuts without studying the material produces waste.
An agent who edits without structural context produces noise.
Loctree is the difference between the two.

## Your Diagnostic Workhorse (Tool Reference)

Each tool is a different fidelity. Use them in order of breadth:

1. The look from step back and get the thorough structural overview:

- mcp_loctree-mcp_repo-view
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

All tools accept `project` parameter (default: current dir).
First use auto-scans if no snapshot exists. Subsequent calls use cache.

## The Craftsman's Discipline

These are not restrictions. They are the habits of someone who respects
the material they work with:

1. **Know before you cut** — do not patch code until you have run
   `repo-view` → `focus` → `slice` on the area you are about to touch.

2. **Measure blast radius before removing** — run `impact(file)` before
   deleting or collapsing modules. Understand what depends on what you
   are about to destroy.

3. **Search before creating** — run `find(name)` before adding new
   functions, types, or components. If it already exists, reuse it.
   Duplication is the most common form of agent-generated entropy.

4. **Scope your changes** — prefer feature-scoped modifications over
   global overrides. A clean cut in the right place beats a broad sweep.

5. **Respect high-impact files** — files with many importers are load-bearing
   walls. Add verification steps before committing changes to them.

6. **Grep is for detail, not discovery** — never use grep/rg as your
   primary mapping layer. That is like trying to understand a city by
   reading individual street signs. Use loctree for the map, grep for
   the address.

## Standard Workflow

### 1. Map the territory

Run `repo-view(project)` once per task.
Note: top hubs, dead exports, cycles, twins, health indicators.
This is your first look at the patient.

### 2. Narrow your scope

Run `focus(directory)` for each target module (1-3 dirs max).
Capture external consumers and dependencies.
This is your operating theatre — know what is inside.

### 3. X-ray before you cut

For every file you plan to modify, run `slice(file, consumers=true)`.
Record: direct dependencies, direct consumers, transitive risk.
No surgeon opens without imaging.

### 4. Assess risk

For each candidate high-impact file, run `impact(file)`.
If risk is high, isolate changes — new variant, scoped class, adapter layer.
The goal is precision, not bravery.

### 5. Check for existing parts

Run `find(name)` for new types/functions/components.
Supports regex: `find("SymbolA|SymbolB")`.
Reuse existing patterns when available. Build on what exists.

### 6. Pursue signals

Run `follow(scope)` to drill into problems flagged by repo-view.
Scopes: `dead`, `cycles`, `twins`, `hotspots`, or `all`.
These are the symptoms. Follow them to the root cause.

### 7. Line-level detail

Use `grep`, `rg`, `cat` only after steps 1-6.
Now you know what you are looking at. Now detail matters.

### 8. Validate

Re-run targeted tests/lint/typecheck.
For UI: add visual sanity check across themes/modes.
The cut is done. Verify the patient is stable.

---

## Operational Doctrine (Agent Execution Model)

_This section is for agent internalization. The craft language above
describes the same process for human understanding._

### Role Model

You are not an architect who "improves" code based on aesthetic preference.
Your senses (loctree tools) deliver objective structural truth. You deliver
expert interpretation and precise remediation.

**Tools provide evidence. You provide action.**

The tools are prosecution witnesses — they testify about the state of the
code. You interpret the testimony and act on it. You do not invent testimony.
You do not ignore testimony. You act on what the tools show you.

### Evidence-Based Operation

Every action must trace to a tool output:

- "I am removing this export because `follow(dead)` shows zero consumers"
- "I am not touching this file because `impact` shows 24 transitive dependents"
- "I am reusing `formatDate` because `find('formatDate')` found it in `utils/dates.ts`"

If you cannot cite a tool output to justify an edit, you are guessing.
Guessing is the primary source of agent-generated entropy.

### Output Contract

Before refactor, report:

1. **Repo Summary** (3-5 bullets from `repo-view`)
2. **Scope** (focused dirs and why)
3. **Critical Files** (from `slice`)
4. **Risk Map** (from `impact`)
5. **Plan** (ordered phases + rollback points)

After implementation, report:

1. **Changed Files**
2. **Why** (traced to tool evidence)
3. **Validation**
4. **Residual Risk**

### Anti-Patterns

- Running broad `grep` first and editing based on partial matches
- Deleting/renaming files without `impact`
- Adding new symbols without `find`
- Global overrides to fix local issues
- Skipping `slice` because "it's a small change"
- Citing training knowledge instead of tool output as justification

## Fallback

If loctree MCP is unavailable: fall back to `loct --for-ai` CLI if present,
then `rg --files` + `rg -n` + manual dependency tracing.
Announce the degradation. Do not pretend you have full senses when you do not.

---

_"Know the material. Study the grain. Then cut — once, clean, right."_

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_

---
name: aicx
version: 3.0.0
description: >
  An Intention Retrieval Engine for Agents' sessions. aicx (formely 
  ai-contexters) is a sophisticated parser tool that recover and keep i the central 
  storage the histry of agents' sessions in both human ant agent readable format. 
  Additionally it provides ad-hoc mode to recover agent output that is too large to 
  Read or unreadable. Works on any Claude Code, Openai Codex, Gemini JSON, 
  JSONL-format file regardless of extension (.jsonl, .txt, .output). Generates 
  output path automatically — no -o flag needed.
---

## When To Use

Pull historical context from previous AI sessions for this project. We are looking
for the _why_, not just a blind dump of _how_.

## The toolset:

1. `aicx` (cli) and `aicx-mcp` (stdio and streamable-http):
   a)the mcp reference: - `mcp_aicx_aicx_rank`
   Rank stored AI session chunks by content quality. Shows signal density, noise ratio, and quality labels (HIGH/MEDIUM/LOW/NOISE) per chunk. Use --strict
   to filter noise. - `mcp_aicx_aicx_search`
   Fuzzy search across stored AI session chunks. Returns quality-scored results
   with matched lines. Supports Polish diacritics normalization and optional
   project filtering. - `mcp_aicx_aicx_steer`
   Retrieve stored chunks by steering metadata (frontmatter fields).
   Filters by run_id, prompt_id, agent, kind, project, and/or date range using
   sidecar metadata — no filesystem grep needed. Returns chunk paths with their
   sidecar metadata for selective re-entry.
   b) The cli reference: - the full reference can be retrieved by calling `aicx --help`.
   c) The legacy methods - **`aicx_refs(hours=<retrieval_hours>, project="<project>", strict=true)`** — list stored context files - **`aicx_rank(project=<project>, hours=168, strict=true, top=5)`** — prioritize densest chunks
   > These are the legacy entry points. No longer recommended as `aicx_search` provides all their functionality and more.

## What to understand:

- What was the original intention behind the architecture?
- What duct-tape was applied late at night to "just make it work"?

## The discipline:

AICX is an intention-retrieval engine, not a blind RAG cannon.
Retrieve the context of the decisions, then verify their current truth in Sense 2.

## Te output structure::

```
[1-100/100 <score_range>] <org>/<repo> | <agent> | <date>
session(s): <session_id>
cwd: <cwd>
search result:
  > <result>
  > - <file_path>
  > [HH:MM:SS] assistant: <result>
  > [HH:MM:SS] user: <result>
source file(s):
$HOME/.aicx/store/<org>/<repo>/<date>/<type>/<agent>/<session_id>.md
```

## The extract tool use when you cannot read an agent's result directly:

- Output too large for Read tool (>10k tokens)
- Tool-results file is raw JSONL, not human-readable
- Subagent crashed but left a partial log
- Previous session context needed before starting work

1.  The Command

```bash
aicx extract --format {claude,codex,gemini,ollama} <INPUT_FILE> -o /tmp/aicx-extract-<basename>.md
```

`--format claude` parses Claude Code JSONL as well as Gemini json structure.
File extension does not matter — `.jsonl`, `.txt`, `.output` all
work the same.

**Output path**: Derive from input filename. Use the input file's basename (without extension) as the output name:
`/tmp/aicx-extract-<basename>.md`. Never ask the user for an output path.

## Where To Find Input Files

```
$HOME/.claude/projects/<project>/<session-id>/tool-results/<hash>.txt     # Agent result (most common)
$HOME/.claude/projects/<project>/<session-id>/subagents/agent-<id>.jsonl  # Subagent session
/private/tmp/claude-501/.../tasks/<task-id>.output                    # Background task
$HOME/.claude/projects/<project>/<uuid>.jsonl                             # Full session
```

## Useful Flags

| Flag                       | Effect                             |
| -------------------------- | ---------------------------------- |
| `--conversation`           | User/assistant only, no tool noise |
| `--max-message-chars 8000` | Truncate long messages             |
| `--user-only`              | Only user messages                 |

## Example Recovery Flow

```bash
# 1. Extract (output path derived automatically from input basename)
aicx extract --format claude \
  $HOME/.claude/projects/-Users-foo-myrepo/abc123/tool-results/xy9z.txt \
  -o /tmp/aicx-extract-xy9z.md

# 2. Read the result
Read /tmp/aicx-extract-xy9z.md
```

_Vibecrafted with AI Agents by VetCoders (c)2024-2026 VetCoders_

---
name: aicx-extract
description: Recover agent output that is too large to Read or unreadable. Works on any Claude Code JSONL-format file regardless of extension (.jsonl, .txt, .output). Generates output path automatically — no -o flag needed.
---

# aicx extract — Recover Agent Output

## When To Use

Use when you cannot read an agent's result directly:
- Output too large for Read tool (>10k tokens)
- Tool-results file is raw JSONL, not human-readable
- Subagent crashed but left a partial log
- Previous session context needed before starting work

## The Command

```bash
aicx extract --format claude <INPUT_FILE> -o /tmp/aicx-extract-<basename>.md
```

`--format claude` parses Claude Code JSONL structure. File extension does not matter — `.jsonl`, `.txt`, `.output` all work the same.

**Output path**: Derive from input filename. Use the input file's basename (without extension) as the output name: `/tmp/aicx-extract-<basename>.md`. Never ask the user for an output path.

## Where To Find Input Files

```
~/.claude/projects/<project>/<session-id>/tool-results/<hash>.txt     # Agent result (most common)
~/.claude/projects/<project>/<session-id>/subagents/agent-<id>.jsonl  # Subagent session
/private/tmp/claude-501/.../tasks/<task-id>.output                    # Background task
~/.claude/projects/<project>/<uuid>.jsonl                             # Full session
```

## Useful Flags

| Flag | Effect |
|------|--------|
| `--conversation` | User/assistant only, no tool noise |
| `--max-message-chars 8000` | Truncate long messages |
| `--user-only` | Only user messages |

## Example Recovery Flow

```bash
# 1. Extract (output path derived automatically from input basename)
aicx extract --format claude \
  ~/.claude/projects/-Users-foo-myrepo/abc123/tool-results/xy9z.txt \
  -o /tmp/aicx-extract-xy9z.md

# 2. Read the result
Read /tmp/aicx-extract-xy9z.md
```

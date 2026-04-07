---
name: vc-delegate
version: 2.0.0
description: >
  [DEPRECATED / MERGED] Native Claude subagent delegation skill.
  This skill has been merged into vc-agents (Execution Protocol).
  Use vc-agents for ALL delegation tasks, selecting the appropriate execution
  mode (Terminal vs Native Task tool) within that skill.
  Trigger phrases: "implement with agents", "delegate to subagents", "zaimplementuj",
  "run agents", "parallel tasks", "delegate safely", "native agents",
  "Task tool agents", "implement plan", "uruchom agentów", "subagenty natywne",
  "bezpieczne agenty", "implement without externals", "no osascript".
compatibility:
  tools: []
---

# vc-delegate

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

Do not launch `vc-delegate` directly. Its operator-facing replacement is:

```bash
vibecrafted <workflow> <agent> --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> --prompt '<prompt>'
```

That active workflow then delegates through `vc-agents` when external workers
are actually needed.

### Concrete dispatch examples

```bash
vibecrafted codex implement /path/to/plan.md
vibecrafted claude implement /path/to/plan.md
vc-agents gemini --file /path/to/plan.md
```

> **DEPRECATED**: This skill has been merged into `vc-agents`.
> Do not use this file anymore.

Please read `skills/vc-agents/SKILL.md` which now serves as the Unified Execution Protocol covering BOTH Terminal Agent Swarms and Native Task Delegation.

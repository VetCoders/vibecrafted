---
name: vc-justdo
version: 2.1.0
canonical: vc-implement
description: >
  Legacy alias of vc-implement — kept for agents already wired to the
  vc-justdo name. Same end-to-end autonomous implementation skill: agent takes
  ownership of the task, picks the right tools, implements properly, runs
  followup audits, loops marbles until clean, and delivers a finished surface.
  Trigger phrases (legacy): "just do", "just do it", "zrób to", "dowiez to",
  "implement this e2e", "build this properly", "I'm tired but this needs to
  ship", "full implementation", "od pomyslu do realizacji", "caly feature",
  "before tomorrow", "nie mam siły ale musi byc gotowe".
  Prefer the canonical name vc-implement going forward.
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
---

# vc-justdo — Legacy alias of `vc-implement`

> **Use `vc-implement` going forward.** This skill name is the legacy alias kept
> alive so agents (Codex, Claude, Gemini sessions, plugin marketplaces) that
> already learned `vc-justdo` keep working without disruption.

The full skill body lives at [`../vc-implement/SKILL.md`](../vc-implement/SKILL.md).
Both `vc-justdo` and `vc-implement` dispatch to the same end-to-end
implementation flow under the hood (internal skill identifier: `justdo`,
run-id prefix: `just`). The launcher accepts:

```bash
vibecrafted implement <agent>     # canonical
vibecrafted justdo <agent>        # legacy alias, identical behavior
vc-implement <agent>              # shell helper, canonical
vc-justdo <agent>                 # shell helper, legacy alias
```

Per-agent shell helpers (`codex-justdo`, `claude-justdo`, `gemini-justdo`,
`codex-skill-justdo`, …) remain in place. New helpers exposing the
canonical brand (`codex-skill-implement`, `claude-skill-implement`,
`gemini-skill-implement`) are wired to the same dispatcher.

For the full doctrine, judgment-call rules, agent-usage table, anti-patterns
and contract semantics, read [`vc-implement/SKILL.md`](../vc-implement/SKILL.md).

---

_"Not sloppy. Not ceremonial. Just done." — `vc-implement` (formerly `vc-justdo`)_

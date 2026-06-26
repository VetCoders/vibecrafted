---
description: "Cancel active Codex Marbles"
hide-from-slash-command-tool: "true"
---

# Cancel Codex Marbles

Run:

```bash
root="${CLAUDE_PLUGIN_ROOT:-runtime/vc-marbles/orchestrator}"
bash "$root/scripts/codex-loop-step.sh" cancel
```

Then report the iteration number that was cancelled and the audit file printed
by `status` if the operator asks for evidence. Cancellation is appended to
`.codex/marbles.audit.jsonl`.

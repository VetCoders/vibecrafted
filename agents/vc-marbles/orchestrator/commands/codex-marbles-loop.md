---
description: "Start a Codex interactive Marbles loop"
argument-hint: "PROMPT [--max-iterations N] [--completion-promise TEXT]"
hide-from-slash-command-tool: "true"
---

# Codex Marbles Loop

This is the Codex adaptation of the Claude Stop-hook Marbles command.

Claude has a native Stop hook that can block session exit. Codex does not expose
that same hook in this environment, so the loop is a command discipline inside
the current interactive session:

1. Initialize state with `setup-codex-loop.sh`.
2. Work normally in this same Codex session.
3. Before producing a final answer, call `codex-loop-step.sh next`.
4. If it prints `CONTINUE`, continue the same prompt in this session.
5. Only finish when the completion promise is genuinely true, then call
   `codex-loop-step.sh complete --promise '<text>'`.

Run:

```bash
"${CLAUDE_PLUGIN_ROOT:-../vibecrafted/skills/vc-marbles/orchestrator}/scripts/setup-codex-loop.sh" $ARGUMENTS
```

After setup, obey this hard rule:

```text
Do not send a final answer while .codex/marbles.local.md has active: true.
At every apparent stopping point, run:

  bash ../vibecrafted/skills/vc-marbles/orchestrator/scripts/codex-loop-step.sh next

If it prints CONTINUE, treat the printed PROMPT as the next user instruction and
keep working in the same session. If it prints STOP, you may final.
```

If a completion promise is configured, do not call `complete` unless the promise
statement is completely true.

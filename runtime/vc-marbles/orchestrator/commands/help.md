---
description: "Explain Marbles plugin and available commands"
---

# Marbles Plugin Help

Please explain the following to the user:

## What is Marbles?

Marbles implements the Ralph Wiggum technique - an iterative development methodology based on continuous AI loops,
pioneered by Geoffrey Huntley.

**Core concept:**

```bash
while :; do
  cat PROMPT.md | vc-marbles claude --continue
done
```

The same prompt is fed to the agent repeatedly. The "self-referential" aspect comes from the agent seeing its own
previous work in the files and git history, not from feeding output back as input.

**Each iteration:**

1. Agent receives the SAME prompt
2. Works on the task, modifying files
3. Tries to exit
4. Stop hook intercepts and feeds the same prompt again
5. Agent sees its previous work in the files
6. Iteratively improves until completion

The technique is described as "deterministically bad in an undeterministic world" - failures are predictable, enabling
systematic improvement through prompt tuning.

## Available Commands

### /marbles <PROMPT> [OPTIONS]

Start a Marbles in your current session.

**Usage:**

```
/marbles "Refactor the cache layer" --max-iterations 20
/marbles "Add tests" --completion-promise "TESTS COMPLETE"
```

**Options:**

- `--max-iterations <n>` - Max iterations before auto-stop
- `--completion-promise <text>` - Promise phrase to signal completion

**How it works:**

1. Creates `.claude/.marbles.local.md` state file
2. You work on the task
3. When you try to exit, stop hook intercepts
4. Same prompt fed back
5. You see your previous work
6. Continues until promise detected or max iterations

---

### /cancel-marbles

Cancel an active Marbles (removes the loop state file).

**Usage:**

```
/cancel-marbles
```

**How it works:**

- Checks for active loop state file
- Removes `.claude/.marbles.local.md`
- Reports cancellation with iteration count

---

## Key Concepts

### Completion Promises

To signal completion, the agent must output a `<promise>` tag:

```
<promise>TASK COMPLETE</promise>
```

The stop hook looks for this specific tag. Without it (or `--max-iterations`), Marbles runs infinitely.

### Self-Reference Mechanism

The "loop" doesn't mean the agent talks to itself. It means:

- Same prompt repeated
- The previous work persists in files
- Each iteration sees previous attempts
- Builds incrementally toward goal

## Example

### Interactive Bug Fix

```
/marbles "Fix the token refresh logic in auth.ts. Output <promise>FIXED</promise> when all tests pass." --completion-promise "FIXED" --max-iterations 10
```

You'll see Marbles:

- Attempt fixes
- Run tests
- See failures
- Iterate on solution
- In your current session

## When to Use Marbles

**Good for:**

- Well-defined tasks with clear success criteria
- Tasks requiring iteration and refinement
- Iterative development with self-correction
- Greenfield projects

**Not good for:**

- Tasks requiring human judgment or design decisions
- One-shot operations
- Tasks with unclear success criteria
- Debugging production issues (use targeted debugging instead)

## Learn More

- Original technique: https://ghuntley.com/ralph/
- Ralph Orchestrator: https://github.com/mikeyobrien/ralph-orchestrator

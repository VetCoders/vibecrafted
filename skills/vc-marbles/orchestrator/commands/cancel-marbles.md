---
description: "Cancel active Marbles"
allowed-tools:
  [
    "Bash(test -f .claude/marbles.local.md:*)",
    "Bash(rm .claude/marbles.local.md)",
    "Read(.claude/marbles.local.md)",
  ]
hide-from-slash-command-tool: "true"
---

# Cancel Marbles

To cancel the Marbles:

1. Check if `.claude/marbles.local.md` exists using Bash:
   `test -f .claude/marbles.local.md && echo "EXISTS" || echo "NOT_FOUND"`

2. **If NOT_FOUND**: Say "No active Marbles found."

3. **If EXISTS**:
   - Read `.claude/marbles.local.md` to get the current iteration number from the `iteration:` field
   - Remove the file using Bash: `rm .claude/marbles.local.md`
   - Report: "Cancelled Marbles (was at iteration N)" where N is the iteration value

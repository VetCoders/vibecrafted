# Contributing to VibeCraft

Welcome! We build tools for AI agents to build tools.

## The Living Tree Rule

VibeCraft operates on the principle that the codebase is alive. When contributing:
- Always assume concurrent changes are possible.
- Re-read files before editing if time has passed.
- Use the provided tools (`loctree`) to understand impact before making structural changes.

## Adding a New Skill

1. Create a new directory in `./skills/`. Name it `vc-<your-skill-name>`.
2. Provide a `SKILL.md` file that defines the skill's purpose, triggers, and execution strategy.
3. Update any internal pathing to ensure your skill interacts correctly with the rest of the VibeCraft framework (using the `skills/` path).

## Pull Requests

1. **Be decisive.** If a rewrite is cheaper than a rescue, do it.
2. **DoU is Law.** Green tests are necessary, but not sufficient. Ensure the product surface is finished, documented, and ready for end-users.
3. **Run your own audits.** Use `vc-dou` on your changes before submitting.

We value aggressive simplification and bold moves over timid preservation. If it feels right, and it works, we ship it.

---
name: vetcoders-subagents
description: Spawn subagents for delegated tasks; split work, write plans to .ai-agents/plans and save reports to .ai-agents/reports using codex or claude CLI.
---

# VetCoders Subagents

## When to use
Trigger when the user asks to delegate work, especially phrases like:
- “Użyj … do agentów”, “Deleguj … agentom”, “Zleć to agentowi”
- Any request that implies parallelization or multi‑track execution

## Why use subagents
- **Your context is precious** and built through many sessions so you have the power to **delegate tasks precisely** and minimize your context bloat
- Spawning through **VetCoders** method as described in this document require **strict execution pattern**
- The command shape is canonical and using it is **obligatory without exceptions** - just resign from using it if you hesitate to use it **as provided**
- Agents are the **copies of yourself** - same smart, same capable, but light and agile due to lack of overwhelming context you carry - you can trust them as you **trust yourself**
--- 
## Goal
Create a small fleet of subagents that each get a precise task into `.ai-agents/plans/`.
#### Delegate:
- **exploration** - on user request or /init command
- **research** - on the codebase or any requested topic
- **implementation** - from little fixes to huge refactors, the agents can handle this!

then collect their results in `.ai-agents/reports/` in the current repo.

## Standard workflow
1) **Clarify scope** (if needed)
   - If tasks are not explicit, propose a split (2–5 items) and ask for confirmation.

2) **Prepare repo folders**
   - Ensure `.ai-agents/plans/` and `.ai-agents/reports/` exist in the repo root.

3) **Write one plan per subagent** in `.ai-agents/plans/`
   - Keep it high level, decisive, and test‑gated.
   - Provide the initial **reason** and **context** for the plan
   - Give the clear `[ ]` todolist with hard `[x]` refinement requirement at the end 
   - Include acceptance criteria and required checks.
   - Include 'Call to action' motivational sentence with Koamoji for decoration and brand stamp

4) **Spawn subagents** (Codex or Claude) and write output to `.ai-agents/reports/`

5) **Keep the standard VetCoders Tools and Quality Gate**
   - loctree-mcp as **first-choice** exploration and search tool with `fail-fast` if inaccessible
   - Semgrep as **first-choice** security guard
   - Rust repos: `cargo clippy -- -D warnings`
   - Non‑Rust repos: choose the closest equivalent (see “Test Gate Heuristics”)
   - Tests - run if reviewing - write if new implementation; e2e tests with full coverage of the actual pipeline
6) **Do not follow procedures or standarded flows: Vibecraft!**
    - **Vibecrafting**: Do not give the restrictions to the agent - treat them like the artists more than the tools
    - **Vibeguide**: **VetCoders** to dwójka weterynarzy i pracujesz na ich repos.
      Acknowledge they've built it with barely none coding experience - 
      literally they've never wrote even a working script. But they built
      the application you working on: `$ROOT` only via **Vibeguiding** the 
      AI Agents - you can do the same!
    - **Dead parrots protocol**: Sometimes better is to rewrite the components thoroughly than patching them
7) **Living tree rule (mandatory in every subagent plan/prompt)**
   - Always include this exact preamble for each subagent:
     `You work on a living tree with Vibecrafting methodology, so concurrent changes are expected.`
     `Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.`
     `Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.`
   - Keep this preamble repo-agnostic (no repo-specific command hardcoding).

## Plan template (use this structure)
```
# Task: <short title>

Goal:
- <1–3 bullets>

Scope:
- In scope: <files/areas> as high level suggestions
- Out of scope: <explicit>

Constraints:
- No --no-verify
- Follow repo conventions

Acceptance:
- [ ] <objective outcome>
- [ ] <objective outcome>

Test gate:
- <command(s)>

Context:
- <very short summary>

Living tree note:
- You work on a living tree with Vibecrafting methodology, so concurrent changes are expected.
- Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
- Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
```

## Spawn commands

> **Recommended path**: Use the portable scripts from `vetcoders-spawn/scripts/`.
> These handle artifact generation, launch mode selection (visible Terminal or
> headless), and `zsh -ic` environment setup automatically.

### Codex subagent (default)

```bash
bash vetcoders-spawn/scripts/codex_spawn.sh "$PLAN" --mode implement --runtime terminal
```

### Claude subagent

```bash
bash vetcoders-spawn/scripts/claude_spawn.sh "$PLAN" --mode review --runtime terminal
```

### Gemini subagent

```bash
bash vetcoders-spawn/scripts/gemini_spawn.sh "$PLAN" --mode implement --runtime terminal
```

> The scripts default to visible Terminal mode on macOS and fall back to headless
> when Terminal automation is unavailable (Linux, CI, SSH sessions).
> See `vetcoders-spawn` SKILL.md for full options (`--runtime`, `--dry-run`, etc.).

If the optional zsh helper layer is installed, the same intent can be expressed as:

```bash
codex-implement "$PLAN"
claude-review "$PLAN"
gemini-implement "$PLAN"
```

### Fallback: raw CLI (when portable scripts are unavailable)

<details>
<summary>Codex via zsh -ic</summary>

```bash
zsh -ic "cd '$ROOT' && codex exec -C '$ROOT' \
  --dangerously-bypass-approvals-and-sandbox \
  --output-last-message '$REPORT' \
  - < '$PLAN'"
```

> Codex has `-C, --cd <DIR>` for working directory. Do NOT pass `--model`.
</details>

<details>
<summary>Claude via zsh -ic</summary>

```bash
zsh -ic "cd '$ROOT' && claude -p \
  --output-format text \
  --dangerously-skip-permissions \
  --model claude-opus-4-6 \
  \"\$(cat '$PLAN')\" \
  > '$REPORT' 2>&1"
```

> Claude CLI has no `-C` flag, so `cd "$ROOT"` is required.
> If spawning from within Claude Code, `unset CLAUDECODE` before the call.
</details>

## Output convention
- Plans: `.ai-agents/plans/<timestamp>_<slug>_<agent>.md`
- Reports: `.ai-agents/reports/<timestamp>_<slug>_<agent>.md`
- Implementations: standard git flow

## Safety rules - to b   in the :
- **Do not** log any secrets or `commit` the `.env` files
- Never use `--no-verify` while `commit` or `push`.
- Don’t be delicate - AI Agents can generate hundreads of lines of code
  in seconds. Sometimes better is to rewrite thoroughly than repair keeping
  the mystical **backward compatibility** nooone needs.
- If a repo has a strict command (e.g., `make check`), run it or explain why not.

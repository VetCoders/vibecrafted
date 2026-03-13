---
name: vetcoders-spawn
version: 1.2.0
description: >
  Spawn external subagents via the portable scripts shipped in
  vetcoders-spawn/scripts/. The real trick is an explicit spawn contract over
  zsh -ic, so each spawned agent gets a fresh interactive shell, sees the local
  CLI/runtime exactly as a user would, and writes durable report/transcript/meta
  artifacts into .ai-agents/. Terminal.app is supported as a visible mode, with
  headless mode now first-class.
  Trigger phrases: "spawn agents", "terminal agents", "spawn fleet",
  "odpal agentow", "deleguj przez terminal", "codex agents",
  "power spawn".
---

# VetCoders Spawn - External Agent Fleet via Terminal

> The power-user path. Full process isolation, visible Terminal windows, and
> durable artifacts in `.ai-agents/reports/`.
>
> Canonical path now lives in this repo under `vetcoders-spawn/scripts/`.
> Personal dotfile wrappers are optional sugar, not the source of truth.
>
> For the safe in-session alternative, see `vetcoders-implement`.

## When to use

Trigger when the user wants full isolation, long-running delegated work, or a
visible fleet in Terminal, especially for:

- parallel implementation or review tracks
- work that should survive your current context window
- Codex, Claude, or Gemini in separate processes
- observation through durable artifacts instead of chat memory

## Why this skill exists

- Your main context stays focused while subagents take bounded slices.
- The portable scripts remove dependency on one person's private dotfiles.
- The contract is explicit: terminal/visible mode is optional, headless mode is
  supported, and both use the same durable artifact outputs.
- Repo-owned scripts are easier to install, review, version, and improve.

## Goal

Create a small fleet of subagents that each get a precise task in
`.ai-agents/plans/`, then collect their results in `.ai-agents/reports/`.

Delegate:

- exploration
- research
- implementation
- review

## Standard workflow

1. Clarify scope if the task split is not explicit.
2. Ensure `.ai-agents/plans/`, `.ai-agents/reports/`, and `.ai-agents/tmp/`
   exist in the repo root.
3. Write one plan per subagent in `.ai-agents/plans/`.
4. Spawn agents through the repo-owned scripts.
5. Observe progress through metadata/transcripts.
6. Synthesize reports back into the main thread.

## Mandatory plan rules

Every subagent plan should:

- be high level, decisive, and test-gated
- include reason/context
- include a clear checkbox todo list
- include acceptance criteria
- include required checks
- end with a short call to action

## Living tree rule

Always include this exact preamble in every subagent plan or prompt:

```text
You work on a living tree with Vibecrafting methodology, so concurrent changes are expected.
Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
```

Keep this preamble repo-agnostic.

## Canonical runtime

Portable scripts now live here:

- `vetcoders-spawn/scripts/common.sh`
- `vetcoders-spawn/scripts/codex_spawn.sh`
- `vetcoders-spawn/scripts/claude_spawn.sh`
- `vetcoders-spawn/scripts/gemini_spawn.sh`
- `vetcoders-spawn/scripts/observe.sh`
- `vetcoders-spawn/scripts/install.sh`
- `vetcoders-spawn/scripts/skills_sync.sh`

The scripts generate:

- report: `.ai-agents/reports/<timestamp>_<slug>_<agent>.md`
- transcript: `.ai-agents/reports/<timestamp>_<slug>_<agent>.transcript.log`
- metadata: `.ai-agents/reports/<timestamp>_<slug>_<agent>.meta.json`
- launcher: `.ai-agents/tmp/<timestamp>_<slug>_<agent>_launch.sh`

## Canonical commands

From a repo checkout, the cleanest direct path is:

Codex:

```bash
bash vetcoders-spawn/scripts/codex_spawn.sh .ai-agents/plans/<plan>.md --mode implement --runtime terminal
```

Claude:

```bash
bash vetcoders-spawn/scripts/claude_spawn.sh .ai-agents/plans/<plan>.md --mode review --runtime terminal
```

Gemini:

```bash
bash vetcoders-spawn/scripts/gemini_spawn.sh .ai-agents/plans/<plan>.md --mode implement --runtime terminal
```

If the skill is installed into the default home paths, the installed-script path is:

Codex:

```bash
bash ~/.codex/skills/vetcoders-spawn/scripts/codex_spawn.sh .ai-agents/plans/<plan>.md --mode implement --runtime terminal
```

Claude:

```bash
bash ~/.claude/skills/vetcoders-spawn/scripts/claude_spawn.sh .ai-agents/plans/<plan>.md --mode review --runtime terminal
```

Gemini:

```bash
bash ~/.gemini/skills/vetcoders-spawn/scripts/gemini_spawn.sh .ai-agents/plans/<plan>.md --mode implement --runtime terminal
```

Observe latest Codex run:

```bash
bash ~/.codex/skills/vetcoders-spawn/scripts/observe.sh codex --last
```

If you install the optional zsh helper layer, the human-friendly wrappers are:

```bash
codex-implement .ai-agents/plans/<plan>.md
claude-review .ai-agents/plans/<plan>.md
gemini-plan .ai-agents/plans/<plan>.md
codex-prompt "Review the latest changes"
skills-sync mgbook16
skills-sync mgbook16 --with-shell
```

## Canonical launch modes

All three launchers share:

- `--runtime terminal|visible` (default): launch via visible Terminal.app
- `--runtime headless|background|detached`: launch as detached background process
- `--root <path>`: explicit repo root for `cd` and artifact staging
- `--dry-run`: generate launcher and metadata without executing it

`--runtime terminal` falls back to headless mode when Terminal automation is not
available in the current environment.

## The real trick

The important discovery is not the wrapper name. The important discovery is:

```bash
zsh -ic "cd <repo> && <agent-cli> ..."
```

That gives the spawned process an interactive shell in the chosen spawn runtime
(visible or headless), so it sees the user's real
`~/.zshrc` environment and CLI setup.

Raw example without helper wrappers:

```bash
zsh -ic "cd '/path/to/repo' && codex exec -C '/path/to/repo' --dangerously-bypass-approvals-and-sandbox --output-last-message '/path/to/report.md' - < '/path/to/plan.md'"
```

## Scope note

The repo-owned runtime currently covers:

- spawn
- artifact generation
- observe

Resume flows can remain local sugar for now if a team wants them, but they are
not required for the portable core.

By default the installer and remote sync are conservative: they do not delete
extra files inside already-installed skills. Use `--mirror` when you want a
strict 1:1 canonical copy.

## Install and distribution

The portable path now has three layers:

- `install.sh` at repo root: bootstrap for the future `curl | sh` flow
- `vetcoders-spawn/scripts/install.sh`: local install into `~/.{codex,claude,gemini}/skills`
- `vetcoders-spawn/scripts/install-shell.sh`: optional zsh helper install (`codex-implement`, `claude-implement`,
  `gemini-implement`, `*-prompt`, `*-observe`, `skills-sync`, Gemini Keychain helpers)
- `vetcoders-spawn/scripts/skills_sync.sh`: remote sync to another machine's skill homes, optionally with the same
  helper layer

The installer and remote sync now also preflight the two foundation binaries that make the whole stack feel complete:

- `aicx`
- `loctree-mcp`

`prview` is treated as a specialist companion tool, not a hard base dependency for every install.

If they are missing, install still proceeds, but the user gets the explicit next step:
`cargo install aicx loctree-mcp`

## Fallback method

Use raw `osascript` only if the portable scripts are unavailable.

Codex fallback:

```bash
osascript -e '
tell application "Terminal"
  activate
  do script "zsh -ic \"cd '\''$ROOT'\'' && codex exec -C '\''$ROOT'\'' --dangerously-bypass-approvals-and-sandbox --output-last-message '\''$REPORT'\'' - < '\''$PLAN'\''\""
end tell
'
```

## Quality gate expectations

Keep the standard VetCoders quality bar:

- loctree-mcp first for exploration when available
- semgrep first for security when available
- Rust repos: `cargo clippy -- -D warnings`
- non-Rust repos: nearest equivalent lint/type/test gate
- write and run tests for new implementation work when feasible
- if a gate is blocked, report the exact blocker and run the closest safe equivalent

## Safety rules

- Do not log secrets or commit `.env` files.
- Never use `--no-verify` for `commit` or `push`.
- Do not rewrite git history unless the user explicitly asks.
- Treat concurrent edits as normal, but still verify before overwriting.
- If the repo has a canonical gate such as `make check`, run it or explain why not.

# Quick Start

You have a repo. You have AI agents. You want them to stop breaking things and start shipping.

## 1. Install

```
git clone https://github.com/VetCoders/vc-skills.git
cd vc-skills
make install
```

The installer is interactive. It tells you what it does before it does it.
It asks before touching your shell config. Everything is reversible with `make uninstall`.

After install, open a new terminal (or `source ~/.zshrc`).

## 2. Verify

```
make doctor
```

If you see green — you're good. If something is yellow — the doctor tells you why.

## 3. Your first pipeline

Go to any git repo you're working on:

```
cd ~/your-project
```

Start a Claude Code session and say:

```
Init session
```

This runs `vc-init` — it reads your repo history, maps the structure, and runs quality gates. Your agent now knows what it's looking at instead of guessing.

## 4. Build something

```
Ship: add user authentication with JWT
```

That's it. `vc-ship` chains the entire pipeline:
- **Craft** — examines the repo, researches the approach, implements
- **Converge** — runs marbles loops until P0/P1/P2 are all zero
- **Ship** — checks product surface, decorates, hydrates for market

You can also run phases individually:

```
ERi pipeline for adding auth module     (vc-workflow)
Follow-up check                         (vc-followup)
Marbles -- loop until clean             (vc-marbles)
DoU audit -- are we shippable?          (vc-dou)
```

## 5. Spawn the fleet

When one agent isn't enough, spawn external agents in parallel:

```
codex-implement .ai-agents/plans/my-plan.md
claude-research .ai-agents/plans/my-plan.md
gemini-implement .ai-agents/plans/my-plan.md
```

Or use skill-specific shortcuts:

```
codex-dou           (Definition of Undone audit via Codex)
claude-marbles      (convergence loop via Claude)
gemini-hydrate      (market packaging via Gemini)
```

Each agent works in its own terminal. Reports land in `~/.vibecrafted/artifacts/`.

## 6. Check what they did

```
codex-observe --last
claude-observe --last
```

## 7. Keep iterating

VibeCraft is not a one-shot tool. It's a loop:

```
Build something → Check what broke → Fix it → Check again → Ship when clean
```

The framework does this for you. You provide the vision. Agents provide the labor.

---

## What you need

- macOS or Linux
- One or more AI agent CLIs: `claude`, `codex`, `gemini`
- Python 3.10+ and Git
- Optionally: `cargo` (to install loctree-mcp, aicx-mcp, prview from source)

## What you get

```
~/.vibecrafted/
  skills/        16 VibeCraft skills, readable by all your agents
  artifacts/     Plans, reports, transcripts — organized by project and date
  helpers/       Shell commands (codex-implement, claude-plan, etc.)
```

Symlinks in `~/.claude/skills/`, `~/.codex/skills/`, `~/.agents/skills/` point to the central store. Your agents read from there automatically.

## Vocabulary

| You say | Framework does |
|---------|---------------|
| "Init session" | Reads history, maps repo, runs gates |
| "Ship: ..." | Full pipeline end-to-end |
| "Follow-up check" | P0/P1/P2 triage of what's broken |
| "Marbles" | Convergence loop until clean |
| "DoU audit" | Gap analysis: code vs. shippable product |
| "Decorate" | Visual polish using your existing design tokens |
| "Hydrate" | Market packaging, SEO, distribution |

---
VibeCrafted by VetCoders | vibecrafted.io

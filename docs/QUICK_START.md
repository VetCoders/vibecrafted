# Quick Start

You have a repo. You have AI agents. You want them to stop breaking things and start shipping.

## 1. Install

```bash
curl -fsSLO https://raw.githubusercontent.com/VetCoders/vibecrafted/main/install.sh
bash install.sh
```

The bootstrap is non-destructive and stages its local control plane under `~/.vibecrafted/tools/`.
Then the orchestrator becomes interactive. It tells you what it does before it does it.
It asks before touching your shell config. Everything is reversible with `make -C ~/.vibecrafted/tools/vibecrafted-current uninstall`.

After install, open a new terminal (or `source ~/.zshrc`).

## 2. Verify

```bash
make -C ~/.vibecrafted/tools/vibecrafted-current doctor
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
Just do: add user authentication with JWT
```

That's it. `vc-justdo` chains the entire pipeline:
- **Craft** — examines the repo, researches the approach, implements
- **Converge** — runs marbles loops until P0/P1/P2 are all zero
- **Ship** — checks product surface, decorates, hydrates, releases to market

You can also run phases individually:

```
Scaffold this                           (vc-scaffold — architecture planning)
Init session                            (vc-init — context bootstrap)
ERi pipeline for adding auth module     (vc-workflow)
Follow-up check                         (vc-followup)
Marbles -- loop until clean             (vc-marbles)
DoU audit -- are we shippable?          (vc-dou)
Decorate                                (vc-decorate — visual coherence)
Hydrate                                 (vc-hydrate — packaging & SEO)
Release prep -- launch/deploy path      (vc-release)
```

## 5. Spawn the fleet

When one agent isn't enough, spawn external agents in parallel:

```
codex-implement .vibecrafted/plans/my-plan.md
claude-research .vibecrafted/plans/my-plan.md
gemini-implement .vibecrafted/plans/my-plan.md
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
  skills/        17 VibeCraft skills, readable by all your agents
  artifacts/     Plans, reports, transcripts — organized by project and date
  tools/         Staged control plane used by the bootstrap installer
  helpers/       Shell commands (codex-implement, claude-plan, etc.)
```

Symlinks in `~/.agents/skills/`, `~/.claude/skills/`, and `~/.codex/skills/` point to the central store by default. `~/.gemini/skills/` can still be added selectively.

## Vocabulary

| You say | Framework does |
|---------|---------------|
| "Init session" | Reads history, maps repo, runs gates |
| "Just do: ..." | Full pipeline end-to-end |
| "Scaffold this" | Founder-first architecture and scoping plan |
| "Release this" | Launch, deploy, and market-readiness mechanics |
| "Follow-up check" | P0/P1/P2 triage of what's broken |
| "Marbles" | Convergence loop until clean |
| "DoU audit" | Gap analysis: code vs. shippable product |
| "Decorate" | Visual polish using your existing design tokens |
| "Hydrate" | Market packaging, SEO, distribution |

---
VibeCrafted by VetCoders | vibecrafted.io

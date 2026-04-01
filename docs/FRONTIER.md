# Frontier Config — Zellij, Mise, Starship, Atuin

## What This Is

Frontier tools are optional operator enhancements that turn VibeCrafted into a cockpit.
They give you visible agent panes, smart shell prompts, searchable history, and reproducible tool versions.
**None of them are required.** VibeCrafted works the same without any of them installed.

---

## Quick Setup

```bash
# 1. Install the tools (macOS)
brew install mise zellij starship atuin

# 2. Trust the mise config (one-time per repo clone)
cd <your-vibecrafted-repo>
mise trust

# 3. Install tool versions and verify
mise install
mise run doctor

# 4. Source the VibeCrafted shell (if not already in your .bashrc or .zshrc)
#    The canonical helper lives at ~/.config/vetcoders/vc-skills.sh and auto-detects frontier tools on load.

# 5. Launch the cockpit
zellij --layout vibecrafted
```

After step 5 you have: a main pane + two agent panes, smart prompt with branch/runtime context, and fuzzy shell history. Agent spawns (`claude-implement`, etc.) auto-detect Zellij and open in panes instead of Terminal.app windows.

---

## Mise

**What it does:** Manages tool versions (Python, Node), environment variables, and task running for the repo.

### Key concepts

| Concept       | How it works                                                                                         |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| Tool versions | `mise.toml` pins Python 3.12 and Node LTS — every contributor gets the same versions                 |
| Environment   | `VIBECRAFTED_HOME` and other vars are set automatically when you `cd` into the repo                  |
| Task runner   | `mise run <task>` replaces ad-hoc scripts — `doctor`, `install`, `skills`, `list`, `frontier-config` |

### Daily use

```bash
mise trust                  # One-time: trust this repo's mise.toml
mise install                # Install pinned tool versions
mise run doctor             # Health check — verifies tools and paths
mise run list               # List available tasks
mise run frontier-config    # Show resolved frontier config paths
```

### Coexistence with Makefile

Mise and `make` coexist. The Makefile handles build/help/branded output. Mise handles tool versions, env vars, and operational tasks. Use whichever fits: `make help` for framework commands, `mise run doctor` for environment health.

---

## Zellij

**What it does:** Terminal multiplexer with named panes. VibeCrafted uses it to give each spawned agent a visible, labeled workspace.

### Starting a session

```bash
zellij --layout vibecrafted
```

This loads `config/zellij/layouts/vibecrafted.kdl` which creates:

```
┌──────────────────────┬─────────────┐
│                      │  agent-1    │
│    main (60%)        ├─────────────┤
│                      │  agent-2    │
└──────────────────────┴─────────────┘
```

- **Main pane** (left, 60%): Your working shell, focused by default
- **Agent panes** (right, 40%): Two side-by-side panes where spawned agents appear

### How agent spawn detects Zellij

When you run `claude-implement`, `codex-implement`, etc., the spawn system checks for the `ZELLIJ` environment variable. If present, agents open in Zellij panes instead of new Terminal.app windows. No configuration needed — it's automatic.

When Zellij is not running, agents fall back to Terminal.app (macOS) or background processes depending on the runtime mode.

### Navigation

| Key                      | Action                               |
| ------------------------ | ------------------------------------ |
| `Ctrl+t` then arrow keys | Switch between panes                 |
| `Ctrl+t` then `d`        | Detach session (agents keep running) |
| `zellij attach`          | Reattach to a detached session       |

---

## Starship

**What it does:** Cross-shell prompt that shows repo context at a glance — branch, dirty state, active agent, runtime, language versions.

### How it loads

The canonical `vc-skills.sh` helper auto-detects Starship on shell init. If installed, it sets `STARSHIP_CONFIG` to `config/starship.toml`. No manual config needed.

### What you see in the prompt

```
12:34:56 ~/vetcoders-skills main ⇡2 !3 +1 🐍3.12.0 ⬢22.0.0
❯
```

- **Time** — when the command ran
- **Directory** — truncated to 3 segments
- **Git branch** — with ahead/behind/diverged indicators
- **Git status** — staged (`+`), modified (`!`), deleted (`✘`)
- **Language versions** — Python (yellow), Node (green), Rust (red)
- **Agent context** — shows `VETCODERS_AGENT` and `VETCODERS_SPAWN_RUNTIME` when an agent is active

### Custom config location

```
config/starship.toml
```

Edit this file to adjust prompt format, colors, or module visibility. Changes take effect on next shell prompt.

---

## Atuin

**What it does:** Replaces default shell history with a searchable, syncable database. Fuzzy search across all sessions.

### How it loads

Like Starship, auto-detected by the canonical `vc-skills.sh` helper. Config lives at `config/atuin/config.toml`.

### Daily use

| Key      | Action                                    |
| -------- | ----------------------------------------- |
| `Ctrl+r` | Fuzzy search through history              |
| `↑`      | Browse recent commands (inline, 12 lines) |

### Key settings in the VibeCrafted config

- **Fuzzy search** with workspace filtering (searches current project first)
- **Preview** enabled — see full command before selecting (8 lines)
- **Secrets filter** on — commands with tokens/passwords excluded from history
- **Auto-sync** every 10 minutes (if sync configured)
- **Noise filtered** — `ls`, `cd`, `pwd`, `clear`, `history` excluded

---

## Frontier Config Resolution

The sidecar searches for configs in this order (first match wins):

1. `$VIBECRAFT_ROOT/config/` — if VIBECRAFT_ROOT is set
2. `<git-repo-root>/config/` — auto-detected from current directory
3. `$VIBECRAFTED_HOME/tools/vibecrafted-current/config/`
4. `$XDG_CONFIG_HOME/vetcoders/frontier/`

Check resolved paths with:

```bash
vc-frontier-paths        # Shows which configs are active
mise run frontier-config  # Same, via mise task runner
```

---

## None of This is Required

VibeCrafted works without any frontier tools. The skills, agent spawners, pipeline commands, and all framework functionality operate the same way with or without Zellij, Mise, Starship, or Atuin.

These are enhancements for operators who want the full cockpit experience:

- **Mise** removes "works on my machine" tool version drift
- **Zellij** makes agents visible instead of hidden in background processes
- **Starship** puts context in your prompt so you stop running `git status`
- **Atuin** means you never lose a command

Install any combination. Install none. VibeCrafted adapts.

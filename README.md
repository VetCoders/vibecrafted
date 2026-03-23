# VetCoders Skills

Canonical source of truth for the reusable VetCoders skill stack.

This repo exists so our skills stop drifting across:

- canonical shared store: `~/.agents/skills`
- per-agent symlink views: `~/.codex/skills`, `~/.claude/skills`, `~/.gemini/skills`

The goal is simple: one place to edit, review, version, and ship the skills,
runtime foundations, installers, and shell glue that power the VetCoders workflow.

## What This Repo Is

This is not a random backup of local skill folders.

This repo is meant to be:

- the canonical home for VetCoders skills
- the docs and install surface for the runtime foundations beneath them
- the reviewable source for shared agent instructions
- the sync source for the shared install store plus Codex, Claude, and Gemini symlink views
- the place where we enforce basic standards: no secrets, no local junk, no silent drift

## What Lives Here

### VetCoders pipeline skills

- `vetcoders-init` — session bootstrap (AICX MCP history index + loctree eyes + verify)
- `vetcoders-workflow` — ERi pipeline (Examine, Research, Implement)
- `vetcoders-followup` — post-implementation audit
- `vetcoders-marbles` — convergence loops
- `vetcoders-dou` — Definition of Undone (product surface audit)
- `vetcoders-hydrate` — packaging and go-to-market gap fill
- `vetcoders-decorate` — visual polish and micro-interactions
- `vetcoders-delegate` — in-session implementation (safe alternative when external agents are unnecessary)
- `vetcoders-partner` — executive debug + agent swarms
- `vetcoders-ownership` — full-spectrum end-to-end delivery mode
- `vetcoders-screenscribe` — screenshot analysis
- `vetcoders-agents` — external agent fleet via portable scripts
- `vetcoders-ship` — shipping orchestrator
- `vetcoders-prune` — dead code and runtime cone extraction
- `vetcoders-prview` — PR review pipeline (wraps `prview` binary)

Together, these define the current VetCoders operating model:

```text
init -> workflow -> followup -> marbles -> dou -> hydrate
                    \-> delegate / partner / agents
```

## Dependency Classification

Not every tool is required for every install. Here is the honest dependency map:

### Runtime foundations

These binaries are the substrate beneath the suite. The installer preflights
them, offers to install them, and reports clearly when they are missing.

| Tool          | What it does                                     | Install                     |
|---------------|--------------------------------------------------|-----------------------------|
| `aicx-mcp`    | AICX MCP history index + session recovery        | `cargo install ai-contexters` |
| `loctree-mcp` | Structural code mapping for agents               | `cargo install loctree-mcp` |
| `prview`      | Durable PR review artifacts and merge clarity    | `cargo install prview`      |

If they are missing, skills still install, but the suite loses real substance:

- `vetcoders-init` loses History (`aicx-mcp`) and Eyes (`loctree-mcp`)
- review surfaces lose durable artifact generation (`prview`)
- the system becomes less truthful, less inspectable, and less reusable

### Recommended ecosystem tools

| Tool                   | What it does       | When you need it                |
|------------------------|--------------------|---------------------------------|
| `codex` CLI            | OpenAI Codex agent | Spawning Codex subagents        |
| `claude` CLI           | Claude Code agent  | Spawning Claude subagents       |
| `gemini` CLI           | Gemini agent       | Spawning Gemini subagents       |
| `semgrep`              | Security scanning  | Quality gates in followup/spawn |
| `brave-search` API key | Web search         | Research phase of ERi pipeline  |

You only need the agent CLIs for the runtimes you actually use.

### Optional specialist tools

| Tool       | What it does                  | When you need it                      |
|------------|-------------------------------|---------------------------------------|
| `loct` CLI | Local loctree without MCP     | Fallback when loctree-mcp unavailable |

### System requirements

- `zsh` — spawn scripts use `zsh -ic` for interactive shell with user environment
- `rsync` — installer and remote sync
- `git` — clone and update
- `cargo` — installing runtime foundations (`ai-contexters`, `loctree-mcp`, `prview`)

## Repo Principles

### 1. Canonical beats copied

If a skill is edited in a per-agent symlink view like `~/.codex/skills` but not
brought back here, the system starts lying to us.

This repo should become the first place we update skills, and local home-folder
copies should become install targets, not hidden sources of truth.

### 2. No secrets in skill repos

If a skill needs credentials, it must read them from environment variables or a
local machine config that is outside git.

Example:

- `BRAVE_SEARCH_API_KEY` or `BRAVE_API_KEY` should come from user environment
- hardcoded demo keys are not acceptable here

### 3. No machine exhaust as canonical content

This repo should not normalize local clutter such as:

- `.DS_Store`
- `.loctree/`
- editor junk
- transient test outputs

If something is useful only on one machine, it should not become canonical just
because it was nearby when we copied a folder.

## Current Structure

```text
README.md
.gitignore
vetcoders-*/
vetcoders-agents/
docs/
vetcoders-suite-showcase.html
```

Notes:

- `docs/` and the showcase HTML were inherited from the seed copy.
- They may stay if they serve real packaging or documentation value.
- If they are just historical carry-over, they should eventually be pruned.

## Installation and Sync

The repo ships a Smart Installer (Python), optional zsh helper layer, and
remote sync helpers.

### Smart Installer

The installer is interactive when run in a terminal, non-interactive for
CI/scripting. It auto-detects system deps, agent CLIs, and runtime foundations,
then offers to install missing components with consent.

```bash
# Interactive install (full bundle, all runtimes)
bash vetcoders-agents/scripts/install.sh

# With zsh shell helpers
bash vetcoders-agents/scripts/install.sh --with-shell

# Limit to specific runtimes
bash vetcoders-agents/scripts/install.sh --tool codex --tool claude

# Install specific skills only
bash vetcoders-agents/scripts/install.sh --skill vetcoders-init --skill vetcoders-workflow

# Dry-run preview
bash vetcoders-agents/scripts/install.sh --dry-run

# Canonical mirror (deletes extra files in installed dirs)
bash vetcoders-agents/scripts/install.sh --mirror

# Non-interactive (CI/scripts)
bash vetcoders-agents/scripts/install.sh --non-interactive --with-shell
```

Or call the Python installer directly:

```bash
python3 scripts/vetcoders_install.py install [flags]
python3 scripts/vetcoders_install.py doctor
python3 scripts/vetcoders_install.py list
```

The `doctor` subcommand verifies installation health: shared store, symlink
views, stale copies, runtime foundations, and shell helpers.

The shell helper layer provides:

- `codex-implement`, `claude-review`, `gemini-plan`
- `*-prompt` and `*-observe`
- `skills-sync`
- Gemini Keychain helpers for macOS

It does **not** try to copy private shell aesthetics, banners, or unrelated aliases.

Install only the zsh helper layer:

```bash
bash vetcoders-agents/scripts/install-shell.sh
```

### Remote sync

Sync the canonical skills to another machine without copying private dotfiles:

```bash
bash vetcoders-agents/scripts/skills_sync.sh mgbook16
bash vetcoders-agents/scripts/skills_sync.sh mgbook16 --dry-run
bash vetcoders-agents/scripts/skills_sync.sh mgbook16 --mirror
bash vetcoders-agents/scripts/skills_sync.sh mgbook16 --with-shell
```

### Bootstrap installer

The repo root ships `install.sh`, the `curl | sh` entrypoint:

```bash
curl -fsSL <raw-install-url> | bash -s -- --with-shell
```

That bootstrap script clones or updates the repo into a local checkout and then
delegates to the Smart Installer. It also supports `doctor` and `list`:

```bash
bash install.sh doctor
bash install.sh list
```

If runtime foundations (`aicx-mcp`, `loctree-mcp`, `prview`) are missing, the
interactive installer offers to install them via `cargo install`. In
non-interactive mode it reports what's missing and continues.

## Portable Quality Bar

The repo now carries a first portable acceptance harness:

```bash
bash scripts/check-portable.sh
```

This checks:

- shell syntax for installers and spawn runtime
- install into a clean `HOME`
- optional zsh helper install
- headless spawn smoke with fake Codex / Claude / Gemini CLIs
- docs truth against stale `osascript`-canonical wording

## Editing Workflow

Recommended workflow:

1. Edit the canonical skill here.
2. Review the diff like normal product code.
3. Sync to the target tool homes.
4. Smoke test the trigger and the behavior in the actual agent runtime.
5. Bring improvements back here, not only into the local installed copies.

## Showcase

`vetcoders-suite-showcase.html` is good enough to be a real outward-facing
artifact, not just a local file.

My take: yes, it should probably live on `vetcoders.github.io`.

Good next shapes:

- `https://vetcoders.github.io/skills/`
- or `https://vetcoders.github.io/vetcoders-skills/`

That gives the skills suite:

- a public landing page
- a shareable explanation of the pipeline
- a cleaner bridge between "internal skill repo" and "external product surface"

## Near-Term Cleanup

The highest-leverage next moves for this repo are:

1. Decide whether `docs/` and `pdf/` are canonical or seed residue.
2. Publish and harden the new install/sync path now that the portable spawn runtime is in repo scripts.
3. Add a lightweight repo quality gate for:
    - secret scan
    - malformed `SKILL.md`
    - accidental junk files
4. Publish the showcase to GitHub Pages.

## VetCoders Context

VetCoders build through Vibecrafting, but that does not mean we should accept
chaotic skill drift.

This repo is the stonecutting step:

- shared instructions become versioned
- tool behavior becomes reviewable
- the stack becomes portable across machines and runtimes

Move fast, but make the source of truth real.

# VetCoders Skills

Canonical source of truth for the reusable VetCoders skill stack.

This repo exists so our skills stop drifting across:
- `~/.codex/skills`
- `~/.claude/skills`
- `~/.gemini/skills`

The goal is simple: one place to edit, review, version, and ship the skills that
power the VetCoders workflow.

## What This Repo Is

This is not a random backup of local skill folders.

This repo is meant to be:
- the canonical home for VetCoders skills
- the reviewable source for shared agent instructions
- the sync source for local installs in Codex, Claude, and Gemini
- the place where we enforce basic standards: no secrets, no local junk, no silent drift

## What Lives Here

### Shared foundation skills

- `ai-contexters`
- `loctree`
- `bravesearch`

These are not all "VetCoders-branded", but they are part of the practical stack
our skills depend on.

### VetCoders pipeline skills

- `vetcoders-init`
- `vetcoders-workflow`
- `vetcoders-followup`
- `vetcoders-marbles`
- `vetcoders-dou`
- `vetcoders-hydrate`
- `vetcoders-decorate`
- `vetcoders-implement`
- `vetcoders-partner`
- `vetcoders-screenscribe`
- `vetcoders-spawn`
- `vetcoders-subagents`
- `vetcoders-ship`
- `vetcoders-prune`

Together, these define the current VetCoders operating model:

```text
init -> workflow -> followup -> marbles -> dou -> hydrate
                    \-> implement / partner / spawn / subagents
```

## Repo Principles

### 1. Canonical beats copied

If a skill is edited in `~/.codex/skills` but not brought back here, the system
starts lying to us.

This repo should become the first place we update skills, and local home-folder
copies should become install targets, not hidden sources of truth.

### 2. No secrets in skill repos

If a skill needs credentials, it must read them from environment variables or a
local machine config that is outside git.

Example:
- `bravesearch/brave_search.py` now expects `BRAVE_SEARCH_API_KEY` or `BRAVE_API_KEY`
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
ai-contexters/
bravesearch/
loctree/
vetcoders-*/
vetcoders-spawn/scripts/
docs/
pdf/
vetcoders-suite-showcase.html
```

Notes:
- `docs/`, `pdf/`, and the showcase HTML were inherited from the seed copy.
- They may stay if they serve real packaging or documentation value.
- If they are just historical carry-over, they should eventually be pruned.

## Installation and Sync

The repo now ships its own portable installer and remote sync helpers.

### Local install

Install all canonical skills into Codex, Claude, and Gemini:

```bash
bash vetcoders-spawn/scripts/install.sh
```

Install only selected runtimes:

```bash
bash vetcoders-spawn/scripts/install.sh --tool codex --tool claude
```

Dry-run the install:

```bash
bash vetcoders-spawn/scripts/install.sh --dry-run
```

Canonical 1:1 mirror when you explicitly want deletions inside installed skill dirs:

```bash
bash vetcoders-spawn/scripts/install.sh --mirror
```

### Remote sync

Sync the canonical skills to another machine without copying private dotfiles:

```bash
bash vetcoders-spawn/scripts/skills_sync.sh mgbook16
```

Dry-run remote sync:

```bash
bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --dry-run
```

Canonical 1:1 remote mirror when you explicitly want deletions on the target machine:

```bash
bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --mirror
```

### Bootstrap installer

The repo root also ships `install.sh`, which is the future `curl | sh` entrypoint.
By default the installer is conservative and does not delete extra files inside already-installed skills; use `--mirror` when you want canonical 1:1 alignment.
Once the repo is public, the intended shape is:

```bash
curl -fsSL <raw-install-url> | bash
```

That bootstrap script clones or updates the repo into a local checkout and then
delegates to `vetcoders-spawn/scripts/install.sh`.

The installer also runs a foundation preflight for:
- `aicx`
- `loctree-mcp`

If they are missing, it still installs the skills, but tells the user exactly
what to add next:

```bash
cargo install aicx loctree-mcp
```

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

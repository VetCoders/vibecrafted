# Repository Guidelines

## Project Structure & Module Organization
This repository is the canonical source of truth for VetCoders skills. Each skill lives in its own directory (for example `vetcoders-partner/`, `vetcoders-spawn/`, `vetcoders-screenscribe/`) and should contain a `SKILL.md`. Some skills also include `README.md`, `scripts/`, or `evals/` when they need helper tooling or validation data. Shared foundation skills live alongside VetCoders-branded ones (`ai-contexters/`, `loctree/`, `bravesearch/`). Packaging artifacts live in `docs/` and `vetcoders-suite-showcase.html`.

## Build, Test, and Development Commands
- `bash vetcoders-spawn/scripts/install.sh` — install canonical skills into local Codex/Claude/Gemini homes.
- `bash vetcoders-spawn/scripts/install.sh --dry-run` — preview install actions without changing anything.
- `bash vetcoders-spawn/scripts/install.sh --tool codex --tool claude` — install only selected runtimes.
- `bash vetcoders-spawn/scripts/skills_sync.sh mgbook16 --dry-run` — preview remote sync to another machine.
- `bash install.sh --checkout "$HOME/.local/share/vetcoders-skills"` — bootstrap a fresh local checkout, then run the installer.

## Coding Style & Naming Conventions
Keep skill folders kebab-case and aligned with trigger names, for example `vetcoders-partner`. `SKILL.md` is the required entrypoint; keep it concise, operational, and free of machine-specific paths unless absolutely necessary. Shell scripts should be portable Bash with `set -euo pipefail`. Prefer explicit examples over prose. Do not commit secrets, API keys, `.DS_Store`, or local tool exhaust.

## Testing Guidelines
There is no single global test runner yet. Validate changes by:
- running installer/sync scripts with `--dry-run`
- smoke-testing the edited skill in the target runtime
- checking any skill-local `evals/` or helper scripts when present
Treat trigger behavior and installability as the real acceptance test.

## Commit & Pull Request Guidelines
Follow the current history style: short, imperative commit subjects, e.g. `Add VetCoders skills suite and docs`. Keep PRs focused on one skill or one repo-wide concern. Include: what changed, why it matters, affected skill paths, and any manual smoke tests (`install --dry-run`, runtime trigger checks, remote sync preview). Screenshots are useful when updating `docs/` or the showcase.

## Security & Canonical Source Rules
Edit skills here first, then sync outward. Do not treat `~/.codex/skills`, `~/.claude/skills`, or `~/.gemini/skills` as canonical. If a skill needs credentials, read them from environment variables or local machine config outside git.

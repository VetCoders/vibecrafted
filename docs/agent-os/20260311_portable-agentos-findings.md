# Portable Runtime / Agent OS Findings

Date: 2026-03-11
Mode: append-only
Repo: vetcoders-skills

## Findings

- The repo is already partially machine-agnostic for install and sync:
  - `install.sh` bootstraps a checkout and delegates to repo-owned installer.
  - `vetcoders-spawn/scripts/install.sh` installs skills into `~/.{codex,claude,gemini}/skills` without relying on private aliases.
  - `vetcoders-spawn/scripts/skills_sync.sh` syncs the same canonical skills to another machine.
- The portable core still assumes a macOS-visible-window spawn path for the main UX:
  - `vetcoders-spawn/scripts/common.sh` requires `osascript` for visible Terminal spawns.
  - `vetcoders-spawn/SKILL.md`, `docs/index.html`, and `vetcoders-suite-showcase.html` still frame osascript/Terminal as the canonical or power-user path.
- The repo preflights `aicx` and `loctree-mcp`, but does not yet provide a first-class path for provisioning them.
- `prview` is documented in `vetcoders-prview/SKILL.md` as an external binary, but is not yet part of install/bootstrap preflight in the same way.
- Current quality posture is light:
  - no single repo-wide test harness for portable install/sync/spawn flows
  - no CI matrix for machines without private shell aliases
  - no acceptance suite for "fresh machine, no helper aliases, no local dotfiles"
- There is a strategic question above helper polish:
  - keep improving script-first portable runtime
  - vendor/notarize external binaries for the foundation tools
  - or build a Rust mini-binary / "Agent OS" that becomes the canonical entrypoint and orchestrates `aicx`, `loctree`, and `prview` directly.

## Open questions

- What is the correct canonical UX surface for a new machine:
  - shell scripts,
  - installed CLI wrappers,
  - or one Rust binary?
- Which parts truly need embedded/notarized binaries, and which are better left as external managed tools?
- Is `prview` a foundation dependency at the same level as `aicx` and `loctree-mcp`, or a higher-tier optional tool?
- What is the minimum viable machine-agnostic acceptance matrix we should enforce before calling the repo portable?

## 2026-03-12 delta

- Pulled new upstream metadata into `vetcoders-partner/agents/openai.yaml`, so partner-facing product surface is still evolving.
- Confirmed current local worktree is now mainly about spawn/runtime hardening, not broad repo ambiguity.
- Fixed a real launcher bug in repo-owned spawn scripts:
  - `gemini_spawn.sh` and `claude_spawn.sh` were generating launchers that could explode on `prompt` quoting under `set -u`.
  - This reinforces the broader finding that spawn is still the sharpest portability/runtime seam in the repo.
- Decision pressure remains the same:
  - stabilize portable spawn + preflight + acceptance first
  - postpone full Agent OS binary until the shell/runtime contract stops moving
- Extracted a repo-owned zsh helper layer from private dotfiles instead of treating personal shell config as canonical:
  - installable through `vetcoders-spawn/scripts/install-shell.sh`
  - sourceable from `~/.zshrc`
  - carries only product-worthy wrappers and Gemini Keychain ergonomics, not personal banner/theme baggage
- Tightened the visible spawn contract around `zsh -ic <launcher>` rather than plain `zsh <launcher>`, which matters for real user-shaped runtime and fixes the discovered Gemini auth path on machines where the key lives in Keychain.
- Added a path to sync the same helper layer to another machine via `skills_sync.sh --with-shell`, so the "best parts of the shell" are now something the repo can install and ship.

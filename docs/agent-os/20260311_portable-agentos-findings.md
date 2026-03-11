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

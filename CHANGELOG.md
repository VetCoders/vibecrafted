# Changelog

All notable changes to 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

## 1.3.0 — 2026-04-11

### Added

- Browser-based guided installer: `scripts/installer_gui.py`
- `install.sh --gui` bootstrap path for the guided installer
- `make gui-install` for launching the guided installer from source
- Marketplace submission pack in `docs/SUBMISSION_FORMS.md`
- Release kickoff docs now ship inside the marketplace bundle artifact
- Release-contract pytest guard for promise / CTA drift across public surfaces

### Changed

- Product positioning now leads with the release-engine promise instead of generic framework language
- Public install docs now explicitly show the guided GUI path for founders and non-terminal operators
- `install.sh` help text now matches the actual bootstrap paths instead of promising a TUI that was not wired in
- `install.sh` fallback now prefers the live GitHub source snapshot when the channel manifest is missing, instead of pinning a stale tarball URL
- Submission forms now cite current adjacent-tool directory evidence and official launch surfaces
- Frontier / installer copy now talks about the current framework surface instead of a stale frozen version string

## 1.2.1 — 2026-04-01

### Added

- `make foundations` — portable installer for loctree and ai-contexters binaries
  - Downloads pre-built loctree v0.8.16 binaries (notarized/signed) for macOS, Linux, Windows
  - Installs ai-contexters via GitHub release binary or `cargo install` fallback
  - `make foundations-check` for dry-run preview
  - `scripts/install-foundations.sh` works standalone or via Make
- Python-native `shutil.copytree` fallback when `rsync` is not available
  - `rsync` downgraded from critical to recommended dependency
  - `make install` now succeeds on systems without rsync (fresh containers, Windows WSL)

### Fixed

- **Python 3.11 compatibility**: f-string backslash escapes in `vetcoders_install.py`
  caused `SyntaxError` on Python < 3.12 (the `\U` unicode escapes inside f-string
  expressions). Extracted to variables.
- `rsync` no longer blocks installation — `make install` uses pure-Python copy as fallback

## 1.2.0 — 2026-03-29

### Added

- Marbles loop orchestrator: `marbles_spawn.sh`, `marbles_next.sh`, `marbles_plan.sh`
  - `<agent>-marbles --depth <n> --count <y>` — crawl recent sessions, run convergence loops
  - `<agent>-marbles --task <plan.md> --count <y>` — loop against a plan file
  - `<agent>-marbles --prompt "text" --count <y>` — inline prompt loops
  - Filesystem-based loop chaining via `success_hook` — no cron, no watcher
  - Convergence through CODE STATE, not report chaining — each loop gets the same plan, sees improved repo
  - `CONVERGENCE.md` written after final loop (or on failure)
  - Lock files in `$VIBECRAFTED_ROOT/.vibecrafted/locks/<org>/<repo>/`
- `--success-hook` and `--failure-hook` flags for all spawn scripts (claude, codex, gemini)
- Landing page: 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. → 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. rebrand, sprite caching for Safari performance
- Installer TUI wizard (in progress): Rich-based step-by-step flow from docs/installer/ mockups

### Changed

- Product name: **𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.** (the product), **𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙** (the methodology)

### Fixed

- **Clarified `zsh -ic` requirement for shell helpers**: The 1.0.3 changelog stated
  "removes zsh runtime dependency" which is true for spawn SCRIPTS (`eval "$SPAWN_CMD"`
  works in bash). However, operator-facing shell helpers (`codex-implement`,
  `claude-research`, etc.) are functions sourced from `.zshrc`/`.bashrc` and require
  an interactive shell to load. The canonical agent-to-agent invocation remains
  `zsh -ic "codex-implement $PLAN"` (or `bash -ic` on zsh-less systems).
  Skill documentation (vc-agents SKILL.md) updated to reflect this.
- Marbles board animation: sprite pre-rendering (was creating new canvas per marble per frame — Chrome hid the cost,
  Safari showed 5fps)
- `init-hooks` Makefile target: guard with `git rev-parse --git-dir` for non-git bootstrap contexts
- Portable test: marbles helper uses new `--prompt` interface, flexible `run_id` check

## 1.0.4 — 2026-03-29

### Added

- 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework overview and README branding
- Marbles orchestration skill and hook/runtime fixes
- AICX extract skill documentation
- Mission-control layout for Zellij
- Compact install mode and enhanced logging
- ScreenScribe foundation setup
- GitHub Pages onboarding pages for Quick Start and answered FAQ
- Marketplace listing draft for the framework
- GitHub issue templates for bugs and workflow requests

### Changed

- Refactored installer UI and polished docs
- Reset Gemini plan dir on install
- Uses `VIBECRAFTED_HOME` with Gemini include dir

### Fixed

- Canonical URL, sitemap, and robots alignment for the public presence surface
- Public docs updated to match the current shell-agnostic helper path and non-interactive install flow
- Installer issues and UI
- Gemini and MCP stream filters

## 1.0.3 — 2026-03-27

### Added

- Framework version tracking (`VERSION` file, installer + doctor report it)
- Bash shell helper support — helpers work in bash and zsh, not zsh-only
- Dual rcfile installation (`.bashrc` + `.zshrc`)
- Release CI workflow (tag `v*` builds archive without `presence/`, GitHub Release with SHA256)
- `curl-bootstrap` CI job for install.sh end-to-end smoke testing
- Stream filters: Claude jq, Codex jq, Gemini awk — clean readable agent terminal output
- Codex `--json` JSONL streaming with structured event parsing
- Spawn telemetry: `framework_version`, `prompt_id`, `run_id`, `loop_nr`, `skill_code`, `duration_s`
- Skill helpers: `<agent>-dou`, `<agent>-hydrate`, `<agent>-marbles`, `<agent>-scaffold`, etc.
- `vc-dashboard` for Zellij Mission Control layout
- Active spawn scan before each launch
- Material palette: copper/patina/timber/steel/stone

### Changed

- Spawn launcher: `zsh -ic` -> `eval` — removes zsh runtime dependency
- Terminal.app spawn: `zsh -ic` -> `bash`
- Shell helpers renamed `vetcoders.zsh` -> `vetcoders.sh` (compat symlink kept)
- Helper install path: `$HOME/.config/vetcoders/vc-skills.sh` (was `$HOME/.config/zsh/vc-skills.zsh`)
- CI no longer requires zsh on Ubuntu
- Installer: zsh downgraded from required to optional dependency
- No hardcoded model flags in spawn scripts — agents choose their own

### Fixed

- Headless spawn failing in CI (zsh -ic in nohup context)
- Codex spawn exit code 1 from session grep with pipefail
- Loctree release URL (Loctree-Repos -> Loctree/Loctree)

### Removed

- Judgmental/condescending language from presence copy and FAQ
- zsh as runtime dependency for agent spawns

## 1.0.2 — 2026-03-27

### Added

- `LICENSE` — Business Source License 1.1
- `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- Skill taxonomy refactor: 17 skills with coherent pipeline references
- `vc-justdo`, `vc-scaffold`, `vc-release` skills
- FAQ-ANSWERED.md
- Centralized artifacts under `$VIBECRAFTED_ROOT/.vibecrafted/`
- OG image and social card meta tags
- GitHub issue templates

### Fixed

- Hardcoded paths in skill files replaced with portable references

### Removed

- `vc-ship`, `vc-ownership` (absorbed into other skills)
- 60-file taxonomy cleanup

### Skills (as of 1.0.2)

- vc-agents 1.4.1, vc-decorate 1.1.0, vc-delegate 1.0.0, vc-dou 1.0.0
- vc-followup 1.0.0, vc-hydrate 1.0.0, vc-init 2.2.0, vc-justdo 2.0.0
- vc-marbles 1.1.0, vc-partner 2.0.0, vc-prune 2.0.0, vc-release 0.1.0
- vc-research 1.2.0, vc-review 1.0.0, vc-scaffold 0.1.0, vc-screenscribe 1.2.1
- vc-workflow 1.0.0

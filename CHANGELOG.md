# Changelog

All notable changes to VibeCraft are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
- Helper install path: `~/.config/vetcoders/vc-skills.sh` (was `~/.config/zsh/vc-skills.zsh`)
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
- Centralized artifacts under `~/.vibecrafted/`
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

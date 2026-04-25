# Changelog

All notable changes to 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Added

- `vc-release` Release Report Contract: every release report now requires
  four mandatory sections — security gate (Semgrep), exposed surface
  inventory (ports, proxies, auth, headers, secrets), deployment mode
  decision, and post-release install smoke from the **published**
  artefact (not the working tree). Canonical template lives at
  `skills/vc-release/references/release-report-template.md`.
- `skills/vc-release/references/deployment-reality.md` gains an
  "Exposed Surface Inventory" matrix (process, bind, port, proxy, TLS,
  auth, edge headers, secret materialization) so the inventory has a
  doctrine to reference.
- `tests/tui/test_release_contract.py` adds two locks: the four
  mandatory sections in `skills/vc-release/SKILL.md` plus the surface
  inventory tokens in `deployment-reality.md`. Future drift fails the
  pytest gate.

### Changed

- `skills/vc-release/SKILL.md` Semgrep release gate now points at the
  canonical `make semgrep` (mirrored by `scripts/hooks/pre-commit` and
  `scripts/hooks/pre-push`), classifies findings by dataflow boundary
  (path / regex / merge / shell / auth / other), and treats silent
  unavailability as a release block.
- `skills/vc-release/SKILL.md` Post-release smoke now requires a cold
  install from the published artefact source (registry URL, tag,
  digest, or download URL) and forbids using the local checkout as the
  witness.
- `docs/runtime/CONTRACT.md` quality gate section references the
  canonical `make semgrep` invocation and links the Release Report
  Contract.
- `docs/RELEASE_KICKOFF.md` adds `make semgrep` to the kickoff gate
  block and links the release report template plus the deployment
  reality matrix.
- `README.md` release-flow paragraph names the four-section release
  report and links the doctrine + template.

## 1.4.1 — 2026-04-22

### Added

- `tools/bin/` bundled toolchain drop-in for pre-notarized binaries: installer
  resolves local bundle first, then falls back to remote fetch. Enables
  fully-offline first-install UX for cold users.
  - `scripts/build_marketplace_bundle.py` now collects `tools/bin/**` into the
    plugin bundle artifact
  - `scripts/install-foundations.sh` gains `bundled_bin_root()` and
    `install_from_bundled()` with explicit fallback order
  - `installer_tui.py` / `installer_gui.py` surface bundled diagnostics as a
    new category in the pre-flight doctor
  - Documented resolution order and notarization expectations in
    `tools/bin/README.md`
- `skills/vc-agents/scripts/marbles_verify_watch.sh` — standalone detached
  verification poller that waits for `*_verified.md`, updates `state.json` under
  lock, and marks verification as `completed` or `timed_out`. Decouples
  verification from the main watcher process and eliminates watcher holding
  PIDs for long periods.
- `vc-research` swarm launcher + worker charter for research passes that need
  multiple parallel agents converging on one plan.
- `vc-intents` skill for retrieval of past decisions from AI Chronicles /
  session history (complements `vc-init`).
- `await` helper for synchronous wait-on-agent flows in orchestration scripts.
- Help overlay in operator-tui launch flow.
- `--echo-stdout` flag in codex stream bridge for visibility into headless
  runs without losing machine-readable frames.
- Agent telemetry captured into loop `state.json` (dispatch time, completion
  time, exit code, session_id) so marbles state is the single source of truth
  for multi-loop runs.
- New skill **`vc-implement`** becomes the canonical end-to-end implementation
  skill. The `vc-justdo` name stays in-tree as a **backward-compatible legacy
  alias** (frontmatter: `canonical: vc-implement`) so agents already wired to
  the old name keep working. Every public surface (START_HERE `Simplest path`,
  install banner, skill registry in `vetcoders_install.py`) now shows
  `vibecrafted implement ...`; the `justdo` command still executes but is no
  longer advertised. Full trigger-phrase inventory — including Polish triggers
  ("zrób to", "dowiez to", "od pomyslu do realizacji") — migrated to
  `vc-implement`.

### Changed

- Operator TUI refactored into a tabbed console — three tabs: **Monitor**
  (live runs + recent events), **Dispatch** (mission kind / agent / runtime /
  prompt), **Controls** (attach / resume / report / transcript for selected
  run). Tab navigation contracts stabilized (`Tab` / `Shift+Tab`, arrow keys
  scoped to active tab), direct tab switches normalized.
- Operator TUI split into dedicated **`vc-operator`** crate at the
  `vc-runtime` workspace root. The crate owns its versioning (`vibecrafted-
operator v0.1.1`) and release cycle. `scripts/vibecrafted` launcher gracefully
  falls back between in-source operator-tui and the installed `vc-operator`
  binary, with a clear error if neither is available.
- Marbles spawn now **honors `VIBECRAFTED_MARBLES_RUN_ID` only when it doesn't
  conflict with existing state** (unless `VIBECRAFTED_MARBLES_RESUME=1` is set
  explicitly). Otherwise it mints a **PID-suffixed** run id (`$$` appended to
  the timestamp) so parallel spawns cannot collide on the same second.
- Marbles watcher decoupled from verification polling — instead of holding PIDs
  and polling inline, it marks loops as `pending` and hands off to
  `marbles_verify_watch.sh` via `nohup`. Summary logic simplified; configurable
  verification grace period added.
- Zellij spawn uses **tab/pane IDs** (not just names) for targeting marbles
  panes — non-disruptive spawn that doesn't steal focus from operator's
  active pane; tab index noise suppressed in marbles spawn output.
- Zellij layouts renamed (`operator` / `vc-marbles` / `vc-workflow` / `vc-
research` / `vc-dashboard`) with matching launcher and test updates.
- Uninstall now removes **only manifest-tracked entries** + framework
  artifacts — no broad filesystem sweeps that could clobber user files.
- Operator TUI launches **Ghostty** natively (via `zellij`) as the terminal
  surface when running in `terminal` / `visible` runtime.
- Marbles active-only run filter in operator-tui so Monitor tab stops showing
  cold runs from previous sessions.
- System-wide docs refresh: README, FAQ, FAQ-ANSWERED, QUICK_START, SKILLS,
  WORKFLOWS, installer/DESIGN, workflows/MARBLES — copy brought in line with
  the canonical command set (`vibecrafted implement`) and the current 1.4.1
  surface.
- FLOW + SKILL polish across `vc-delegate`, `vc-init`, `vc-justdo` (marked
  legacy), `vc-partner`, `vc-research`, `vc-scaffold`, `vc-workflow`.

### Fixed

- Marbles wrapper publication drift: wrappers are now force-republished on
  every dispatch so stale files can't point at removed scripts.
- Launcher drift repair in place — `doctor` now fixes broken launcher
  configurations without requiring a clean install.
- `doctor` rc repair path for launcher rc files.
- Operator TUI control-plane wiring — pane names + control-plane state
  aligned, polish pass on tab surfaces.
- Operator TUI terminal agnosticism — no longer hard-codes Zellij or any
  single terminal assumption.
- Operator TUI Zellij env isolation in tests (previously leaked
  `ZELLIJ_CONFIG_DIR` between parallel test runs).
- Flaky CI expectations for marbles statuses and Makefile dry-run output.
- `uv` bootstrap assertion messages now align with export `PATH` checks.

### Removed

- `operator-tui/` directory from vibecrafted (moved to dedicated `vc-
operator` crate — see **Changed** above).
- Stale research docs (`docs/MODULARIZATION_PLAN_2026_04_16.md`,
  `docs/REPO_GROUND_TRUTH_2026_04_13.md`, multiple `docs/research/*.md`
  artifacts, `docs/FAQ-ANSWERED.md` noise).
- `scripts/mission-control/restore-orphaned.sh` (superseded by
  `marbles_verify_watch.sh` + ghost reaping path in the watcher).

## 1.4.0 — 2026-04-18

### Added

- Marbles `delete` subcommand for cleaning up finished / abandoned runs.
- Installer TUI textual wizard flow with real keybindings, sticky layout,
  dynamic interpolation, and manifest-driven step rendering — implements the
  `docs/installer/` mockups 1-for-1.
- Worker contract in generated child plans so sub-agents know the exact
  constraints of their slice (scope, artifacts, gates).
- Shell syntax checks for spawn scripts in the pre-commit path.
- Attended bootstrap confirmation + `--yes` flag in `install.sh` — humans get
  a "what's about to happen" pause by default; CI / automation pipelines get
  a clean non-interactive path.
- Regression tests for installer manifest / branding + codex_stream_bridge.
- `zellij` panes for marbles dispatch (in place of bare new-tab).

### Changed

- **Installer TUI-first swap**: terminal front-door defaults to the guided
  TUI wizard; the GUI stays available via `--gui`. Sticky-bottom streaming
  log, unified `make install` entrypoint.
- Zellij orchestration hardened: tab isolation, spawn probe before every
  dispatch, session GC for stale zellij daemons.
- Framework bumped **1.3.0 → 1.4.0**; VERSION truth propagated across all
  installer surfaces (no more "1.3.0 in README, 1.4.0 in bundle"
  disagreements).
- Installer GUI converted to single-page no-scroll layout; branding + docs
  polished; FRAMEWORK tag squared-block unicode restored (reverted accidental
  normalization).

### Fixed

- `uv` bootstrap shell boundary: installer now correctly propagates the
  ephemeral uv install into the downstream shell instead of losing it to
  subshell isolation.
- Marbles spawn failures no longer masked by codex stream: pipeline status is
  read from pipefail, not inferred from "did we get some stdout?".
- Marbles next-hook contract: child loops only advance after the real
  handoff, not after tmp prompt file arrives.
- Arrow keys in installer TUI now scroll within a step instead of switching
  steps.
- Truthful landing page: no fake URLs, no fake commands, copy matches actual
  install flow.
- Marbles ancestor steering: mtime race fixed, spawn fallback hardened, run-
  id / spawn prefs respected under concurrent dispatches.
- Watcher state race, doctor dashboard smoke, session semantics, update
  path, commit labels — a marble convergence sweep closed these as one loop.

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

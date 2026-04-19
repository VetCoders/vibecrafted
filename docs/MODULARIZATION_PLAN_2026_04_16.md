# Vibecrafted Modularization Plan

Date: 2026-04-16
Scope: shell control plane, installer stack, and high-churn frontend monoliths

## Current State

The repo still has several high-value surfaces where one file owns too many
responsibilities:

- `skills/vc-agents/shell/vetcoders.sh` mixes path discovery, runtime context,
  Zellij lifecycle, frontier config wiring, Atuin wrapping, prompt assembly,
  research layout generation, marbles orchestration, and user-facing command
  wrappers.
- `scripts/vetcoders_install.py` is the single mutation backend, but it is now
  large enough to blur boundaries between manifest execution, environment
  discovery, diagnostics, install actions, logging, and UI-facing summaries.
- `scripts/installer_gui.py`, `scripts/installer_tui.py`, and
  `scripts/installer/vetcoders_installer/` still duplicate installer truth.
  Loctree already flags shared symbols such as `default_source_dir`,
  `installer_script_path`, `build_install_command`, and
  `summarize_diagnostics`.
- `docs/presence/app.js`, `docs/presence/framework.js`, and
  `docs/presence/styles.css` are effectively app-scale files with content,
  behavior, and rendering concerns bundled together.

This is not just a style issue. It raises regression risk because the control
plane has to preserve runtime contracts across shell startup, spawned agents,
headless execution, Zellij attach/resume, and installer surfaces.

## Proposal

### 1. Split `vetcoders.sh` into a thin shell entrypoint plus sourced modules

Target shape:

- `skills/vc-agents/shell/vetcoders.sh`
  - thin compatibility entrypoint
  - sources `shell/lib/*.sh`
  - exports the public wrapper functions only
- `skills/vc-agents/shell/lib/paths.sh`
  - `_vetcoders_repo_root`
  - `_vetcoders_org_repo`
  - `_vetcoders_store_dir`
  - `_vetcoders_tmp_dir`
  - `_vetcoders_tmp_script_path`
  - `_vetcoders_spawn_home`
  - `_vetcoders_spawn_script`
- `skills/vc-agents/shell/lib/context.sh`
  - run IDs, lock paths, ambient context normalization
  - skill prefixes, operator session naming
- `skills/vc-agents/shell/lib/frontier.sh`
  - frontier candidate discovery
  - config file resolution
  - sidecar export policy
- `skills/vc-agents/shell/lib/zellij.sh`
  - Zellij detection
  - session state inspection
  - operator session preparation
  - attach/switch/create behavior
- `skills/vc-agents/shell/lib/atuin.sh`
  - binary discovery
  - fallback logic
  - wrapper function installation
- `skills/vc-agents/shell/lib/contracts.sh`
  - contract parsing
  - file validation
  - prompt/context composition
  - shell quoting and temp command scripts
- `skills/vc-agents/shell/lib/research.sh`
  - research launcher resolution
  - dynamic layout generation
  - research-specific CLI help and runtime flow
- `skills/vc-agents/shell/lib/marbles.sh`
  - marbles contract validation
  - env assembly
  - operator tab spawning
  - transcript tailing
- `skills/vc-agents/shell/lib/commands.sh`
  - public wrapper commands such as `vc-research`, `codex-review`,
    `claude-marbles`, `marbles-pause`, and `vc-resume`

Why this shape matches `common.sh`:

- `common.sh` already works as a stable aggregator over focused library modules.
- The shell helper should use the same pattern so sourcing cost stays stable,
  contracts stay backward-compatible, and tests can import modules
  independently over time.

Migration sequence:

1. Extract pure helpers first: paths, context, quoting, contract parsing.
2. Extract Zellij/frontier/Atuin behavior next, because those already behave
   like service modules.
3. Move research and marbles into their own runtime modules.
4. Leave public function names untouched until the module boundaries are
   stable and tests are green.

## Other Monoliths

### Installer stack

Target shape:

- `scripts/installer_shared/paths.py`
  - `default_source_dir`
  - `installer_script_path`
  - `start_here_path`
  - `vibecrafted_home`
- `scripts/installer_shared/commands.py`
  - `build_install_command`
  - shell/env command assembly
- `scripts/installer_shared/diagnostics.py`
  - collection, normalization, summarization
- `scripts/installer_shared/steps.py`
  - shared install step descriptions and progress states
- `scripts/installer_shared/versioning.py`
  - framework version reading and surface metadata
- thin front doors:
  - `scripts/installer_gui.py`
  - `scripts/installer_tui.py`
  - `scripts/installer/vetcoders_installer/`

Principle:

- Keep `install.toml` as the orchestration contract.
- Keep `scripts/vetcoders_install.py` as the only mutation backend until the
  shared installer helpers are stable.
- Delete duplicated helper logic from GUI/TUI/vendored runner only after the
  shared module passes the existing tests.

### `scripts/vetcoders_install.py`

Target internal cuts:

- `scripts/install_backend/env.py`
- `scripts/install_backend/doctor.py`
- `scripts/install_backend/actions.py`
- `scripts/install_backend/manifests.py`
- `scripts/install_backend/logging.py`
- `scripts/install_backend/verification.py`

Principle:

- Do not rewrite the installer backend and front doors at the same time.
- First centralize shared helper truth, then cut the backend into modules.

### Presence frontend

Target shape:

- `docs/presence/app/clipboard.js`
- `docs/presence/app/state.js`
- `docs/presence/app/render.js`
- `docs/presence/framework/content.js`
- `docs/presence/framework/scene.js`
- `docs/presence/framework/controls.js`
- `docs/presence/styles/tokens.css`
- `docs/presence/styles/layout.css`
- `docs/presence/styles/components.css`
- `docs/presence/styles/animations.css`

Principle:

- Separate content from interaction logic from visual system.
- Keep static site output unchanged while making the behavior easier to audit.

## Quick Wins

1. Extract `vetcoders.sh` path/context helpers first. They are mostly pure and
   heavily reused.
2. Create `scripts/installer_shared/` and move the duplicated installer helper
   functions there before touching UX flows.
3. Split `docs/presence/styles.css` into tokens/layout/components so visual
   changes stop colliding in one file.

## Risks To Watch

- `vetcoders.sh` is sourced by user shells, tests, `skills_sync.sh`, and
  `scripts/vibecrafted`. Public function names and source-time side effects must
  remain compatible during the first extraction phase.
- Zellij and frontier config behavior is already covered by tests and must not
  drift while moving functions.
- Installer modularization must preserve the current browser-first public path
  and local-shell operator path while reducing duplicate logic underneath.

## Recommended Order

1. `vetcoders.sh` extraction into `shell/lib/`
2. shared installer helper extraction
3. `scripts/vetcoders_install.py` backend split
4. presence frontend split

This order reduces runtime risk first, then removes duplicated install truth,
and only then touches product-surface presentation code.

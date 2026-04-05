# Architecture Plan: ݆𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Installer TUI

## Problem Statement

`scripts/installer_tui.py` is currently a hand-rolled terminal renderer built on `termios`, `select`, and `print`. It
can fake a step flow, but it is not a real TUI surface and it does not match the installer mockups in
`docs/installer/*.md`. The current shape also shells into `vetcoders_install.py --compact --non-interactive`, which
means the interactive UI and the installation truth are split across two different execution paths.

We need one real installer architecture that can do three things at once:

- give interactive users a proper alternate-screen wizard with stable header, body, footer, and live progress
- keep non-interactive bootstrap and portable checks working without a TTY
- share one installation engine between TUI and CLI so we stop duplicating behavior and stop lying about what the
  installer is doing
- move task orchestration onto a reproducible substrate instead of letting `make`, shell wrappers, and UI entrypoints
  drift apart

## Visual Identity

- **Material metaphor:** dark steel control surface with copper accents and disciplined mono terminal chrome
- **Color strategy:** copper for action/brand, steel/graphite for structure, green for healthy state, amber for warning,
  red for hard failure, dim gray for hints and paths
- **Typography strategy:** mono for all UI chrome, status, navigation, and system output; keep decorative vapor header
  as a brand accent, not as the primary reading surface
- **Tone:** koleżeński, fachowy, operator-to-operator; informative but never apologetic, never defensive, never
  “compliance form”
- **Dark/light:** dark-first only for the TUI; CLI summary continues to degrade cleanly to plain text in non-TTY
  environments

## Key Architectural Decisions

### Decision 1: Rewrite the interactive installer on Textual, not on manual `tty` rendering

**Choice:** Replace the current `scripts/installer_tui.py` render loop with a real Textual app.
**Trade-off:** Adds a Python UI dependency and forces a sharper separation between state, engine, and view code.
**Why:** The current Python renderer is an imitation of a TUI, not a TUI. Textual gives us real alternate-screen
lifecycle, layout, key bindings, focus handling, workers, resize handling, and testability. This keeps the
implementation in Python next to the existing installer logic, while borrowing architectural discipline from the
`rmcp-mux` and `rmcp-memex` wizard patterns.

### Decision 2: Extract a shared installer engine and event model out of `vetcoders_install.py`

**Choice:** Move diagnostics, plan construction, install stages, and doctor verification into a shared service layer
that emits structured events.
**Trade-off:** Requires refactoring the current monolithic verbose/compact flow before the TUI can become first-class.
**Why:** A real TUI cannot depend on shelling out to `--compact` mode and scraping text. The TUI and the compact CLI
should both consume the same event stream and the same install plan. This is the cut that turns the installer into a
product surface instead of a pile of print statements.

### Decision 3: Keep two front doors, but only one installation truth

**Choice:** Interactive TTY sessions always enter the Textual TUI. Non-interactive sessions continue to bypass TUI and
call the installer engine through compact CLI mode.
**Trade-off:** We keep two presentation layers instead of pretending one surface can satisfy both humans and automation.
**Why:** This preserves the working bootstrap contract in `install.sh` and `scripts/check-portable.sh`, while
guaranteeing that humans always get the real installer experience. The shared engine prevents drift between the two
modes.

### Decision 4: Existing `config/mise.toml` becomes the canonical task substrate; `make` stays as a compatibility shim

**Choice:** Promote the existing `config/mise.toml` from “config payload” to the real task/runtime substrate, and move
the installer entrypoints onto named tasks such as `installer:tui`, `installer:compact`, and `doctor`.
**Trade-off:** Adds one more explicit dependency to the framework substrate and requires task migration discipline.
**Why:** Our own research already converged on `mise` as the missing keystone for reproducible tooling and task
execution. The file already exists in `config/`, but runtime truth says it is not yet the canonical entrypoint: plain
`mise tasks ls` from repo root returns nothing. `mise` should own tool/runtime/task determinism; the installer TUI
should own the interactive surface. A `tui-runner.mjs`-style launcher can still exist later as an operator deck, but it
should launch canonical `mise run ...` tasks, not become the installer architecture itself.

### Decision 5: The mockups define a fixed chrome and step-specific widgets, not a linear print log

**Choice:** Implement the installer as a persistent chrome with:

- fixed header hero
- dynamic middle region composed per step
- fixed action strip
- fixed footer/help strip

Diagnostics and installation become structured panes with live state and details toggles. Welcome, explain, and listing
remain centered narrative steps.
**Trade-off:** More widget code than a simple print loop, and more explicit UI state.
**Why:** This directly matches the mockups in `docs/installer/0_welcome_step.zsh.md` through
`docs/installer/5_installation.zsh.md`. It also aligns with the `rmcp-*` wizard pattern: explicit step enum, explicit
app state, explicit per-step renderer.

### Decision 6: Consent gates happen before mutation; installation becomes a staged pipeline

**Choice:** Split the flow into:

- read-only discovery
- explicit checklist/consent
- backup/install/link/helper/apply
- verification/result

No filesystem mutation occurs before the checklist step is approved.
**Trade-off:** Slightly more state transitions and one more layer of plan serialization.
**Why:** This matches the trust contract in the mockups and the product promise. The installer should explain what
changes and why it matters, but it should not touch the machine before the user approves the exact plan.

## Scope Boundaries

### Phase 1: MVP (This Cycle)

**In scope:**

- Replace the current fake TUI with a real Textual wizard
- Extract a shared installer engine from `vetcoders_install.py`
- Implement the six installer steps from `docs/installer/*.md`
- Keep `install.sh` behavior: TTY -> TUI, non-TTY -> compact CLI
- Promote `config/mise.toml` into the canonical task/runtime substrate
- Stream real diagnostics and install progress into the interactive UI
- Preserve compact summary mode for automation and logs
- Add a real install log pointer and explicit result screen

**Out of scope:**

- Auto-installing missing foundations that are currently only detected and reported
- A Rust rewrite of the installer
- A Node/Blessed rewrite of the installer
- Marketplace-grade art direction inside the TUI beyond the existing brand language
- Reworking shell helper semantics or the install payload itself

**Explicitly out of scope:**

- Further investment in the current `termios`/`select` pseudo-TUI
- Building the shipping installer surface on `vista`’s Node stack
- Treating a `tui-runner.mjs` clone as the installer architecture instead of as a launcher shell
- Treating `--compact` text output as the source of truth for interactive mode

## Architecture Overview

```text
install.sh
  |
  +-- interactive TTY ------------------------------+
  |                                                 |
  |   make vibecrafted                              |
  |     -> mise run installer:tui                   |
  |     -> scripts/installer_tui.py                 |
  |     -> Textual App                              |
  |           -> installer.engine                   |
  |           -> installer.model/events             |
  |           -> installer.brand                    |
  |           -> installer.widgets.*                |
  |                                                 |
  +-- non-interactive ------------------------------+
                                                    |
      python3 scripts/vetcoders_install.py install --compact --non-interactive
           -> installer.engine
           -> installer.model/events
           -> compact event sink / summary renderer
```

### Proposed module layout

```text
scripts/
  installer/
    __init__.py
    brand.py
    model.py          # Step enum, plan dataclasses, diagnostic rows, install result
    events.py         # Structured progress events
    engine.py         # Shared diagnostics + plan + install pipeline
    compact.py        # Compact CLI renderer/event sink
    tui_app.py        # Textual app and screen controller
    widgets/
      chrome.py
      welcome.py
      explain.py
      listing.py
      diagnostics.py
      checklist.py
      installation.py
      result.py
  installer_tui.py    # Tiny launch shim into installer.tui_app
  vetcoders_install.py  # CLI adapter over installer.engine
config/mise.toml       # canonical task/runtime substrate
```

### Reference patterns we are deliberately borrowing

- `vista/scripts/tui/scripts-runner.mjs`
  - useful for split-pane operator UX, status bar, hints, and “command deck” feel
  - useful as a future operator deck or launcher shell
  - not suitable as the shipping installer implementation because the installer core is Python and the mockups want a
    wizard, not a script browser
- `ScreenScribe/screenscribe/cli.py`
  - useful for branded CLI surfaces, Rich composition, and non-TUI fallbacks
  - not enough alone for a full-screen installer wizard
- `rmcp-mux/src/wizard/mod.rs` + `rmcp-mux/src/wizard/ui.rs`
  - best reference for a real wizard architecture: step enum, app state, per-panel renderers, alternate screen, event
    loop
- `rmcp-memex/src/tui/app.rs` + `rmcp-memex/src/tui/ui.rs`
  - best reference for step titles, footer help contract, and explicit render-by-step composition

## Task Breakdown

Each task is agent-ready. Agents can execute in parallel once the shared engine contract exists.

### Task 1: Freeze the installer domain model

**Produces:** `scripts/installer/model.py`, `scripts/installer/events.py`, unit tests for plan/event serialization
**Depends on:** None
**Owner:** Python core agent
**Acceptance:** Diagnostics, checklist items, runtime selections, install stages, and final result can be represented
without printing any UI text.

### Task 2: Extract the shared installer engine

**Produces:** `scripts/installer/engine.py`, refactor of `vetcoders_install.py` to consume the engine
**Depends on:** Task 1
**Owner:** Python installer agent
**Acceptance:** `install`, `doctor`, and compact summary mode run through shared engine calls instead of duplicating
logic inside the CLI file.

### Task 3: Replace the pseudo-TUI with a Textual app shell

**Produces:** `scripts/installer/tui_app.py`, launch shim rewrite in `scripts/installer_tui.py`
**Depends on:** Tasks 1-2
**Owner:** TUI agent
**Acceptance:** Interactive sessions open a real alternate-screen UI with stable header, content area, footer, key
bindings, resize safety, and quit handling.

### Task 4: Promote `config/mise.toml` into the canonical task surface

**Produces:** updated `config/mise.toml`, thin `Makefile` wrappers, installer task naming contract
**Depends on:** Task 2
**Owner:** Tooling/substrate agent
**Acceptance:** `make vibecrafted` can become a thin shim over `mise run installer:tui`, non-interactive flows have a
canonical `mise run installer:compact`, and task naming no longer lives in ad-hoc shell glue. The repo root must also
resolve those tasks cleanly, either by moving/symlinking the file to canonical discovery or by exporting one official
`MISE_CONFIG_FILE` path.

### Task 5: Implement the six mockup-driven installer screens

**Produces:** `scripts/installer/widgets/*.py`, mapped to `docs/installer/0..5`
**Depends on:** Task 3
**Owner:** TUI agent
**Acceptance:** Welcome, explain, listing, diagnostics, checklist, installation, and result states visually map to the
mockups and fit within a normal terminal without becoming a text wall.

### Task 6: Stream real diagnostics and installation events into the UI

**Produces:** worker wiring between Textual app and installer engine, progress panes, details toggle
**Depends on:** Tasks 2, 3, and 5
**Owner:** Integration agent
**Acceptance:** The diagnostics step shows structured status from real checks; the installation step shows live progress
and retained summary lines without scraping compact stdout.

### Task 7: Align compact CLI and logs with the same engine

**Produces:** `scripts/installer/compact.py`, cleanup of compact footer/result rendering
**Depends on:** Task 2
**Owner:** CLI agent
**Acceptance:** `python3 scripts/vetcoders_install.py install --compact --non-interactive` remains portable, readable,
and sourced from the same event stream as the TUI.

### Task 8: Wire bootstrap and release gates around the new surface

**Produces:** updates to `install.sh`, `Makefile`, `scripts/check-portable.sh`, TTY smoke tests
**Depends on:** Tasks 3-7
**Owner:** Release/QA agent
**Acceptance:** Interactive `install.sh` always opens the TUI, non-interactive bootstrap still passes, and the release
path stops lying about installer readiness.

## Test Gates

- **Engine unit tests:** plan construction, diagnostics grouping, event emission, and result aggregation
- **Textual pilot/snapshot tests:** each screen renders its chrome and key content without crashing
- **Portable smoke:** `bash scripts/check-portable.sh` passes in non-interactive mode
- **Interactive smoke:** pseudo-TTY launch proves `install.sh` and `make vibecrafted` open the TUI, not the compact CLI
- **Dry-run install:**
  `python3 scripts/vetcoders_install.py install --source . --with-shell --compact --non-interactive --dry-run` remains
  green
- **Real-path verification:** install -> doctor -> uninstall -> restore on a temp HOME
- **UX contract:** no mutation before checklist consent, and no shell file writes unless the user explicitly enables the
  helper layer

## Living Tree Note

This plan replaces a moving target. The current `scripts/installer_tui.py` should be treated as transitional and should
not receive more polish passes. If the plan changes:

1. Date the change
2. Record whether the driver was product truth, runtime truth, or release truth
3. Update the task dependencies if the shared engine boundary moves
4. Re-run portable and interactive gates before claiming convergence

## Running This Plan

1. Stop investing in the current pseudo-TUI
2. Cut the shared engine out of `vetcoders_install.py`
3. Stand up the Textual app shell with fixed chrome
4. Port screens one by one from the mockups
5. Wire the real event stream into diagnostics and installation
6. Re-run portable and interactive gates

## Quick Win

The smallest sharp move is **Task 1 + Task 4A**:

- define the installer plan/event dataclasses
- make `config/mise.toml` visible as the actual repo task surface from root

Once those exist, the fake TUI loses its leverage immediately, because the real Textual surface can be built against
stable installer truth and launched through a canonical substrate instead of scraping printed summaries.

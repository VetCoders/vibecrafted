# Installer Shipping Plan

Current truth as of 2026-04-10:

- Public front door: browser-guided installer in `scripts/installer_gui.py`
- Public CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui`
- Local human entrypoint: `make vibecrafted`
- Automation entrypoint: `curl -fsSL https://vibecrafted.io/install.sh | bash`
- Mutation engine: `scripts/vetcoders_install.py`
- Operator-grade reference surface: `scripts/installer_tui.py`

This file replaces the older "rewrite the installer around a full Textual TUI"
roadmap. That plan was useful exploration, but it is no longer the shipping
shape.

## Decision

The effortless install path now follows the TwinSweep-style GUI line, not the
`rmcp-memex`-style TUI line.

Why this won:

- it gives founders and less terminal-native operators a lower-friction first run
- it creates a better marketplace and launch-day demo surface
- it keeps the install truth readable instead of burying it in terminal chrome
- it reuses the same compact installation engine used by automation
- it still allows the TUI branch to inform the wizard rhythm without becoming the
  public onboarding contract

## What we kept from each reference

### From `rmcp-memex`

The useful inheritance from [`src/tui/mod.rs`](/Users/polyversai/Libraxis/01_deployed_libraxis_vm/rmcp-memex/src/tui/mod.rs)
is the wizard rhythm:

- welcome
- detection / preflight
- settings / choices
- health check
- summary
- explicit finish state

That repo proves the value of a disciplined step-based flow. It does **not**
need to dictate Vibecrafted's public install surface.

### From `TwinSweep`

The useful inheritance from [`twinsweep/macos_app.py`](/Users/polyversai/Libraxis/TwinSweep/twinsweep/macos_app.py)
and [`twinsweep/server.py`](/Users/polyversai/Libraxis/TwinSweep/twinsweep/server.py)
is the effortless GUI handoff:

- launch locally without demanding that the operator "live in the terminal"
- use a health-checked local web surface as the interaction layer
- keep the heavy lifting in the existing runtime instead of duplicating logic in
  a second installer implementation

That pattern matches Vibecrafted's release promise better than a TUI-first
story.

## Shipping Architecture

```text
install.sh
  ├─ stages a repo snapshot into $VIBECRAFTED_ROOT/.vibecrafted/tools/
  ├─ `--gui` → scripts/installer_gui.py
  │            ├─ browser-based guided surface
  │            ├─ preflight diagnostics + category cards
  │            └─ compact install steps reused from the real installer
  └─ default / automation → scripts/vetcoders_install.py --compact --non-interactive
```

Supporting truth:

- `installer_gui.py` is the public human surface
- `installer_tui.py` still contributes diagnostics, helper-path logic, and
  operator-friendly summaries
- `vetcoders_install.py` remains the one mutation engine
- `install.sh` is responsible for selecting the correct front door

## Public Contract

Every release surface should agree on these points:

- promise: `Release engine for AI-built software.`
- supporting line: `Ship AI-built software without the vibe hangover.`
- primary CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui`
- secondary CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash`
- first verification step after install: `vibecrafted doctor`

## Explicit Non-Goals

These are not the shipping priority:

- turning the public install path into a Textual rewrite
- making TUI the default onboarding contract
- maintaining two equally primary public install stories
- letting docs, portal, installer, and marketplace copy drift into different
  descriptions of the product

## Where TUI Still Matters

TUI is still valuable when we need:

- operator-facing diagnostics in terminal-heavy environments
- a future expert deck for advanced runtime inspection
- compact local fallback when browser launch is undesirable

That makes TUI a secondary expert surface, not the first thing a new adopter
should see.

## Done Definition

The installer work is "done" for release when:

1. the guided GUI path is the public human default
2. the compact path remains clean for CI and automation
3. `doctor` validates the staged install truth
4. the portal, docs, README, and marketplace packet all point to the same
   install contract

If those surfaces disagree, the installer is not done, even if the code runs.

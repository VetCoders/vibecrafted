# Installer Reference

Canonical reference for the shipping installer shape as of 2026-04-11.

This file exists so we stop re-litigating the same question every pass:
which installer is public, which one is expert-only, and what counts as
"done" for the release-facing onboarding path.

## Decision

- Public human front door: browser-guided installer in `scripts/installer_gui.py`
- Public CTA: `curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui`
- Local terminal-native entrypoint: `make vibecrafted`
- Local browser GUI entrypoint: `make wizard` (alias: `make gui-install`)
- Mutation engine: `scripts/vetcoders_install.py`

The public GUI-first path won because it is the most effortless surface for
founders and launch-day strangers. A local checkout still defaults to
`make vibecrafted` so repo-native operators keep a terminal-first path, while
`make wizard` stays the browser surface on demand.

## Reference sources

The shipping shape is a synthesis of three sources, not a freeform redesign:

- `docs/installer/0_welcome_step.zsh.md` through `5_installation.zsh.md`
  define the trust-building cadence and the mock intent.
- `rmcp-memex` contributes the disciplined wizard rhythm from its
  `src/tui/mod.rs`.
- `TwinSweep` contributes the effortless local-web handoff from its
  `twinsweep/macos_app.py` and `twinsweep/server.py`.

## Crosswalk

| Intent source                | Shipping translation in Vibecrafted                     |
| ---------------------------- | ------------------------------------------------------- |
| TUI mock "Welcome"           | GUI step `Welcome` with read-only trust framing         |
| TUI mock "Explain"           | GUI step `Explain` with why-this-shape rationale        |
| `rmcp-memex` wizard sequence | Progress dots + explicit staged flow                    |
| TUI mock checklist / examine | GUI `Diagnostics` and `Checklist` steps                 |
| TwinSweep local-web handoff  | Local HTTP server + browser onboarding surface          |
| Existing installer truth     | `vetcoders_install.py` remains the only mutation engine |
| TUI finish state             | GUI `Finish` slide + `START_HERE` handoff               |

## UI contract

The browser installer is only shippable if all of these remain true:

- It behaves as a one-page wizard with progress dots.
- The page itself should not become a long scrolling document. No page scroll is
  part of the contract.
- If a viewport is short, scrolling is contained inside the rail or the active
  slide body, not the whole page.
- Keyboard navigation works across slides.
- The live install step streams the real staged commands and real output.
- The finish state only unlocks after a clean install run.
- `START_HERE` remains the first plain-language handoff artifact.

## Responsibilities by surface

- `install.sh --gui`
  Chooses the browser-guided front door for human onboarding.
- `make vibecrafted`
  Runs the terminal-native installer wizard from a local checkout.
- `make wizard` / `make gui-install`
  Open the browser-guided installer from a local checkout when you want the GUI surface.
- `scripts/vetcoders_install.py`
  Owns filesystem mutations, doctor output, and the reusable install truth.
- `scripts/installer_tui.py`
  Remains a deeper operator surface and a source of diagnostics / cadence.

## Acceptance checklist

The installer contract is ready for release only when:

1. README, Quick Start, FAQ, submission pack, and portal CTA all point to the
   same guided install command.
2. The public CTA stays browser-first and the local checkout path stays shell-first.
3. The browser wizard keeps the no page scroll contract on laptop and mobile
   viewports.
4. The finish state hands off to `START_HERE`, `vibecrafted help`, and
   `vibecrafted doctor`.
5. No document or built artifact claims that interactive terminals "always"
   enter the TUI unless that is actually true in the shipping portal repo.

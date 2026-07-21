# vc-frame Multi-Agent Layouts

> Plan 12 (META_22) — Wave 4 agent-native runtime cut.

Vibecrafted ships a vc-frame configuration tuned for the way Vetcoders actually
work: parallel agents, shared Living Tree, mesh of workstations, no babysitting.
The shipped surface gives every layout host-aware identity colors so an
operator instantly knows which machine they are looking at.

This document covers what is shipped, how it auto-discovers itself, and how to
extend it.

## What ships

```
config/vc-frame/
├── config.kdl                       # base config + monochrome chrome (flat UI)
├── auto-theme.sh                    # host detection -> theme name
├── themes/
│   └── vetcoders-mesh.kdl           # 4 mesh themes (dragon/sztudio/silver/div0)
└── layouts/
    ├── operator.kdl                 # launch alias of built-in vibecrafted — `vibecrafted start`
    ├── dashboard.kdl                # mission control 2x2 grid
    ├── marbles.kdl                  # convergence workspace
    ├── research.kdl                 # triple-agent research swarm
    └── workflow.kdl                 # ERi implementation workspace
```

Once installed (`vibecrafted install` or `make install`), the framework symlinks
this directory under `~/.config/vetcoders/frontier/vc-frame/` and the layouts
become reachable through the `vibecrafted dashboard <layout>` family of CLIs.

## Mesh-aware host theming

Kronika 2026-05-05 fixed the Vetcoders mesh topology and assigned a default
accent color to each workstation so an operator can instantly tell which
machine they are looking at through screen-share or browser-mirrored vc-frame:

| host    | theme               | accent | role                             |
| ------- | ------------------- | ------ | -------------------------------- |
| dragon  | `vetcoders-dragon`  | red    | LibraxisAI server, central hub   |
| sztudio | `vetcoders-sztudio` | purple | Operator desktop                 |
| silver  | `vetcoders-silver`  | cyan   | Operator laptop                  |
| div0    | `vetcoders-div0`    | green  | Primary dev laptop               |
| \*      | `vibecrafted`       | amber  | Neutral default (fleet baseline) |

The themes live in `config/vc-frame/themes/vetcoders-mesh.kdl`. vc-frame auto-loads
nested theme blocks from the same config dir, so no extra wiring is needed at
the framework level.

### Resolving the theme at runtime

`config/vc-frame/auto-theme.sh` emits the theme name for the current workstation.
Detection order:

1. `VIBECRAFTED_HOST_NAME` (operator override — useful for tests/staging)
2. `scutil --get LocalHostName` (macOS default local name)
3. `scutil --get ComputerName` (macOS user-friendly name)
4. `hostname -s` / `hostname` (Linux fallback)

The result is normalized (lowercase + strip `.local`/`.lan`) before matching,
and `mgbook16` is wired as an alias for `div0` because that is the value
`scutil --get LocalHostName` actually returns on that laptop.

The `VIBECRAFTED_THEME` env var bypasses host detection outright, so an
operator can pin a fleet baseline theme even when running on a mesh host.

### Fleet chrome default (status-bar / tab-bar)

Shipped `config.kdl` uses two eyes + flat tiles:

```kdl
theme "monochrome"
theme_dark "monochrome"
theme_light "vibecrafted-ivory"
simplified_ui true
```

| Mode                           | Theme               | Feel                       |
| ------------------------------ | ------------------- | -------------------------- |
| dark (fallback + `theme_dark`) | `monochrome`        | greyscale graphite         |
| light (`theme_light`)          | `vibecrafted-ivory` | kość słoniowa / warm paper |

- **simplified_ui** — flat `Ctrl+<key> LABEL` tiles (no powerline ``)
- Ivory lives in `themes/vibecrafted-ivory.kdl` (auto-loaded with mesh themes)
- Brand block `vibecrafted` (graphite + amber) and mesh host accents are **opt-in**

### Operator layout = vibecrafted standard

`layouts/operator.kdl` (vc-start) is the same file content as built-in
`default_layout "vibecrafted"` (tabs **Start here** + **Shell**, no spaces in
layout _filenames_; never `Vibecrafted Operator.kdl`):

- `default_tab_template` — compact-bar brand + **SESSIONS rail always** + status-bar
- tab **Guide** — Mission Control (`about` / `guide_mode "mission-control"`)
- tab **vibecrafted** — operator shell

No strider split on the entrypoint.

### Activating the host theme

The shipped chrome default is monochrome (flat). To activate a host accent
instead, wire one of the following in your shell init or in a host-local
`config/vc-frame/local.kdl` overlay:

```bash
# Shell init — print the matching theme name for diagnostics.
~/.config/vetcoders/frontier/vc-frame/auto-theme.sh
```

or pin via env:

```bash
export VIBECRAFTED_THEME="$(~/.config/vetcoders/frontier/vc-frame/auto-theme.sh)"
```

When the operator-facing launcher in a future plan rewrites the theme line on
session start, all five layouts will pick up the host accent automatically.

## Verification

```bash
make test-vc-frame
```

Runs `tests/vc-frame-layouts-smoke.sh`, which asserts:

- every shipped layout parses via `vc-frame --layout <name> setup --check`
- every mesh theme loads alongside `config.kdl` without parse errors
- `auto-theme.sh` passes `bash -n` and shellcheck (when installed)
- `auto-theme.sh` maps `dragon|sztudio|silver|div0|mgbook16` to the right
  mesh theme and falls back to neutral for unknown hosts (case-insensitive,
  `.local` suffix tolerant)

Tolerant of missing `vc-frame` / `shellcheck` — those checks are deferred to CI
when the host doesn't have them.

## Living Tree etiquette

- Layout edits are **append-only**. Existing pane configurations are preserved
  byte-for-byte.
- `auto-theme.sh` probes multiple roots
  (`$VIBECRAFTED_HOME/tools/vibecrafted-current/config/vc-frame`,
  `$VIBECRAFTED_ROOT/config/vc-frame`, `./config/vc-frame`) so it works whether
  invoked from the installed framework, a Living Tree worktree, or a CI runner.

## Related

- Kronika 2026-05-05 — Vetcoders mesh topology + per-host color assignments
- Kronika 2026-04-12 — first vc-frame landing
- `docs/plans/META_22_SCAFFOLD_TO_RELEASE.md` Plan 12 — full contract
- `skills/vc-agents/SKILL.md` — operator-facing dispatch surface

Vibecrafted with AI Agents (c)2024-2026 LibraxisAI

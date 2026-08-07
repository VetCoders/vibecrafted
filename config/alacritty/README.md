# Host terminal presets (Alacritty / vc-terminal)

This directory is the **vibecrafted-side pointer** for host-terminal config that
must survive reinstalls. The **canonical preset** lives in the vc-frame repo:

| Asset                                               | Canonical path                                      |
| --------------------------------------------------- | --------------------------------------------------- |
| Host preset (option_as_alt, wheel split, Cmd layer) | `vc-frame/tools/alacritty/vc-frame.toml`            |
| Plain-shell entrypoint (primary buffer only)        | `vc-frame/tools/alacritty/launch-primary-shell.zsh` |
| Integration contract                                | `vc-frame/docs/ALACRITTY_INTEGRATION.md` §5         |

Files here are staged into `$XDG_CONFIG_HOME/vetcoders/frontier/alacritty/` by
`install-frontier-config.sh` when present. They are **sidecars** — they do not
overwrite `~/.config/alacritty/alacritty.toml`.

## What the operator should wire

```toml
# ~/.config/alacritty/alacritty.toml
[general]
import = [
  # after: cp $VC_FRAME_CHECKOUT/tools/alacritty/vc-frame.toml ~/.config/alacritty/
  "~/.config/alacritty/vc-frame.toml",
]
```

Or copy from the frontier sidecar after `vc-frontier-install`.

## Wheel contract (do not regress)

| Buffer            | Wheel                  |
| ----------------- | ---------------------- |
| primary (`~Alt`)  | scrollback             |
| alternate (`Alt`) | Up/Down for TUIs       |
| Shift+wheel       | always host scrollback |

Never wrap the login shell in permanent `smcup`. Use `launch-primary-shell.zsh`.

## Atuin on keyboard Up

Shell binding is separate — see `config/shell/atuin-up.zsh` and
`vibecrafted-vm/zshrc.template`. Keyboard Up may open Atuin; wheel on primary
does not, because Alacritty no longer turns primary-buffer scroll into arrows.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI

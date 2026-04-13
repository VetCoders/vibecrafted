# Frontier Config — Starship, Atuin, Optional Zellij

## What This Is

Frontier config is the lightweight operator layer that still belongs inside
the current framework surface:

- `starship` for prompt context
- `atuin` for searchable history
- optional `zellij` config and dashboards for people who want a repo-owned session surface

The key constraint is non-invasive ownership: the repo can ship Zellij assets
without bulldozing the user's terminal setup. Frontier files resolve per asset,
so an external companion config can override only the Zellij bits while the repo
still provides the prompt and history defaults.

None of this is required. `vibecrafted` works without any of it.

---

## Quick Setup

```bash
brew install starship atuin
make install
vc-frontier-paths
```

That gives you:

- a prompt with repo/runtime context
- searchable shell history tuned for project recall
- optional Zellij dashboards that stay dormant until you launch them

If you already run your shell inside a `zellij` session, spawned agents still
reuse panes automatically. If you want the repo-owned dashboards too, install
the frontier presets and launch them explicitly with `vibecrafted dashboard`.

---

## Starship

The helper layer auto-detects Starship and points it at
`config/starship.toml`.

What it shows:

- current directory
- git branch and dirty state
- Python / Node / Rust context
- active agent and runtime when a spawn is running

Check the resolved path:

```bash
vc-frontier-paths
```

---

## Atuin

The repo keeps an Atuin config at `config/atuin/config.toml` for:

- fuzzy history
- workspace-first filtering
- home-scope fallback when the current repo/workspace is empty
- preview-enabled recall
- noise filtering for trivial commands

Install or refresh the sidecars with:

```bash
vc-frontier-install
```

If `zellij` is on your machine, the same command also stages the repo-owned
`config.kdl` and dashboard layouts. Nothing gets forced on until you run a
dashboard command or point your shell at those files. The installer places all
three assets under `$HOME/.config/vetcoders/frontier/`, not into your global
`$HOME/.config/zellij` or `$HOME/.config/starship.toml`.

---

## Config Resolution

The helper layer resolves each artifact independently:

1. `$XDG_CONFIG_HOME/vetcoders/frontier/`
2. `$VIBECRAFTED_HOME/tools/vibecrafted-current/config/`
3. `$VIBECRAFTED_ROOT/config/`
4. `<current vibecrafted repo>/config/`

That means repo-owned `starship` / `atuin` presets can stay local to the core
framework while a companion repo can provide only `zellij/config.kdl` or only a
single layout without being shadowed by the checkout you are currently in.

Inspect the active paths with:

```bash
vc-frontier-paths
```

---

## Shipped Surface

The core repo now ships:

- repo-owned `zellij` layouts
- repo-owned `zellij` config
- repo-owned `starship` and `atuin` presets

What stays outside the core repo:

- terminal-emulator presets such as Alacritty

If you prefer `zellij`, keep using it. The spawn runtime still detects an
active session and opens panes there when possible. If a companion repo stages
`zellij/config.kdl` under `$HOME/.config/vetcoders/frontier/`, the helper layer can
pick it up without changing the core repo contract. The difference is simple:
the framework owns an optional dashboard surface, not your whole terminal
identity.

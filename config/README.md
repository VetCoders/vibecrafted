# VetCoders Frontier Config

Repo-owned shell presets for the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. operator surface.

This layer is intentionally separate from personal shell identity:

- banner art stays user-owned
- shell helpers stay in `vc-agents/shell/`
- these files cover reproducible prompt/history presets plus optional Zellij layouts
- per-asset frontier resolution lets companion overrides win without shadowing the repo defaults
- `vc-frontier-install` stages them under `$HOME/.config/vetcoders/frontier/` as sidecars, not as a global takeover

Current presets:

- `starship.toml` — compact operator prompt with repo/runtime context
- `atuin/config.toml` — history defaults tuned for project/workspace recall
- `zellij/config.kdl` — optional Zellij baseline that stays opt-in
- `zellij/layouts/*.kdl` — branded dashboards launched only when you ask for them

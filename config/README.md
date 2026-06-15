# VetCoders Frontier Config

Repo-owned shell presets for the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. operator surface.

This layer is intentionally separate from personal shell identity:

- banner art stays user-owned
- shell helpers stay in `runtime/shell/`
- these files cover reproducible prompt/history presets plus optional vc-frame layouts
- per-asset frontier resolution lets companion overrides win without shadowing the repo defaults
- `vc-frontier-install` stages them under `$HOME/.config/vetcoders/frontier/` as sidecars, not as a global takeover

Current presets:

- `starship.toml` — compact operator prompt with repo/runtime context
- `atuin/config.toml` — history defaults tuned for project/workspace recall
- `vc-frame/config.kdl` — optional vc-frame baseline that stays opt-in
- `vc-frame/layouts/*.kdl` — branded dashboards launched only when you ask for them

# Vibecrafted built-in installer runner

Sequential trust-building installer runner, vendored into Vibecrafted so that
`make vibecrafted`, `make wizard`, and `install.sh` have **zero external runtime
dependencies** — the terminal-native default path bootstraps `uv` once,
`uv sync`s this directory into an isolated local `.venv/`, and drives the
install from `install.toml` at the repo root. The browser-guided path launches
directly from the repo-owned Python script.

## Why vendored?

The canonical source lives in the
[`vetcoders-tools`](https://github.com/VetCoders/vetcoders-tools) repo
(`installer/` sub-tree) and targets universal use (any repo,
Python/Rust/anything). This directory is a vendored copy kept in sync —
Vibecrafted must remain self-contained so that a fresh clone +
`make vibecrafted` or `make wizard` _just works_, without requiring the user
to `uv tool install vetcoders-installer` globally first.

When the canonical source changes, copy the module over (paths relative to
your two local checkouts of `vetcoders-tools` and `vibecrafted`):

```bash
cp <vetcoders-tools>/installer/vetcoders_installer/__init__.py \
   <vibecrafted>/scripts/installer/vetcoders_installer/__init__.py
```

## How it's wired

- **`Makefile` target `vibecrafted`** → `uv run --project scripts/installer vetcoders-installer install.toml` (terminal-native default)
- **`Makefile` target `wizard`** → `python3 scripts/installer_gui.py --source "$PWD"` (browser-guided surface)
- **`Makefile` target `gui-install`** → alias for `wizard`
- **`install.sh`** default path → compact CLI installer on the staged snapshot (also used by `make vibecrafted`-style bootstrap)
- **`install.sh --gui`** → `python3 scripts/installer_gui.py --source <staged snapshot>`
- **`install.toml`** at repo root declares the three phases (Foundations /
  Skills & Helpers / Doctor) with `persist = true`
- **`.venv/`** lives in this directory (git-ignored); first `uv sync` creates
  it, subsequent runs reuse it

## Testing without mutating state

From your local checkout of `vibecrafted`:

```bash
python3 scripts/installer_gui.py --source .
uv run --project scripts/installer vetcoders-installer install.toml --dry-run
uv run --project scripts/installer vetcoders-installer install.toml --only doctor --verbose
```

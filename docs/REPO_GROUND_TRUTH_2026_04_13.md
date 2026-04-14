# Vibecrafted Repo Ground Truth — vc-research Summary

Date: 2026-04-13
Run ID: `rsch-230053`

This is the repo-local summary of the external vc-research artifact written to:

`/Users/polyversai/.vibecrafted/artifacts/VetCoders/vibecrafted/2026_0413/reports/20260413_2300_20260413_2300_perform-the-vc-research-skill-on-this-reposito_codex.md`

## Problem

We needed runtime truth for Vibecrafted's install and control-plane shape:
which path is actually canonical today, where code/docs/contracts drift apart,
and what architectural cut would reduce that drift without breaking the current
release engine.

## Current State

Vibecrafted is not one installer engine yet. It is a layered system:

- `install.sh` stages a snapshot into
  `~/.vibecrafted/tools/vibecrafted-current` and chooses between:
  - `scripts/installer_gui.py` for `--gui`
  - `scripts/vetcoders_install.py install --with-shell --compact --non-interactive`
    for non-interactive bootstrap
  - `uv run --project scripts/installer vetcoders-installer install.toml`
    for the interactive local shell path
- `make vibecrafted` uses the vendored `vetcoders-installer` runner.
- `make wizard` opens `scripts/installer_gui.py`.
- `install.toml` is the newer orchestration graph, but it still shells into
  `scripts/vetcoders_install.py` for `list`, `install`, and `doctor`.
- `scripts/vibecrafted` is the runtime command deck, not the installer.

## Main Findings

### 1. Split installer brain is the main architectural risk

The repo currently has two live installer layers:

- the vendored manifest runner in `scripts/installer/`
- the imperative mutation engine in `scripts/vetcoders_install.py`

That would be manageable if one clearly orchestrated the other everywhere, but
today behavior still forks by surface and by TTY state.

### 2. Public install story and executable truth are only partially aligned

The good news:

- installer docs and tests now agree on the polarized contract:
  - public CTA is browser-first
  - local checkout path is shell-first
  - `make install` is automation

The bad news:

- README still leads with the browser-first public story
- Quick Start still leads with the terminal-native human kickoff story
- `install.sh` non-interactive bootstrap still bypasses the manifest runner and
  jumps directly into `scripts/vetcoders_install.py`

So the repo is telling a cleaner story than it actually executes.

### 3. Path ownership language is drifting harder than the code

Executable truth resolves the durable store from `VIBECRAFTED_HOME` and helper
config from `XDG_CONFIG_HOME`.

But docs, runtime contracts, and even `install.toml` still mix in
`$VIBECRAFTED_ROOT/.vibecrafted/...` language.

That drift is not cosmetic:

- verification commands in docs still point at
  `$VIBECRAFTED_ROOT/.vibecrafted/tools/...`
- `install.toml` still describes workspace directories under
  `$VIBECRAFTED_ROOT/.vibecrafted/`
- runtime docs still describe the canonical artifact store as repo-rooted in
  some places and `VIBECRAFTED_HOME`-rooted in others

### 4. Repo-local artifact links are a convenience view, not durable truth

`.vibecrafted/plans` and `.vibecrafted/reports` inside the repo are created as
symlinked convenience views over the canonical artifact store.

In this workspace they currently point into a pytest temp directory, which is a
good demonstration of why docs must not describe those links as canonical or
guaranteed to exist immediately after install.

### 5. Gates are mostly green, but runtime truth is not fully green

Security and shell hygiene are fine:

- `python3 scripts/check_shell.py` → clean
- `semgrep scan --config auto --error --quiet --exclude-rule html.security.audit.missing-integrity.missing-integrity .` → clean

But the TUI/runtime surface is not fully green:

- `PYTHONPATH="$PWD" python3 -m pytest tests/tui -q` →
  `1 failed, 203 passed, 2 skipped`
- current failing test:
  `tests/tui/test_frontier_resolution.py::test_vc_dashboard_mixes_companion_zellij_config_with_repo_layout`
- failure meaning:
  `vc-dashboard` currently prefers the repo Zellij config over the companion
  XDG config the test expects

## Highest-Leverage Cut

Do not rewrite the mutation logic twice.

Recommended order:

1. Make `install.toml` plus the built-in `vetcoders-installer` runner the one
   canonical installer graph.
2. Keep `scripts/vetcoders_install.py` as the only mutation backend until the
   shared graph and path model are stable.
3. Thin `install.sh`, `installer_gui.py`, and `installer_tui.py` into wrappers
   over that shared orchestration and one shared path module.
4. Remove `$VIBECRAFTED_ROOT/.vibecrafted` language from docs, `install.toml`,
   and verification snippets unless the code really uses it.
5. Only after that, decide whether `scripts/vetcoders_install.py` should be
   absorbed into the manifest runner or retained as the backend engine.

## Verification Snapshot

- `PYTHONPATH="$PWD" python3 -m pytest tests/tui -q`
  - result: `1 failed, 203 passed, 2 skipped`
  - failing test:
    `tests/tui/test_frontier_resolution.py::test_vc_dashboard_mixes_companion_zellij_config_with_repo_layout`
- `python3 scripts/check_shell.py`
  - result: clean
- `semgrep scan --config auto --error --quiet --exclude-rule html.security.audit.missing-integrity.missing-integrity .`
  - result: clean

## Operational Note

I also attempted the repo-native headless `vc-research` terminal swarm for this
run. In this environment, Claude and Gemini only wrote `.meta.json` files stuck
at `launching`, and Codex only emitted a session stub transcript. That does not
change the repo-architecture findings above, but it is a real runtime signal:
the headless spawn surface is not trustworthy enough yet to be treated as
boringly reliable.

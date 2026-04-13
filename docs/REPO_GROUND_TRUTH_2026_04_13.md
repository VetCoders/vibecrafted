# Vibecrafted Repo Ground Truth — vc-research Summary

Date: 2026-04-13
Run ID: `rsch-230053`

This is the repo-local summary of the external vc-research artifact written to:

`/Users/polyversai/.vibecrafted/artifacts/VetCoders/vibecrafted/2026_0413/reports/20260413_2300_20260413_2300_perform-the-vc-research-skill-on-this-reposito_codex.md`

## Current State

Vibecrafted is not yet one packaged runtime. It is a staged-repo control plane
with multiple front doors:

- `install.sh` stages a snapshot into `~/.vibecrafted/tools/vibecrafted-current`
  and routes to GUI or compact headless install.
- `make vibecrafted` / `make install` run the vendored packaged runner
  `vetcoders-installer` via `uv run --project scripts/installer ...`.
- `installer_gui.py` and headless bootstrap still shell directly into
  `scripts/vetcoders_install.py`, which remains the actual mutation engine.

## Main Finding

The biggest risk is not failing tests. The repo’s gates are strong. The real
risk is structural drift caused by duplicate orchestration:

- `install.toml` defines one installer graph.
- `install.sh` defines another routing graph.
- `installer_gui.py` constructs its own install plan.
- `installer_tui.py` still carries duplicated helper/path/install logic.

This creates hidden divergence between public install, local install, and
automation paths even when copy remains coherent.

## Highest-Leverage Cut

Do not spend the next pass on more polish first. Spend it on deleting duplicate
installer brains.

Recommended order:

1. Make `install.toml` or a generated derivative the one canonical installer
   graph for all paths.
2. Keep `scripts/vetcoders_install.py` as the only mutation engine until the
   unified graph is stable.
3. Reduce `install.sh`, `installer_gui.py`, and any surviving TUI surface to
   thin wrappers/renderers over that same graph.
4. Then package the real runtime surface so `vibecrafted`, `doctor`, installer
   behavior, and optional GUI launch ship from one versioned distribution.

## Secondary Drift To Fix Early

Unify path language around `VIBECRAFTED_HOME` / `~/.vibecrafted` and
`XDG_CONFIG_HOME`. The current mix of `$VIBECRAFTED_ROOT/.vibecrafted/...` and
runtime code based on `VIBECRAFTED_HOME` is avoidable trust debt.

## Verification Snapshot

- `PYTHONPATH="$PWD" python3 -m pytest tests/tui -q` → `204 passed, 2 skipped`
- `python3 scripts/check_shell.py` → clean
- `semgrep scan --config auto --error --quiet --exclude-rule html.security.audit.missing-integrity.missing-integrity .` → clean

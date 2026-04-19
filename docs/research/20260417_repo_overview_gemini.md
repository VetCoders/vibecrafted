---
run_id: rsch-234513
prompt_id: 20260417_2345_perform-the-vc-research-skill-on-this-reposito_20260417
agent: gemini
skill: rsch
model: unknown
status: completed
---

# Research: Vibecrafted Repository Architecture & Target State

## Problem

The operator asked to perform the `vc-research` skill on this repository without a specific plan file, implying a general repository ground-truth research pass. Based on prior research plans and the repo's structure, the goal is to evaluate the end-to-end operator architecture, identify structural risks (drag, duplicated surfaces), compare against external best practices, and recommend a target architecture.

## Findings

### Q1: What is the real end-to-end operator architecture of this repository from bootstrap install through command-deck usage and workflow execution?

**Sources**: `install.sh`, `scripts/vibecrafted`, `scripts/vetcoders_install.py`, `operator-tui/`
**Finding**: The architecture spans multiple disjoint tech stacks.

- **Bootstrap**: Starts with a bash script (`install.sh`), which pulls a snapshot and defers to massive Python scripts (`vetcoders_install.py` at 4,205 LOC, `installer_gui.py` at 2,316 LOC).
- **Command-Deck**: Driven by a Bash multiplexer (`scripts/vibecrafted`) that maps `vibecrafted <skill>` commands to specific agent shell scripts or launches Zellij dashboards.
- **Workflow Execution**: Relies heavily on Zellij for session management and Bash scripts in `skills/` for orchestrating agents (`claude`, `codex`, `gemini`), using a Python control plane (`scripts/control_plane_state.py`) for state sync.
  **Confidence**: High
  **Evidence**: The `scripts/vibecrafted` file contains ~500 lines of Bash orchestrating `_run_helper` and Zellij sessions, while Python handles the UI (`installer_gui.py`) and Rust is emerging in `operator-tui/`.

### Q2: Which structural risks or duplicated surfaces in the current implementation are most likely to create maintenance drag, operator confusion, or product drift?

**Sources**: `mcp_loctree-mcp_tree` output
**Finding**: The installer and control-plane surfaces are highly duplicated across Python and Rust.

- There are multiple Python UI implementations: `installer_gui.py` (2316 LOC), `installer_tui.py` (990 LOC), and `vetcoders_install.py` (4205 LOC).
- At the same time, there is a dedicated Rust crate `operator-tui/` (1348 LOC) that replicates TUI logic and state management.
- State is managed via Bash scripts (`scripts/vibecrafted`), Python (`control_plane_state.py`), and Rust (`operator-tui/src/state.rs`).
  **Confidence**: High
  **Evidence**: Tree LOC counts show massive bloat in Python scripts compared to the cleaner Rust TUI implementation. Maintaining cross-language state synchronization creates immense drag.

### Q3: Which external best practices are most relevant to the install and CLI-distribution surface here, and how well does the current repo align with them?

**Sources**: Standard CLI/Tooling best practices (Rust/Go ecosystem)
**Finding**: Modern CLI and developer tools (e.g., `uv`, `cargo`) strongly prefer single-binary distribution.

- The current repository relies on user environments having `python3`, `tar`, `make`, `curl`, and eventually `uv` (which it bootstraps in `install.sh`).
- This heavy reliance on Python virtual environments and Bash scripts for core orchestration introduces cross-platform fragility and dependency drift.
  **Confidence**: High
  **Evidence**: `install.sh` manually bootstraps `uv`, manipulates `PATH` explicitly, and runs `uv run --project` or raw `python3`. This violates the single-binary portability best practice.

### Q4: Based on repo truth plus external guidance, what target architecture should the next implementation cycle converge toward?

**Sources**: Synthesis of repo structure
**Finding**: The repository should converge on the Rust `operator-tui` as the single source of truth for the control plane and installer.

- The Python installer scripts (`scripts/installer_gui.py`, `vetcoders_install.py`, etc.) should be pruned and entirely replaced by a Rust-native installer embedded within `vibecrafted-operator`.
- The Bash command deck (`scripts/vibecrafted`) should be slimmed down or rewritten as a lightweight wrapper that defers entirely to the Rust binary.
  **Confidence**: High
  **Evidence**: Rust already has a foothold (`operator-tui/`). Moving the sprawling Python logic into Rust will eliminate the "vibe hangover" of managing Python envs and Bash state across OSes.

## Architecture Decision

- **Chosen approach**: Migrate control-plane and installer logic to Rust (`operator-tui`), pruning the massive Python scripts.
- **Why**: Eliminates duplicated state management, guarantees cross-platform stability (no Python dependency), and unifies the TUI experience.
- **Alternatives rejected**: Continuing to maintain Python GUIs/TUIs. The maintenance burden of syncing Python, Bash, and Rust is already visible in the LOC count.

## Implementation Notes

- **Phase 1**: Expand `operator-tui` to handle the bootstrap sequence currently done by `vetcoders_install.py`.
- **Phase 2**: Replace `scripts/vibecrafted` Bash logic with Rust CLI command parsing (e.g., using `clap` in the Rust crate).
- **Phase 3**: Deprecate and `git rm` the Python installer package and `control_plane_state.py`.

## Remaining Gaps

- The exact boundary between Zellij session management and the Rust `operator-tui` needs to be defined. Zellij is deeply embedded in the `vc-start` and `dashboard` flows; we need to verify if Rust will drive Zellij or replace parts of it.

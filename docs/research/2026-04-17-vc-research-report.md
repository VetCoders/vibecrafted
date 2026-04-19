---
run_id: rsch-234513
prompt_id: 20260417_2345_perform-the-vc-research-skill-on-this-reposito_20260417
agent: codex
skill: rsch
model: unknown
status: completed
---

# Research: Control-Plane Convergence on the Current Branch

## Problem

This repository already had a broad ground-truth research pass on 2026-04-16.
The current branch changes the picture by introducing a Rust `operator-tui`
crate, new Python control-plane helpers, and a branch-level push toward a more
formal operator console. The real research question for today is not "what is
Vibecrafted in the abstract?" but "what architecture is actually emerging now,
where is it still split-brain, and what is the strongest next convergence move?"
Out of scope: implementing the fixes, redesigning the product surface, or
reopening the whole framework strategy.

## Findings

### Q1: What is the real runtime center of gravity after the new operator-console work?

**Sources**: `scripts/control_plane_state.py`, `scripts/control_plane_launch.py`, `scripts/vibecrafted`, `operator-tui/src/app.rs`, `operator-tui/src/launch.rs`, `operator-tui/src/state.rs`, `operator-tui/tests/state_contract.rs`, `operator-tui/README.md`

**Finding**: The current branch is converging on a shared control-plane contract, not on a full Rust replacement. Python is still the writer and normalizer of runtime truth, Bash is still the command-deck executor, and Rust is currently a consumer-facing operator shell on top of that existing contract.

**Confidence**: high

**Evidence**:

- `scripts/control_plane_state.py` defines the canonical aggregate today: it
  merges agent metadata, lock files, and marbles loop state into
  `control_plane/runs/*.json`, returns `active_runs`, `recent_runs`, warnings,
  and an `events.jsonl` tail, and exposes that through `sync_state()`.
- `scripts/control_plane_launch.py` still launches the live workflow surface by
  shelling out to `scripts/vibecrafted`, then re-syncing the control plane.
- `operator-tui/src/app.rs` loads `ControlPlaneState`, renders runs/events, and
  builds launch requests, but its `launch_command()` still points back at the
  command deck instead of owning workflow execution itself.
- `operator-tui/tests/state_contract.rs` verifies that the Rust side reads the
  `runs/` snapshots and `events.jsonl` contract rather than inventing an
  independent state model.

### Q2: What are the highest-leverage structural risks on this branch?

**Sources**: `operator-tui/README.md`, `operator-tui/src/config.rs`, `scripts/control_plane_state.py`, `scripts/control_plane_launch.py`, `operator-tui/src/launch.rs`, `scripts/vibecrafted`, `docs/MODULARIZATION_PLAN_2026_04_16.md`, loctree `follow(all)`

**Finding**: The sharpest risk is not "too much Python" by itself. It is contract drift hidden behind compatibility fallbacks. The branch now has multiple path conventions, multiple launch builders, and multiple surfaces that can appear correct locally while diverging semantically over time.

**Confidence**: high

**Evidence**:

- Path drift is already visible:
  - `scripts/control_plane_state.py` writes under `VIBECRAFTED_HOME/control_plane`
  - `scripts/vibecrafted` launches the Rust console with `--state-root "$crafted_home/control_plane"`
  - `operator-tui/README.md` documents `$VIBECRAFTED_HOME/state/control-plane`
  - `operator-tui/src/config.rs` compensates by probing four candidates:
    `control_plane`, `state/control-plane`, `state`, and `control-plane`
- Launch logic is duplicated:
  - Python: `scripts/control_plane_launch.py::build_launch_command`
  - Rust: `operator-tui/src/launch.rs::build_launch_command`
    Both target the same command deck, but they encode the workflow contract in
    two languages.
- Loctree flags the Python/Rust `build_launch_command` duplication directly,
  which is a stronger signal than a stylistic complaint because it sits on the
  workflow boundary.
- The broader modularization plan is still valid: installer truth is duplicated
  too, but on this branch the control-plane and launch contract are the most
  immediate split-brain risk because they now span Bash, Python, and Rust at
  once.

### Q3: Which external best practices matter most here, and how well does the branch align?

**Sources**: XDG Base Directory Specification (`https://specifications.freedesktop.org/basedir/latest/`), Zellij layouts/config docs (`https://zellij.dev/documentation/layouts-with-config`), uv installation docs (`https://docs.astral.sh/uv/getting-started/installation/`)

**Finding**: The repo aligns reasonably well with inspectable bootstrap practice, but only partially aligns with filesystem/state conventions. The external guidance does not force a Rust rewrite; it mostly argues for a cleaner contract and path model.

**Confidence**: medium-high

**Evidence**:

- The XDG Base Directory Specification distinguishes config, data, state, cache,
  and runtime data, and explicitly says state that persists across restarts
  belongs under `$XDG_STATE_HOME`, while runtime communication belongs under
  `$XDG_RUNTIME_DIR`. Vibecrafted currently keeps long-lived control-plane state
  under `~/.vibecrafted/control_plane`, which works, but is only partially
  normalized against that spec.
- Zellij's own layout/config model supports leaving pane orchestration external
  and declarative. That supports Vibecrafted's current "thin front door over a
  session orchestrator" approach and argues against prematurely burying Zellij
  behavior inside the Rust TUI.
- uv's official installation guidance explicitly supports both inspectable
  installer scripts and package-manager distribution. That means Vibecrafted's
  current install posture is defensible; the stronger gap is standardization of
  state/layout contracts, not the mere existence of shell and Python in the
  bootstrap path.

### Q4: What should the next implementation cycle converge toward?

**Sources**: repo-local control-plane files, `docs/MODULARIZATION_PLAN_2026_04_16.md`, prior repo-local research reports from 2026-04-16 and 2026-04-17

**Finding**: The next cycle should converge on one versioned control-plane schema, one path policy, and one launch-contract implementation. The best move is not "rewrite everything in Rust now" and not "leave the mixed stack alone." It is to make Bash, Python, and Rust speak one boring contract first, then decide which layer deserves long-term ownership.

**Confidence**: high

**Evidence**:

- The new Rust console already proves there is value in a typed reader/UI layer.
- The Python control-plane writer already proves there is existing runtime truth
  worth preserving.
- The current branch already contains the warning signs of an uncontrolled
  split: fallback path probing, duplicated launch assembly, and documentation
  disagreement.
- Existing repo-local research disagreement is productive here:
  - the earlier Codex pass favored "thin front doors over one shared contract"
  - the current Gemini pass favored "move the control plane into Rust"
    My synthesis is that the contract must converge before the ownership language
    choice becomes a healthy decision.

## Synthesis

- Recommended approach: formalize the control-plane as the product, not any one implementation language. Introduce a versioned schema for run snapshots and events, normalize the state root to one policy, and extract one shared launch-contract definition that both Python and Rust consume.
- Why this is stronger: it removes the most dangerous present lie in the repo, which is that multiple surfaces appear to be "the control plane" while quietly translating between slightly different path and launch assumptions.
- Alternatives considered:
  - Full Rust rewrite now: attractive, but premature while the state and launch contract are still shifting. It would replace implementation duplication with migration risk.
  - Keep the current mixed stack indefinitely: cheaper today, but it bakes in hidden drift and guarantees more compatibility scaffolding later.
- Open questions:
  - Whether long-lived run snapshots should stay under a custom `VIBECRAFTED_HOME`
    root or move toward a clearer XDG split for config vs state
  - Whether the Rust console should eventually own workflow launch semantics or
    remain a UI shell over the command deck
  - Whether the control-plane schema should be generated from one source
    (for example JSON Schema or a shared manifest) to avoid Python/Rust drift

## Implementation Notes

1. Make the control-plane root canonical.
   Choose one path model and delete the compatibility ambiguity after a short
   migration window. Right now the codebase accepts multiple roots because the
   docs and implementations disagree.

2. Version the snapshot and event schema.
   Add an explicit schema version to run snapshots and events before more
   consumers appear. The branch is at the exact point where this is still cheap.

3. Remove duplicated launch assembly.
   Keep one source of truth for how `workflow`, `research`, `review`, and
   `marbles` launches are encoded. The other language layer should call or
   deserialize that truth, not reinterpret it.

4. Keep the Rust console thin for one more cycle.
   Let it stay a reader/launcher over the live command deck until the contract
   stops moving. The current tests support that shape.

5. Revisit installer modularization after the control-plane contract settles.
   The installer duplication called out in the modularization plan is real, but
   the branch-local highest leverage move is to stop the new Rust/Python/Bash
   control-plane from forking first.

## Verification Snapshot

- `pytest tests/tui/test_control_plane_state.py tests/tui/test_vibecrafted_launcher.py -q` -> `25 passed`
- `cargo test --manifest-path operator-tui/Cargo.toml` -> `4 passed`
- Loctree confirms:
  - no import cycles
  - direct duplication around `build_launch_command`
  - hotspot concentration in `scripts/` and the new `operator-tui` control-plane files

## Boundary

This report is intentionally a research artifact, not an implementation pass.
I did not rewrite the contract, change the state root, or refactor the launch
path. The repo still contains substantial unrelated in-flight changes on this
branch, so I kept this task to ground-truth research, a committed report, and a
clear recommendation for the next cut.

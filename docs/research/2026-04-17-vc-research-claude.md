---
run_id: rsch-234513
prompt_id: 20260417_2345_perform-the-vc-research-skill-on-this-reposito_20260417
agent: claude
skill: rsch
model: claude-opus-4-7
status: completed
---

# Research: Vibecrafted Repository Ground Truth (Δ since 2026-04-16)

## Problem

The prior ground truth (`docs/research/2026-04-16-vc-research-report.md`, run `rsch-183346`)
already answered the four canonical questions for `vibecrafted` as of 2026-04-16.
Between that report and today (2026-04-17), the branch `fix/uzi-marbles-spawn-fix`
gained a substantial new surface: a Rust `operator-tui` crate, two new Python
control-plane modules, a formal `MODULARIZATION_PLAN_2026_04_16.md`, two new
`vibecrafted` subcommands (`gui`, `tui`), and a control-plane sync hook wired into
the agent meta lifecycle. The question for this pass is _what changed in ground
truth_, where the new surface already drifts, and whether yesterday's architectural
recommendation still holds. Out of scope: implementing fixes, touching the presence
frontend, editing install docs.

## Method

- `git status` / `git log` / targeted `git diff HEAD` on every modified or staged
  file.
- Read of the full new Rust crate (`operator-tui/src/{main,lib,app,state,launch,config,ui}.rs`
  plus `tests/state_contract.rs` and `Cargo.toml`) and the full new Python modules
  (`scripts/control_plane_state.py`, `scripts/control_plane_launch.py`).
- Focused diffs on `scripts/vibecrafted`, `scripts/installer_gui.py`,
  `skills/vc-agents/scripts/lib/meta.sh`, and the two updated test files.
- Live runtime probes: `python -m pytest tests/tui/test_control_plane_state.py
tests/tui/test_installer_gui.py tests/tui/test_vibecrafted_launcher.py -q`
  (result: 31 passed), `cargo build`, `cargo test`, `cargo clippy -- -D warnings`,
  `bash scripts/vibecrafted doctor`, `bash scripts/vibecrafted tui --help`,
  `bash scripts/vibecrafted gui --help`, `python -c 'from scripts.control_plane_state
import sync_state; ...'`, and inspection of `~/.vibecrafted/control_plane/`.
- Constraints per the plan in `docs/research/2026-04-16-vc-research-plan.md`:
  repo truth wins over docs; drift between them is called out explicitly; no
  invented command flows.

## Findings

### Q1: What is the real end-to-end operator architecture today?

**Answer**: Yesterday's bootstrap → installer stack → bash command deck description
is still correct, but the repo has grown a **third operator surface** on top of it:
an out-of-process control-plane that writes `~/.vibecrafted/control_plane/runs/*.json`
and `~/.vibecrafted/control_plane/events.jsonl`, and two parallel readers — a
Python browser GUI (`scripts/installer_gui.py`) and a new Rust TUI
(`operator-tui/`). The lifecycle is:

1. `skills/vc-agents/scripts/lib/meta.sh` (via `spawn_promise_meta` and
   `spawn_finish_meta`) writes the agent meta.json and now calls
   `spawn_sync_control_plane` → `python3 scripts/control_plane_state.py sync`
   on every agent state transition.
2. `scripts/control_plane_state.py` crawls `~/.vibecrafted/{artifacts,locks,marbles}`,
   normalizes into `RunStatus` rows, merges duplicates, writes one snapshot per
   `run_id` to `runs/`, and appends state transitions to `events.jsonl`.
3. `scripts/control_plane_launch.py` takes a normalized launch spec (skill, agent,
   prompt/file, runtime, root) and `subprocess.Popen`s `bash scripts/vibecrafted
<skill> [<agent>] --runtime ... --root ... --prompt ...` while the HTTP GUI and
   the Rust TUI observe the resulting snapshot updates.
4. `scripts/vibecrafted` gained `cmd_gui` and `cmd_tui` so the operator can enter
   either reader from the existing command deck. Both call
   `_sync_control_plane_best_effort` before handing off.
5. `operator-tui/` is a stand-alone Rust binary (`vibecrafted-operator`) built with
   `ratatui` + `crossterm` + `serde_json` + `chrono`. It reads the same
   control-plane directory, classifies runs (`active`/`stalled`/`failed`/…),
   renders a list + detail + event + launch-panel layout, and, on Enter, suspends
   the alt-screen and shells out to `scripts/vibecrafted <skill> [<agent>] ...`.

The bash command deck is still the only launcher. The GUI and the TUI are
**thin presentation surfaces** on top of a shared JSONL/JSON state contract.
That is a meaningful shape shift from yesterday's "command deck + installer stack"
description: the deck is now a library, not the front door, for two out-of-process
observers.

**Confidence**: high.

**Sources**:

- `scripts/control_plane_state.py:74` (control-plane home), `:167` (operator session
  naming), `:413` (`sync_state` contract).
- `scripts/control_plane_launch.py:16` (supported sets), `:77`
  (`build_launch_command`), `:99` (`launch_workflow` orchestration).
- `scripts/vibecrafted:197` (new helpers), `:655` (`cmd_gui`), `:676` (`cmd_tui`),
  `:1342` (wrapper symlink dispatch for `vc-gui` / `vc-tui`), `:1398` (skill switch).
- `skills/vc-agents/scripts/lib/meta.sh:3` (`spawn_control_plane_script`), `:18`
  (`spawn_sync_control_plane`), `:121` + `:171` (hook placement).
- `operator-tui/src/main.rs:17` (entrypoint), `:111` (`launch_selected` +
  suspend/restore), `operator-tui/src/state.rs:18` (`ControlPlaneState::load`),
  `:260` (`SafeControlPlaneRoot` symlink-escape guard),
  `operator-tui/src/launch.rs:61` (`build_launch_command`).
- Live runtime: `~/.vibecrafted/control_plane/events.jsonl` = 750 lines,
  `control_plane/runs/` holds dozens of per-run JSON files, confirming the writer
  is live.

### Q2: Which structural risks or duplicated surfaces in the _new_ implementation are most likely to create drag, drift, or operator confusion?

**Answer**: The new surface already carries four risks worth flagging before the
next cycle merges more onto it.

1. **Path-shape drift in brand-new code.** `operator-tui/README.md:11` documents the
   state layout as `$VIBECRAFTED_HOME/state/control-plane/runs/*.json` (hyphen,
   nested under `state/`). The Python writer
   (`scripts/control_plane_state.py:74`) and the live filesystem both use
   `$VIBECRAFTED_HOME/control_plane/` (underscore, top-level). The Rust
   `default_state_root()` (`operator-tui/src/config.rs:89`) defensively probes
   four candidate paths (`control_plane`, `state/control-plane`, `state`,
   `control-plane`) to cover the mismatch. That defensive probing is already a
   symptom: **docs and code disagree on the state root on the day they shipped.**
   Fix direction: pick one path (almost certainly `control_plane/` — the writer
   wins), rewrite the README, and drop the three extra candidates in Rust.

2. **Cargo edition regression against the charter.**
   `.claude/CLAUDE.md` says "Rust: edition = 2024" under
   `CUTOFFFLU PREVENTION`, and the existing `rust/` tree historically tracks that.
   `operator-tui/Cargo.toml:4` pins `edition = "2021"`. This is an easy one-line
   correction that will otherwise rot into an exception that subsequent Rust
   crates will copy.

3. **Clippy gate is not green.** The charter says "Rust repos: `cargo clippy --
-D warnings`." Today:

   ```
   error: this `if` can be collapsed into the outer `match`
     --> src/main.rs:82:17
   = note: `-D clippy::collapsible-match` implied by `-D warnings`
   ```

   The crate builds and the four `state_contract.rs` tests pass, but the lint
   gate fails. Left unfixed, the crate ships with a lint exception that lowers
   the bar for every subsequent Rust module.

4. **Surface triplication risk for the operator front door.** Yesterday the repo
   already had three install front doors (`install.sh`, `installer_tui`,
   `installer_gui`) converging on one mutation backend. Today the operator front
   door has inherited the same shape: `installer_gui` (browser),
   `operator-tui` (Rust), and the raw `scripts/vibecrafted` command deck all
   read/write the same control-plane contract. The contract itself is currently
   only documented in docstrings and `operator-tui/README.md`. If that contract
   is not promoted to a single source of truth (schema + sample fixtures + one
   shared parser or validator), the three readers will quietly diverge on field
   aliases, state classifications, and lifecycle assumptions. Early signal:
   `operator-tui/src/state.rs:78` already carries `#[serde(alias = "runId")]` /
   `alias = "session_id"` / `alias = "lastHeartbeat"` etc., which only make sense
   if the author has seen multiple capitalizations of the same field in the
   wild.

Secondary observations:

- `scripts/control_plane_state.py:297` (`_merge_status`) uses
  `dt.datetime.min.replace(tzinfo=dt.timezone.utc)` as a sentinel for missing
  timestamps inside a comparison that expects real UTC timestamps. That works
  for the happy path but conflates "unknown" with "oldest possible", which will
  make stalled-run classification brittle once `updated_at` strings get sloppy.
- `scripts/control_plane_launch.py:115` uses `subprocess.Popen` with
  `start_new_session=True` and writes stdout/stderr into a per-launch log file
  without tracking the child PID anywhere the reader can see. There is no
  mechanism in the GUI or the TUI to reap or cancel a previously launched run
  other than by inspecting the control-plane snapshot. Good enough for now;
  worth naming as a deliberate limitation before it leaks into a "cancel" button.

**Confidence**: high on (1), (2), (3); medium-high on (4) (assessed from code
shape, not from concrete divergence yet).

**Sources**:

- `operator-tui/README.md:11`, `scripts/control_plane_state.py:74`,
  `operator-tui/src/config.rs:89`.
- `operator-tui/Cargo.toml:4`, `.claude/CLAUDE.md` (CUTOFFFLU PREVENTION block).
- `cargo clippy -- -D warnings` output (captured above).
- `operator-tui/src/state.rs:78`, `scripts/control_plane_state.py:297`,
  `scripts/control_plane_launch.py:115`.

### Q3: How does the new surface align with external best practice for Rust TUIs and Python control-plane daemons?

**Answer**: Reasonably well, with two specific gaps.

- **Rust TUI stack.** `ratatui 0.29` + `crossterm 0.29` is the current mainstream
  pairing for terminal UIs, and the alt-screen enable/disable around
  `suspend_and_run` (`operator-tui/src/main.rs:121`) matches how
  `ratatui`'s own docs recommend handling suspended subprocesses. The pattern
  used here — tick-rate event loop with `event::poll(timeout)`, separate
  `App::refresh()` that reloads the filesystem snapshot — is also what the
  ratatui examples demonstrate. Gap: there is no SIGTERM/panic hook that calls
  `disable_raw_mode` + `LeaveAlternateScreen` before dying, so a crashed TUI can
  leave the terminal in alt-screen mode. The standard ratatui solution is a
  `std::panic::set_hook` that restores the terminal.

- **Python control-plane.** `_sync_lock()` on `~/.vibecrafted/control_plane/.sync.lock`
  with `fcntl.LOCK_EX` is the right shape for a multi-writer directory where
  each writer is an agent meta hook. The snapshot-per-run layout
  (`runs/<run_id>.json`) plus an append-only `events.jsonl` is close to the
  append-only event-sourcing pattern used by CLI control planes like `systemd-run`
  and `nomad`. Gap: `_append_event` (`scripts/control_plane_state.py:176`) opens
  `events.jsonl` without an fcntl lock, so a crash mid-append can leave a
  half-written line that the Rust reader silently drops
  (`state.rs:332`: `if let Ok(event) = serde_json::from_str::<RunEvent>(line)`).
  This is a "silent loss on crash" vs. "explicit fsync" tradeoff. For a local
  operator console the current behavior is defensible, but the charter's
  "measure twice, cut once" stance would ask for an explicit call-out in the
  module docstring.

**Confidence**: medium-high on the tooling alignment, medium on the two specific
gaps (derived from code reading against documented patterns, not from a formal
comparison against a reference implementation).

**Sources**:

- `operator-tui/Cargo.toml` dependency pins.
- `operator-tui/src/main.rs:23`, `:121` (terminal lifecycle).
- `scripts/control_plane_state.py:90` (`_sync_lock`), `:176` (`_append_event`).
- `operator-tui/src/state.rs:332` (tolerant per-line parse).

### Q4: Does yesterday's target architecture still hold, or does it need to be updated?

**Answer**: Yesterday's recommendation (_"converge on `install.toml` +
`vetcoders-installer` as the sole install graph, keep
`scripts/vetcoders_install.py` as the sole mutator, and treat every other install
surface as a thin selector or presentation wrapper"_) is **still correct and
unchanged for the install side**. Nothing in today's delta contradicts it. What
today adds is a **second convergence target** on the operator side:

> Converge on `$VIBECRAFTED_HOME/control_plane/` as the single control-plane
> contract. `scripts/control_plane_state.py` is the sole writer (invoked from
> `meta.sh` and from launch). `scripts/control_plane_launch.py` is the sole
> launcher shim. Every reader — `installer_gui.py`, `operator-tui/`, and
> whatever `vibecrafted dashboard` grows into — is a thin presentation surface
> over that contract, bound by a _single documented schema_ (JSON schema + fixture
> files), and _never_ talks to the meta/locks/marbles filesystem directly.

The `docs/MODULARIZATION_PLAN_2026_04_16.md` already proposes the internal split
of `vetcoders.sh` and `vetcoders_install.py`. This research only adds three
explicit items to that plan:

1. Add `scripts/control_plane/` (or `scripts/operator/`) as a first-class Python
   package with `state.py`, `launch.py`, `schema.py`, and `events.py` instead of
   two sibling files in `scripts/`. That gives the repo somewhere obvious to put
   the fixture `.json` files and the shared contract docstring.
2. Promote the control-plane shape to `docs/operator/CONTROL_PLANE.md` so the
   Rust TUI, the Python GUI, and any future reader agree on field names, state
   vocabulary (`initialized|launching|promise|confirmed|running|paused|stalled|
completed|converged|stopped|failed|timed_out|gc` per `control_plane_state.py`),
   and timestamp conventions.
3. Add a small Rust binary feature gate or compile-time `include_str!` of the
   schema fixture so the `state_contract.rs` tests keep checking the Python-owned
   contract, not a Rust-local idealization. This prevents the two implementations
   from drifting under their aliases.

The ordering from yesterday's plan is still correct: converge the internal
contract first, then decide whether the packaged public CLI should become
`vibecrafted` itself.

**Confidence**: medium-high.

**Sources**:

- Yesterday's report, `docs/research/2026-04-16-vc-research-report.md` (Q4 +
  Architecture Decision).
- `docs/MODULARIZATION_PLAN_2026_04_16.md` (proposal, quick wins, recommended
  order).
- `scripts/control_plane_state.py` (ACTIVE_STATES / FINAL_STATES),
  `operator-tui/src/state.rs` (RunKind classification),
  `operator-tui/tests/state_contract.rs` (contract-style tests).

## Architecture Decision

- **Chosen approach**: Keep the two convergence targets side by side:
  1. Yesterday's install-side target (single install graph, single mutator, thin
     front doors).
  2. A new operator-side target: single control-plane contract under
     `$VIBECRAFTED_HOME/control_plane/`, one writer (`control_plane_state.py`),
     one launcher shim (`control_plane_launch.py`), thin readers
     (`installer_gui`, `operator-tui`).

- **Why**: The install and operator surfaces are now structurally analogous
  (orchestration contract + mutation backend + N thin presentation layers). A
  single discipline applied to both keeps mental load down and prevents the same
  drift from emerging twice.

- **Alternatives rejected**:
  - _Fold the operator console into `installer_gui.py` and drop `operator-tui/`._
    Rejected because the charter explicitly values a crafted Rust TUI for
    operator work and because a local-browser-only flow is a weak fit for the
    "dragon-in-the-tmux" operator reality.
  - _Make `operator-tui/` the primary launcher and collapse the bash command
    deck._ Premature. The bash deck is the sole launcher today, absorbs all the
    existing skill semantics, and is already tested by
    `tests/tui/test_vibecrafted_launcher.py`. Collapsing it should follow, not
    lead, the contract unification.

## Implementation Notes

1. **Fix the path-shape drift first.** Pick `control_plane/` (underscore,
   top-level). Update `operator-tui/README.md:11` to reference
   `$VIBECRAFTED_HOME/control_plane/`. Trim the fallback list in
   `operator-tui/src/config.rs:89` to one candidate. This is a ~10-line change
   that removes a foot-gun.

2. **Green the Rust lint gate.** Either apply clippy's suggested
   `KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => { ... }`
   in `operator-tui/src/main.rs:82` or add an explicit
   `#[allow(clippy::collapsible_match)]` with a one-line justification. No gate
   should ship red on the same day it was opened.

3. **Bump to `edition = "2024"`** in `operator-tui/Cargo.toml`. Verify `cargo
test` and `cargo clippy -- -D warnings` still pass. This is the charter
   default and the rest of the Rust surface is aligned on it.

4. **Harden the state contract in one place.** Create
   `scripts/operator/schema.py` (or `scripts/control_plane/schema.py`) holding a
   single JSON schema or TypedDict for `RunStatus` and `RunEvent`, plus fixture
   files. Point both `operator-tui/tests/state_contract.rs` and
   `tests/tui/test_control_plane_state.py` at the same fixtures.

5. **Promote operator docs.** Add `docs/operator/CONTROL_PLANE.md` that describes:
   - the state directory layout
   - the state vocabulary (`ACTIVE_STATES`, `FINAL_STATES`, classification rules)
   - the event shape
   - the launch wire format
   - the sync + lock semantics.
     This is the one thing most likely to prevent field-alias drift six months
     from now.

6. **Document the surface triplication as a deliberate choice.** The operator
   front door is browser-first for onboarding (per `docs/installer/DESIGN.md`)
   and TUI-first for power use. Both are legitimate; the risk is silent drift
   between them. A one-page "Operator surfaces" doc under `docs/operator/` plus
   the shared fixtures from (4) addresses this.

7. **Defer the modularization plan's Phase 1 until the contract is stable.**
   Splitting `vetcoders.sh` into `shell/lib/*.sh` is still a good idea and is
   already scheduled; it does not interact with the operator surface, so no
   sequencing conflict here. Phase 2 (installer shared helpers) also remains
   sequenced after the contract is frozen.

8. **Cluster-fix the meta/report fallback seam.** Do not treat the four red
   tests as four separate bugs. They all live on the path _"meta.json written,
   but the paired `<run>.md` fallback report is not materialized"_. Fix the
   writer in `skills/vc-agents/scripts/lib/meta.sh` (or its callers) so that
   `spawn_finish_meta` always leaves a well-formed markdown report beside the
   meta, including on auth-error and child-dies-before-meta paths. This one
   change should turn the test count from `4 failed, 217 passed` back to green.

## Verification Snapshot

- `git status` on `fix/uzi-marbles-spawn-fix` — 13 staged new/modified entries
  spanning `operator-tui/`, `scripts/control_plane_*.py`, `docs/MODULARIZATION_
PLAN_2026_04_16.md`, `tests/tui/test_control_plane_state.py`,
  `scripts/vibecrafted`, `scripts/installer_gui.py`,
  `skills/vc-agents/scripts/lib/meta.sh`, and the two updated test files.
- `python -m pytest tests/tui/test_control_plane_state.py
tests/tui/test_installer_gui.py tests/tui/test_vibecrafted_launcher.py -q`
  → `31 passed in 16.29s`.
- `cargo build` under `operator-tui/` → clean (no warnings emitted during the
  build phase).
- `cargo test` under `operator-tui/` → `4 passed; 0 failed` on
  `tests/state_contract.rs` plus empty unit-test bins.
- `cargo clippy --all-targets --quiet -- -D warnings` under `operator-tui/` →
  **FAILED** on `clippy::collapsible_match` in `src/main.rs:82`.
- `make check` → `Running shellcheck on 55 shell files... Check complete.`
- `bash scripts/vibecrafted doctor` → `95 ok, 2 warnings, 0 failures`
  ("Installation healthy with minor warnings").
- `bash scripts/vibecrafted tui --help` and `bash scripts/vibecrafted gui --help`
  both render the expected help screens, confirming the new skill wiring in
  `cmd_help`/`cmd_help_full`/`run_wrapper`/`main`.
- `python -c "from scripts.control_plane_state import control_plane_home,
sync_state; print(control_plane_home()); ..."` →
  `/Users/polyversai/.vibecrafted/control_plane`, `active: 322`, `recent: 12`.
  The writer is live and is being exercised by real runs.
- `wc -l ~/.vibecrafted/control_plane/events.jsonl` → 750 lines, covering weeks
  of agent state transitions.
- `make test` completed end-to-end in ~7:49: **4 failed, 217 passed, 2 skipped**,
  exit code non-zero (`make: *** [test] Error 1`). The three marbles runtime
  failures flagged in yesterday's report still fail:
  - `tests/tui/test_marbles_runtime.py::test_marbles_materializes_failed_loop_when_child_spawn_dies_before_meta`
  - `tests/tui/test_marbles_runtime.py::test_marbles_watcher_waits_for_meta_completion_before_advancing`
  - `tests/tui/test_marbles_runtime.py::test_marbles_watcher_does_not_consume_failed_fallback_report`
    One **new** failure appeared since yesterday:
  - `tests/tui/test_spawn_common.py::test_codex_spawn_marks_meta_failed_when_codex_emits_non_json_auth_error`
    asserts that a `<run>.md` report file gets materialized next to the
    `.meta.json` when a codex spawn exits with a non-JSON auth error (exit 17).
    The meta is correctly marked `failed` with `exit_code=17`, but the markdown
    fallback report is not written. That is a regression in the spawn-error
    fallback path, not a flake — the same failure surface as the three marbles
    "watcher/meta/report timing" failures. All four failures live on the same
    seam: _meta is written, but the report/transcript fallback is not
    materialized in time or at all_. Treat this as one cluster, not four
    independent bugs.

## Remaining Gaps

- `make test` is still red (4 failures, 217 passes). All four failures hit the
  same meta/report fallback seam. Yesterday's implementation note ("treat
  `marbles` watcher/meta/report timing as the highest-priority runtime fix
  before advertising the broader workflow surface as fully stable") is
  confirmed, and today's fourth failure widens the surface from `marbles`-only
  to `test_spawn_common`-level. This is the single biggest concrete blocker
  flagged by this research.
- No formal schema file exists yet for the control-plane contract; the Rust and
  Python sides agree today because the code is fresh, not because they reference
  a shared schema.
- The packaging question ("does `vibecrafted` itself become the distributed CLI?")
  is unchanged from yesterday and is still gated on the install-graph and
  control-plane contracts settling.
- I did not re-inspect the downstream `vibecrafted-io-link` mirror repo beyond
  noting its presence; yesterday's report already documented its effect on
  `pytest -q` discovery.

## Honest Boundary

Per the worker charter, I did not spawn another research fleet and did not
re-open frontier selection. The parallel codex and gemini workers launched from
the same vc-research invocation are expected to produce independent reports at
their own paths; this report is self-contained and does not assume their
findings.

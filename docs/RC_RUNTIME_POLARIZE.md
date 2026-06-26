# RC 3.2.0 Runtime Polarize — Decision Ledger

> `vc-polarize` doctrine pass. Prism score **15/15 (doctrine band)** across
> code/runtime/tests/memory/closure. This is the decisive cut entering the
> `-rc` period: no compat shims, no split-brain.

## Polarized Thesis

**`vibecrafted-core` (Python) is the single runtime authority; the `./runtime`
shell layer — deck, `*_spawn.sh`, `meta.sh` bare-python resolvers, `ZELLIJ_*`
bridges — is legacy, rejected as a competing runtime, and survives only as
not-yet-migrated operator surface to be ported into core, never extended.**

## Mode

`concept` — architectural runtime smear.

## Prism Evidence

- `total_score: 15/15`, band `13..15 doctrine` (regression-contract required).
- All five axes 3/3: spread, runtime_centrality (166 runtime signals, 53 central
  files), authority_diversity, drift_risk (stale/dirty cache), closure_evidence.
- Runtime proof that core is self-contained: `grep` of `vibecrafted_core/*.py`
  for `runtime/scripts|*_spawn.sh|deck` returns only comments — notably
  `workflow.py:900` ("Do not call legacy runtime/scripts launchers"). Core does
  not call the shell layer; they are parallel, not interwoven.

## Per-Axis Decision Ledger

| Axis                                                         | Wins (one truth)                                                       | Rejected                             | Runtime proof                                                                                                                                                                                                                 | RC action                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. `ZELLIJ_*` dual-emit**                                  | `VC_FRAME_*` is canonical                                              | `ZELLIJ_*` as a primary source       | vc-frame binary **still dual-emits** both (`strings`: `VC_FRAME_SESSION_NAME` + `ZELLIJ_SESSION_NAME`, `*_SOCKET_DIR`, `*_AUTO_ATTACH`); pane detection (`${ZELLIJ+set}`, `VC_FRAME=0`/`ZELLIJ=0` valid indexes) relies on it | **Handoff — needs in-session proof.** Keep the fallback as a _documented legacy bridge_ (not "transition"); remove only after verifying in a live vc-frame session that `VC_FRAME_*` is emitted on every pane path. Cutting blind would break pane detection. |
| **2. `_vibecrafted_python()` + `spawn_python_bin()`**        | uv-tool shim shebang carries uv-python                                 | bare-`python3` resolvers             | Both live in the legacy shell (`scripts/vibecrafted` deck, `runtime/scripts/lib/meta.sh:374`); python-core never calls them (`workflow_runtime` uses `_stdin_command`, not `*_spawn.sh`)                                      | **Dies with axis 3.** Rejected; removed when the deck / `*_spawn.sh` path is retired. Already surfaced by `doctor` launcher finding (`cfe5010`).                                                                                                              |
| **3. split-brain `./runtime` vs `./vibecrafted-core`**       | `vibecrafted-core` Python = single runtime                             | `./runtime` shell as a runtime       | Core proven self-contained (above); `workflow.py:900` forbids calling legacy launchers                                                                                                                                        | **Staged migration handoff.** Port deck lifecycle verbs (init/start/status/server/dashboard/gui/tui/telemetry/update/uninstall/version) into `cli:main`, then retire deck + `*_spawn.sh` + `meta.sh` resolvers. Locked by the regression contract below.      |
| **4. operator-session naming (`vibecrafted` vs `vc-frame`)** | `basename(scope_root)` is the single rule (`vibecrafted` in this repo) | hardcoded / env-pinned session names | Live session `vc-frame` is a user-context artifact (bare binary / `../vc-frame` fork basename), not a code truth; `_vetcoders_session_base_name` already falls back to `vibecrafted`                                          | **Aligned (`9ed1395`).** Terminal launch now degrades to headless when the requested session is not live, so a name mismatch no longer strands the worker.                                                                                                    |

## Regression Contract (doctrine band)

`vibecrafted-core/tests/test_workflow.py::test_build_launch_command_never_delegates_to_legacy_shell_runtime`
asserts `build_launch_command` spawns through `vibecrafted_core.workflow_runtime`
or an agent stdin command and **never** a `*_spawn.sh` launcher or the deck.
This locks the split-brain shut: core cannot re-grow a shell-runtime dependency
without failing the gate.

## Gates Run

- `uv run --project vibecrafted-core pytest test_workflow.py` — contract +
  transport/degrade/session tests green.
- Walk-around per [VERIFICATION_RULE](../skills/VERIFICATION_RULE.md): not just
  green tests — live runtime proof. A repo-core terminal launch into the dead
  `vibecrafted` session reported `transport=headless`, ran `python -m
vibecrafted_core.dispatcher`, and produced a growing `transcript.log` (worker
  spawned) instead of a dead tab. Truck walked, taśmy checked.
- Complementary tree direction: `3120f52` (control-plane terminalize abandoned
  runs) now GCs the runs a name-mismatch used to strand — degrade (axis 4) stops
  the stranding, the GC reaps the residue.

## DoU Handoff

- Verify (in a live vc-frame session) whether `VC_FRAME_*` is emitted on every
  pane path before removing the `ZELLIJ_*` fallback (axis 1).
- The deck-on-PATH disease is reported by `vibecrafted doctor` (axis 2/3);
  DoU should treat a `fail: launcher` finding as a release blocker.

## Release Handoff

- `3.2.0-rc` can honestly ship: single-runtime thesis chosen, degrade-not-die in
  the Python launch path, regression contract locking the boundary.
- **Still blocked for GA:** the staged deck→core migration (axis 3) and the
  `ZELLIJ_*` removal (axis 1) are not done — they are named handoffs, not
  shipped truth.

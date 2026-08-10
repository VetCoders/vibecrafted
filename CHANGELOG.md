# Changelog

All notable changes to 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## 3.7.1 — 2026-08-08

> **The bootstrap onion.** Patch release that took the root `curl | bash`
> install path from seven stacked failure layers to a green matrix on every
> runner — and sealed the P0 class where a test stub could lose to the
> operator's live launcher and fire a real dispatch.

### Fixed

- **Deck resolution gate** — single `_vetcoders_resolve_deck_bin` for every
  shell path that reaches the installed deck: `VIBECRAFTED_DECK_BIN` wins
  verbatim, `VIBECRAFTED_TEST_MODE=1` never discovers a live deck, no deck
  reports a clean 127; wrapper fallback restores spawn/marbles/help on bare
  hosts. Kills the measured stub-escape (a pytest run had launched a live
  `--dangerously-skip-permissions` worker).
- **Launcher twin parity** — forward-ported both one-sided hunks
  (product-entry choke, trusted pane-id predicate); `scripts/vibecrafted`
  and the packaged deck are byte-equal again.
- **`vc-polarize --task`** routes through the shell band gate again
  (abort/memo/pass/doctrine + prism.json); the python deck rejects the flag
  (port-debt: `docs/RC_RUNTIME_POLARIZE.md`).
- **Bootstrap layers** — vc-frame cockpit install defers loudly while its
  release does not exist (`REQUIRE_FOUNDATIONS=1` re-arms); server shell
  defers without cargo-leptos while CI provisions the full leptos toolchain
  and builds it for real; uv sh-wrapper entrypoints under long venv paths
  are recognized as uv-owned (kernel shebang limit); doctor runs from a
  neutral cwd (no living-tree shadowing) with persistent `safe.directory`
  in containers; `vc-frame:truth` compares against a fresh host-adapted
  materialization instead of raw hashes; unpublished slack provider defers.
- **Portable rc contract** — asserts the PATH-only guard and the absence of
  retired `vc-skills.sh` sourcing.
- **Shell gate** honestly skips files whose interpreter is missing on the
  host, and Linux CI installs zsh so `.zsh` sources are really checked.
- **Research arity keywords** — `uno|duo|trio` expand to exact agent lists
  and fail closed on wrong lane counts; public variadic argv preserved.

### Added

- **Ownership canary catalog** — 17-agent sweep cataloged 2842
  def/class/module units across 103 production python files and added 1999
  docstrings where none existed (comment-content preserved; zero logic
  changes); catalog artifact shipped to the operator artifact store.

### Notes

- Verdict source: gate colours on main (Portable, Skill Loader, Install
  Matrix after #35, vibecrafted-server, docker+doctor). Site channel
  (`make site-release`) and the vc-frame release remain manual operator
  actions.

## 3.7.0 — 2026-07-27

> **Runtime truth recovery.** The release where a killed supervisor, a stale
> lock, a torn journal, or a lying "healthy" receipt can no longer fake the
> board. 114 commits across 202 files, every recovery path proof-gated.

### Highlights

- **Durable settlement V2** — immutable, append-only, hash-chained
  `SettlementEventV2` ledger (`settlement_ledger` / `settlement_history`),
  published as durable revisions and read back by triage, guardian, and the
  control plane. Zero on the f/x/n rail is now a verdict, not a default.
- **Read-only settlements CLI** — `vibecrafted settlements`
  (summary / list / inspect / revalidatable) over the canonical ledger,
  schema `vibecrafted.settlements-query.v1`.
- **Untriaged-run sweep** — `run_triage --sweep-control-plane` retro-triages
  every finished run the dispatcher never came back for (the 418-runs-of-
  silence class), idempotent and bounded, with rotating candidates.
- **Guardian recovery** — event-driven recovery guardian with server-owned
  sidecar lifecycle, exact argv identity, trust-outbox recovery before
  attach, reconciled recovery lineage, and race-closed native resume.
- **Supervised service truth** — canonical pair health proof before any
  healthy receipt; foreign live PIDs and minimal identity JSON are rejected;
  doctor fails closed on dead supervision; malformed service plists are
  contained; stale lifecycle locks recover after SIGKILL.
- **Trust journal crash-safety** — torn/partial JSONL tails after a
  prepared-outbox crash are repaired to the exact prefix; newline crash
  recovery gaps closed; post-hoc commit verdicts.
- **Scaffold control room** — plan library + picker with a deterministic
  machine-checked `scaffold-doctor` gate (R1–R11), bounded catalog
  discovery, and health checks that stay cheap and isolated.
- **Install/runtime handoff** — crash-atomic tool handoff, supervision
  enabled only after payload verification, terminal failure truth preserved,
  and dirfd-anchored restore publication with digest checks.
- **Test-suite hermeticity vs live operator runtime** — TUI/core suites and
  the portable gate now strip ambient frame/session env (`ZELLIJ*`,
  `VC_FRAME*`, prepared-session vars, `PYTHONPATH`), so green in CI can no
  longer redden on an operator machine with a live cockpit.

## 3.6.0 — 2026-07-24

> **Ship AI-built software without the vibe hangover.**
>
> 3.6.0 is the release where the board stops lying, the cockpit stays honest,
> the installer survives a hostile filesystem, and a stranger can still install
> with one command. Not a list of commits — a product story with gates behind it.

### The story

For months Mission Control could show activity while the settlement strip said
`0 · 0 · 0`. Operators learned to distrust the board. Agents finished work,
reports claimed success, and the retained control plane still had no canonical
f/x/n truth to hand to the next session.

3.6.0 closes that gap. **Retained control-plane settlement is the single run-level
source of truth for f/x/n.** Mission Control, vc-server API, and SSR read the same
board. vc-frame's rail still reports **tab inventory**, not fleet settlement —
two surfaces, two jobs, no false equivalence.

Around that board sits a **delivery-proof kernel**
(`vibecrafted_core.delivery.*`): execution envelopes, proof contracts, reconstructable
seals. Dispatch no longer treats a completion label as proof. A run is final when the
envelope, the proof, and the seal agree — or it is not final.

The operator cockpit is **vc-frame 0.46**. Every dispatch layout (dashboard, marbles,
operator, research, workflow) welds the session-manager rail into the default tab
template so a reinstall cannot strip the sidebar the operator hand-welded last week.
Layouts passed parser dump and live `new-tab` load probes before this line shipped.

The **installer container lane** earned its scars on a real Vetcoders container
mount: sshfs that dropped executable bits, broke symlinks, and corrupted bytecode
on copy. The lane is resilient under those conditions — stage, verify, refuse to
pretend a half-copied tree is an install. That is not marketing; it is wartime
filesystem engineering.

**ACP adapter (MVP + P2)** is the gate to IDE-shaped clients. Thin glue over the
existing control plane and workflow APIs — launch, observe, await, stream, stop —
without inventing a parallel runtime truth. IDE integration starts from evidence the
CLI already trusts.

**Prune / health** moved the structural health readout from the low-70s into the
low-80s range on the release candidate path (78 → 81 on the measured prune pass).
Not "perfect architecture" — a cleaner cone for the next cut.

### What landed (facts, not hype)

| Surface                  | Claim                                                        | Evidence bar                            |
| ------------------------ | ------------------------------------------------------------ | --------------------------------------- |
| Settlement board f/x/n   | Canonical retained control-plane counts                      | Python core suite; API/SSR parity tests |
| Delivery-proof kernel    | Envelopes + proof + seal layout                              | Delivery unit + e2e tests               |
| vc-frame 0.46 cockpit    | Rail on every default layout; honest inventory vs settlement | Layout dump + live new-tab probes       |
| Installer container lane | Survives symlink / +x / bytecode damage on hostile mounts    | Installer + delivery path tests         |
| ACP adapter MVP+P2       | stdio ACP over control_plane                                 | `tests/acp/`                            |
| Research agent pick      | Fail-closed arity + announced source                         | Research launcher suite (16)            |
| Gemini lane              | Hard-removed; **agy** is the Google successor                | Dispatch/marbles/research rotation      |
| Version truth            | Framework stamps **3.6.0**                                   | `VERSION`, package metadata             |

### Gates at merge of PR #20 (release candidate head)

- Full Python core suite: **910 passed**, 8 skipped
- Research launcher suite: **16 passed**
- Rust workspace: `cargo check --all-targets --all-features`, clippy `-D warnings`, 47 tests + 1 doctest
- All five vc-frame layouts: parser dump + live `new-tab` load
- Local quality stack: Semgrep, Ruff, mypy, ShellCheck, Prettier, diff-check, pre-commit, pre-push

### Install (stranger path)

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
vibecrafted doctor
```

Foundations are **prebuilt-first** (npm / curl release assets / crates.io / PyPI),
then package-manager, then `cargo build` only as a last fallback with preflight.
See [docs/FOUNDATION.md](docs/FOUNDATION.md).

### Compatibility notes

- Canonical delivery artifact filenames replace non-canonical seal defaults;
  `vc-ship` consumes the same layout owner as reconstruction.
- `.gemini` remains discoverable only as a legacy data-directory compatibility
  view; active research/sync targets use **agy**.
- This changelog entry does not itself create a git tag. Tag and public deploy
  follow the published-artifact smoke path on vibecrafted.io.

---

## 2.0.0 — 2026-05-20

> Quality-layer reform. The pipeline epistemic rhythm
> (READ-ONLY perception ↔ WRITE action) is now first-class in the
> manifest and across every skill. `vc-audit` is added as a new
> READ-ONLY falsification step. `vc-marbles` is reframed from
> "truth convergence" to "deliberate over-write whose excess is the
> point of polarize stripping it back". All edited skills land under
> the 12k marketplace cap with companion files for detail.

### vc-operator 2.0.0 reform (2026-05-21)

- **Operator mode shipped as a coherent reform batch**: `skills/vc-operator/RUNNER.md`,
  `skills/vc-operator/WHY_MATRIX_TABLE.md`,
  `skills/vc-operator/DISPATCH_TEMPLATE.md`,
  `skills/vc-operator/FEEDBACK_2026-05-20_claude.md`, and
  `skills/vc-operator/FEEDBACK_2026-05-20_claude_runtime.md` are the
  durable operator references instead of transcript-only doctrine.
- **Wave 5 await/watch rail landed**: `runtime/scripts/vibecrafted-await-watch.sh`
  plus the `spawn_await_watch_pane` hook in
  `runtime/scripts/lib/vc_frame.sh` give long-running dispatches a
  visible watch surface.
- **`skills/vc-operator/SKILL.md` patched from 0.1.0 to 2.0.0** with the
  runner contract, why-matrix dispatch discipline, feedback intake, and
  operator-facing closure rails.
- **Sharp-move recommendations absorbed**: REC-1/2/3/4/6/7/8/9/10/11 are
  now represented across the operator contract, modes table mandate, dispatch
  template, runner loop, and feedback files.
- **17 live runtime pains recorded** in
  `skills/vc-operator/FEEDBACK_2026-05-20_claude.md` and
  `skills/vc-operator/FEEDBACK_2026-05-20_claude_runtime.md`, including the
  REC-10 modes-table requirement and dispatcher/runtime pain catalog that made
  the reform necessary.

### Added

- **`docs/runtime/MANIFESTO_PL.md` + `MANIFESTO_EN.md`**: new
  **Pipeline (Sculpting Pattern)** section with the explicit
  WRITE → READ → WRITE → READ rhythm diagram and the **carve-from-
  marble** pattern at the centre of the quality cycle. Tooling
  ontology table grows a **Mode** column (READ / READ-ONLY / WRITE /
  meta / infra) and splits the **Quality** layer into perception
  (`vc-followup` + `vc-review`, READ) and falsification (`vc-audit`,
  READ-ONLY).
- **`skills/vc-audit/`** (NEW): READ-ONLY plan-vs-code falsification
  skill. Default verdict UNVERIFIED, PASS earned via code + test +
  negative check. Eight-phase procedure (Context Receipt → Task
  Ingestion → Atomic Requirements → Positive + Negative Verification →
  Adversarial Pass → Stage-Aware Verdict → Per-Task Table → Self-
  Attack + Model Check). Output contract: `audit_report.md`,
  `audit_requirements_matrix.jsonl`, `audit_trace.log`. Companions:
  `PHASES.md`, `DISPATCH.md`. Plugin manifest registered.
- **Pipeline-position section** added to every reformed skill
  (`vc-review`, `vc-marbles`, `vc-polarize`, `vc-audit`,
  `vc-followup`, `vc-dou`) so READ-ONLY vs WRITE membership is
  explicit at the top of each skill.

### Changed

- **`skills/vc-review/SKILL.md` → version 2.0.0**. Explicit READ-ONLY
  framing. Default-stance section: every spec-claim defaults to
  UNVERIFIED until proven by code/tests. Hard non-trust rules: PR
  descriptions, commit messages, `// done` comments, AICX entries,
  and `fixes #N` annotations are claims, not evidence. New evidence
  taxonomy (STRONG / MEDIUM / WEAK / NONE) on every finding. New
  adversarial pass between pattern scans and output. Stage-aware
  finding tags (`[STAGE-OK-DEFERRED]`, `[STAGE-PARTIAL]`,
  `[STAGE-DRIFT]`) prevent mid-stage PRs from being mis-blocked. New
  self-attack + model check section in output. Heavy detail moved to
  companion files `PRVIEW.md` (Phase 1 artifact generation) and
  `FINDINGS.md` (Phase 2 reading order, pattern scans, output
  template). SKILL.md trimmed from 12.4k to 10.7k.
- **`skills/vc-marbles/SKILL.md` → version 7.0.0**. Epistemic reframe
  from "Truth Convergence Rounds" to **"Deliberate Excess (Worker-
  Blind, Swarm-Wide)"**. Individual worker discipline preserved (one
  round, one commit, up to 3 targets) — but the swarm-level intent is
  now explicit: marbles in every crack, deliberate over-application,
  `vc-polarize` strips back. Pipeline-position diagram added. Worker
  blindness + reception remembers section condensed. Detail kept in
  existing `FLOW.md` and `RECEPTION.md` companions. SKILL.md trimmed
  to 11.8k.
- **`skills/vc-polarize/SKILL.md` → version 2.0.0**. Explicit
  framing as the **decisive cut** WRITE step that strips back the
  marbles excess. Pipeline-position diagram added. Heavy detail
  (full lifecycle, prism axis scoring criteria, context-corpus
  retention contract, minimum-gates list, failure-mode playbook)
  moved to new companion `PROCEDURE.md`. SKILL.md trimmed from 12.8k
  to 10.0k. Closing rail + suchar + canonical signature added.
- **`skills/vc-followup/SKILL.md` → version 2.2.0**. Explicit READ-
  ONLY framing in description and body. New "Pipeline Position"
  section locates it in the trajectory-perception slot.
- **`skills/vc-dou/SKILL.md` → version 2.0.0**. Explicit READ-ONLY
  framing in description and body. New "Pipeline Position" section
  locates it in the shipping-readiness slot between polarize and
  hydrate / decorate / release.
- **Marketplace cap discipline**: every reformed SKILL.md is now
  under the 12 000-character marketplace cap. Heavy detail lives in
  companion files at the same level as SKILL.md (no `references/`
  subdir), matching the `vc-operator` reference pattern.

### Removed

- Earlier "Unreleased" entries from 1.x cycle (Prism → Polarize gate,
  release-report contract, marketplace plugin stubs) are kept inline
  below for historical continuity; the 2.0.0 reform is the first
  named cycle.

---

## Unreleased (legacy 1.x — folded into 2.0.0 release scope)

### Added

- **Prism → Polarize gate (Plan 01)**: `vc-polarize` runner (`runtime/shell/vetcoders.sh:1168-1186`) now parses `loct prism --json` output, reads `total_score`, and routes to the default action band: `0..4` abort (no polarize, no memo), `5..8` memo (capture local Loctree tag / context-corpus entry, do not dispatch), `9..12` pass (run full `vc-polarize` agent dispatch), `13..15` doctrine (write default decision into context corpus). The runner also emits a prism preflight that injects the band/score into the polarize prompt so the dispatched agent can cite structural evidence rather than re-deriving it. The same threshold mapping is consumed independently by `vc-operator` (`src/polarize.rs:18-23 PolarizeBand::from_score`) — single source of truth at the boundaries `5 / 9 / 13`.
- New `.claude-plugin/plugin.json` stub manifests for `skills/vc-polarize/`, `skills/vc-intents/`, and `skills/vc-ownership/` to bring them in line with the rest of the framework's marketplace surface (vc-marbles / vc-init / vc-implement / vc-followup / vc-decorate / vc-hydrate / vc-dou / vc-prune / vc-research / vc-review / vc-release / vc-scaffold / vc-workflow / vc-agents / vc-delegate / vc-partner all already shipped manifests).
- `vc-release` Release Report Contract: every release report now requires
  four mandatory sections — security gate (Semgrep), exposed surface
  inventory (ports, proxies, auth, headers, secrets), deployment mode
  decision, and post-release install smoke from the **published**
  artefact (not the working tree). Canonical template lives at
  `skills/vc-release/references/release-report-template.md`.
- `skills/vc-release/references/deployment-reality.md` gains an
  "Exposed Surface Inventory" matrix (process, bind, port, proxy, TLS,
  auth, edge headers, secret materialization) so the inventory has a
  doctrine to reference.
- `tests/tui/test_release_contract.py` adds two locks: the four
  mandatory sections in `skills/vc-release/SKILL.md` plus the surface
  inventory tokens in `deployment-reality.md`. Future drift fails the
  pytest gate.

### Changed

- `skills/vc-release/SKILL.md` Semgrep release gate now points at the
  default `make semgrep` (mirrored by `scripts/hooks/pre-commit` and
  `scripts/hooks/pre-push`), classifies findings by dataflow boundary
  (path / regex / merge / shell / auth / other), and treats silent
  unavailability as a release block.
- `skills/vc-release/SKILL.md` Post-release smoke now requires a cold
  install from the published artefact source (registry URL, tag,
  digest, or download URL) and forbids using the local checkout as the
  witness.
- `docs/runtime/CONTRACT.md` quality gate section references the
  default `make semgrep` invocation and links the Release Report
  Contract.
- `docs/RELEASE_KICKOFF.md` adds `make semgrep` to the kickoff gate
  block and links the release report template plus the deployment
  reality matrix.
- `README.md` release-flow paragraph names the four-section release
  report and links the doctrine + template.

## 1.4.1 — 2026-04-22

### Added

- `tools/bin/` bundled toolchain drop-in for pre-notarized binaries: installer
  resolves local bundle first, then falls back to remote fetch. Enables
  fully-offline first-install UX for cold users.
  - `scripts/build_marketplace_bundle.py` now collects `tools/bin/**` into the
    plugin bundle artifact
  - `scripts/install-foundations.sh` gains `bundled_bin_root()` and
    `install_from_bundled()` with explicit fallback order
  - `installer_gui.py` surfaces bundled diagnostics as a new category in the
    pre-flight doctor
  - Documented resolution order and notarization expectations in
    `tools/bin/README.md`
- `runtime/scripts/marbles_verify_watch.sh` — standalone detached
  verification poller that waits for `*_verified.md`, updates `state.json` under
  lock, and marks verification as `completed` or `timed_out`. Decouples
  verification from the main watcher process and eliminates watcher holding
  PIDs for long periods.
- `vc-research` swarm launcher + worker charter for research passes that need
  multiple parallel agents converging on one plan.
- `vc-intents` skill for retrieval of past decisions from AI Chronicles /
  session history (complements `vc-init`).
- `await` helper for synchronous wait-on-agent flows in orchestration scripts.
- Help overlay in operator-tui launch flow.
- `--echo-stdout` flag in codex stream bridge for visibility into headless
  runs without losing machine-readable frames.
- Agent telemetry captured into loop `state.json` (dispatch time, completion
  time, exit code, session_id) so marbles state is the single source of truth
  for multi-loop runs.
- New skill **`vc-implement`** becomes the default end-to-end implementation
  skill. The `vc-justdo` name stays in-tree as a **backward-compatible
  alias** (frontmatter: `default: vc-implement`) so agents already wired to
  the old name keep working. Every public surface (START_HERE `Simplest path`,
  install banner, skill registry in `vetcoders_install.py`) now shows
  `vibecrafted implement ...`; the `justdo` command still executes but is no
  longer advertised. Full trigger-phrase inventory — including Polish triggers
  ("zrób to", "dowiez to", "od pomyslu do realizacji") — migrated to
  `vc-implement`.

### Changed

- Operator TUI refactored into a tabbed console — three tabs: **Monitor**
  (live runs + recent events), **Dispatch** (mission kind / agent / runtime /
  prompt), **Controls** (attach / resume / report / transcript for selected
  run). Tab navigation contracts stabilized (`Tab` / `Shift+Tab`, arrow keys
  scoped to active tab), direct tab switches normalized.
- Operator TUI split into dedicated **`vc-operator`** crate at the
  `vc-runtime` workspace root. The crate owns its versioning (`vibecrafted-
operator v0.1.1`) and release cycle. `scripts/vibecrafted` launcher gracefully
  falls back between in-source operator-tui and the installed `vc-operator`
  binary, with a clear error if neither is available.
- Marbles spawn now **honors `VIBECRAFTED_MARBLES_RUN_ID` only when it doesn't
  conflict with existing state** (unless `VIBECRAFTED_MARBLES_RESUME=1` is set
  explicitly). Otherwise it mints a **PID-suffixed** run id (`$$` appended to
  the timestamp) so parallel spawns cannot collide on the same second.
- Marbles watcher decoupled from verification polling — instead of holding PIDs
  and polling inline, it marks loops as `pending` and hands off to
  `marbles_verify_watch.sh` via `nohup`. Summary logic simplified; configurable
  verification grace period added.
- vc-frame spawn uses **tab/pane IDs** (not just names) for targeting marbles
  panes — non-disruptive spawn that doesn't steal focus from operator's
  active pane; tab index noise suppressed in marbles spawn output.
- vc-frame layouts renamed (`operator` / `vc-marbles` / `vc-workflow` / `vc-
research` / `vc-dashboard`) with matching launcher and test updates.
- Uninstall now removes **only manifest-tracked entries** + framework
  artifacts — no broad filesystem sweeps that could clobber user files.
- Operator TUI launches **Ghostty** natively (via `vc-frame`) as the terminal
  surface when running in `terminal` / `visible` runtime.
- Marbles active-only run filter in operator-tui so Monitor tab stops showing
  cold runs from previous sessions.
- System-wide docs refresh: README, FAQ, FAQ-ANSWERED, QUICK_START, SKILLS,
  WORKFLOWS, installer/DESIGN, workflows/MARBLES — copy brought in line with
  the default command set (`vibecrafted implement`) and the current 1.4.1
  surface.
- FLOW + SKILL polish across `vc-delegate`, `vc-init`, `vc-justdo` (alias),
  `vc-partner`, `vc-research`, `vc-scaffold`, `vc-workflow`.

### Fixed

- Marbles wrapper publication drift: wrappers are now force-republished on
  every dispatch so stale files can't point at removed scripts.
- Launcher drift repair in place — `doctor` now fixes broken launcher
  configurations without requiring a clean install.
- `doctor` rc repair path for launcher rc files.
- Operator TUI control-plane wiring — pane names + control-plane state
  aligned, polish pass on tab surfaces.
- Operator TUI terminal agnosticism — no longer hard-codes vc-frame or any
  single terminal assumption.
- Operator TUI vc-frame env isolation in tests (previously leaked
  `VC_FRAME_CONFIG_DIR` between parallel test runs).
- Flaky CI expectations for marbles statuses and Makefile dry-run output.
- `uv` bootstrap assertion messages now align with export `PATH` checks.

### Removed

- `operator-tui/` directory from vibecrafted (moved to dedicated `vc-
operator` crate — see **Changed** above).
- Stale research docs (`docs/MODULARIZATION_PLAN_2026_04_16.md`,
  `docs/REPO_GROUND_TRUTH_2026_04_13.md`, multiple `docs/research/*.md`
  artifacts, `docs/FAQ-ANSWERED.md` noise).
- `scripts/mission-control/restore-orphaned.sh` (superseded by
  `marbles_verify_watch.sh` + ghost reaping path in the watcher).

## 1.4.0 — 2026-04-18

### Added

- Marbles `delete` subcommand for cleaning up finished / abandoned runs.
- Installer TUI textual wizard flow with real keybindings, sticky layout,
  dynamic interpolation, and manifest-driven step rendering — implements the
  `docs/installer/` mockups 1-for-1.
- Worker contract in generated child plans so sub-agents know the exact
  constraints of their slice (scope, artifacts, gates).
- Shell syntax checks for spawn scripts in the pre-commit path.
- Attended bootstrap confirmation + `--yes` flag in `install.sh` — humans get
  a "what's about to happen" pause by default; CI / automation pipelines get
  a clean non-interactive path.
- Regression tests for installer manifest / branding + codex_stream_bridge.
- `vc-frame` panes for marbles dispatch (in place of bare new-tab).

### Changed

- **Installer TUI-first swap**: terminal front-door defaults to the guided
  TUI wizard; the GUI stays available via `--gui`. Sticky-bottom streaming
  log, unified `make install` entrypoint.
- vc-frame orchestration hardened: tab isolation, spawn probe before every
  dispatch, session GC for stale vc-frame daemons.
- Framework bumped **1.3.0 → 1.4.0**; VERSION truth propagated across all
  installer surfaces (no more "1.3.0 in README, 1.4.0 in bundle"
  disagreements).
- Installer GUI converted to single-page no-scroll layout; branding + docs
  polished; FRAMEWORK tag squared-block unicode restored (reverted accidental
  normalization).

### Fixed

- `uv` bootstrap shell boundary: installer now correctly propagates the
  ephemeral uv install into the downstream shell instead of losing it to
  subshell isolation.
- Marbles spawn failures no longer masked by codex stream: pipeline status is
  read from pipefail, not inferred from "did we get some stdout?".
- Marbles next-hook contract: child loops only advance after the real
  handoff, not after tmp prompt file arrives.
- Arrow keys in installer TUI now scroll within a step instead of switching
  steps.
- Truthful landing page: no fake URLs, no fake commands, copy matches actual
  install flow.
- Marbles ancestor steering: mtime race fixed, spawn fallback hardened, run-
  id / spawn prefs respected under concurrent dispatches.
- Watcher state race, doctor dashboard smoke, session semantics, update
  path, commit labels — a marble convergence sweep closed these as one loop.

## 1.3.0 — 2026-04-11

### Added

- Browser-based guided installer: `scripts/installer_gui.py`
- `install.sh --gui` bootstrap path for the guided installer
- `make gui-install` for launching the guided installer from source
- Marketplace submission pack in `docs/SUBMISSION_FORMS.md`
- Release kickoff docs now ship inside the marketplace bundle artifact
- Release-contract pytest guard for promise / CTA drift across public surfaces

### Changed

- Product positioning now leads with the release-engine promise instead of generic framework language
- Public install docs now explicitly show the guided GUI path for founders and non-terminal operators
- `install.sh` help text now matches the actual bootstrap paths instead of promising a TUI that was not wired in
- `install.sh` fallback now prefers the live GitHub source snapshot when the channel manifest is missing, instead of pinning a stale tarball URL
- Submission forms now cite current adjacent-tool directory evidence and official launch surfaces
- Frontier / installer copy now talks about the current framework surface instead of a stale frozen version string

## 1.2.1 — 2026-04-01

### Added

- `make foundations` — portable installer for historical loctree / ai-contexters binaries
  - Superseded by the product foundation contract: do not use this entry as a current install source
  - Current runtime foundations are validated on `$PATH`; missing AICX/Loctree should point at the canonical Loctree installer
  - `make foundations-check` for dry-run preview
  - `scripts/install-foundations.sh` works standalone or via Make
- Python-native `shutil.copytree` fallback when `rsync` is not available
  - `rsync` downgraded from critical to recommended dependency
  - `make install` now succeeds on systems without rsync (fresh containers, Windows WSL)

### Fixed

- **Python 3.11 compatibility**: f-string backslash escapes in `vetcoders_install.py`
  caused `SyntaxError` on Python < 3.12 (the `\U` unicode escapes inside f-string
  expressions). Extracted to variables.
- `rsync` no longer blocks installation — `make install` uses pure-Python copy as fallback

## 1.2.0 — 2026-03-29

### Added

- Marbles loop orchestrator: `marbles_spawn.sh`, `marbles_next.sh`, `marbles_plan.sh`
  - `<agent>-marbles --depth <n> --count <y>` — crawl recent sessions, run convergence loops
  - `<agent>-marbles --task <plan.md> --count <y>` — loop against a plan file
  - `<agent>-marbles --prompt "text" --count <y>` — inline prompt loops
  - Filesystem-based loop chaining via `success_hook` — no cron, no watcher
  - Convergence through CODE STATE, not report chaining — each loop gets the same plan, sees improved repo
  - `CONVERGENCE.md` written after final loop (or on failure)
  - Lock files in `$VIBECRAFTED_ROOT/.vibecrafted/locks/<org>/<repo>/`
- `--success-hook` and `--failure-hook` flags for all spawn scripts (claude, codex, gemini)
- Landing page: 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. → 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. rebrand, sprite caching for Safari performance
- Installer TUI wizard (in progress): Rich-based step-by-step flow from docs/installer/ mockups

### Changed

- Product name: **𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.** (the product), **𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙** (the methodology)

### Fixed

- **Clarified `zsh -ic` requirement for shell helpers**: The 1.0.3 changelog stated
  "removes zsh runtime dependency" which is true for spawn SCRIPTS (`eval "$SPAWN_CMD"`
  works in bash). However, operator-facing shell helpers (`codex-implement`,
  `claude-research`, etc.) are functions sourced from `.zshrc`/`.bashrc` and require
  an interactive shell to load. The default agent-to-agent invocation remains
  `zsh -ic "codex-implement $PLAN"` (or `bash -ic` on zsh-less systems).
  Skill documentation (vc-agents SKILL.md) updated to reflect this.
- Marbles board animation: sprite pre-rendering (was creating new canvas per marble per frame — Chrome hid the cost,
  Safari showed 5fps)
- `init-hooks` Makefile target: guard with `git rev-parse --git-dir` for non-git bootstrap contexts
- Portable test: marbles helper uses new `--prompt` interface, flexible `run_id` check

## 1.0.4 — 2026-03-29

### Added

- 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. framework overview and README branding
- Marbles orchestration skill and hook/runtime fixes
- AICX extract skill documentation
- Mission-control layout for vc-frame
- Compact install mode and enhanced logging
- Screenscribe foundation setup
- GitHub Pages onboarding pages for Quick Start and answered FAQ
- Marketplace listing draft for the framework
- GitHub issue templates for bugs and workflow requests

### Changed

- Refactored installer UI and polished docs
- Reset Gemini plan dir on install
- Uses `VIBECRAFTED_HOME` with Gemini include dir

### Fixed

- Canonical URL, sitemap, and robots alignment for the public presence surface
- Public docs updated to match the current shell-agnostic helper path and non-interactive install flow
- Installer issues and UI
- Gemini and MCP stream filters

## 1.0.3 — 2026-03-27

### Added

- Framework version tracking (`VERSION` file, installer + doctor report it)
- Bash shell helper support — helpers work in bash and zsh, not zsh-only
- Dual rcfile installation (`.bashrc` + `.zshrc`)
- Release CI workflow (tag `v*` builds archive without `presence/`, GitHub Release with SHA256)
- `curl-bootstrap` CI job for install.sh end-to-end smoke testing
- Stream filters: Claude jq, Codex jq, Gemini awk — clean readable agent terminal output
- Codex `--json` JSONL streaming with structured event parsing
- Spawn telemetry: `framework_version`, `prompt_id`, `run_id`, `loop_nr`, `skill_code`, `duration_s`
- Skill helpers: `<agent>-dou`, `<agent>-hydrate`, `<agent>-marbles`, `<agent>-scaffold`, etc.
- `vc-dashboard` for vc-frame Mission Control layout
- Active spawn scan before each launch
- Material palette: copper/patina/timber/steel/stone

### Changed

- Spawn launcher: `zsh -ic` -> `eval` — removes zsh runtime dependency
- Terminal.app spawn: `zsh -ic` -> `bash`
- Shell helpers renamed `vetcoders.zsh` -> `vetcoders.sh` (compat symlink kept)
- Helper install path: `$HOME/.config/vetcoders/vc-skills.sh` (was `$HOME/.config/zsh/vc-skills.zsh`)
- CI no longer requires zsh on Ubuntu
- Installer: zsh downgraded from required to optional dependency
- No hardcoded model flags in spawn scripts — agents choose their own

### Fixed

- Headless spawn failing in CI (zsh -ic in nohup context)
- Codex spawn exit code 1 from session grep with pipefail
- Loctree release URL (Loctree-Repos -> Loctree/Loctree)

### Removed

- Judgmental/condescending language from presence copy and FAQ
- zsh as runtime dependency for agent spawns

## 1.0.2 — 2026-03-27

### Added

- `LICENSE` — Business Source License 1.1
- `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- Skill taxonomy refactor: 17 skills with coherent pipeline references
- `vc-justdo`, `vc-scaffold`, `vc-release` skills
- FAQ-ANSWERED.md
- Centralized artifacts under `$VIBECRAFTED_ROOT/.vibecrafted/`
- OG image and social card meta tags
- GitHub issue templates

### Fixed

- Hardcoded paths in skill files replaced with portable references

### Removed

- `vc-ship`, `vc-ownership` (absorbed into other skills)
- 60-file taxonomy cleanup

### Skills (as of 1.0.2)

- vc-agents 1.4.1, vc-decorate 1.1.0, vc-delegate 1.0.0, vc-dou 1.0.0
- vc-followup 1.0.0, vc-hydrate 1.0.0, vc-init 2.2.0, vc-justdo 2.0.0
- vc-marbles 1.1.0, vc-partner 2.0.0, vc-prune 2.0.0, vc-release 0.1.0
- vc-research 1.2.0, vc-review 1.0.0, vc-scaffold 0.1.0, vc-screenscribe 1.2.1
- vc-workflow 1.0.0

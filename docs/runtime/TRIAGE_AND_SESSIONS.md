# Run settlement truth and terminal triage projection (`f` · `x` · `n`)

> **Canonical settlement truth:** the append-only hash-chained ledger in
> `vibecrafted_core/settlement_ledger.py`.
>
> **Optional terminal projection:** finished-run tab placement through
> `run_triage.py` and `vc-frame triage-run`.
>
> Bucket tabs are retained compatibility/viewer surfaces. They do not own
> worker processes and are not the source of `f · x · n`.
>
> Source of terminal placement behavior: `vibecrafted_core/run_triage.py`,
> `vibecrafted_core/dispatcher.py` (Python finish hook),
> `runtime/scripts/lib/meta.sh` → `spawn_triage_run` (shell finish hook),
> `vc-frame triage-run` (transfer primitive).
> Related: [CONTRACT.md](./CONTRACT.md) (report frontmatter),
> [AGENT_OPS.md](./AGENT_OPS.md) (process and session ownership),
> [VC-FRAME.md](../VC-FRAME.md) (layouts and SESSIONS rail).

This document exists because field evidence repeatedly confused three different
numbers:

| What operators see                                        | What it actually counts                                                 |
| --------------------------------------------------------- | ----------------------------------------------------------------------- |
| Many `impl-*` / `rese-*` viewer tabs still open           | UI projections; not worker liveness or settlement                       |
| Control-plane `status=completed` + exit `0` + report path | Run state and artifacts; still not an immutable settlement history      |
| Settlement rail `f · x · n`                               | Ledger transitions or latest-per-run verdicts, depending on the UI view |

**Those are not the same axis.** Settlement ≠ triage. Worker ≠ viewer.
Push ≠ install. Layout ≠ ledger.

---

## Product shape (what “good” looks like)

```text
1. Ordinary worker launches headless in its own process session.
2. Agent output lands in the durable transcript; control-plane state exposes
   liveness independently of vc-frame.
3. Worker reaches a terminal state; the launcher/dispatcher finalizes
   artifacts (report/meta/transcript), then reaps orphan processes.
4. A V2 settlement event is appended to
   `control_plane/settlement_ledger.jsonl` before its bounded notification is
   published. Guardian and UI consumers must derive `f · x · n` from this
   ledger.
5. For an explicit `--runtime terminal` compatibility run only, runtime may call
   triage and `vc-frame triage-run` may:
   - capture scrollback + run identity
   - recreates a viewer/rerun tab in a bucket session
   - only then closes the origin tab
   → the origin pane often never shows the EXIT footer; that footer is
     what remains when triage skips or errors (fail-open leave-origin):
     [ EXIT CODE: N ]  <ENTER> re-run, <ESC> drop to shell, <Ctrl-c> exit
6. Closing, moving, or losing that viewer changes no ledger fact and has no
   authority over a headless worker.
```

`vc-frame` owns only the terminal transfer/projection. The runtime owns
classification and settlement. A PTY **cannot migrate** between sessions;
triage **recreates**, then closes origin. Fail-open on the projection side:
missing binary, dead session, or non-zero `triage-run` becomes a receipt —
never a lost report, never an exception that fails an already-finished run.

---

## Viewer bucket sessions (legacy wire names)

Exact session names are a **vc-frame wire contract** (`BucketKind::session_name`).
Vibecrafted mirrors them for receipts only.

| Rail  | Session name      | Verdict in meta `triage` | `--bucket` flag   |
| ----- | ----------------- | ------------------------ | ----------------- |
| **f** | `Finalized runs`  | `finalized`              | `finalized`       |
| **x** | `Failed runs`     | `failed`                 | `failed`          |
| **n** | `Needs attention` | `needs_attention`        | `needs-attention` |

The names remain a vc-frame compatibility wire for viewer placement. Product
`f · x · n` counters must instead read the settlement ledger:

- `counts.historical_transitions` for every immutable transition;
- `counts.latest_by_run` for one current verdict per run.

Missing bucket sessions therefore do not make ledger counts zero.

---

## Terminal projection classification (where a viewer lands)

Implemented by `classify_run` / `read_run_signals` in `run_triage.py`.

### Principle

**Single signals lie.** The drawer is a **conjunction**, never exit code alone.

Historical counterexample (AICX 2026-05-14 and later field runs): top-level
`completed` / exit `0` while the report body said `failed`, or
`timed_out` / `report_missing` next to complete artifacts. Contradictions go to
**Needs attention**, not a confident drawer.

### Inputs (non-exhaustive)

| Signal                                       | Role                                                                            |
| -------------------------------------------- | ------------------------------------------------------------------------------- |
| `exit_code`                                  | Required numeric; non-int treated as failure path                               |
| Control-plane / meta `status` / state        | Delivered vs died vs contradictory families                                     |
| Report path + size                           | Missing or &lt; `MINIMAL_REPORT_BYTES` (1) contradicts “delivered”              |
| Transcript size                              | Below `MINIMAL_TRANSCRIPT_BYTES` (512) treated as empty work                    |
| Delivery-kernel axes                         | When present: `execution_state` / `proof_state` / `delivery_state` own the path |
| Report frontmatter `claim_status` / `status` | **Claim only** — triangulated, never self-seals Finalized                       |

### Claim vs Finalized

Contract id: `vibecrafted.report-frontmatter.v1` (see [CONTRACT.md](./CONTRACT.md)).

- Agent frontmatter `claim_status: completed` is an **input claim**.
- It is **not** a self-issued Finalized verdict.
- Contradictions with exit / report / transcript / kernel axes → **Needs attention (`n`)**.

### Degraded path

If the installed `vc-frame` has `triage-run` but predates `--bucket` (W2-B-4a),
the runtime omits `--bucket` and records `verdict_degraded: exit_code_only`.
**Without `--bucket`, destination is exit-code-only: `0` → Finalized, any
non-zero → Needs attention (never Failed).** The conjunction classifier is not
applied for destination on that degraded wire.

---

## Origin identity (required for transfer)

`plan_triage` **refuses** transfer when it cannot name the host session:

| Field   | Preferred meta keys                                                        | Env fallbacks (live pane / stamp)                                                                            |
| ------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| session | `origin_session`, `vc_frame_session`, `operator_session`, `worker_session` | `VIBECRAFTED_WORKER_SESSION`, `VIBECRAFTED_OPERATOR_SESSION`, `VC_FRAME_SESSION_NAME`, `ZELLIJ_SESSION_NAME` |
| tab     | `origin_tab`, `vc_frame_tab`, `tab_name`                                   | `VC_FRAME_TAB_NAME`, else **run_id**                                                                         |
| pane    | `origin_pane_id`, `vc_frame_pane_id`, `pane_id`                            | `VC_FRAME_PANE_ID`, `ZELLIJ_PANE_ID`                                                                         |

**Skip / no-transfer reasons** (receipt, not crash) — non-exhaustive but field-complete for `triage_finished_run`:

| Reason               | Meaning                                                                            |
| -------------------- | ---------------------------------------------------------------------------------- |
| `disabled`           | Opt-out: `VIBECRAFTED_TRIAGE_RUN` ∈ `{0, false, no, off}`                          |
| `no_run_id`          | Meta has no run id                                                                 |
| `no_session`         | No origin session (common for headless / unfinished origin stamp / old tools home) |
| `shared_tab`         | Marbles shared tab — closing would destroy sibling scrollback                      |
| `no_binary`          | `vc-frame` not on `PATH` and `VIBECRAFTED_VC_FRAME_BIN` unset/missing              |
| `unsupported_binary` | Binary present but lacks a working `triage-run` subcommand                         |
| `no_meta`            | Meta path unreadable / not an object (outcome only; no receipt write)              |
| `error` / `exit N:…` | Transfer attempted; `triage-run` non-zero or invoke failed (origin left in place)  |

For an explicit terminal run, the Python dispatcher finishes **outside** the
viewer pane, so ambient `VC_FRAME_*` is often empty at triage time. That is why
terminal finish paths **stamp**
`origin_session` / `origin_tab` / `origin_pane_id` into meta (see
`supervisor_async._origin_fields_from_env` and meta summary write).

Ordinary headless, CI, and setsid runs have no session: skip is correct — there
is no terminal to triage.

---

## Call sites (who must invoke triage)

| Path                                 | Hook                                                                                                                                                 |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shell launchers                      | `spawn_triage_run` in `meta.sh` after finalize (and after reaper; reaper runs **before** triage because successful triage may close the current tab) |
| Python `vibecrafted_core.dispatcher` | After finalize, if `meta_path` and `exit_code` set → `triage_finished_run`                                                                           |
| Manual / backfill                    | `python -m vibecrafted_core.run_triage <meta.json>` or `vc-frame triage-run ...`                                                                     |

CLI shape for the primitive:

```bash
vc-frame triage-run \
  --run <run_id> \
  --exit-code <N> \
  [--bucket finalized|failed|needs-attention] \
  [--origin-session <session>] \
  [--origin-tab <tab>] \
  [--pane-id <pane>] \
  [--cwd <dir>] \
  [--dry-run] \
  -- <COMMAND>...
```

Rerun command preference in the plan: meta `command` or `launcher` (the
generated launcher is the reproducible run).

---

## Push ≠ install (tools home vs checkout)

| Layer             | Role                                                           |
| ----------------- | -------------------------------------------------------------- |
| Git checkout      | Development tree (`feat/...`, local HEAD)                      |
| Staged tools home | **What the daily CLI and launchers execute**                   |
| `vc-frame` binary | Separate install (`~/.local/bin/vc-frame` → cargo or vendored) |

Canonical staging (install contract):

- Prefer stable tools home resolved by `vibecrafted_core.runtime_paths.vibecrafted_tools_home`
  (honours `VIBECRAFTED_TOOLS_HOME` / `VIBECRAFTED_RUNTIME_HOME` / XDG).
- Typical path: `~/.local/share/vibecrafted/tools/vibecrafted-current/`
  (and/or `vibecrafted-local` during install mirrors).
- `make install` / installer `refresh_current_tools` stages the checkout into
  that home and stamps **`VERSION`** as `X.Y.Z+g<shortsha>`.
- `uv tool install --editable` of the CLI must point at the **stable staged
  tree**, never at a floating dev checkout (branch switch would break the
  daily driver).

**Verification after install:**

```bash
cat ~/.local/share/vibecrafted/tools/vibecrafted-current/VERSION
vibecrafted --version
# both should show the same +g<sha> as: git -C <checkout> rev-parse --short HEAD

python3 -c "
from pathlib import Path
p = Path.home()/'.local/share/vibecrafted/tools/vibecrafted-current/vibecrafted-core/vibecrafted_core/dispatcher.py'
print('triage_finished_run', 'triage_finished_run' in p.read_text())
"

vc-frame triage-run --help   # must list triage-run; ideally --bucket
```

Field failure mode (2026-07-22):

- Checkout `93bc849f` already contained dispatcher triage + origin stamp.
- Installed tools still `…+gca17ed91` → `triage_finished_run` **absent**.
- ~17 `impl-260722*` runs: `completed`, exit `0`, reports present, **`triage: null`**,
  **no origin fields** → SESSIONS `f·x·n` stayed `0` while the work rail was
  clogged with finished tabs.

**Re-run install after landing runtime changes.** `git push` alone does not
refresh the tools home.

---

## Research projections vs ordinary workers

These are different models. Do not force one into the other.

| Surface                                   | Default model                                                                                        |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Implement / scaffold / most skill workers | Detached headless process; receipt, transcript, and state may be projected into a viewer             |
| Research swarm                            | One common run_id with headless lanes; explicit terminal compatibility may use one multi-pane viewer |

### Static explicit-terminal layout (`config/vc-frame/layouts/research.kdl`)

- Includes **session-manager** rail (`Sessions` column) like operator/dashboard.
- Multi-pane: synthesis left (~55%), agents stacked right.
- Swap layouts: `grid`, `synthesis` (documented in the KDL header).

### Workflow-generated explicit-terminal layout

When terminal compatibility is explicitly selected,
`workflow._write_research_layout` (and the shell twin path) builds a **minimal**
KDL viewer for the swarm: compact-bar + status-bar + panes. It **does not** currently
include the session-manager rail, even though static `research.kdl` does.

That is a **layout generator gap**, not “research learning sessions over time.”
Until the generator includes the same rail block as the static layout, workflow-launched
research will look like it “does not know” the Sessions column.

### When does research touch `f · x · n`?

When the **whole research run** emits a V2 settlement event. Terminal triage
and a valid origin are optional projection concerns. Id prefixes in the wild:

| Path                                   | Typical `run_id` prefix |
| -------------------------------------- | ----------------------- |
| Python workflow / multi-pane research  | `rese-*`                |
| Shell spawn / `vc-research` skill path | `rsch-*`                |

Either form is a research run identity, not “four session columns for four agents.”

- For an explicit terminal run, prefer **one** transfer of the research viewer
  tab into a bucket — not one bucket entry per agent pane.
- Agent panes are viewer lanes inside the compatibility layout; they are not
  separate workers or SESSIONS board columns.

---

## Operator diagnostics (when a viewer rail or ledger count stays at 0)

Work through this list in order:

1. **Install stamp** — tools `VERSION` `+g` matches intended HEAD?
2. **Dispatcher wire** — installed `dispatcher.py` contains `triage_finished_run`?
3. **Binary** — `vc-frame triage-run --help` works? `--bucket` present?
4. **Meta sample** (one finished run under `~/.vibecrafted/control_plane/`):
   - `status` / `exit_code` / report path
   - `origin_session`, `origin_tab`
   - `triage` receipt (null vs `finalized` / `skipped` / `error`)
5. **Bucket sessions exist?** — `vc-frame list-sessions` should eventually show
   `Finalized runs` / `Failed runs` / `Needs attention` after successful
   projection transfers. This does not affect ledger counts.
6. **Ledger** — verify `settlement_ledger.jsonl` through
   `read_settlement_ledger()`; never repair counts by inventing pre-ledger facts.
7. **Historical runs** — triage is at finish time. Past runs without origin do
   not auto-backfill. Options: manual `triage-run` with explicit
   `--origin-session` / `--origin-tab`, or close orphan tabs manually.

### Manual backfill sketch

```bash
# Prefer dry-run first
vc-frame triage-run --dry-run \
  --run impl-YYYYMMDD-... \
  --exit-code 0 \
  --bucket finalized \
  --origin-session aicx \
  --origin-tab impl-YYYYMMDD-...
```

Only close/transfer tabs you can name. Fail-open means a bad call leaves the
origin alone — do not invent origin fields.

---

## What this is not

- Not a count of green control-plane rows.
- Not proof of product readiness (DoU still applies).
- Not a replacement for await/settlement contracts.
- Not permission to force-close marbles shared tabs.
- Not automatic GC of pre-install finished tabs.

---

## Related tests and probes

| Check               | Location / command                                 |
| ------------------- | -------------------------------------------------- |
| Triage unit surface | `vibecrafted-core/tests/test_run_triage.py`        |
| Settlement ledger   | `vibecrafted-core/tests/test_settlement_ledger.py` |
| Layout smoke        | `make test-vc-frame`                               |
| Report frontmatter  | `report_contract` + artifact validation tests      |
| Install stamp       | `VERSION` under tools home after `make install`    |

---

## Change log (docs)

| Date       | Note                                                                                                                                                                                                     |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-22 | Initial canon from runtime land (`run_triage` + dispatcher hook + origin stamp) and field proof: many completed runs + `f·x·n=0` when tools home lagged checkout and origin/triage receipts were absent. |

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_

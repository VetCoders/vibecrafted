# control-core — design record

_Wave W1-a · `server/control-core/` · 2026-05-31 · authored-by: claude_

## What this is

`control-core` is the read-only typed Rust model of the Vibecrafted control
plane. It mirrors the canonical Python writer
`vibecrafted-core/vibecrafted_core/control_plane.py` and exposes a typed read
API plus the SSE event-stream substrate. One core, two frontends:

```
~/.vibecrafted/control_plane/        Python control_plane.py  (writer — source of truth)
        │  runs/<id>.json
        │  events.jsonl
        ▼
   control-core (Rust)               read-only typed model  ← THIS CRATE
        ├── server/web   (W1-b/W2)   axum + Leptos live-runs view
        └── vc-agent     (later)     TUI (renamed vc-tui)
```

The Python side keeps owning every write (snapshots, event appends, the
`.sync.lock`). control-core never writes — it is a pure projection.

## Decision: read + merge in Rust (SCAFFOLD flaga — option a)

The scaffold left a flag: should the Rust core (a) read the three raw merge
sources and merge them itself, or (b) lean entirely on the merged
`runs/<id>.json` snapshots the Python `sync_state` produces?

**Chosen: (a) — merge in Rust, while still supporting the cheap snapshot path.**

Rationale:

- **Frontend self-sufficiency.** A `vibecrafted server` web process should not
  have to shell into Python `control_plane sync` on every refresh just to get a
  fresh view. Porting the merge (`_normalize_agent_meta` / `_normalize_lock` /
  `_normalize_marbles_state` / `_merge_status`) into Rust lets the web and TUI
  frontends compute the live view directly, read-only, on their own tick.
- **No write coupling.** Python `sync_state` both reads the three sources *and*
  writes `runs/<id>.json` + appends transition events under an exclusive lock.
  control-core deliberately keeps only the read half. It never takes the lock,
  never writes a snapshot, never appends an event. This avoids two writers
  racing on the same files and keeps the Python side authoritative.
- **Cheap path preserved.** [`ControlPlane::read_state_view`] still trusts the
  already-merged `runs/<id>.json` snapshots when freshness from the last Python
  sync is acceptable (cheaper: one directory of small JSON files, no recursive
  `artifacts/` walk). [`ControlPlane::compute_view`] is the option-(a) path that
  re-derives the view from `*.meta.json` + `*.lock` + `marbles/**/state.json`.

The two API surfaces:

| Method | Source | Cost | Use when |
|---|---|---|---|
| `load_snapshots` / `lookup_run` | `runs/<id>.json` | low | Python sync is recent enough |
| `read_state_view` | `runs/<id>.json` + event tail | low | dashboard refresh, trust last sync |
| `compute_view(now)` | meta + lock + marbles, merged in Rust | higher | frontend must be self-sufficient |

`now` is always an explicit parameter for the merge/health derivation, so the
clock is injectable and the golden tests are deterministic.

## SSE substrate

`events.jsonl` is the event log. The cursor is a **byte offset** into that file,
exactly like Python `subscribe_events` (`cursor = handle.tell()`).
[`EventStream::read_since(cursor, kinds)`] seeks to the offset, decodes every
complete line to a typed `Event`, and returns the batch plus the next cursor. A
W2 axum SSE route drains this on a tick and hands the cursor back to the client
as `Last-Event-ID` for resume.

Two deliberate divergences from the Python `subscribe_events`, both safer for a
live SSE tail:

1. **Non-blocking.** No `time.sleep(1.0)` poll loop. The async runtime owns the
   tick; `read_since` returns immediately at EOF.
2. **Partial-line guard.** If the last line has no trailing newline (Python is
   mid-`append`), the Rust reader stops *before* it and leaves the cursor at the
   line's start, so the next drain re-reads it once complete. The Python reader
   advances `tell()` past the half-written line and drops it on the
   `JSONDecodeError` — a latent data-loss under concurrent append. control-core
   does not reproduce that bug.

## Golden-schema drift guard

`tests/schema_fidelity.rs` pins the serde model to **real** on-disk samples
captured 2026-05-31 from `~/.vibecrafted/control_plane/`:

- A terminal `runs/<id>.json` (`marb-000`: `exit_code` present, lock absent) and
  an in-flight one (`just-…`: null Options, live lock) — both asserted to
  round-trip to a structurally identical JSON value, so **no field is gained or
  lost**. If `control_plane.py` adds/renames a field and control-core is not
  updated, the key-set assertion fails loudly.
- A real `*.meta.json` normalised into a `RunStatus`, asserting the field
  remap (`status`→`state`, `skill_code`→`skill` via the code map, etc.) and the
  health derivation at both the active and stalled side of the 1200s threshold.
- A real `events.jsonl` line, asserting the `cursor`-absent-on-disk contract and
  the partial-tail cursor behaviour on a temp file.

## Documented field drift vs Python

The on-disk JSON is runtime truth; where the Python *type hints* and the JSON
disagree, control-core tracks the JSON. Known, intentional divergences:

- **`Event.cursor`** — present on the Rust `Event` (byte offset), absent from
  `events.jsonl` lines. Defaults to `0` on deserialize, stamped by the reader.
- **`_coerce_int`** — Rust strips a single leading `-`; Python `lstrip("-")`
  strips all leading dashes. Both reject bools and accept digit-strings; the
  only behavioural gap is the pathological `"--5"`, which never occurs on disk.
- **`SKILL_CODE_MAP`** — mirrored exactly (18 entries). Unknown codes such as
  `owne` fall through to the code string itself, matching the Python default —
  control-core does **not** invent extra mappings.
- **`health`** — stored as a `String` on `RunStatus` for lossless fidelity to
  disk (a future Python health value won't break deserialize). The `Health`
  enum is the derivation/return type, not the storage type.

## Out of scope for W1-a (handed to later waves)

- No HTTP / axum / Leptos — the web layer is W1-b/W2. control-core only exposes
  the typed model + read API + the `EventStream` an SSE route will wrap.
- No edits to `control_plane.py`. The Python writer stays the source of truth.
- No `vc-tui` edits / rename.

## Acceptance evidence

Gates (run from `server/`):

```
cargo build  -p control-core            → Finished (clean)
cargo clippy -p control-core --all-targets -- -D warnings → Finished (no warnings)
cargo test   -p control-core            → 7 passed (schema_fidelity) + 1 doctest
```

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_

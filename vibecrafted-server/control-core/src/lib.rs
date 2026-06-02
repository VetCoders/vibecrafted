//! `control-core` — read-only typed model of the Vibecrafted control plane.
//!
//! One core, two frontends. The Python writer
//! (`vibecrafted-core/vibecrafted_core/control_plane.py`) owns
//! `~/.vibecrafted/control_plane/`; this crate gives Rust callers a typed,
//! **read-only** view of the same data so the `vibecrafted server` web UI
//! (W1-b/W2) and the future `vc-agent` TUI can share one contract instead of
//! re-parsing JSON ad hoc.
//!
//! Three layers:
//!
//! * [`model`] — `RunStatus`, `Event`, state classes, `health` derivation, the
//!   skill-code map, and the `*.meta.json` → `RunStatus` normalisation. A
//!   field-for-field mirror of `control_plane.py`.
//! * [`read`] — [`ControlPlane`], a handle that loads `runs/<id>.json`
//!   snapshots, looks up a single run, and (option a) merges the three raw
//!   sources in Rust. Never writes.
//! * [`events`] — [`EventStream`], the cursor-as-byte-offset substrate a W2
//!   axum SSE route drains.
//!
//! ```no_run
//! use control_core::ControlPlane;
//!
//! let plane = ControlPlane::from_env();
//! for run in plane.load_snapshots() {
//!     println!("{} {} ({})", run.run_id, run.state, run.health);
//! }
//! let batch = plane.events().read_since(0, &[]).unwrap();
//! println!("{} events, next cursor {}", batch.events.len(), batch.cursor);
//! ```

pub mod events;
pub mod model;
pub mod read;

pub use events::{EventBatch, EventStream};
pub use model::{
    AgentMeta, Event, Health, RunStatus, StateClass, ACTIVE_STATES, EVENT_TAIL_LIMIT, FINAL_STATES,
    RECENT_RUN_LIMIT, RUN_STALL_SECONDS, SKILL_CODE_MAP, classify_state, coerce_int_value,
    is_active_state, is_final_state, merge_status, operator_session_name, parse_iso,
    skill_from_code, state_health,
};
pub use read::{ControlPlane, StateView, vibecrafted_home};

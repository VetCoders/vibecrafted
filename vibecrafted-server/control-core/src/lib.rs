//! `control-core` — typed model of the Vibecrafted control plane.
//!
//! One core, two frontends. The Python writer
//! (`vibecrafted-core/vibecrafted_core/control_plane.py`) owns
//! `~/.vibecrafted/control_plane/`; this crate gives Rust callers a typed,
//! **read-only** view of the same data so the `vibecrafted server` web UI
//! (W1-b/W2) and the future `vc-agent` TUI can share one contract instead of
//! re-parsing JSON ad hoc.
//!
//! The scaffold editor is the deliberate exception to the read-only rule: it
//! edits manifest-declared Markdown artifacts under canonical
//! `artifacts/<org>/<repo>/<day>/plans/<plan_id>/` roots and records
//! change/checkpoint sidecars there. Legacy `operator/` roots are read-only.
//! It never writes Python
//! control-plane snapshots.
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
//! * [`scaffold`] — typed discovery, artifact writes, change feed, and
//!   checkpoints for vc-scaffold review artifacts.
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
pub mod scaffold;

pub use events::{EventBatch, EventStream};
pub use model::{
    ACTIVE_STATES, AgentMeta, EVENT_TAIL_LIMIT, Event, FINAL_STATES, Health, LifecycleBaton,
    LifecycleDouIndex, LifecycleOperatorAction, LifecycleRun, LifecycleRunSummary, LifecycleStage,
    LifecycleTransition, RECENT_RUN_LIMIT, RUN_STALL_SECONDS, RunStatus, SKILL_CODE_MAP,
    StateClass, classify_state, coerce_int_value, is_active_state, is_final_state, merge_status,
    operator_session_name, parse_iso, skill_from_code, state_health,
};
pub use read::{ControlPlane, StateView, vibecrafted_home};
pub use scaffold::{
    SCAFFOLD_MANIFEST_SCHEMA_JSON, SCAFFOLD_SCHEMA_VERSION, ScaffoldArtifact,
    ScaffoldArtifactDeclaration, ScaffoldArtifactPatch, ScaffoldArtifactRole,
    ScaffoldArtifactStore, ScaffoldChange, ScaffoldCheckpoint, ScaffoldCheckpointPatch,
    ScaffoldDoctorError, ScaffoldDoctorReport, ScaffoldError, ScaffoldManifest,
    ScaffoldPlanSummary, ScaffoldResult, ScaffoldWorkspace,
};

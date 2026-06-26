//! Control-plane read surface for the `vibecrafted server`.
//!
//! Mirrors the `scaffold::api` shape: an `ssr`-gated axum sub-router merged into
//! the Leptos app in `main.rs`. Every route is a **read** over the live
//! `~/.vibecrafted/control_plane/` (or `$VIBECRAFTED_HOME`) via
//! [`control_core::ControlPlane`] — the same typed read-model the future TUI
//! shares. Nothing here writes; this is remote observability of what the Python
//! runtime already produced.
//!
//! Routes:
//! * `GET /api/control/state` — merged [`StateView`](control_core::StateView)
//!   (active/recent runs, warnings, event tail), computed in Rust from the three
//!   raw sources so the server never depends on the Python sync having run.
//! * `GET /api/control/runs` — every `runs/<id>.json` snapshot, newest-first.
//! * `GET /api/control/runs/{run_id}` — a single run, or `404` JSON.

#[cfg(feature = "ssr")]
pub mod api {
    use axum::Json;
    use axum::Router;
    use axum::extract::Path;
    use axum::http::StatusCode;
    use axum::response::IntoResponse;
    use axum::routing::get;
    use chrono::Utc;
    use control_core::{ControlPlane, StateView};
    use serde_json::json;

    /// The control-plane read router, keyed to the same `LeptosOptions` state the
    /// app router carries so it merges without a state-type mismatch.
    pub fn control_routes() -> Router<leptos::config::LeptosOptions> {
        Router::<leptos::config::LeptosOptions>::new()
            .route("/api/control/state", get(state))
            .route("/api/control/runs", get(runs))
            .route("/api/control/runs/{run_id}", get(run))
    }

    /// Serialise a [`StateView`] into the JSON envelope. `StateView` itself is
    /// not `Serialize` (it carries no clock), but its `RunStatus` / `Event`
    /// members are, so we project field-by-field and stamp `generated_at` here —
    /// matching the `generated_at` the Python `sync_state` payload adds.
    fn state_envelope(plane: &ControlPlane, view: &StateView, generated_at: String) -> Json<serde_json::Value> {
        Json(json!({
            "control_plane": plane.control_plane_home().display().to_string(),
            "generated_at": generated_at,
            "active_runs": view.active_runs,
            "recent_runs": view.recent_runs,
            "warnings": view.warnings,
            "events": view.events,
        }))
    }

    /// Merged control-plane state view. The self-sufficient path: merges
    /// `*.meta.json` + `*.lock` + `marbles/**/state.json` in Rust.
    async fn state() -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        let now = Utc::now();
        let view = plane.compute_view(now);
        state_envelope(&plane, &view, now.to_rfc3339())
    }

    /// Every `runs/<id>.json` snapshot, newest-first.
    async fn runs() -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        let snapshots = plane.load_snapshots();
        Json(json!({
            "control_plane": plane.control_plane_home().display().to_string(),
            "count": snapshots.len(),
            "runs": snapshots,
        }))
    }

    /// A single run by id, or a `404` JSON body when absent.
    async fn run(Path(run_id): Path<String>) -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        match plane.lookup_run(&run_id) {
            Some(run) => Json(json!(run)).into_response(),
            None => (
                StatusCode::NOT_FOUND,
                Json(json!({ "error": format!("run not found: {run_id}") })),
            )
                .into_response(),
        }
    }
}

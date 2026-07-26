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
//! * `GET /api/health` — constant-time process readiness; never scans the
//!   control plane.
//! * `GET /api/control/state` — merged [`StateView`](control_core::StateView)
//!   (canonical settlement board, active/recent runs, warnings, event tail),
//!   computed in Rust from retained snapshots plus the three raw live sources
//!   and lifecycle projections.
//! * `GET /api/control/runs` — every `runs/<id>.json` snapshot, newest-first.
//!   Each run serialises optional delivery-proof axes (`execution_state`,
//!   `proof_state`, `delivery_state`) and optional `seal` when present on the
//!   kernel receipt / snapshot. Absent axes stay absent (never invented from
//!   `completed`).
//! * `GET /api/control/runs/{run_id}` — a single run, or `404` JSON. Same axis
//!   / seal projection as the list route.
//! * `GET /api/control/lifecycle` — lifecycle run summaries, newest-first.
//! * `GET /api/control/lifecycle/{run_id}` — full nested lifecycle state with
//!   projected per-run and per-stage axes (shape of `write_lifecycle_report`).
//! * `GET /api/control/events` — Server-Sent Events stream of `events.jsonl`
//!   from a client-held cursor (`?since=` / `Last-Event-ID`), with `: ping`
//!   keepalives. Read-only; see [`events_sse`].

#[cfg(feature = "ssr")]
mod events_sse;

#[cfg(feature = "ssr")]
pub mod api {
    use axum::Json;
    use axum::Router;
    use axum::extract::Path;
    use axum::http::StatusCode;
    use axum::response::IntoResponse;
    use axum::routing::get;
    use chrono::{DateTime, Utc};
    use control_core::{ControlPlane, Event, RunStatus, SettlementBoard};
    use serde::Serialize;
    use serde_json::json;

    use super::events_sse::events_sse;

    /// The control-plane read router, keyed to the same `LeptosOptions` state the
    /// app router carries so it merges without a state-type mismatch.
    pub fn control_routes() -> Router<leptos::config::LeptosOptions> {
        Router::<leptos::config::LeptosOptions>::new()
            .route("/api/health", get(health))
            .route("/api/control/state", get(state))
            .route("/api/control/runs", get(runs))
            .route("/api/control/runs/{run_id}", get(run))
            .route("/api/control/lifecycle", get(lifecycle))
            .route("/api/control/lifecycle/{run_id}", get(lifecycle_run))
            .route("/api/control/events", get(events_sse))
    }

    /// Constant-time readiness for service supervision. Runtime health must
    /// not recursively trigger an unbounded control-plane projection.
    async fn health() -> StatusCode {
        StatusCode::OK
    }

    /// Canonical server projection consumed by both JSON and dashboard SSR.
    /// Settlement classification remains wholly owned by `control-core`.
    #[derive(Clone, Serialize)]
    pub(crate) struct StateEnvelope {
        pub(crate) control_plane: String,
        pub(crate) generated_at: String,
        pub(crate) active_runs: Vec<RunStatus>,
        pub(crate) recent_runs: Vec<RunStatus>,
        pub(crate) warnings: Vec<String>,
        pub(crate) events: Vec<Event>,
        pub(crate) settlement_counts: SettlementBoard,
    }

    pub(crate) fn state_payload(plane: &ControlPlane, now: DateTime<Utc>) -> StateEnvelope {
        let view = plane.compute_view(now);
        StateEnvelope {
            control_plane: plane.control_plane_home().display().to_string(),
            generated_at: now.to_rfc3339(),
            active_runs: view.active_runs,
            recent_runs: view.recent_runs,
            warnings: view.warnings,
            events: view.events,
            settlement_counts: view.settlement_counts,
        }
    }

    /// Merged control-plane state view. The self-sufficient path: merges
    /// `*.meta.json` + `*.lock` + `marbles/**/state.json` in Rust.
    async fn state() -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        let now = Utc::now();
        Json(state_payload(&plane, now))
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

    /// Lifecycle run summaries, newest-first by `state.json` mtime.
    async fn lifecycle() -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        let lifecycle_runs = plane.load_lifecycle_run_summaries();
        Json(json!({
            "control_plane": plane.control_plane_home().display().to_string(),
            "count": lifecycle_runs.len(),
            "lifecycle_runs": lifecycle_runs,
        }))
    }

    /// Full nested lifecycle state by id, or a `404` JSON body when absent.
    ///
    /// The payload includes projected delivery-proof axes on the run and each
    /// stage (`execution_state` / `proof_state` / `delivery_state`). Projection
    /// is owned by `control_core` and never maps `completed` → delivered/sealed.
    async fn lifecycle_run(Path(run_id): Path<String>) -> impl IntoResponse {
        let plane = ControlPlane::from_env();
        match plane.resolve_lifecycle_run(&run_id) {
            Some(run) => Json(json!(run)).into_response(),
            None => (
                StatusCode::NOT_FOUND,
                Json(json!({ "error": format!("lifecycle run not found: {run_id}") })),
            )
                .into_response(),
        }
    }

    /// A single run by id, or a `404` JSON body when absent.
    ///
    /// Serialises typed delivery axes and seal when the snapshot/receipt carries
    /// them; omits those keys for legacy runs (no completed→delivery guess).
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

//! Read-only access to `~/.vibecrafted/control_plane/`.
//!
//! Mirrors the *read half* of `control_plane.sync_state` / `lookup_run`, but
//! never writes: no snapshot files, no event appends, no `.sync.lock`. Two
//! paths are offered:
//!
//! * [`ControlPlane::load_snapshots`] / [`ControlPlane::lookup_run`] — the cheap
//!   path that trusts the merged `runs/<id>.json` snapshots the Python writer
//!   already produced.
//! * [`ControlPlane::compute_view`] — the "merge in Rust" path (SCAFFOLD flaga,
//!   option a): read the three raw sources (`*.meta.json`, `*.lock`,
//!   `marbles/**/state.json`), normalise and merge them in-process, and project
//!   active/recent/warnings without ever depending on the Python sync having
//!   run. This is what lets the web/TUI frontends be self-sufficient.

use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};

use crate::events::EventStream;
use crate::model::{
    AgentMeta, DeliverySealRef, Event, FINAL_STATES, Health, LifecycleRun, LifecycleRunSummary,
    RECENT_RUN_LIMIT, RUN_STALL_SECONDS, RunStatus, SettlementBoard, coerce_int_value,
    is_final_state, merge_status, operator_session_name, parse_iso, skill_from_code, state_health,
};

/// Resolve `~`-prefixed paths against `$HOME`. Other paths pass through.
fn expanduser(path: PathBuf) -> PathBuf {
    if let Ok(stripped) = path.strip_prefix("~") {
        if let Some(home) = home_dir() {
            return home.join(stripped);
        }
    }
    path
}

/// `$HOME` as a path. Unix/macOS only — Vibecrafted runs on darwin/linux.
fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

/// Vibecrafted home. Mirrors `runtime_paths.vibecrafted_home`:
/// `$VIBECRAFTED_HOME` (expanded) if set & non-empty, else `~/.vibecrafted`.
#[must_use]
pub fn vibecrafted_home() -> PathBuf {
    if let Some(raw) = std::env::var_os("VIBECRAFTED_HOME") {
        if !raw.is_empty() {
            return expanduser(PathBuf::from(raw));
        }
    }
    home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".vibecrafted")
}

/// A read-only handle on a control-plane root directory.
#[derive(Debug, Clone)]
pub struct ControlPlane {
    home: PathBuf,
    control_plane_home: PathBuf,
}

/// Aggregate projection. Mirrors the read-shape of `control_plane.sync_state`'s
/// return payload, minus `generated_at` (callers stamp their own clock).
#[derive(Debug, Clone)]
pub struct StateView {
    /// In-flight runs (health active/stalled and not in a final state).
    pub active_runs: Vec<RunStatus>,
    /// Up to [`RECENT_RUN_LIMIT`] most-recently-updated runs.
    pub recent_runs: Vec<RunStatus>,
    /// Human-readable warnings (stalls, locks without reports).
    pub warnings: Vec<String>,
    /// Newest-first event tail.
    pub events: Vec<Event>,
    /// Python-owned settlement truth across retained `runs/*.json` snapshots,
    /// plus the active count from this Rust projection.
    pub settlement_counts: SettlementBoard,
}

impl ControlPlane {
    /// Handle rooted at the given Vibecrafted home (the dir that *contains*
    /// `control_plane/`).
    #[must_use]
    pub fn new(home: impl Into<PathBuf>) -> Self {
        let home = home.into();
        let control_plane_home = home.join("control_plane");
        Self {
            home,
            control_plane_home,
        }
    }

    /// Handle rooted at an explicit control-plane directory.
    ///
    /// Frontends already receive `.../control_plane` as their state root. This
    /// constructor lets them consume the canonical reader without guessing a
    /// second state path or reparsing the same files.
    #[must_use]
    pub fn from_control_plane_home(control_plane_home: impl Into<PathBuf>) -> Self {
        let control_plane_home = control_plane_home.into();
        let home = control_plane_home
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| control_plane_home.clone());
        Self {
            home,
            control_plane_home,
        }
    }

    /// Handle rooted at [`vibecrafted_home`] (env-aware default).
    #[must_use]
    pub fn from_env() -> Self {
        Self::new(vibecrafted_home())
    }

    /// `<home>/control_plane`.
    #[must_use]
    pub fn control_plane_home(&self) -> PathBuf {
        self.control_plane_home.clone()
    }

    /// `<home>/control_plane/runs`.
    #[must_use]
    pub fn run_snapshot_dir(&self) -> PathBuf {
        self.control_plane_home().join("runs")
    }

    /// `<home>/control_plane/runtime_runs/<id>` — where the core runtime writes
    /// a run (`prompt.md`/`transcript.log`; `meta.json` optional) before the
    /// snapshot sync merges it into `runs/<id>.json`. Mirrors the Python
    /// `control_plane._runtime_run_dir`.
    #[must_use]
    pub fn runtime_run_dir(&self, run_id: &str) -> PathBuf {
        self.control_plane_home().join("runtime_runs").join(run_id)
    }

    /// `<home>/control_plane/lifecycle_runs`.
    #[must_use]
    pub fn lifecycle_runs_dir(&self) -> PathBuf {
        self.control_plane_home().join("lifecycle_runs")
    }

    /// `<home>/control_plane/lifecycle_runs/<id>`.
    #[must_use]
    pub fn lifecycle_run_dir(&self, run_id: &str) -> PathBuf {
        self.lifecycle_runs_dir().join(run_id)
    }

    /// `<home>/control_plane/events.jsonl`.
    #[must_use]
    pub fn event_stream_path(&self) -> PathBuf {
        self.control_plane_home().join("events.jsonl")
    }

    /// An [`EventStream`] over this plane's `events.jsonl` — the SSE substrate.
    #[must_use]
    pub fn events(&self) -> EventStream {
        EventStream::new(self.event_stream_path())
    }

    /// Load every `runs/<id>.json` snapshot, sorted newest-first by
    /// `updated_at`. Unreadable / malformed files are skipped, not fatal
    /// (mirrors the Python `_read_json` swallow-on-error behaviour).
    #[must_use]
    pub fn load_snapshots(&self) -> Vec<RunStatus> {
        let mut runs = self.read_snapshot_dir();
        sort_recent_first(&mut runs);
        runs
    }

    fn read_snapshot_dir(&self) -> Vec<RunStatus> {
        let dir = self.run_snapshot_dir();
        let Ok(entries) = fs::read_dir(&dir) else {
            return Vec::new();
        };
        let mut runs = Vec::new();
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            if let Some(run) = read_json::<RunStatus>(&path) {
                if !run.run_id.is_empty() {
                    runs.push(self.attach_seal_if_present(run));
                }
            }
        }
        runs
    }

    /// Look up a single run by id from the on-disk snapshots. Mirrors
    /// `control_plane.lookup_run` but without the write-side sync — reads the
    /// merged snapshot directly.
    #[must_use]
    pub fn lookup_run(&self, run_id: &str) -> Option<RunStatus> {
        let target = run_id.trim();
        if target.is_empty() {
            return None;
        }
        let direct = self.run_snapshot_dir().join(format!("{target}.json"));
        if let Some(run) = read_json::<RunStatus>(&direct) {
            if run.run_id == target {
                return Some(self.attach_seal_if_present(run));
            }
        }
        if let Some(run) = self
            .load_snapshots()
            .into_iter()
            .find(|run| run.run_id == target)
        {
            return Some(run);
        }
        // Read-follows-write: a still-launching run lives in runtime_runs/ before
        // the snapshot sync merges it into runs/<id>.json. Mirror the first probe
        // of control_plane.resolve_run so this frontend eye reads the same place
        // the runtime wrote (Niezmiennik 3 — one contract, many eyes).
        if let Some(run) = self.resolve_runtime_run(target) {
            return Some(self.attach_seal_if_present(run));
        }
        self.resolve_lifecycle_run(target)
            .map(|run| self.lifecycle_run_status(&run))
    }

    /// Attach a seal projection from `runtime_runs/<id>/delivery-seal.json`
    /// when the snapshot does not already carry one. Read-only; never invents
    /// delivery axes from process state.
    fn attach_seal_if_present(&self, mut run: RunStatus) -> RunStatus {
        if run.seal.is_none() {
            run.seal = self.read_seal_ref(&run.run_id);
        }
        run
    }

    /// Read `delivery-seal.json` under the runtime run directory, if present
    /// and well-formed enough to project.
    #[must_use]
    pub fn read_seal_ref(&self, run_id: &str) -> Option<DeliverySealRef> {
        let target = run_id.trim();
        if target.is_empty() {
            return None;
        }
        let path = self.runtime_run_dir(target).join("delivery-seal.json");
        read_json::<DeliverySealRef>(&path).filter(|seal| !seal.seal_id.is_empty())
    }

    /// Resolve a run straight from `runtime_runs/<id>/` — the read-follows-write
    /// fallback mirroring `control_plane.resolve_run`. A just-launched run lives
    /// here (`transcript.log`; `meta.json` optional and frequently absent at
    /// launch) before the Python sync merges it into the `runs/` snapshots.
    /// Runtime metadata is projected when present so an old completed directory
    /// never masquerades as a fresh launch. `None` means the run has not reached
    /// the runtime tree yet (the "still launching → await" case).
    #[must_use]
    pub fn resolve_runtime_run(&self, run_id: &str) -> Option<RunStatus> {
        let target = run_id.trim();
        if target.is_empty() {
            return None;
        }
        let dir = self.runtime_run_dir(target);
        if !dir.is_dir() {
            return None;
        }
        let meta = read_json::<serde_json::Value>(&dir.join("meta.json"));
        let value = |key: &str| {
            meta.as_ref()
                .and_then(|payload| payload.get(key))
                .and_then(serde_json::Value::as_str)
                .unwrap_or_default()
                .to_string()
        };
        let state = {
            let status = value("status");
            if status.is_empty() {
                let state = value("state");
                if state.is_empty() {
                    "launching".to_string()
                } else {
                    state
                }
            } else {
                status
            }
        };
        let exit_code = meta
            .as_ref()
            .and_then(|payload| payload.get("exit_code"))
            .and_then(coerce_int_value);
        let completed_at = value("completed_at");
        let terminal = is_final_state(&state) || exit_code.is_some() || !completed_at.is_empty();
        let transcript = dir.join("transcript.log");
        let latest_transcript = {
            let declared = value("transcript");
            if !declared.is_empty() {
                declared
            } else if transcript.is_file() {
                transcript.to_string_lossy().into_owned()
            } else {
                String::new()
            }
        };
        let updated_at = {
            let updated = value("updated_at");
            if updated.is_empty() {
                completed_at.clone()
            } else {
                updated
            }
        };
        Some(RunStatus {
            run_id: target.to_string(),
            state,
            agent: value("agent"),
            skill: nonempty_runtime_value(&value("skill"), &value("workflow")),
            mode: value("mode"),
            root: value("root"),
            operator_session: value("operator_session"),
            latest_report: value("report"),
            latest_transcript,
            last_error: nonempty_runtime_value(&value("message"), &value("reason")),
            updated_at,
            started_at: value("started_at"),
            health: if terminal { "final" } else { "active" }.to_string(),
            source: "runtime_runs".to_string(),
            lock_present: false,
            exit_code,
            liveness: if terminal {
                "terminal".to_string()
            } else {
                value("liveness")
            },
            launcher_pid: None,
            completed_at,
            session_id: value("session_id"),
            current_loop: None,
            total_loops: None,
            settlement_verdict: None,
            settlement_tui: None,
            // No delivery section on a still-launching runtime dir unless a
            // seal file is later attached by attach_seal_if_present.
            execution_state: None,
            proof_state: None,
            delivery_state: None,
            seal: None,
        })
    }

    /// Every run currently materialised under `runtime_runs/` as a read-only
    /// [`RunStatus`]. The aggregate counterpart to
    /// [`Self::resolve_runtime_run`]; used by [`Self::compute_view`] so a fresh
    /// run shows on the dashboard before the snapshot sync merges it.
    fn iter_runtime_run_status(&self) -> Vec<RunStatus> {
        let root = self.control_plane_home().join("runtime_runs");
        let Ok(entries) = fs::read_dir(&root) else {
            return Vec::new();
        };
        let mut runs = Vec::new();
        for entry in entries.flatten() {
            if !entry.path().is_dir() {
                continue;
            }
            if let Some(name) = entry.file_name().to_str() {
                if let Some(run) = self.resolve_runtime_run(name) {
                    runs.push(run);
                }
            }
        }
        runs
    }

    /// Resolve a full nested lifecycle run from `lifecycle_runs/<id>/state.json`.
    ///
    /// Delivery-proof axes are projected onto the run and each stage (shape of
    /// `write_lifecycle_report`) so `/api/control/lifecycle/{run_id}` never
    /// has to re-derive them from `completed`/`artifact_ok` in the server.
    #[must_use]
    pub fn resolve_lifecycle_run(&self, run_id: &str) -> Option<LifecycleRun> {
        let target = run_id.trim();
        if target.is_empty() {
            return None;
        }
        let state_path = self.lifecycle_run_dir(target).join("state.json");
        let mut run = read_json::<LifecycleRun>(&state_path)?;
        if run.run_id == target {
            run.project_delivery_axes();
            Some(run)
        } else {
            None
        }
    }

    /// Full nested lifecycle runs, newest first by `state.json` mtime.
    /// Each run carries projected delivery-proof axes (see
    /// [`LifecycleRun::project_delivery_axes`]).
    #[must_use]
    pub fn load_lifecycle_runs(&self) -> Vec<LifecycleRun> {
        let Ok(entries) = fs::read_dir(self.lifecycle_runs_dir()) else {
            return Vec::new();
        };
        let mut runs = Vec::new();
        for entry in entries.flatten() {
            if !entry.path().is_dir() {
                continue;
            }
            let state_path = entry.path().join("state.json");
            let Some(mut run) = read_json::<LifecycleRun>(&state_path) else {
                continue;
            };
            if run.run_id.is_empty() {
                continue;
            }
            run.project_delivery_axes();
            runs.push((modified_at(&state_path), run));
        }
        runs.sort_by_key(|(modified, _)| std::cmp::Reverse(*modified));
        runs.into_iter().map(|(_, run)| run).collect()
    }

    /// Compact lifecycle summaries for list APIs and dashboard cards.
    #[must_use]
    pub fn load_lifecycle_run_summaries(&self) -> Vec<LifecycleRunSummary> {
        self.load_lifecycle_runs()
            .iter()
            .map(|run| self.lifecycle_run_summary(run))
            .collect()
    }

    /// Every lifecycle run as a flat status projection for existing state views.
    #[must_use]
    pub fn iter_lifecycle_run_status(&self) -> Vec<RunStatus> {
        self.load_lifecycle_runs()
            .iter()
            .map(|run| self.lifecycle_run_status(run))
            .collect()
    }

    fn lifecycle_run_summary(&self, run: &LifecycleRun) -> LifecycleRunSummary {
        run.summary(
            self.lifecycle_run_updated_at(run),
            self.lifecycle_dou_index_from_reports(run),
        )
    }

    fn lifecycle_run_status(&self, run: &LifecycleRun) -> RunStatus {
        run.to_run_status(
            self.lifecycle_run_updated_at(run),
            self.lifecycle_dou_index_from_reports(run),
        )
    }

    fn lifecycle_dou_index_from_reports(&self, run: &LifecycleRun) -> Option<i64> {
        self.lifecycle_stage_report_path(run)
            .as_deref()
            .and_then(report_dou_index)
            .or_else(|| report_dou_index(&self.lifecycle_report_path(run)))
    }

    fn lifecycle_state_path(&self, run: &LifecycleRun) -> PathBuf {
        existing_or_canonical(
            &run.state_path,
            self.lifecycle_run_dir(&run.run_id).join("state.json"),
        )
    }

    fn lifecycle_report_path(&self, run: &LifecycleRun) -> PathBuf {
        existing_or_canonical(
            &run.report_path,
            self.lifecycle_run_dir(&run.run_id).join("report.md"),
        )
    }

    fn lifecycle_stage_report_path(&self, run: &LifecycleRun) -> Option<PathBuf> {
        let raw = run.stages.last()?.launch.get("report")?.as_str()?.trim();
        if raw.is_empty() {
            return None;
        }
        let path = PathBuf::from(raw);
        path.is_file().then_some(path)
    }

    fn lifecycle_run_updated_at(&self, run: &LifecycleRun) -> String {
        modified_at(&self.lifecycle_state_path(run))
            .map(DateTime::<Utc>::from)
            .map(|dt| dt.to_rfc3339())
            .unwrap_or_default()
    }

    /// Read the newest-first event tail (default [`crate::model::EVENT_TAIL_LIMIT`]).
    #[must_use]
    pub fn read_event_tail(&self, limit: usize) -> Vec<Event> {
        self.events().tail(limit).unwrap_or_default()
    }

    /// Build a [`StateView`] from the on-disk snapshots plus the event tail.
    /// The cheap path: assumes `runs/<id>.json` are already merged by the
    /// Python writer. Read-only.
    #[must_use]
    pub fn read_state_view(&self) -> StateView {
        let runs = self.load_snapshots();
        let settlement_counts = SettlementBoard::from_snapshots(&runs);
        self.project_view(runs, settlement_counts)
    }

    /// Build a [`StateView`] by merging the three raw sources in Rust
    /// (`*.meta.json`, `*.lock`, `marbles/**/state.json`) — option (a). Never
    /// writes snapshots; `now` drives health derivation. This is the
    /// frontend-self-sufficient path.
    #[must_use]
    pub fn compute_view(&self, now: DateTime<Utc>) -> StateView {
        // Verdict truth is Python's persisted snapshot projection. Raw meta,
        // lock, runtime, marbles, and lifecycle sources below can disagree on
        // process state, but they must never be used to invent a settlement.
        let retained_snapshots = self.load_snapshots();
        let settlement_counts = SettlementBoard::from_snapshots(&retained_snapshots);
        let mut merged: Vec<RunStatus> = Vec::new();

        for path in self.iter_meta_files() {
            if let Some(meta) = read_json::<AgentMeta>(&path) {
                if let Some(status) = meta.normalize(now) {
                    absorb_status(&mut merged, status);
                }
            }
        }
        for path in self.iter_lock_files() {
            if let Some(status) = normalize_lock(&path, now) {
                absorb_status(&mut merged, status);
            }
        }
        for path in self.iter_marbles_state_files() {
            if let Some(status) =
                read_json::<MarblesState>(&path).and_then(|state| state.normalize(now))
            {
                absorb_status(&mut merged, status);
            }
        }
        // Python sync_state folds the event stream after raw sources. The
        // Mission Control active total must use the same projection; counting
        // every durable runtime_runs/ directory resurrects old workers.
        let mut events = self
            .events()
            .read_all()
            .map(|batch| batch.events)
            .unwrap_or_default();
        for event in &events {
            if event.run_id.trim().is_empty() {
                continue;
            }
            let existing = merged.iter().find(|run| run.run_id == event.run_id);
            let status = normalize_event(event, existing, now);
            absorb_status(&mut merged, status);
        }
        // runtime_runs/: a just-launched run no richer source has surfaced yet.
        // Read-follows-write — keeps the dashboard from a silent gap before the
        // sync merges the run (Niezmiennik 3). Only a recently touched fallback
        // can be live; the durable directory itself is not liveness evidence.
        for run in self.iter_runtime_run_status() {
            if !merged.iter().any(|r| r.run_id == run.run_id)
                && self.runtime_run_is_fresh(&run.run_id, now)
            {
                merged.push(run);
            }
        }
        for run in self.iter_lifecycle_run_status() {
            if !merged.iter().any(|r| r.run_id == run.run_id)
                && (run.is_terminal() || run.health == "active")
            {
                merged.push(run);
            }
        }

        // Persisted terminal snapshots are the completion authority over the
        // runtime_runs/ read-follows-write fallback. Runtime directories
        // intentionally outlive workers, so their mere existence cannot
        // resurrect a finished run. Other richer sources keep their existing
        // merge semantics.
        for snapshot in retained_snapshots
            .iter()
            .filter(|snapshot| snapshot.is_terminal())
        {
            if let Some(idx) = merged.iter().position(|run| {
                run.run_id == snapshot.run_id && run.source.as_str() == "runtime_runs"
            }) {
                merged[idx] = snapshot.clone();
            }
        }

        sort_recent_first(&mut merged);
        if events.len() > crate::model::EVENT_TAIL_LIMIT {
            let start = events.len() - crate::model::EVENT_TAIL_LIMIT;
            events.drain(..start);
        }
        events.reverse();
        Self::project_view_with_events(merged, settlement_counts, events)
    }

    fn project_view(&self, runs: Vec<RunStatus>, settlement_counts: SettlementBoard) -> StateView {
        Self::project_view_with_events(
            runs,
            settlement_counts,
            self.read_event_tail(crate::model::EVENT_TAIL_LIMIT),
        )
    }

    fn project_view_with_events(
        runs: Vec<RunStatus>,
        mut settlement_counts: SettlementBoard,
        events: Vec<Event>,
    ) -> StateView {
        let warnings = warnings_for_runs(&runs);
        let active_runs: Vec<RunStatus> = runs
            .iter()
            .filter(|run| {
                matches!(run.health.as_str(), "active" | "stalled") && !is_final_state(&run.state)
            })
            .cloned()
            .collect();
        settlement_counts.active = active_runs.len();
        let recent_runs = runs.into_iter().take(RECENT_RUN_LIMIT).collect();
        StateView {
            active_runs,
            recent_runs,
            warnings,
            events,
            settlement_counts,
        }
    }

    fn runtime_run_is_fresh(&self, run_id: &str, now: DateTime<Utc>) -> bool {
        let dir = self.runtime_run_dir(run_id);
        [
            dir.clone(),
            dir.join("meta.json"),
            dir.join("transcript.log"),
        ]
        .into_iter()
        .filter_map(|path| modified_at(&path))
        .map(DateTime::<Utc>::from)
        .max()
        .is_some_and(|updated| (now - updated).num_seconds() <= RUN_STALL_SECONDS)
    }

    fn iter_meta_files(&self) -> Vec<PathBuf> {
        rglob(&self.home.join("artifacts"), &|p| {
            p.to_str().is_some_and(|s| s.ends_with(".meta.json"))
        })
    }

    fn iter_lock_files(&self) -> Vec<PathBuf> {
        rglob(&self.home.join("locks"), &|p| {
            p.extension().and_then(|e| e.to_str()) == Some("lock")
        })
    }

    fn iter_marbles_state_files(&self) -> Vec<PathBuf> {
        rglob(&self.home.join("marbles"), &|p| {
            p.file_name().and_then(|n| n.to_str()) == Some("state.json")
        })
    }
}

fn absorb_status(merged: &mut Vec<RunStatus>, incoming: RunStatus) {
    if let Some(idx) = merged.iter().position(|run| run.run_id == incoming.run_id) {
        let existing = merged.remove(idx);
        merged.push(merge_status(Some(existing), incoming));
    } else {
        merged.push(incoming);
    }
}

fn normalize_event(event: &Event, existing: Option<&RunStatus>, now: DateTime<Utc>) -> RunStatus {
    let payload_string = |key: &str| {
        event
            .payload
            .get(key)
            .map(json_scalar_string)
            .unwrap_or_default()
    };
    let existing_string = |value: &str, fallback: &str| {
        if value.is_empty() {
            fallback.to_string()
        } else {
            value.to_string()
        }
    };

    let mut state = payload_string("state");
    if state.is_empty() {
        if let Some(lifecycle_state) = event.kind.strip_prefix("lifecycle:") {
            state = lifecycle_state.to_string();
        } else if event.kind == "launch" {
            state = "created".to_string();
        } else if event.kind == "audit:stop"
            && event
                .payload
                .get("accepted")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false)
        {
            state = "stopped".to_string();
        } else {
            state = existing
                .map(|run| run.state.clone())
                .unwrap_or_else(|| "unknown".to_string());
        }
    }

    let root = existing_string(
        &payload_string("root"),
        existing.map(|run| run.root.as_str()).unwrap_or_default(),
    );
    let agent = existing_string(
        &payload_string("agent"),
        existing.map(|run| run.agent.as_str()).unwrap_or("unknown"),
    );
    let skill = existing_string(
        &payload_string("skill"),
        existing.map(|run| run.skill.as_str()).unwrap_or("unknown"),
    );
    let mode = existing_string(
        &payload_string("mode"),
        existing.map(|run| run.mode.as_str()).unwrap_or("unknown"),
    );
    let updated_at = if event.ts.is_empty() {
        existing
            .map(|run| run.updated_at.clone())
            .unwrap_or_default()
    } else {
        event.ts.clone()
    };
    let started_at = existing_string(
        &payload_string("started_at"),
        existing
            .map(|run| run.started_at.as_str())
            .filter(|value| !value.is_empty())
            .unwrap_or(&updated_at),
    );
    let exit_code = event
        .payload
        .get("exit_code")
        .and_then(coerce_int_value)
        .or_else(|| existing.and_then(|run| run.exit_code));
    let launcher_pid = event
        .payload
        .get("launcher_pid")
        .and_then(coerce_int_value)
        .or_else(|| existing.and_then(|run| run.launcher_pid));
    let payload_error = existing_string(&payload_string("error"), &payload_string("last_error"));
    let last_error = if !payload_error.is_empty() {
        payload_error
    } else if let Some(existing) = existing.filter(|run| !run.last_error.is_empty()) {
        existing.last_error.clone()
    } else if event.kind != "state"
        && matches!(
            state.as_str(),
            "blocked" | "failed" | "ghost" | "stalled" | "timed_out"
        )
    {
        event.message.clone()
    } else {
        String::new()
    };

    RunStatus {
        run_id: event.run_id.trim().to_string(),
        state: state.clone(),
        agent,
        skill,
        mode,
        root: root.clone(),
        operator_session: operator_session_name(&root, event.run_id.trim()),
        latest_report: existing_string(
            &payload_string("report"),
            existing
                .map(|run| run.latest_report.as_str())
                .unwrap_or_default(),
        ),
        latest_transcript: existing_string(
            &payload_string("transcript"),
            existing
                .map(|run| run.latest_transcript.as_str())
                .unwrap_or_default(),
        ),
        last_error,
        updated_at: updated_at.clone(),
        started_at,
        health: state_health(&state, &updated_at, now).as_str().to_string(),
        source: "event-stream".to_string(),
        lock_present: existing.is_some_and(|run| run.lock_present),
        exit_code,
        liveness: existing_string(
            &payload_string("liveness"),
            existing
                .map(|run| run.liveness.as_str())
                .unwrap_or_default(),
        ),
        launcher_pid,
        completed_at: existing_string(
            &payload_string("completed_at"),
            existing
                .map(|run| run.completed_at.as_str())
                .unwrap_or_default(),
        ),
        session_id: existing_string(
            &payload_string("session_id"),
            existing
                .map(|run| run.session_id.as_str())
                .unwrap_or_default(),
        ),
        current_loop: existing.and_then(|run| run.current_loop),
        total_loops: existing.and_then(|run| run.total_loops),
        settlement_verdict: None,
        settlement_tui: None,
        execution_state: None,
        proof_state: None,
        delivery_state: None,
        seal: None,
    }
}

fn json_scalar_string(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => String::new(),
        serde_json::Value::String(value) => value.clone(),
        other => other.to_string(),
    }
}

fn sort_recent_first(runs: &mut [RunStatus]) {
    let epoch = DateTime::<Utc>::from_timestamp(0, 0).expect("epoch is valid");
    runs.sort_by(|a, b| {
        let a_dt = parse_iso(&a.updated_at).unwrap_or(epoch);
        let b_dt = parse_iso(&b.updated_at).unwrap_or(epoch);
        b_dt.cmp(&a_dt)
    });
}

/// Mirrors `control_plane._warnings_for_runs` (capped at 6).
fn warnings_for_runs(runs: &[RunStatus]) -> Vec<String> {
    let mut warnings = Vec::new();
    for run in runs {
        if run.health == "stalled" {
            warnings.push(format!("{} looks stalled ({}).", run.run_id, run.state));
        }
        if run.lock_present
            && run.latest_report.is_empty()
            && !FINAL_STATES.contains(&run.state.as_str())
        {
            warnings.push(format!(
                "{} still has a live lock but no report artifact yet.",
                run.run_id
            ));
        }
    }
    warnings.truncate(6);
    warnings
}

fn read_json<T: serde::de::DeserializeOwned>(path: &Path) -> Option<T> {
    let text = fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn nonempty_runtime_value(primary: &str, fallback: &str) -> String {
    if primary.is_empty() {
        fallback.to_string()
    } else {
        primary.to_string()
    }
}

fn modified_at(path: &Path) -> Option<std::time::SystemTime> {
    fs::metadata(path).and_then(|meta| meta.modified()).ok()
}

fn existing_or_canonical(declared: &str, canonical: PathBuf) -> PathBuf {
    if declared.is_empty() {
        return canonical;
    }
    let declared = PathBuf::from(declared);
    if declared.is_file() {
        declared
    } else {
        canonical
    }
}

fn report_dou_index(path: &Path) -> Option<i64> {
    let text = fs::read_to_string(path).ok()?;
    let mut lines = text.lines();
    if lines.next()?.trim() != "---" {
        return None;
    }
    for line in lines {
        let trimmed = line.trim();
        if trimmed == "---" {
            break;
        }
        let Some((key, value)) = trimmed.split_once(':') else {
            continue;
        };
        if key.trim() == "dou_index" {
            return parse_nonnegative_i64(value.trim());
        }
    }
    None
}

fn parse_nonnegative_i64(raw: &str) -> Option<i64> {
    let value = raw.trim().trim_matches('"').trim_matches('\'');
    coerce_int_value(&serde_json::Value::String(value.to_string())).filter(|item| *item >= 0)
}

/// Recursively collect files under `root` matching `pred`. Empty when `root`
/// is absent. A small std-only stand-in for `Path.rglob`.
fn rglob(root: &Path, pred: &dyn Fn(&Path) -> bool) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            match entry.file_type() {
                Ok(ft) if ft.is_dir() => stack.push(path),
                Ok(ft) if ft.is_file() && pred(&path) => out.push(path),
                _ => {}
            }
        }
    }
    out
}

/// Normalise a `*.lock` key=value file. Mirrors `control_plane._normalize_lock`.
fn normalize_lock(path: &Path, now: DateTime<Utc>) -> Option<RunStatus> {
    let text = fs::read_to_string(path).ok()?;
    let mut kv = std::collections::BTreeMap::new();
    for line in text.lines() {
        if let Some((key, value)) = line.split_once('=') {
            kv.insert(key.trim().to_string(), value.trim().to_string());
        }
    }
    let get = |k: &str| kv.get(k).cloned().unwrap_or_default();
    let run_id = get("run_id");
    let run_id = run_id.trim();
    if run_id.is_empty() {
        return None;
    }
    let root = get("root");
    let state = {
        let s = get("status");
        if s.is_empty() {
            "running".to_string()
        } else {
            s
        }
    };
    let started_at = get("started");
    let mode = {
        let m = get("mode");
        if m.is_empty() { get("runtime") } else { m }
    };
    let mode = if mode.is_empty() {
        "unknown".to_string()
    } else {
        mode
    };
    let agent = {
        let a = get("agent");
        if a.is_empty() {
            "unknown".to_string()
        } else {
            a
        }
    };
    Some(RunStatus {
        run_id: run_id.to_string(),
        state: state.clone(),
        agent,
        skill: skill_from_code(&get("skill")),
        mode,
        root: root.clone(),
        operator_session: operator_session_name(&root, run_id),
        latest_report: String::new(),
        latest_transcript: String::new(),
        last_error: String::new(),
        updated_at: started_at.clone(),
        started_at: started_at.clone(),
        health: state_health(&state, &started_at, now).as_str().to_string(),
        source: "lock".to_string(),
        lock_present: true,
        exit_code: None,
        liveness: "lock_present".to_string(),
        launcher_pid: None,
        completed_at: String::new(),
        session_id: String::new(),
        current_loop: None,
        total_loops: None,
        settlement_verdict: None,
        settlement_tui: None,
        execution_state: None,
        proof_state: None,
        delivery_state: None,
        seal: None,
    })
}

/// Raw `marbles/**/state.json`. Only the fields used by
/// `control_plane._normalize_marbles_state` are modelled.
#[derive(Debug, Clone, serde::Deserialize)]
struct MarblesState {
    #[serde(default)]
    run_id: String,
    #[serde(default)]
    agent: String,
    #[serde(default)]
    mode: String,
    #[serde(default)]
    root: String,
    #[serde(default)]
    status: String,
    #[serde(default)]
    updated_at: String,
    #[serde(default)]
    started_at: String,
    #[serde(default)]
    failure_hint: String,
    #[serde(default)]
    current_loop: Option<i64>,
    #[serde(default)]
    total_loops: Option<i64>,
    #[serde(default)]
    loops: Vec<MarblesLoop>,
}

#[derive(Debug, Clone, serde::Deserialize)]
struct MarblesLoop {
    #[serde(default)]
    report: String,
    #[serde(default)]
    transcript: String,
    #[serde(default)]
    reason: String,
}

impl MarblesState {
    fn normalize(&self, now: DateTime<Utc>) -> Option<RunStatus> {
        let run_id = self.run_id.trim();
        if run_id.is_empty() {
            return None;
        }
        let latest = self.loops.last();
        let updated_at = if self.updated_at.is_empty() {
            self.started_at.clone()
        } else {
            self.updated_at.clone()
        };
        let state = if self.status.is_empty() {
            "unknown".to_string()
        } else {
            self.status.clone()
        };
        let mode = if self.mode.is_empty() {
            "steered".to_string()
        } else {
            self.mode.clone()
        };
        let agent = if self.agent.is_empty() {
            "unknown".to_string()
        } else {
            self.agent.clone()
        };
        let last_error = if !self.failure_hint.is_empty() {
            self.failure_hint.clone()
        } else {
            latest.map(|l| l.reason.clone()).unwrap_or_default()
        };
        let health = if is_final_state(&state) {
            Health::Final
        } else {
            state_health(&state, &updated_at, now)
        };
        let _ = RUN_STALL_SECONDS; // documented threshold lives in state_health
        Some(RunStatus {
            run_id: run_id.to_string(),
            state,
            agent,
            skill: "marbles".to_string(),
            mode,
            root: self.root.clone(),
            operator_session: operator_session_name(&self.root, run_id),
            latest_report: latest.map(|l| l.report.clone()).unwrap_or_default(),
            latest_transcript: latest.map(|l| l.transcript.clone()).unwrap_or_default(),
            last_error,
            updated_at,
            started_at: self.started_at.clone(),
            health: health.as_str().to_string(),
            source: "marbles-state".to_string(),
            lock_present: false,
            exit_code: None,
            liveness: String::new(),
            launcher_pid: None,
            completed_at: String::new(),
            session_id: String::new(),
            current_loop: self.current_loop,
            total_loops: self.total_loops,
            settlement_verdict: None,
            settlement_tui: None,
            execution_state: None,
            proof_state: None,
            delivery_state: None,
            seal: None,
        })
    }
}

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
    AgentMeta, Event, FINAL_STATES, Health, RunStatus, RECENT_RUN_LIMIT, RUN_STALL_SECONDS,
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
}

impl ControlPlane {
    /// Handle rooted at the given Vibecrafted home (the dir that *contains*
    /// `control_plane/`).
    #[must_use]
    pub fn new(home: impl Into<PathBuf>) -> Self {
        Self { home: home.into() }
    }

    /// Handle rooted at [`vibecrafted_home`] (env-aware default).
    #[must_use]
    pub fn from_env() -> Self {
        Self::new(vibecrafted_home())
    }

    /// `<home>/control_plane`.
    #[must_use]
    pub fn control_plane_home(&self) -> PathBuf {
        self.home.join("control_plane")
    }

    /// `<home>/control_plane/runs`.
    #[must_use]
    pub fn run_snapshot_dir(&self) -> PathBuf {
        self.control_plane_home().join("runs")
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
                    runs.push(run);
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
                return Some(run);
            }
        }
        self.load_snapshots()
            .into_iter()
            .find(|run| run.run_id == target)
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
        self.project_view(runs)
    }

    /// Build a [`StateView`] by merging the three raw sources in Rust
    /// (`*.meta.json`, `*.lock`, `marbles/**/state.json`) — option (a). Never
    /// writes snapshots; `now` drives health derivation. This is the
    /// frontend-self-sufficient path.
    #[must_use]
    pub fn compute_view(&self, now: DateTime<Utc>) -> StateView {
        let mut merged: Vec<RunStatus> = Vec::new();

        let mut absorb = |incoming: RunStatus| {
            if let Some(idx) = merged.iter().position(|r| r.run_id == incoming.run_id) {
                let existing = merged.remove(idx);
                merged.push(merge_status(Some(existing), incoming));
            } else {
                merged.push(incoming);
            }
        };

        for path in self.iter_meta_files() {
            if let Some(meta) = read_json::<AgentMeta>(&path) {
                if let Some(status) = meta.normalize(now) {
                    absorb(status);
                }
            }
        }
        for path in self.iter_lock_files() {
            if let Some(status) = normalize_lock(&path, now) {
                absorb(status);
            }
        }
        for path in self.iter_marbles_state_files() {
            if let Some(status) = read_json::<MarblesState>(&path)
                .and_then(|state| state.normalize(now))
            {
                absorb(status);
            }
        }

        sort_recent_first(&mut merged);
        self.project_view(merged)
    }

    fn project_view(&self, runs: Vec<RunStatus>) -> StateView {
        let warnings = warnings_for_runs(&runs);
        let active_runs = runs
            .iter()
            .filter(|run| {
                matches!(run.health.as_str(), "active" | "stalled")
                    && !is_final_state(&run.state)
            })
            .cloned()
            .collect();
        let recent_runs = runs.into_iter().take(RECENT_RUN_LIMIT).collect();
        StateView {
            active_runs,
            recent_runs,
            warnings,
            events: self.read_event_tail(crate::model::EVENT_TAIL_LIMIT),
        }
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
        if s.is_empty() { "running".to_string() } else { s }
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
        if a.is_empty() { "unknown".to_string() } else { a }
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
        })
    }
}

use chrono::{DateTime, TimeZone, Utc};
use serde::Deserialize;
use serde_json::Value;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ControlPlaneState {
    pub root: PathBuf,
    pub runs: Vec<RunSnapshot>,
    pub events: Vec<RunEvent>,
    pub archived_run_ids: HashSet<String>,
}

impl ControlPlaneState {
    pub fn load(root: impl AsRef<Path>) -> io::Result<Self> {
        let requested_root = root.as_ref().to_path_buf();
        let Some(root) = SafeControlPlaneRoot::new(root.as_ref())? else {
            return Ok(Self::empty(requested_root));
        };
        let archived_run_ids = root.load_archived_run_ids()?;
        let runs = root
            .load_runs()?
            .into_iter()
            .filter(|snapshot| !archived_run_ids.contains(&snapshot.run_id))
            .collect();
        let events = root.load_events()?;
        Ok(Self {
            root: root.as_path().to_path_buf(),
            runs,
            events,
            archived_run_ids,
        })
    }

    pub fn empty(root: impl AsRef<Path>) -> Self {
        Self {
            root: root.as_ref().to_path_buf(),
            runs: Vec::new(),
            events: Vec::new(),
            archived_run_ids: HashSet::new(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunKind {
    Active,
    Recent,
    Completed,
    Failed,
    Stalled,
    Paused,
    Unknown,
}

impl RunKind {
    pub fn label(self) -> &'static str {
        match self {
            RunKind::Active => "active",
            RunKind::Recent => "recent",
            RunKind::Completed => "completed",
            RunKind::Failed => "failed",
            RunKind::Stalled => "stalled",
            RunKind::Paused => "paused",
            RunKind::Unknown => "unknown",
        }
    }

    pub fn sort_rank(self) -> u8 {
        match self {
            RunKind::Active => 0,
            RunKind::Stalled => 1,
            RunKind::Failed => 2,
            RunKind::Paused => 3,
            RunKind::Recent => 4,
            RunKind::Completed => 5,
            RunKind::Unknown => 6,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct RunSnapshot {
    #[serde(alias = "runId")]
    pub run_id: String,
    #[serde(default, alias = "session_id")]
    pub session_id: Option<String>,
    #[serde(default)]
    pub agent: Option<String>,
    #[serde(default)]
    pub skill: Option<String>,
    #[serde(default)]
    pub mode: Option<String>,
    #[serde(default)]
    pub state: Option<String>,
    #[serde(default, alias = "status")]
    pub status: Option<String>,
    #[serde(default, alias = "startedAt")]
    pub started_at: Option<String>,
    #[serde(default, alias = "updatedAt")]
    pub updated_at: Option<String>,
    #[serde(default, alias = "lastHeartbeat")]
    pub last_heartbeat: Option<String>,
    #[serde(default)]
    pub root: Option<String>,
    #[serde(default, alias = "operatorSession")]
    pub operator_session: Option<String>,
    #[serde(default, alias = "latestReport")]
    pub latest_report: Option<String>,
    #[serde(default, alias = "latestTranscript")]
    pub latest_transcript: Option<String>,
    #[serde(default, alias = "lastError")]
    pub last_error: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

impl RunSnapshot {
    pub fn display_state(&self) -> String {
        self.state
            .as_deref()
            .or(self.status.as_deref())
            .unwrap_or("unknown")
            .to_string()
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct RunEvent {
    #[serde(alias = "timestamp")]
    pub ts: String,
    #[serde(alias = "runId")]
    pub run_id: Option<String>,
    pub kind: String,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub payload: Option<Value>,
}

#[derive(Debug, Clone)]
pub struct RenderedRun {
    pub snapshot: RunSnapshot,
    pub kind: RunKind,
    pub age_label: String,
    pub recent_events: Vec<RunEvent>,
}

pub fn render_runs(state: &ControlPlaneState) -> Vec<RenderedRun> {
    let now = Utc::now();
    let mut runs: Vec<RenderedRun> = state
        .runs
        .iter()
        .cloned()
        .map(|snapshot| {
            let kind = classify_run(&snapshot, now);
            let recent_events = recent_events_for(&state.events, &snapshot.run_id);
            let age_label = age_label(&snapshot, now);
            RenderedRun {
                snapshot,
                kind,
                age_label,
                recent_events,
            }
        })
        .collect();

    runs.sort_by(compare_runs);
    runs
}

pub fn classify_run(snapshot: &RunSnapshot, now: DateTime<Utc>) -> RunKind {
    let state = snapshot.display_state().to_lowercase();
    let heartbeat = snapshot
        .last_heartbeat
        .as_deref()
        .and_then(parse_timestamp)
        .or_else(|| snapshot.updated_at.as_deref().and_then(parse_timestamp));

    if snapshot.last_error.is_some() || state.contains("fail") || state.contains("error") {
        return RunKind::Failed;
    }
    if state.contains("stalled") {
        return RunKind::Stalled;
    }
    if state.contains("pause") {
        return RunKind::Paused;
    }
    if state.contains("done")
        || state.contains("complete")
        || state.contains("succeed")
        || state.contains("converged")
        || state.contains("stopped")
        || state.contains("gc")
    {
        return if is_recent(heartbeat, now) {
            RunKind::Recent
        } else {
            RunKind::Completed
        };
    }
    if is_active_like(&state) {
        if is_stale(heartbeat, now) {
            return RunKind::Stalled;
        }
        return RunKind::Active;
    }
    if is_recent(heartbeat, now) {
        return RunKind::Recent;
    }
    RunKind::Unknown
}

fn compare_runs(left: &RenderedRun, right: &RenderedRun) -> Ordering {
    left.kind
        .sort_rank()
        .cmp(&right.kind.sort_rank())
        .then_with(|| compare_timestamp(&right.snapshot.updated_at, &left.snapshot.updated_at))
        .then_with(|| compare_timestamp(&right.snapshot.started_at, &left.snapshot.started_at))
        .then_with(|| {
            compare_timestamp(
                &right.snapshot.last_heartbeat,
                &left.snapshot.last_heartbeat,
            )
        })
        .then_with(|| left.snapshot.run_id.cmp(&right.snapshot.run_id))
}

fn compare_timestamp(left: &Option<String>, right: &Option<String>) -> Ordering {
    let left = left.as_deref().and_then(parse_timestamp);
    let right = right.as_deref().and_then(parse_timestamp);
    match (left, right) {
        (Some(left), Some(right)) => right.cmp(&left),
        (Some(_), None) => Ordering::Less,
        (None, Some(_)) => Ordering::Greater,
        (None, None) => Ordering::Equal,
    }
}

fn recent_events_for(events: &[RunEvent], run_id: &str) -> Vec<RunEvent> {
    let mut recent: Vec<RunEvent> = events
        .iter()
        .filter(|event| event.run_id.as_deref() == Some(run_id))
        .cloned()
        .collect();
    recent.sort_by(|left, right| right.ts.cmp(&left.ts));
    recent.truncate(8);
    recent
}

fn age_label(snapshot: &RunSnapshot, now: DateTime<Utc>) -> String {
    let timestamp = snapshot
        .last_heartbeat
        .as_deref()
        .and_then(parse_timestamp)
        .or_else(|| snapshot.updated_at.as_deref().and_then(parse_timestamp))
        .or_else(|| snapshot.started_at.as_deref().and_then(parse_timestamp));
    timestamp
        .map(|ts| relative_age(ts, now))
        .unwrap_or_else(|| "age unknown".to_string())
}

#[derive(Debug, Clone)]
struct SafeControlPlaneRoot {
    path: PathBuf,
}

impl SafeControlPlaneRoot {
    fn new(root: &Path) -> io::Result<Option<Self>> {
        if !root.exists() {
            return Ok(None);
        }
        let canonical = fs::canonicalize(root)?;
        if canonical.is_dir() {
            Ok(Some(Self { path: canonical }))
        } else {
            Ok(None)
        }
    }

    fn as_path(&self) -> &Path {
        &self.path
    }

    fn runs_dir(&self) -> PathBuf {
        self.path.join("runs")
    }

    fn event_stream_path(&self) -> PathBuf {
        self.path.join("events.jsonl")
    }

    fn archived_dir(&self) -> PathBuf {
        self.runs_dir().join(".archived")
    }

    fn run_snapshot_files(&self) -> io::Result<Vec<PathBuf>> {
        let runs_dir = self.runs_dir();
        let mut files = Vec::new();
        if !runs_dir.exists() {
            return Ok(files);
        }
        for entry in fs::read_dir(runs_dir)? {
            let entry = entry?;
            let path = entry.path();
            if !is_json_file(&path) {
                continue;
            }
            let Some(path) = self.safe_file(&path)? else {
                continue;
            };
            files.push(path);
        }
        Ok(files)
    }

    fn load_runs(&self) -> io::Result<Vec<RunSnapshot>> {
        let mut snapshots = HashMap::<String, RunSnapshot>::new();
        for path in self.run_snapshot_files()? {
            let Ok(text) = fs::read_to_string(&path) else {
                continue;
            };
            let parsed: Result<RunSnapshot, _> = serde_json::from_str(&text);
            if let Ok(snapshot) = parsed {
                snapshots.insert(snapshot.run_id.clone(), snapshot);
            }
        }
        Ok(snapshots.into_values().collect())
    }

    fn archived_marker_files(&self) -> io::Result<Vec<PathBuf>> {
        let archived_dir = self.archived_dir();
        let mut files = Vec::new();
        if !archived_dir.exists() {
            return Ok(files);
        }
        for entry in fs::read_dir(archived_dir)? {
            let entry = entry?;
            let path = entry.path();
            if !is_json_file(&path) {
                continue;
            }
            let Some(path) = self.safe_file(&path)? else {
                continue;
            };
            files.push(path);
        }
        Ok(files)
    }

    fn load_archived_run_ids(&self) -> io::Result<HashSet<String>> {
        let mut archived = HashSet::new();
        for path in self.archived_marker_files()? {
            if let Some(id) = archived_id_from_marker(&path) {
                archived.insert(id);
            }
        }
        Ok(archived)
    }

    fn load_events(&self) -> io::Result<Vec<RunEvent>> {
        let path = self.event_stream_path();
        let Some(path) = self.safe_file(&path)? else {
            return Ok(Vec::new());
        };
        let Ok(text) = fs::read_to_string(&path) else {
            return Ok(Vec::new());
        };
        let mut events = Vec::new();
        for line in text.lines().filter(|line| !line.trim().is_empty()) {
            if let Ok(event) = serde_json::from_str::<RunEvent>(line) {
                events.push(event);
            }
        }
        Ok(events)
    }

    fn safe_file(&self, path: &Path) -> io::Result<Option<PathBuf>> {
        let meta = match fs::symlink_metadata(path) {
            Ok(meta) => meta,
            Err(_) => return Ok(None),
        };
        if meta.file_type().is_symlink() {
            return Ok(None);
        }
        let Some(parent) = path.parent() else {
            return Ok(None);
        };
        if fs::symlink_metadata(parent)?.file_type().is_symlink() {
            return Ok(None);
        }
        let canonical = fs::canonicalize(path)?;
        if canonical.starts_with(&self.path) {
            Ok(Some(canonical))
        } else {
            Ok(None)
        }
    }
}

fn is_json_file(path: &Path) -> bool {
    path.extension().and_then(|ext| ext.to_str()) == Some("json")
}

fn archived_id_from_marker(path: &Path) -> Option<String> {
    let text = fs::read_to_string(path).ok()?;
    if let Ok(value) = serde_json::from_str::<Value>(&text)
        && let Some(run_id) = value.get("run_id").and_then(Value::as_str)
    {
        return Some(run_id.to_string());
    }
    path.file_stem()
        .and_then(|stem| stem.to_str())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn parse_timestamp(raw: &str) -> Option<DateTime<Utc>> {
    if let Ok(parsed) = DateTime::parse_from_rfc3339(raw) {
        return Some(parsed.with_timezone(&Utc));
    }
    if let Ok(seconds) = raw.parse::<i64>() {
        return Utc.timestamp_opt(seconds, 0).single();
    }
    None
}

fn relative_age(timestamp: DateTime<Utc>, now: DateTime<Utc>) -> String {
    let delta = now.signed_duration_since(timestamp);
    let minutes = delta.num_minutes().max(0);
    let hours = delta.num_hours().max(0);
    if hours >= 24 {
        let days = delta.num_days().max(0);
        return format!("{days}d ago");
    }
    if hours > 0 {
        return format!("{hours}h ago");
    }
    format!("{minutes}m ago")
}

fn is_recent(timestamp: Option<DateTime<Utc>>, now: DateTime<Utc>) -> bool {
    timestamp
        .map(|value| now.signed_duration_since(value).num_hours() < 24)
        .unwrap_or(false)
}

fn is_stale(timestamp: Option<DateTime<Utc>>, now: DateTime<Utc>) -> bool {
    timestamp
        .map(|value| now.signed_duration_since(value).num_minutes() > 15)
        .unwrap_or(false)
}

fn is_active_like(state: &str) -> bool {
    state.contains("active")
        || state.contains("run")
        || state.contains("watch")
        || state.contains("queued")
        || state.contains("pending")
        || state.contains("in-progress")
        || state.contains("progress")
        || state.contains("loop")
}

use chrono::{DateTime, Duration as ChronoDuration, NaiveDate, Utc};
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};

use crate::polarize::{PolarizeBand, PolarizeIntent};
use crate::state::{ControlPlaneState, RunKind, classify_run};

/// Maximum number of `*.meta.json` files we will fold per refresh. Large
/// artifact roots can hold tens of thousands of files; the dashboard
/// refresh cadence (~250ms tick) must not stall the operator on disk IO.
/// Treat the cap as a load-shed marker rather than a hard truth — the
/// `data_quality.scanned_meta_files == capped` signal warns the operator.
const META_SCAN_CAP: usize = 5_000;

/// Aggregation window for per-agent and per-skill statistics. Wider
/// windows dilute the per-agent attribution signal; narrower windows make
/// quiet skills look dead. 30d matches PLAN_23 §4 panel labels.
const STATS_WINDOW_DAYS: i64 = 30;

/// Failure board lookback. 24h matches the PLAN_23 §4 mock-up; older
/// failures should be reasoned about from the wider per-agent panel.
const FAILURE_WINDOW_HOURS: i64 = 24;

/// Active-dispatch ETA is computed from heartbeat-vs-start. Anything older
/// than this is considered stalled in the dashboard and contributes an
/// `ActionQueue` entry instead of an `ActiveDispatch` entry.
const STALL_AFTER_MINUTES: i64 = 15;

#[derive(Debug, Clone, Default, PartialEq)]
pub struct MissionControlState {
    pub generated_at: String,
    pub active_dispatches: Vec<ActiveDispatch>,
    pub wave_atlas: Vec<WaveSegment>,
    pub agent_stats: Vec<AgentStatsRow>,
    pub skill_stats: Vec<SkillStatsRow>,
    pub fleet_health: Vec<FleetHealthSignal>,
    pub failures: Vec<FailureEntry>,
    pub action_queue: Vec<ActionQueueItem>,
    pub data_quality: DataQuality,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActiveDispatch {
    pub run_id: String,
    pub agent: String,
    pub skill: String,
    pub wave: Option<String>,
    pub started_at: Option<String>,
    pub age_label: String,
    pub eta_label: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WaveSegment {
    pub wave_id: String,
    pub total: usize,
    pub completed: usize,
    pub failed: usize,
    pub active: usize,
    pub latest_state: WaveState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WaveState {
    Pending,
    InProgress,
    Completed,
    Failed,
}

impl WaveState {
    pub fn glyph(self) -> &'static str {
        match self {
            WaveState::Pending => "·",
            WaveState::InProgress => "⏳",
            WaveState::Completed => "✓",
            WaveState::Failed => "!",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            WaveState::Pending => "pending",
            WaveState::InProgress => "in-progress",
            WaveState::Completed => "completed",
            WaveState::Failed => "failed",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct AgentStatsRow {
    pub agent: String,
    pub total_runs: usize,
    pub completed: usize,
    pub failed: usize,
    pub success_rate: f32,
    pub avg_duration_s: Option<f64>,
    pub model_known_rate: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SkillStatsRow {
    pub skill: String,
    pub invocations: usize,
    pub completed: usize,
    pub failed: usize,
    pub avg_duration_s: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FleetHealthSignal {
    pub label: String,
    pub status: FleetHealthStatus,
    pub detail: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FleetHealthStatus {
    Ok,
    Warn,
    Blocked,
    Unknown,
}

impl FleetHealthStatus {
    pub fn marker(self) -> &'static str {
        match self {
            FleetHealthStatus::Ok => "✓",
            FleetHealthStatus::Warn => "!",
            FleetHealthStatus::Blocked => "✗",
            FleetHealthStatus::Unknown => "?",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FailureEntry {
    pub run_id: String,
    pub agent: String,
    pub skill: String,
    pub reason: String,
    pub age_label: String,
    pub source_path: Option<PathBuf>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActionQueueItem {
    pub kind: ActionQueueKind,
    pub summary: String,
    pub source_path: Option<PathBuf>,
    pub priority: ActionPriority,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionQueueKind {
    StalledRun,
    Failure,
    Polarize,
    ReportReady,
}

impl ActionQueueKind {
    pub fn label(self) -> &'static str {
        match self {
            ActionQueueKind::StalledRun => "stalled",
            ActionQueueKind::Failure => "failure",
            ActionQueueKind::Polarize => "polarize",
            ActionQueueKind::ReportReady => "report",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ActionPriority {
    Critical,
    High,
    Normal,
}

impl ActionPriority {
    pub fn marker(self) -> &'static str {
        match self {
            ActionPriority::Critical => "!!",
            ActionPriority::High => "!",
            ActionPriority::Normal => "-",
        }
    }
}

/// Explicit data-quality markers. We refuse to silently coerce missing
/// upstream fields into fake successes; the dashboard displays these
/// counters so the operator knows which panels are partially blind.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct DataQuality {
    pub scanned_meta_files: usize,
    pub capped: bool,
    pub missing_model: usize,
    pub missing_duration: usize,
    pub parse_failures: usize,
    pub artifact_root: Option<PathBuf>,
    pub artifact_root_present: bool,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct MetaJson {
    #[serde(default)]
    run_id: Option<String>,
    #[serde(default)]
    agent: Option<String>,
    #[serde(default)]
    skill_code: Option<String>,
    #[serde(default)]
    mode: Option<String>,
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    exit_code: Option<i64>,
    #[serde(default)]
    model: Option<String>,
    #[serde(default)]
    duration_s: Option<f64>,
    #[serde(default)]
    completed_at: Option<String>,
    #[serde(default)]
    updated_at: Option<String>,
    #[serde(default)]
    report: Option<String>,
    #[serde(default)]
    prompt_id: Option<String>,
}

impl MissionControlState {
    /// Build the mission-control view from real local sources. Caller
    /// owns the `ControlPlaneState` snapshot for live runs and supplies
    /// the artifact root where `*.meta.json` history lives.
    pub fn build(state: &ControlPlaneState, artifact_root: &Path) -> Self {
        Self::build_with_intents(state, artifact_root, &[])
    }

    /// Build mission-control state while enriching the action queue with
    /// current `vc-polarize` intents discovered by the app refresh flow.
    pub fn build_with_intents(
        state: &ControlPlaneState,
        artifact_root: &Path,
        intents: &[PolarizeIntent],
    ) -> Self {
        let now = Utc::now();
        Self::build_at_with_intents(state, artifact_root, intents, now)
    }

    /// Deterministic build entrypoint that takes the "now" timestamp
    /// explicitly. Tests use this to keep time-based classifications
    /// stable across CI machines.
    pub fn build_at(state: &ControlPlaneState, artifact_root: &Path, now: DateTime<Utc>) -> Self {
        Self::build_at_with_intents(state, artifact_root, &[], now)
    }

    pub fn build_at_with_intents(
        state: &ControlPlaneState,
        artifact_root: &Path,
        intents: &[PolarizeIntent],
        now: DateTime<Utc>,
    ) -> Self {
        let (meta_records, mut data_quality) = collect_meta_records(artifact_root, now);
        data_quality.artifact_root = Some(artifact_root.to_path_buf());
        data_quality.artifact_root_present = artifact_root.exists();

        let active_dispatches = active_dispatches_from_state(state, now);
        let wave_atlas = wave_atlas_from_meta(&meta_records, state, now);
        let agent_stats = agent_stats_from_meta(&meta_records, now);
        let skill_stats = skill_stats_from_meta(&meta_records, now);
        let failures = failure_board_from_meta(&meta_records, state, now);
        let fleet_health = fleet_health_from_inputs(state, artifact_root, &data_quality);
        let action_queue = action_queue_from_inputs(state, &failures, &meta_records, intents, now);

        Self {
            generated_at: now.to_rfc3339(),
            active_dispatches,
            wave_atlas,
            agent_stats,
            skill_stats,
            fleet_health,
            failures,
            action_queue,
            data_quality,
        }
    }

    /// Convenience: total entries surfaced across all panels. Used by
    /// the tab badge.
    pub fn total_entries(&self) -> usize {
        self.active_dispatches.len()
            + self.wave_atlas.len()
            + self.agent_stats.len()
            + self.skill_stats.len()
            + self.fleet_health.len()
            + self.failures.len()
            + self.action_queue.len()
    }

    pub fn is_empty(&self) -> bool {
        self.total_entries() == 0
    }
}

#[derive(Debug, Clone)]
struct MetaRecord {
    meta: MetaJson,
    path: PathBuf,
    completed_at: DateTime<Utc>,
}

fn collect_meta_records(
    artifact_root: &Path,
    now: DateTime<Utc>,
) -> (Vec<MetaRecord>, DataQuality) {
    let mut quality = DataQuality::default();
    let mut records = Vec::new();
    if !artifact_root.exists() {
        return (records, quality);
    }
    let window_floor = now - ChronoDuration::days(STATS_WINDOW_DAYS);
    let mut files = Vec::new();
    walk_meta_files(artifact_root, &mut files, &window_floor.date_naive());

    for path in files.into_iter().take(META_SCAN_CAP) {
        let text = match fs::read_to_string(&path) {
            Ok(text) => text,
            Err(_) => {
                quality.parse_failures += 1;
                continue;
            }
        };
        let parsed: MetaJson = match serde_json::from_str(&text) {
            Ok(value) => value,
            Err(_) => {
                quality.parse_failures += 1;
                continue;
            }
        };
        quality.scanned_meta_files += 1;
        if parsed
            .model
            .as_deref()
            .map(str::trim)
            .unwrap_or("")
            .is_empty()
            || parsed.model.as_deref() == Some("unknown")
        {
            quality.missing_model += 1;
        }
        if parsed.duration_s.is_none() {
            quality.missing_duration += 1;
        }
        let completed_at = parsed
            .completed_at
            .as_deref()
            .and_then(parse_rfc3339)
            .or_else(|| parsed.updated_at.as_deref().and_then(parse_rfc3339))
            .unwrap_or(window_floor);
        if completed_at < window_floor {
            continue;
        }
        records.push(MetaRecord {
            meta: parsed,
            path,
            completed_at,
        });
    }
    // If the directory walk produced more than the cap before the take
    // applied above, mark the data-quality flag so the operator sees
    // load-shed truth instead of a "5000 runs" claim.
    if quality.scanned_meta_files >= META_SCAN_CAP {
        quality.capped = true;
    }
    (records, quality)
}

fn walk_meta_files(dir: &Path, out: &mut Vec<PathBuf>, window_floor: &NaiveDate) {
    if out.len() >= META_SCAN_CAP {
        return;
    }
    let entries = match fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        if out.len() >= META_SCAN_CAP {
            return;
        }
        let path = entry.path();
        let Ok(metadata) = entry.file_type() else {
            continue;
        };
        // Refuse to follow symlinks; matches the existing
        // `safe_artifact_path` posture in `app.rs`.
        if metadata.is_symlink() {
            continue;
        }
        if metadata.is_dir() {
            if !directory_within_window(&path, window_floor) {
                continue;
            }
            walk_meta_files(&path, out, window_floor);
        } else if metadata.is_file()
            && path
                .file_name()
                .and_then(|name| name.to_str())
                .map(|name| name.ends_with(".meta.json"))
                .unwrap_or(false)
        {
            out.push(path);
        }
    }
}

fn directory_within_window(path: &Path, window_floor: &NaiveDate) -> bool {
    let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
        return true;
    };
    if name.len() == 8
        && name.bytes().all(|b| b.is_ascii_digit())
        && let Ok(date) = NaiveDate::parse_from_str(name, "%Y%m%d")
    {
        return date >= *window_floor;
    }
    if name.len() == 9 && name.as_bytes().get(4) == Some(&b'_') {
        let trimmed = name.replace('_', "");
        if let Ok(date) = NaiveDate::parse_from_str(&trimmed, "%Y%m%d") {
            return date >= *window_floor;
        }
    }
    // Anything that does not look like a YYYYMMDD/YYYY_MMDD bucket is
    // walked unconditionally — it might be an org/project node that
    // hosts the dated buckets below it.
    true
}

fn active_dispatches_from_state(
    state: &ControlPlaneState,
    now: DateTime<Utc>,
) -> Vec<ActiveDispatch> {
    let mut out = Vec::new();
    for snapshot in &state.runs {
        let kind = classify_run(snapshot, now);
        if !matches!(kind, RunKind::Active) {
            continue;
        }
        let started_at = snapshot.started_at.clone();
        let started = started_at.as_deref().and_then(parse_rfc3339);
        let age_label = match started {
            Some(start) => relative_age(start, now),
            None => "age unknown".to_string(),
        };
        let eta_label = compute_eta_label(snapshot.last_heartbeat.as_deref(), now);
        let wave = snapshot
            .extra
            .get("wave")
            .and_then(|value| value.as_str())
            .map(ToOwned::to_owned);
        out.push(ActiveDispatch {
            run_id: snapshot.run_id.clone(),
            agent: snapshot
                .agent
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
            skill: snapshot
                .skill
                .clone()
                .or_else(|| snapshot.mode.clone())
                .unwrap_or_else(|| "unknown".to_string()),
            wave,
            started_at,
            age_label,
            eta_label,
        });
    }
    out.sort_by(|left, right| left.age_label.cmp(&right.age_label));
    out
}

fn compute_eta_label(last_heartbeat: Option<&str>, now: DateTime<Utc>) -> String {
    let Some(heartbeat) = last_heartbeat.and_then(parse_rfc3339) else {
        return "no heartbeat".to_string();
    };
    let lag = now.signed_duration_since(heartbeat);
    let lag_minutes = lag.num_minutes();
    if lag_minutes >= STALL_AFTER_MINUTES {
        format!("stalled {}m", lag_minutes)
    } else if lag_minutes <= 0 {
        "fresh".to_string()
    } else {
        format!("{}m since heartbeat", lag_minutes)
    }
}

fn wave_atlas_from_meta(
    records: &[MetaRecord],
    state: &ControlPlaneState,
    now: DateTime<Utc>,
) -> Vec<WaveSegment> {
    let mut groups: BTreeMap<String, WaveAccumulator> = BTreeMap::new();
    for record in records {
        let Some(wave_id) = derive_wave_id(&record.meta) else {
            continue;
        };
        let entry = groups.entry(wave_id).or_default();
        entry.total += 1;
        match record.meta.exit_code {
            Some(0) => entry.completed += 1,
            Some(code) if code != 0 => entry.failed += 1,
            _ => {}
        }
        match record.meta.status.as_deref().map(str::to_ascii_lowercase) {
            Some(ref status) if status.contains("fail") || status.contains("error") => {
                entry.failed += 1;
            }
            Some(ref status) if status.contains("complete") || status.contains("done") => {
                entry.completed += 1;
            }
            _ => {}
        }
    }
    // Live runs contribute to the wave atlas too — an in-progress wave
    // should show its active dispatches even when no meta.json has been
    // written yet.
    for snapshot in &state.runs {
        let Some(prompt_id) = snapshot
            .extra
            .get("prompt_id")
            .and_then(|value| value.as_str())
            .map(ToOwned::to_owned)
        else {
            continue;
        };
        if !matches!(
            classify_run(snapshot, now),
            RunKind::Active | RunKind::Stalled
        ) {
            continue;
        }
        let entry = groups.entry(prompt_id).or_default();
        entry.active += 1;
        entry.total += 1;
    }

    let mut segments: Vec<WaveSegment> = groups
        .into_iter()
        .map(|(wave_id, acc)| WaveSegment {
            wave_id,
            total: acc.total,
            completed: acc.completed,
            failed: acc.failed,
            active: acc.active,
            latest_state: acc.classify(),
        })
        .collect();
    segments.sort_by(|left, right| {
        right
            .total
            .cmp(&left.total)
            .then(left.wave_id.cmp(&right.wave_id))
    });
    segments.truncate(8);
    segments
}

#[derive(Debug, Default)]
struct WaveAccumulator {
    total: usize,
    completed: usize,
    failed: usize,
    active: usize,
}

impl WaveAccumulator {
    fn classify(&self) -> WaveState {
        if self.active > 0 {
            WaveState::InProgress
        } else if self.failed > 0 && self.completed == 0 {
            WaveState::Failed
        } else if self.completed == self.total && self.total > 0 {
            WaveState::Completed
        } else if self.completed > 0 && self.completed < self.total {
            WaveState::InProgress
        } else {
            WaveState::Pending
        }
    }
}

fn derive_wave_id(meta: &MetaJson) -> Option<String> {
    if let Some(prompt) = meta.prompt_id.as_deref() {
        return Some(prompt.to_string());
    }
    if let (Some(skill), Some(run_id)) = (meta.skill_code.as_deref(), meta.run_id.as_deref()) {
        let prefix = run_id.split('-').next().unwrap_or(run_id);
        return Some(format!("{skill}/{prefix}"));
    }
    meta.skill_code.clone()
}

fn agent_stats_from_meta(records: &[MetaRecord], _now: DateTime<Utc>) -> Vec<AgentStatsRow> {
    let mut buckets: HashMap<String, AgentBucket> = HashMap::new();
    for record in records {
        let agent = record
            .meta
            .agent
            .clone()
            .unwrap_or_else(|| "unknown".to_string());
        let bucket = buckets.entry(agent).or_default();
        bucket.total += 1;
        match record.meta.exit_code {
            Some(0) => bucket.completed += 1,
            Some(code) if code != 0 => bucket.failed += 1,
            _ => {}
        }
        if let Some(duration) = record.meta.duration_s {
            bucket.duration_sum_s += duration;
            bucket.duration_count += 1;
        }
        if let Some(model) = record.meta.model.as_deref()
            && !model.is_empty()
            && model != "unknown"
        {
            bucket.model_known += 1;
        }
    }
    let mut rows: Vec<AgentStatsRow> = buckets
        .into_iter()
        .map(|(agent, bucket)| {
            let success_rate = if bucket.total == 0 {
                0.0
            } else {
                bucket.completed as f32 / bucket.total as f32
            };
            let model_known_rate = if bucket.total == 0 {
                0.0
            } else {
                bucket.model_known as f32 / bucket.total as f32
            };
            let avg_duration_s = if bucket.duration_count == 0 {
                None
            } else {
                Some(bucket.duration_sum_s / bucket.duration_count as f64)
            };
            AgentStatsRow {
                agent,
                total_runs: bucket.total,
                completed: bucket.completed,
                failed: bucket.failed,
                success_rate,
                avg_duration_s,
                model_known_rate,
            }
        })
        .collect();
    rows.sort_by(|left, right| {
        right
            .total_runs
            .cmp(&left.total_runs)
            .then(left.agent.cmp(&right.agent))
    });
    rows
}

#[derive(Debug, Default)]
struct AgentBucket {
    total: usize,
    completed: usize,
    failed: usize,
    duration_sum_s: f64,
    duration_count: usize,
    model_known: usize,
}

fn skill_stats_from_meta(records: &[MetaRecord], _now: DateTime<Utc>) -> Vec<SkillStatsRow> {
    let mut buckets: HashMap<String, SkillBucket> = HashMap::new();
    for record in records {
        let skill = record
            .meta
            .skill_code
            .clone()
            .or_else(|| record.meta.mode.clone())
            .unwrap_or_else(|| "unknown".to_string());
        let bucket = buckets.entry(skill).or_default();
        bucket.invocations += 1;
        match record.meta.exit_code {
            Some(0) => bucket.completed += 1,
            Some(code) if code != 0 => bucket.failed += 1,
            _ => {}
        }
        if let Some(duration) = record.meta.duration_s {
            bucket.duration_sum_s += duration;
            bucket.duration_count += 1;
        }
    }
    let mut rows: Vec<SkillStatsRow> = buckets
        .into_iter()
        .map(|(skill, bucket)| SkillStatsRow {
            skill,
            invocations: bucket.invocations,
            completed: bucket.completed,
            failed: bucket.failed,
            avg_duration_s: if bucket.duration_count == 0 {
                None
            } else {
                Some(bucket.duration_sum_s / bucket.duration_count as f64)
            },
        })
        .collect();
    rows.sort_by(|left, right| {
        right
            .invocations
            .cmp(&left.invocations)
            .then(left.skill.cmp(&right.skill))
    });
    rows
}

#[derive(Debug, Default)]
struct SkillBucket {
    invocations: usize,
    completed: usize,
    failed: usize,
    duration_sum_s: f64,
    duration_count: usize,
}

fn failure_board_from_meta(
    records: &[MetaRecord],
    state: &ControlPlaneState,
    now: DateTime<Utc>,
) -> Vec<FailureEntry> {
    let cutoff = now - ChronoDuration::hours(FAILURE_WINDOW_HOURS);
    let mut failures: Vec<FailureEntry> = Vec::new();

    for record in records {
        let is_failure = match record.meta.exit_code {
            Some(code) if code != 0 => true,
            Some(_) => false,
            None => record
                .meta
                .status
                .as_deref()
                .map(|status| {
                    let status = status.to_ascii_lowercase();
                    status.contains("fail") || status.contains("error")
                })
                .unwrap_or(false),
        };
        if !is_failure {
            continue;
        }
        if record.completed_at < cutoff {
            continue;
        }
        failures.push(FailureEntry {
            run_id: record
                .meta
                .run_id
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
            agent: record
                .meta
                .agent
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
            skill: record
                .meta
                .skill_code
                .clone()
                .or_else(|| record.meta.mode.clone())
                .unwrap_or_else(|| "unknown".to_string()),
            reason: record
                .meta
                .status
                .clone()
                .unwrap_or_else(|| match record.meta.exit_code {
                    Some(code) => format!("exit_code {code}"),
                    None => "failed".to_string(),
                }),
            age_label: relative_age(record.completed_at, now),
            source_path: Some(record.path.clone()),
        });
    }

    for snapshot in &state.runs {
        if !matches!(classify_run(snapshot, now), RunKind::Failed) {
            continue;
        }
        failures.push(FailureEntry {
            run_id: snapshot.run_id.clone(),
            agent: snapshot
                .agent
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
            skill: snapshot
                .skill
                .clone()
                .or_else(|| snapshot.mode.clone())
                .unwrap_or_else(|| "unknown".to_string()),
            reason: snapshot
                .last_error
                .clone()
                .or_else(|| snapshot.status.clone())
                .or_else(|| snapshot.state.clone())
                .unwrap_or_else(|| "failed".to_string()),
            age_label: snapshot
                .updated_at
                .as_deref()
                .and_then(parse_rfc3339)
                .map(|ts| relative_age(ts, now))
                .unwrap_or_else(|| "age unknown".to_string()),
            source_path: snapshot
                .latest_report
                .as_deref()
                .map(PathBuf::from)
                .or_else(|| snapshot.root.as_deref().map(PathBuf::from)),
        });
    }

    failures.sort_by(|left, right| left.age_label.cmp(&right.age_label));
    failures.truncate(20);
    failures
}

fn fleet_health_from_inputs(
    state: &ControlPlaneState,
    artifact_root: &Path,
    data_quality: &DataQuality,
) -> Vec<FleetHealthSignal> {
    let mut signals = Vec::new();

    let control_plane_status = if state.root.exists() {
        FleetHealthStatus::Ok
    } else {
        FleetHealthStatus::Blocked
    };
    signals.push(FleetHealthSignal {
        label: "control-plane".to_string(),
        status: control_plane_status,
        detail: format!(
            "{} ({} runs)",
            state.root.to_string_lossy(),
            state.runs.len()
        ),
    });

    let artifact_status = if data_quality.artifact_root_present {
        FleetHealthStatus::Ok
    } else {
        FleetHealthStatus::Warn
    };
    signals.push(FleetHealthSignal {
        label: "artifact-root".to_string(),
        status: artifact_status,
        detail: artifact_root.to_string_lossy().into_owned(),
    });

    let scan_status = if data_quality.capped {
        FleetHealthStatus::Warn
    } else if data_quality.scanned_meta_files == 0 {
        FleetHealthStatus::Unknown
    } else {
        FleetHealthStatus::Ok
    };
    let scan_detail = if data_quality.capped {
        format!("{} scanned (capped)", data_quality.scanned_meta_files)
    } else {
        format!("{} meta.json scanned", data_quality.scanned_meta_files)
    };
    signals.push(FleetHealthSignal {
        label: "meta scan".to_string(),
        status: scan_status,
        detail: scan_detail,
    });

    let model_status = if data_quality.scanned_meta_files == 0 {
        FleetHealthStatus::Unknown
    } else if data_quality.missing_model == 0 {
        FleetHealthStatus::Ok
    } else if data_quality.missing_model * 4 > data_quality.scanned_meta_files {
        FleetHealthStatus::Warn
    } else {
        FleetHealthStatus::Ok
    };
    signals.push(FleetHealthSignal {
        label: "model parity".to_string(),
        status: model_status,
        detail: format!(
            "{}/{} missing model",
            data_quality.missing_model,
            data_quality.scanned_meta_files.max(1)
        ),
    });

    let duration_status = if data_quality.scanned_meta_files == 0 {
        FleetHealthStatus::Unknown
    } else if data_quality.missing_duration == 0 {
        FleetHealthStatus::Ok
    } else if data_quality.missing_duration * 4 > data_quality.scanned_meta_files {
        FleetHealthStatus::Warn
    } else {
        FleetHealthStatus::Ok
    };
    signals.push(FleetHealthSignal {
        label: "duration parity".to_string(),
        status: duration_status,
        detail: format!(
            "{}/{} missing duration_s",
            data_quality.missing_duration,
            data_quality.scanned_meta_files.max(1)
        ),
    });

    signals
}

fn action_queue_from_inputs(
    state: &ControlPlaneState,
    failures: &[FailureEntry],
    records: &[MetaRecord],
    intents: &[PolarizeIntent],
    now: DateTime<Utc>,
) -> Vec<ActionQueueItem> {
    let mut items = Vec::new();

    for snapshot in &state.runs {
        let kind = classify_run(snapshot, now);
        if matches!(kind, RunKind::Stalled) {
            items.push(ActionQueueItem {
                kind: ActionQueueKind::StalledRun,
                summary: format!(
                    "resume {} ({})",
                    snapshot.run_id,
                    snapshot.agent.as_deref().unwrap_or("unknown")
                ),
                source_path: snapshot
                    .latest_report
                    .as_deref()
                    .map(PathBuf::from)
                    .or_else(|| snapshot.root.as_deref().map(PathBuf::from)),
                priority: ActionPriority::High,
            });
        }
    }

    for failure in failures {
        items.push(ActionQueueItem {
            kind: ActionQueueKind::Failure,
            summary: format!(
                "investigate {} ({} / {})",
                failure.run_id, failure.agent, failure.skill
            ),
            source_path: failure.source_path.clone(),
            priority: ActionPriority::Critical,
        });
    }

    for intent in intents {
        items.push(ActionQueueItem {
            kind: ActionQueueKind::Polarize,
            summary: format!(
                "polarize {} ({} / score {})",
                intent.run_id,
                intent.band.label(),
                intent.score
            ),
            source_path: Some(intent.prism_path.clone()),
            priority: action_priority_from_polarize_band(intent.band),
        });
    }

    // Surface freshly completed reports that haven't been touched yet —
    // operators want to know which artifacts are ready to read without
    // grepping the artifact tree. We cap to keep the queue actionable.
    let mut recent_reports = records
        .iter()
        .filter(|record| matches!(record.meta.exit_code, Some(0)))
        .filter(|record| record.meta.report.is_some())
        .filter(|record| now.signed_duration_since(record.completed_at).num_hours() < 12)
        .collect::<Vec<_>>();
    recent_reports.sort_by_key(|record| std::cmp::Reverse(record.completed_at));
    for record in recent_reports.into_iter().take(5) {
        items.push(ActionQueueItem {
            kind: ActionQueueKind::ReportReady,
            summary: format!(
                "open report {} ({})",
                record.meta.run_id.as_deref().unwrap_or("unknown"),
                record.meta.agent.as_deref().unwrap_or("unknown")
            ),
            source_path: record.meta.report.clone().map(PathBuf::from),
            priority: ActionPriority::Normal,
        });
    }

    items.sort_by_key(|item| item.priority);
    items.truncate(12);
    items
}

fn action_priority_from_polarize_band(band: PolarizeBand) -> ActionPriority {
    match band {
        PolarizeBand::Abort | PolarizeBand::Doctrine => ActionPriority::Critical,
        PolarizeBand::Pass => ActionPriority::High,
        PolarizeBand::Memo => ActionPriority::Normal,
    }
}

fn parse_rfc3339(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|ts| ts.with_timezone(&Utc))
}

fn relative_age(ts: DateTime<Utc>, now: DateTime<Utc>) -> String {
    let delta = now.signed_duration_since(ts);
    let minutes = delta.num_minutes();
    if minutes < 1 {
        return "just now".to_string();
    }
    if minutes < 60 {
        return format!("{minutes}m ago");
    }
    let hours = delta.num_hours();
    if hours < 24 {
        return format!("{hours}h ago");
    }
    let days = delta.num_days();
    format!("{days}d ago")
}

/// Default location for canonical artifact metadata. Resolves the
/// operator's `VIBECRAFTED_HOME` (or `~/.vibecrafted`) and points at the
/// `artifacts/` subtree where every dispatched skill writes its
/// `*.meta.json`.
pub fn default_artifact_root() -> PathBuf {
    crate::config::default_vibecrafted_home().join("artifacts")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{ControlPlaneState, RunEvent, RunSnapshot};
    use std::collections::HashMap;
    use tempfile::tempdir;

    fn ts(value: &str) -> DateTime<Utc> {
        DateTime::parse_from_rfc3339(value)
            .unwrap()
            .with_timezone(&Utc)
    }

    fn empty_state(root: &Path) -> ControlPlaneState {
        ControlPlaneState {
            root: root.to_path_buf(),
            runs: Vec::new(),
            events: Vec::new(),
            archived_run_ids: Default::default(),
        }
    }

    fn write_meta(path: &Path, contents: &str) {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(path, contents).unwrap();
    }

    #[test]
    fn missing_artifact_root_reports_typed_empty_state() {
        let now = ts("2026-05-20T00:00:00Z");
        let dir = tempdir().unwrap();
        let state = empty_state(dir.path());
        let mission = MissionControlState::build_at(&state, &dir.path().join("missing"), now);
        assert!(
            mission.is_empty()
                || mission
                    .fleet_health
                    .iter()
                    .any(|s| s.label == "artifact-root")
        );
        let artifact_signal = mission
            .fleet_health
            .iter()
            .find(|signal| signal.label == "artifact-root")
            .expect("artifact-root signal");
        assert_eq!(artifact_signal.status, FleetHealthStatus::Warn);
        assert_eq!(mission.data_quality.scanned_meta_files, 0);
    }

    #[test]
    fn aggregates_per_agent_and_skill_from_meta_json() {
        let dir = tempdir().unwrap();
        let artifact = dir.path().join("artifacts");
        let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
        write_meta(
            &bucket.join("run-a.meta.json"),
            r#"{
                "run_id": "run-a",
                "agent": "claude",
                "skill_code": "owne",
                "exit_code": 0,
                "model": "claude-opus-4-7",
                "duration_s": 120.5,
                "completed_at": "2026-05-19T10:00:00Z",
                "prompt_id": "wave-1",
                "report": "/tmp/report-a.md"
            }"#,
        );
        write_meta(
            &bucket.join("run-b.meta.json"),
            r#"{
                "run_id": "run-b",
                "agent": "claude",
                "skill_code": "owne",
                "exit_code": 1,
                "model": "unknown",
                "duration_s": null,
                "completed_at": "2026-05-19T11:00:00Z",
                "prompt_id": "wave-1"
            }"#,
        );
        write_meta(
            &bucket.join("run-c.meta.json"),
            r#"{
                "run_id": "run-c",
                "agent": "codex",
                "skill_code": "marb",
                "exit_code": 0,
                "model": "gpt-5-codex",
                "duration_s": 60.0,
                "completed_at": "2026-05-19T12:00:00Z",
                "prompt_id": "wave-2"
            }"#,
        );

        let now = ts("2026-05-19T13:00:00Z");
        let state = empty_state(dir.path());
        let mission = MissionControlState::build_at(&state, &artifact, now);

        assert_eq!(mission.data_quality.scanned_meta_files, 3);
        assert_eq!(mission.data_quality.missing_model, 1);
        assert_eq!(mission.data_quality.missing_duration, 1);

        let claude = mission
            .agent_stats
            .iter()
            .find(|row| row.agent == "claude")
            .expect("claude row present");
        assert_eq!(claude.total_runs, 2);
        assert_eq!(claude.completed, 1);
        assert_eq!(claude.failed, 1);
        assert!((claude.success_rate - 0.5).abs() < 1e-3);
        assert!(claude.avg_duration_s.is_some());
        assert!((claude.model_known_rate - 0.5).abs() < 1e-3);

        let codex = mission
            .agent_stats
            .iter()
            .find(|row| row.agent == "codex")
            .expect("codex row present");
        assert_eq!(codex.total_runs, 1);
        assert!((codex.success_rate - 1.0).abs() < 1e-3);

        let owne = mission
            .skill_stats
            .iter()
            .find(|row| row.skill == "owne")
            .expect("owne skill row present");
        assert_eq!(owne.invocations, 2);
        assert_eq!(owne.failed, 1);

        // Wave atlas should surface the prompt_id groups.
        let wave1 = mission
            .wave_atlas
            .iter()
            .find(|seg| seg.wave_id == "wave-1")
            .expect("wave-1 segment");
        assert_eq!(wave1.total, 2);
        assert_eq!(wave1.completed, 1);
        assert_eq!(wave1.failed, 1);
    }

    #[test]
    fn failure_board_buckets_within_24h_window() {
        let dir = tempdir().unwrap();
        let artifact = dir.path().join("artifacts");
        let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
        write_meta(
            &bucket.join("recent-fail.meta.json"),
            r#"{
                "run_id": "recent-fail",
                "agent": "gemini",
                "skill_code": "rev",
                "exit_code": 2,
                "status": "failed",
                "completed_at": "2026-05-19T12:30:00Z"
            }"#,
        );
        write_meta(
            &bucket.join("old-fail.meta.json"),
            r#"{
                "run_id": "old-fail",
                "agent": "gemini",
                "skill_code": "rev",
                "exit_code": 1,
                "status": "failed",
                "completed_at": "2026-05-15T08:00:00Z"
            }"#,
        );

        let now = ts("2026-05-19T13:00:00Z");
        let state = empty_state(dir.path());
        let mission = MissionControlState::build_at(&state, &artifact, now);
        assert_eq!(mission.failures.len(), 1);
        assert_eq!(mission.failures[0].run_id, "recent-fail");
    }

    #[test]
    fn active_dispatches_split_stalled_into_action_queue() {
        let now = ts("2026-05-19T13:00:00Z");
        let active = RunSnapshot {
            run_id: "live".to_string(),
            session_id: None,
            agent: Some("claude".to_string()),
            skill: Some("workflow".to_string()),
            mode: None,
            state: Some("active".to_string()),
            status: None,
            started_at: Some("2026-05-19T12:50:00Z".to_string()),
            updated_at: Some("2026-05-19T12:59:00Z".to_string()),
            last_heartbeat: Some("2026-05-19T12:59:30Z".to_string()),
            root: None,
            operator_session: None,
            latest_report: None,
            latest_transcript: None,
            last_error: None,
            extra: HashMap::new(),
        };
        let stalled = RunSnapshot {
            run_id: "lost".to_string(),
            session_id: None,
            agent: Some("codex".to_string()),
            skill: Some("workflow".to_string()),
            mode: None,
            state: Some("active".to_string()),
            status: None,
            started_at: Some("2026-05-19T10:00:00Z".to_string()),
            updated_at: Some("2026-05-19T10:30:00Z".to_string()),
            last_heartbeat: Some("2026-05-19T10:30:00Z".to_string()),
            root: Some("/tmp/lost".to_string()),
            operator_session: None,
            latest_report: None,
            latest_transcript: None,
            last_error: None,
            extra: HashMap::new(),
        };
        let state = ControlPlaneState {
            root: PathBuf::from("/tmp/state"),
            runs: vec![active, stalled],
            events: Vec::<RunEvent>::new(),
            archived_run_ids: Default::default(),
        };
        let dir = tempdir().unwrap();
        let mission =
            MissionControlState::build_at(&state, &dir.path().join("missing-artifacts"), now);
        assert_eq!(mission.active_dispatches.len(), 1);
        assert_eq!(mission.active_dispatches[0].run_id, "live");
        assert!(
            mission
                .action_queue
                .iter()
                .any(|item| item.kind == ActionQueueKind::StalledRun
                    && item.summary.contains("lost"))
        );
    }

    #[test]
    fn meta_scan_cap_marks_data_quality_capped() {
        // Real bounds (5000 files) would be slow in CI; we synthesize a
        // mini run that proves the field is wired into DataQuality.
        let dir = tempdir().unwrap();
        let artifact = dir.path().join("artifacts");
        let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
        for idx in 0..3 {
            write_meta(
                &bucket.join(format!("run-{idx}.meta.json")),
                &format!(
                    r#"{{
                        "run_id": "run-{idx}",
                        "agent": "claude",
                        "skill_code": "owne",
                        "exit_code": 0,
                        "completed_at": "2026-05-19T10:00:00Z"
                    }}"#
                ),
            );
        }
        let state = empty_state(dir.path());
        let mission = MissionControlState::build_at(&state, &artifact, ts("2026-05-19T13:00:00Z"));
        assert_eq!(mission.data_quality.scanned_meta_files, 3);
        assert!(!mission.data_quality.capped);
        assert!(mission.data_quality.artifact_root_present);
    }
}

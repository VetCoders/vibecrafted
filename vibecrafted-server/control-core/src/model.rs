//! Typed model of the Vibecrafted control plane.
//!
//! This is a field-for-field Rust mirror of the canonical Python writer
//! `vibecrafted-core/vibecrafted_core/control_plane.py`. The Python side is the
//! source of truth that *writes* `~/.vibecrafted/control_plane/`; this crate
//! only ever *reads* it. Where the Python derivation logic matters (state
//! classes, `health`, skill-code mapping, the three merge sources), it is
//! ported here so a Rust frontend never has to re-shell into Python.
//!
//! Drift policy: the on-disk JSON is runtime truth. When Python type hints and
//! the JSON disagree, fidelity tracks the JSON. Known divergences are recorded
//! in `docs/superpowers/specs/2026-05-31-control-core-design.md` and exercised
//! by `tests/schema_fidelity.rs`.

use std::collections::BTreeMap;
use std::path::Path;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Stall threshold in seconds. Mirrors `control_plane.RUN_STALL_SECONDS`
/// (`20 * 60`). A non-final run whose `updated_at` is older than this is
/// `Health::Stalled`.
pub const RUN_STALL_SECONDS: i64 = 1200;

/// Default number of events returned by an event tail. Mirrors
/// `control_plane.EVENT_TAIL_LIMIT`.
pub const EVENT_TAIL_LIMIT: usize = 16;

/// Number of most-recent runs surfaced in a state view. Mirrors
/// `control_plane.RECENT_RUN_LIMIT`.
pub const RECENT_RUN_LIMIT: usize = 12;

/// States that count as "in flight". Mirrors `control_plane.ACTIVE_STATES`.
pub const ACTIVE_STATES: [&str; 7] = [
    "initialized",
    "launching",
    "promise",
    "confirmed",
    "running",
    "paused",
    "stalled",
];

/// Terminal states. Mirrors `control_plane.FINAL_STATES`.
pub const FINAL_STATES: [&str; 7] = [
    "completed",
    "converged",
    "stopped",
    "failed",
    "timed_out",
    "gc",
    "ghost",
];

/// Skill-code → skill-name map. Mirrors `control_plane.SKILL_CODE_MAP`
/// exactly (18 entries). Unknown codes such as `owne` deliberately fall
/// through to the code itself, matching the Python default.
pub const SKILL_CODE_MAP: [(&str, &str); 18] = [
    ("agnt", "agents"),
    ("deco", "decorate"),
    ("delg", "delegate"),
    ("vdou", "dou"),
    ("fwup", "followup"),
    ("hydr", "hydrate"),
    ("impl", "implement"),
    ("init", "init"),
    ("just", "justdo"),
    ("marb", "marbles"),
    ("prtn", "partner"),
    ("plan", "plan"),
    ("prun", "prune"),
    ("rels", "release"),
    ("rsch", "research"),
    ("rvew", "review"),
    ("scaf", "scaffold"),
    ("wflw", "workflow"),
];

/// Returns `true` when `state` is one of [`ACTIVE_STATES`].
#[must_use]
pub fn is_active_state(state: &str) -> bool {
    ACTIVE_STATES.contains(&state)
}

/// Returns `true` when `state` is one of [`FINAL_STATES`].
#[must_use]
pub fn is_final_state(state: &str) -> bool {
    FINAL_STATES.contains(&state)
}

/// Coarse classification of a run state.
///
/// The on-disk `state` field is a free-form string (forward-compatible with
/// states this build does not know), so this is a *derived* view rather than a
/// lossy enum sitting in [`RunStatus`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StateClass {
    /// One of [`ACTIVE_STATES`].
    Active,
    /// One of [`FINAL_STATES`].
    Final,
    /// A state string this build does not recognise.
    Unknown,
}

/// Classify a raw state string into [`StateClass`].
#[must_use]
pub fn classify_state(state: &str) -> StateClass {
    if is_final_state(state) {
        StateClass::Final
    } else if is_active_state(state) {
        StateClass::Active
    } else {
        StateClass::Unknown
    }
}

/// Derived health of a run. Mirrors the string values written by
/// `control_plane._state_health` (`"final" | "unknown" | "stalled" | "active"`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Health {
    /// Run is in a terminal state.
    Final,
    /// No parseable `updated_at`, so liveness is unknown.
    Unknown,
    /// Non-final but older than [`RUN_STALL_SECONDS`].
    Stalled,
    /// Non-final and recently updated.
    Active,
}

impl Health {
    /// The lowercase string form, matching the Python on-disk value.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Health::Final => "final",
            Health::Unknown => "unknown",
            Health::Stalled => "stalled",
            Health::Active => "active",
        }
    }
}

/// Parse an ISO-8601 / RFC-3339 timestamp the way `control_plane._parse_iso`
/// does. Returns `None` for empty or unparseable input. A trailing `Z` is
/// accepted (chrono handles it natively, matching the Python `Z` → `+00:00`
/// rewrite).
#[must_use]
pub fn parse_iso(raw: &str) -> Option<DateTime<Utc>> {
    if raw.is_empty() {
        return None;
    }
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}

/// Coerce a JSON value to an `i64` the way `control_plane._coerce_int` does:
/// booleans are rejected, numbers pass through, digit-strings (optionally
/// sign-prefixed) parse, everything else is `None`.
#[must_use]
pub fn coerce_int_value(value: &serde_json::Value) -> Option<i64> {
    match value {
        serde_json::Value::Bool(_) => None,
        serde_json::Value::Number(n) => n.as_i64(),
        serde_json::Value::String(s) => {
            let trimmed = s.trim();
            let body = trimmed.strip_prefix('-').unwrap_or(trimmed);
            if !trimmed.is_empty() && !body.is_empty() && body.bytes().all(|b| b.is_ascii_digit()) {
                trimmed.parse::<i64>().ok()
            } else {
                None
            }
        }
        _ => None,
    }
}

/// Health derivation. Mirrors `control_plane._state_health`, but takes `now`
/// explicitly so callers (and tests) control the clock.
#[must_use]
pub fn state_health(state: &str, updated_at: &str, now: DateTime<Utc>) -> Health {
    if is_final_state(state) {
        return Health::Final;
    }
    match parse_iso(updated_at) {
        None => Health::Unknown,
        Some(updated) => {
            if (now - updated).num_seconds() > RUN_STALL_SECONDS {
                Health::Stalled
            } else {
                Health::Active
            }
        }
    }
}

/// Map a skill code to its long name. Mirrors `control_plane._skill_from_code`:
/// known code → mapped name; unknown non-empty code → the code itself; empty →
/// `"unknown"`.
#[must_use]
pub fn skill_from_code(skill_code: &str) -> String {
    for (code, name) in SKILL_CODE_MAP {
        if code == skill_code {
            return name.to_string();
        }
    }
    if skill_code.is_empty() {
        "unknown".to_string()
    } else {
        skill_code.to_string()
    }
}

fn session_base_name(root: &str) -> String {
    let source = if root.is_empty() { "vibecrafted" } else { root };
    let base = Path::new(source)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("vibecrafted")
        .to_lowercase();
    let cleaned: String = base
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { '-' })
        .collect();
    let trimmed = cleaned.trim_matches('-');
    if trimmed.is_empty() {
        "vibecrafted".to_string()
    } else {
        trimmed.to_string()
    }
}

/// Derive the operator tmux/session name for a run. Mirrors
/// `control_plane.operator_session_name`.
#[must_use]
pub fn operator_session_name(root: &str, run_id: &str) -> String {
    let base = session_base_name(root);
    if run_id.is_empty() {
        base
    } else {
        format!("{base}-{run_id}")
    }
}

fn nonempty_or(value: &str, fallback: &str) -> String {
    if value.is_empty() {
        fallback.to_string()
    } else {
        value.to_string()
    }
}

/// A control-plane run projection. Field-for-field mirror of the
/// `control_plane.RunStatus` dataclass; this is exactly what each
/// `runs/<id>.json` snapshot serialises to.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RunStatus {
    pub run_id: String,
    pub state: String,
    pub agent: String,
    pub skill: String,
    pub mode: String,
    pub root: String,
    pub operator_session: String,
    pub latest_report: String,
    pub latest_transcript: String,
    pub last_error: String,
    pub updated_at: String,
    pub started_at: String,
    pub health: String,
    pub source: String,
    pub lock_present: bool,
    #[serde(default)]
    pub exit_code: Option<i64>,
    #[serde(default)]
    pub liveness: String,
    #[serde(default)]
    pub launcher_pid: Option<i64>,
    #[serde(default)]
    pub completed_at: String,
    #[serde(default)]
    pub session_id: String,
    #[serde(default)]
    pub current_loop: Option<i64>,
    #[serde(default)]
    pub total_loops: Option<i64>,
}

impl RunStatus {
    /// `true` when this run is terminal. Mirrors `control_plane._run_is_terminal`:
    /// a final state, a `terminal` liveness, or any present `exit_code`.
    #[must_use]
    pub fn is_terminal(&self) -> bool {
        is_final_state(&self.state) || self.liveness == "terminal" || self.exit_code.is_some()
    }

    /// Classify this run's `state`.
    #[must_use]
    pub fn state_class(&self) -> StateClass {
        classify_state(&self.state)
    }
}

/// Nested lifecycle run state written by `lifecycle_runner.py`.
///
/// This intentionally sits beside [`RunStatus`]: lifecycle state is stageful and
/// nested, while `RunStatus` is the legacy flat dashboard/API projection.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LifecycleRun {
    #[serde(default)]
    pub schema: Option<String>,
    #[serde(default)]
    pub run_id: String,
    #[serde(default)]
    pub workflow: String,
    #[serde(default)]
    pub agent: String,
    #[serde(default)]
    pub root: String,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub await_stages: bool,
    #[serde(default)]
    pub parent_run_id: Option<String>,
    #[serde(default)]
    pub operator_actions: Vec<LifecycleOperatorAction>,
    #[serde(default)]
    pub spec: serde_json::Value,
    #[serde(default)]
    pub supervisor: String,
    #[serde(default)]
    pub human_controls: Vec<String>,
    #[serde(default)]
    pub state_path: String,
    #[serde(default)]
    pub report_path: String,
    #[serde(default)]
    pub transcript_path: String,
    #[serde(default)]
    pub context_atlas: serde_json::Value,
    #[serde(default)]
    pub manifest: serde_json::Value,
    #[serde(default)]
    pub baton: LifecycleBaton,
    #[serde(default)]
    pub stages: Vec<LifecycleStage>,
    #[serde(default)]
    pub next_stage: String,
    #[serde(default)]
    pub error: String,
    #[serde(default, deserialize_with = "de_optional_lifecycle_dou_index")]
    pub dou_index: Option<LifecycleDouIndex>,
    #[serde(default, deserialize_with = "de_nonnegative_int")]
    pub accepted_dou: Option<i64>,
    #[serde(default)]
    pub accepted_dou_findings: Vec<serde_json::Value>,
}

impl LifecycleRun {
    /// Build the compact read-model used by `/api/control/lifecycle` and the
    /// dashboard. `updated_at` is normally the `state.json` mtime because the
    /// lifecycle state file does not carry a canonical timestamp.
    #[must_use]
    pub fn summary(
        &self,
        updated_at: String,
        report_dou_index: Option<i64>,
    ) -> LifecycleRunSummary {
        let state_dou = self.dou_index.as_ref().and_then(|dou| dou.value);
        let stage_dou = self.stages.last().and_then(|stage| stage.dou_index);
        let dou_index = state_dou
            .or(report_dou_index)
            .or(self.baton.dou_index)
            .or(stage_dou);
        let accepted_dou = self
            .accepted_dou
            .unwrap_or(self.accepted_dou_findings.len() as i64);
        let dou_readiness = match dou_index {
            Some(0) => "zero",
            Some(_) => "open",
            None => "unknown",
        }
        .to_string();

        LifecycleRunSummary {
            schema: self.schema.clone(),
            run_id: self.run_id.clone(),
            workflow: self.workflow.clone(),
            status: nonempty_or(&self.status, "unknown"),
            agent: nonempty_or(&self.agent, "unknown"),
            root: self.root.clone(),
            current_stage: self.current_stage(),
            next_stage: nonempty_or(&self.baton.next_stage, &self.next_stage),
            next_agent: self.baton.next_agent.clone(),
            exit_code: self.stages.last().and_then(|stage| stage.await_exit_code()),
            dou_index,
            baton_dou_index: self.baton.dou_index,
            accepted_dou,
            dou_readiness,
            human_controls: self.human_controls.clone(),
            human_controls_count: self.human_controls.len(),
            operator_actions_count: self.operator_actions.len(),
            state_path: self.state_path.clone(),
            report_path: self.report_path.clone(),
            transcript_path: self.transcript_path.clone(),
            updated_at,
            source: "lifecycle_runs".to_string(),
        }
    }

    /// Lossy projection into the existing flat [`RunStatus`] surface.
    #[must_use]
    pub fn to_run_status(&self, updated_at: String, report_dou_index: Option<i64>) -> RunStatus {
        let summary = self.summary(updated_at.clone(), report_dou_index);
        let state = summary.status.clone();
        let health = state_health(&state, &updated_at, Utc::now());
        let final_health = if is_final_state(&state) || summary.exit_code.is_some() {
            Health::Final
        } else {
            health
        };

        RunStatus {
            run_id: summary.run_id,
            state,
            agent: summary.agent,
            skill: nonempty_or(&summary.workflow, "lifecycle"),
            mode: "lifecycle".to_string(),
            root: summary.root.clone(),
            operator_session: operator_session_name(&summary.root, &self.run_id),
            latest_report: summary.report_path,
            latest_transcript: summary.transcript_path,
            last_error: self.error.clone(),
            updated_at: summary.updated_at.clone(),
            started_at: summary.updated_at,
            health: final_health.as_str().to_string(),
            source: summary.source,
            lock_present: false,
            exit_code: summary.exit_code,
            liveness: if final_health == Health::Final {
                "terminal".to_string()
            } else {
                String::new()
            },
            launcher_pid: None,
            completed_at: String::new(),
            session_id: String::new(),
            current_loop: None,
            total_loops: None,
        }
    }

    fn current_stage(&self) -> String {
        self.stages
            .last()
            .map(|stage| stage.id.clone())
            .filter(|id| !id.is_empty())
            .unwrap_or_else(|| self.baton.from_stage.clone())
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LifecycleBaton {
    #[serde(default)]
    pub from_stage: String,
    #[serde(default)]
    pub from_phase: String,
    #[serde(default)]
    pub next_stage: String,
    #[serde(default)]
    pub next_agent: String,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub previous_reports: Vec<String>,
    #[serde(default, deserialize_with = "de_nonnegative_int")]
    pub dou_index: Option<i64>,
    #[serde(default)]
    pub audit_after: String,
    #[serde(default)]
    pub fallback_stage: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LifecycleStage {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub workflow: String,
    #[serde(default)]
    pub phase: String,
    #[serde(default)]
    pub agent: String,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub launch: serde_json::Value,
    #[serde(default, rename = "await")]
    pub await_result: serde_json::Value,
    #[serde(default)]
    pub commit_before: String,
    #[serde(default)]
    pub commit_after: String,
    #[serde(default)]
    pub changed_files: Vec<String>,
    #[serde(default)]
    pub new_commits: Vec<String>,
    #[serde(default)]
    pub transition: Option<LifecycleTransition>,
    #[serde(default, deserialize_with = "de_nonnegative_int")]
    pub dou_index: Option<i64>,
}

impl LifecycleStage {
    fn await_exit_code(&self) -> Option<i64> {
        self.await_result
            .get("exit_code")
            .and_then(coerce_int_value)
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LifecycleTransition {
    #[serde(default)]
    pub next_stage: String,
    #[serde(default)]
    pub requested_next_stage: String,
    #[serde(default)]
    pub next_agent: String,
    #[serde(default)]
    pub requested_next_agent: String,
    #[serde(default)]
    pub conditions: Vec<String>,
    #[serde(default)]
    pub fallback_stage: String,
    #[serde(default)]
    pub audit_after: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LifecycleOperatorAction {
    #[serde(default)]
    pub action: String,
    #[serde(default)]
    pub at: String,
    #[serde(default)]
    pub details: serde_json::Value,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LifecycleDouIndex {
    #[serde(default, deserialize_with = "de_nonnegative_int")]
    pub value: Option<i64>,
    #[serde(default)]
    pub stage: String,
    #[serde(default)]
    pub report: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct LifecycleRunSummary {
    pub schema: Option<String>,
    pub run_id: String,
    pub workflow: String,
    pub status: String,
    pub agent: String,
    pub root: String,
    pub current_stage: String,
    pub next_stage: String,
    pub next_agent: String,
    pub exit_code: Option<i64>,
    pub dou_index: Option<i64>,
    pub baton_dou_index: Option<i64>,
    pub accepted_dou: i64,
    pub dou_readiness: String,
    pub human_controls: Vec<String>,
    pub human_controls_count: usize,
    pub operator_actions_count: usize,
    pub state_path: String,
    pub report_path: String,
    pub transcript_path: String,
    pub updated_at: String,
    pub source: String,
}

/// A control-plane event. Field-for-field mirror of `control_plane.Event`.
///
/// On disk in `events.jsonl` each line carries `ts/run_id/kind/message/payload`
/// but **not** `cursor` — the cursor is the byte offset assigned at read time
/// (see [`crate::events`]). Hence `cursor` defaults to `0` on deserialize and is
/// stamped by the reader.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Event {
    pub ts: String,
    pub run_id: String,
    pub kind: String,
    pub message: String,
    #[serde(default)]
    pub payload: BTreeMap<String, serde_json::Value>,
    #[serde(default)]
    pub cursor: u64,
}

/// Raw `*.meta.json` agent record — the richest of the three merge sources.
///
/// Field names differ from [`RunStatus`] (`status` not `state`, `skill_code`
/// not `skill`, `report`/`transcript` not `latest_*`), matching what the
/// launcher writes. Use [`AgentMeta::normalize`] to project into a
/// [`RunStatus`]; mirrors `control_plane._normalize_agent_meta`.
#[derive(Debug, Clone, Deserialize)]
pub struct AgentMeta {
    #[serde(default)]
    pub run_id: String,
    #[serde(default)]
    pub root: String,
    #[serde(default)]
    pub skill_code: String,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub updated_at: String,
    #[serde(default)]
    pub started_at: String,
    #[serde(default)]
    pub agent: String,
    #[serde(default)]
    pub mode: String,
    #[serde(default)]
    pub report: String,
    #[serde(default)]
    pub transcript: String,
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub reason: String,
    /// Present-but-`null` in flight; an integer once the process exits.
    #[serde(default, deserialize_with = "de_coerced_int")]
    pub exit_code: Option<i64>,
    #[serde(default)]
    pub liveness: String,
    #[serde(default, deserialize_with = "de_coerced_int")]
    pub launcher_pid: Option<i64>,
    #[serde(default)]
    pub completed_at: String,
    #[serde(default)]
    pub session_id: String,
}

fn de_coerced_int<'de, D>(deserializer: D) -> Result<Option<i64>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    Ok(coerce_int_value(&value))
}

fn de_nonnegative_int<'de, D>(deserializer: D) -> Result<Option<i64>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    Ok(coerce_int_value(&value).filter(|value| *value >= 0))
}

fn de_optional_lifecycle_dou_index<'de, D>(
    deserializer: D,
) -> Result<Option<LifecycleDouIndex>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    if !value.is_object() {
        return Ok(None);
    }
    serde_json::from_value(value)
        .map(Some)
        .map_err(serde::de::Error::custom)
}

impl AgentMeta {
    /// Project into a [`RunStatus`] using `now` for health derivation.
    /// Returns `None` when `run_id` is blank (mirrors the Python guard).
    #[must_use]
    pub fn normalize(&self, now: DateTime<Utc>) -> Option<RunStatus> {
        let run_id = self.run_id.trim();
        if run_id.is_empty() {
            return None;
        }
        let state = nonempty_or(&self.status, "unknown");
        let exit_code = self.exit_code;
        let liveness = self.liveness.clone();
        let health = if exit_code.is_some() || liveness == "terminal" {
            Health::Final
        } else {
            state_health(&state, &self.updated_at, now)
        };
        let last_error = if self.message.is_empty() {
            self.reason.clone()
        } else {
            self.message.clone()
        };
        let started_at = if self.started_at.is_empty() {
            self.updated_at.clone()
        } else {
            self.started_at.clone()
        };
        Some(RunStatus {
            run_id: run_id.to_string(),
            state,
            agent: nonempty_or(&self.agent, "unknown"),
            skill: skill_from_code(&self.skill_code),
            mode: nonempty_or(&self.mode, "unknown"),
            root: self.root.clone(),
            operator_session: operator_session_name(&self.root, run_id),
            latest_report: self.report.clone(),
            latest_transcript: self.transcript.clone(),
            last_error,
            updated_at: self.updated_at.clone(),
            started_at,
            health: health.as_str().to_string(),
            source: "agent-meta".to_string(),
            lock_present: false,
            exit_code,
            liveness,
            launcher_pid: self.launcher_pid,
            completed_at: self.completed_at.clone(),
            session_id: self.session_id.clone(),
            current_loop: None,
            total_loops: None,
        })
    }
}

/// Merge two projections for the same `run_id`, preferring the newer
/// `updated_at`. Mirrors `control_plane._merge_status`: the newer record wins
/// field-by-field, missing values fall back to the other record, and
/// `lock_present` / `exit_code` are sticky.
#[must_use]
pub fn merge_status(existing: Option<RunStatus>, incoming: RunStatus) -> RunStatus {
    let Some(existing) = existing else {
        return incoming;
    };
    let existing_dt = parse_iso(&existing.updated_at);
    let incoming_dt = parse_iso(&incoming.updated_at);
    // Prefer existing when its timestamp is present and >= incoming's
    // (a missing incoming timestamp sorts as the epoch floor, like Python).
    let prefer_existing = match (existing_dt, incoming_dt) {
        (Some(e), Some(i)) => e >= i,
        (Some(_), None) => true,
        _ => false,
    };
    let (preferred, other) = if prefer_existing {
        (&existing, &incoming)
    } else {
        (&incoming, &existing)
    };

    RunStatus {
        run_id: preferred.run_id.clone(),
        state: preferred.state.clone(),
        agent: nonempty_or(&preferred.agent, &other.agent),
        skill: nonempty_or(&preferred.skill, &other.skill),
        mode: nonempty_or(&preferred.mode, &other.mode),
        root: nonempty_or(&preferred.root, &other.root),
        operator_session: nonempty_or(&preferred.operator_session, &other.operator_session),
        latest_report: nonempty_or(&preferred.latest_report, &other.latest_report),
        latest_transcript: nonempty_or(&preferred.latest_transcript, &other.latest_transcript),
        last_error: nonempty_or(&preferred.last_error, &other.last_error),
        updated_at: nonempty_or(&preferred.updated_at, &other.updated_at),
        started_at: nonempty_or(&preferred.started_at, &other.started_at),
        health: preferred.health.clone(),
        source: preferred.source.clone(),
        lock_present: existing.lock_present || incoming.lock_present,
        exit_code: preferred.exit_code.or(other.exit_code),
        liveness: nonempty_or(&preferred.liveness, &other.liveness),
        launcher_pid: preferred.launcher_pid.or(other.launcher_pid),
        completed_at: nonempty_or(&preferred.completed_at, &other.completed_at),
        session_id: nonempty_or(&preferred.session_id, &other.session_id),
        current_loop: preferred.current_loop.or(other.current_loop),
        total_loops: preferred.total_loops.or(other.total_loops),
    }
}

use std::fs;
use std::path::Path;
use std::time::Duration;

use tempfile::tempdir;
use vibecrafted_operator::app::{App, DeepAction, LaunchFocus};
use vibecrafted_operator::config::AppConfig;
use vibecrafted_operator::launch::{
    LaunchKind, LaunchRequest, LaunchRuntime, build_launch_command,
};
use vibecrafted_operator::state::{
    ControlPlaneState, RenderedRun, RunKind, RunSnapshot, classify_run,
};

#[cfg(unix)]
use std::os::unix::fs::symlink;

#[test]
fn loads_runs_and_events_from_control_plane_state() {
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::create_dir_all(root.join("runs")).unwrap();
    fs::write(
        root.join("runs/run-a.json"),
        r#"{
            "run_id": "run-a",
            "agent": "codex",
            "skill": "workflow",
            "mode": "implement",
            "state": "active",
            "started_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:02:00Z",
            "operator_session": "session-123",
            "latest_report": "/tmp/report.md"
        }"#,
    )
    .unwrap();
    fs::write(
        root.join("events.jsonl"),
        "{\"ts\":\"2026-04-16T10:02:01Z\",\"run_id\":\"run-a\",\"kind\":\"heartbeat\",\"message\":\"still running\"}\n",
    )
    .unwrap();

    let state = ControlPlaneState::load(root).unwrap();
    assert_eq!(state.runs.len(), 1);
    assert_eq!(state.events.len(), 1);
    assert_eq!(state.runs[0].run_id, "run-a");
    assert_eq!(state.events[0].kind, "heartbeat");
}

#[test]
fn ignores_symlink_escapes_in_control_plane_root() {
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::create_dir_all(root.join("runs")).unwrap();
    let external = tempdir().unwrap();
    let escaped = external.path().join("escaped.json");
    fs::write(
        &escaped,
        r#"{"run_id":"escape","state":"active","updated_at":"2026-04-16T10:00:00Z"}"#,
    )
    .unwrap();

    #[cfg(unix)]
    symlink(&escaped, root.join("runs/symlink.json")).unwrap();

    let state = ControlPlaneState::load(root).unwrap();
    assert!(state.runs.is_empty());
}

#[test]
fn classifies_stale_active_runs_as_stalled() {
    let snapshot = RunSnapshot {
        run_id: "run-a".to_string(),
        session_id: None,
        agent: Some("codex".to_string()),
        skill: Some("workflow".to_string()),
        mode: Some("implement".to_string()),
        state: Some("active".to_string()),
        status: None,
        started_at: Some("2026-04-16T09:00:00Z".to_string()),
        updated_at: Some("2026-04-16T09:05:00Z".to_string()),
        last_heartbeat: Some("2026-04-16T09:06:00Z".to_string()),
        root: None,
        operator_session: None,
        latest_report: None,
        latest_transcript: None,
        last_error: None,
        extra: Default::default(),
    };
    let now = chrono::DateTime::parse_from_rfc3339("2026-04-16T10:30:00Z")
        .unwrap()
        .with_timezone(&chrono::Utc);
    assert_eq!(classify_run(&snapshot, now), RunKind::Stalled);
}

#[test]
fn builds_existing_command_deck_launches() {
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Research,
        agent: "claude".to_string(),
        prompt: "Investigate the state format.".to_string(),
        runtime: LaunchRuntime::Headless,
        root: Some("/tmp/vibecrafted".into()),
        count: Some(3),
        depth: Some(3),
    };
    let command = build_launch_command(deck, &request);
    assert_eq!(command.program, deck);
    assert_eq!(command.args[0], "research");
    assert_eq!(command.args[1], "--prompt");
    assert_eq!(command.args[3], "--runtime");
    assert_eq!(command.args[4], "headless");
    assert_eq!(command.args[5], "--root");
    assert_eq!(command.args[6], "/tmp/vibecrafted");
}

#[test]
fn marbles_launches_keep_runtime_root_and_loop_controls() {
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Marbles,
        agent: "codex".to_string(),
        prompt: "Converge on the operator surface.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/repo".into()),
        count: Some(4),
        depth: Some(7),
    };
    let command = build_launch_command(deck, &request);
    let args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    assert_eq!(
        args,
        vec![
            "marbles",
            "codex",
            "--count",
            "4",
            "--depth",
            "7",
            "--prompt",
            "Converge on the operator surface.",
            "--runtime",
            "terminal",
            "--root",
            "/tmp/repo",
        ]
    );
}

#[test]
fn deep_controls_expose_attach_resume_and_artifacts() {
    let snapshot = RunSnapshot {
        run_id: "run-42".to_string(),
        session_id: Some("sess-42".to_string()),
        agent: Some("codex".to_string()),
        skill: Some("workflow".to_string()),
        mode: Some("implement".to_string()),
        state: Some("running".to_string()),
        status: None,
        started_at: Some("2026-04-16T10:00:00Z".to_string()),
        updated_at: Some("2026-04-16T10:02:00Z".to_string()),
        last_heartbeat: Some("2026-04-16T10:03:00Z".to_string()),
        root: Some("/tmp/repo".to_string()),
        operator_session: Some("repo-run-42".to_string()),
        latest_report: Some("/tmp/repo/report.md".to_string()),
        latest_transcript: Some("/tmp/repo/transcript.log".to_string()),
        last_error: None,
        extra: Default::default(),
    };
    let run = RenderedRun {
        snapshot,
        kind: RunKind::Active,
        age_label: "1m ago".to_string(),
        recent_events: Vec::new(),
    };
    let app = App {
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,
            tick_rate: Duration::from_millis(250),
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![run],
        selected: 0,
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
    };

    assert_eq!(
        app.deep_actions(),
        vec![
            DeepAction::AttachSession("repo-run-42".to_string()),
            DeepAction::ResumeSession {
                agent: "codex".to_string(),
                session: "sess-42".to_string(),
            },
            DeepAction::OpenReport("/tmp/repo/report.md".into()),
            DeepAction::OpenTranscript("/tmp/repo/transcript.log".into()),
            DeepAction::OpenRoot("/tmp/repo".into()),
        ]
    );
}

use std::env;
use std::fs;
use std::path::Path;
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use tempfile::tempdir;
use vibecrafted_operator::app::{App, AppTab, DeepAction, DispatchFocus, LaunchFocus};
use vibecrafted_operator::config::AppConfig;
use vibecrafted_operator::launch::{
    LaunchKind, LaunchRequest, LaunchRuntime, build_launch_command,
};
use vibecrafted_operator::state::{
    ControlPlaneState, RenderedRun, RunKind, RunSnapshot, classify_run,
};

#[cfg(unix)]
use std::os::unix::fs::symlink;

fn env_lock() -> &'static Mutex<()> {
    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    ENV_LOCK.get_or_init(|| Mutex::new(()))
}

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
    // Process env is shared across tests, so pin access while we mutate zellij config.
    let _guard = env_lock().lock().unwrap();
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    unsafe {
        env::remove_var("ZELLIJ_CONFIG_DIR");
    }
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::create_dir_all(root.join("config/zellij")).unwrap();
    fs::write(root.join("config/zellij/config.kdl"), "layout {}\n").unwrap();
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Marbles,
        agent: "codex".to_string(),
        prompt: "Converge on the operator surface.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some(root.to_path_buf()),
        count: Some(4),
        depth: Some(7),
    };
    let command = build_launch_command(deck, &request);
    let args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    let expected_deck_cmd = format!(
        "exec '/usr/bin/vibecrafted' 'marbles' 'codex' '--count' '4' '--depth' '7' '--prompt' 'Converge on the operator surface.' '--runtime' 'terminal' '--root' '{}'",
        root.to_string_lossy()
    );

    assert_eq!(command.program, Path::new("zellij"));

    assert!(args.windows(2).any(|pair| {
        pair == [
            "--config-dir".to_string(),
            root.join("config/zellij").to_string_lossy().into_owned(),
        ]
    }));
    assert!(args.iter().any(|value| value == "--layout-string"));
    assert!(args.iter().any(|value| value == "options"));

    let layout = args
        .iter()
        .position(|value| value == "--layout-string")
        .and_then(|index| args.get(index + 1))
        .expect("layout string");
    assert!(layout.contains("pane name=\"launch\""));
    assert!(layout.contains("command=\"bash\""));
    assert!(layout.contains(&format!("cwd=\"{}\"", root.to_string_lossy())));
    assert!(layout.contains("export ZELLIJ_CONFIG_DIR="));
    assert!(layout.contains(&expected_deck_cmd));

    match previous {
        Some(value) => unsafe {
            env::set_var("ZELLIJ_CONFIG_DIR", value);
        },
        None => unsafe {
            env::remove_var("ZELLIJ_CONFIG_DIR");
        },
    }
}

#[test]
fn terminal_launches_preserve_explicit_zellij_config_dir() {
    // Process env is shared across tests, so pin access while we mutate zellij config.
    let _guard = env_lock().lock().unwrap();
    let deck = Path::new("/usr/bin/vibecrafted");
    let explicit = Path::new("/tmp/custom-zellij");
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    // This test temporarily pins process env to verify that operator-tui
    // respects an already configured frontier location.
    unsafe {
        env::set_var("ZELLIJ_CONFIG_DIR", explicit);
    }
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "codex".to_string(),
        prompt: "Ship the launcher.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/workspace".into()),
        count: Some(3),
        depth: Some(3),
    };

    let command = build_launch_command(deck, &request);
    let args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    let layout = args
        .iter()
        .position(|value| value == "--layout-string")
        .and_then(|index| args.get(index + 1))
        .expect("layout string");

    assert!(layout.contains("export ZELLIJ_CONFIG_DIR='/tmp/custom-zellij'"));

    match previous {
        Some(value) => unsafe {
            env::set_var("ZELLIJ_CONFIG_DIR", value);
        },
        None => unsafe {
            env::remove_var("ZELLIJ_CONFIG_DIR");
        },
    }
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
        active_tab: AppTab::Monitor.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,
        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: false,
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

#[test]
fn empty_state_detail_lines_offer_human_quick_start() {
    let app = App {
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,
            tick_rate: Duration::from_millis(250),
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![],
        selected: 0,
        active_tab: AppTab::Monitor.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,
        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: false,
    };

    let lines = app.detail_lines();
    assert!(lines.iter().any(|line| line.contains("Start here:")));
    assert!(lines.iter().any(|line| line.contains("Workflow")));
    assert!(lines.iter().any(|line| line.contains("Press ?")));
}

#[test]
fn prompt_lines_include_human_kind_copy_and_command_preview() {
    let app = App {
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,
            tick_rate: Duration::from_millis(250),
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![],
        selected: 0,
        active_tab: AppTab::Dispatch.index(),
        launch_kind: LaunchKind::Research,
        launch_agent: 1,
        launch_prompt: "Research the launcher surface.".to_string(),
        launch_runtime: LaunchRuntime::Visible,
        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: false,
    };

    let lines = app.prompt_lines();
    assert!(lines.iter().any(|line| line.contains("Research swarm")));
    assert!(lines.iter().any(|line| line.contains("command:")
        && line.contains("zellij")
        && line.contains("research")));
    assert!(lines.iter().any(|line| line.contains("Arrows:")));
}

#[test]
fn tab_navigation_wraps_and_dispatch_focus_tracks_selected_field() {
    let mut app = App {
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,
            tick_rate: Duration::from_millis(250),
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![],
        selected: 0,
        active_tab: AppTab::Monitor.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,
        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: false,
    };

    app.previous_tab();
    assert_eq!(app.active_tab(), AppTab::Controls);

    app.next_tab();
    assert_eq!(app.active_tab(), AppTab::Monitor);

    app.move_dispatch_selection(1);
    assert_eq!(app.dispatch_focus(), DispatchFocus::Agent);

    app.move_dispatch_selection(2);
    assert_eq!(app.dispatch_focus(), DispatchFocus::Prompt);
}

#[test]
fn tab_labels_surface_monitor_dispatch_and_controls_context() {
    let snapshot = RunSnapshot {
        run_id: "run-7".to_string(),
        session_id: Some("sess-7".to_string()),
        agent: Some("codex".to_string()),
        skill: Some("workflow".to_string()),
        mode: Some("implement".to_string()),
        state: Some("running".to_string()),
        status: None,
        started_at: Some("2026-04-16T10:00:00Z".to_string()),
        updated_at: Some("2026-04-16T10:02:00Z".to_string()),
        last_heartbeat: Some("2026-04-16T10:03:00Z".to_string()),
        root: Some("/tmp/repo".to_string()),
        operator_session: Some("repo-run-7".to_string()),
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
    let mut app = App {
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
        active_tab: AppTab::Monitor.index(),
        launch_kind: LaunchKind::Marbles,
        launch_agent: 2,
        launch_prompt: "Converge".to_string(),
        launch_runtime: LaunchRuntime::Visible,
        dispatch_selected: DispatchFocus::Runtime as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: true,
    };

    let labels = app.tab_labels();
    assert_eq!(labels[0], "Monitor 1/1");
    assert_eq!(labels[1], "Dispatch marbles/gemini");
    assert_eq!(labels[2], "Controls 5");

    app.selected = 1;
    let labels = app.tab_labels();
    assert_eq!(labels[2], "Controls -");
}

#[test]
fn changing_launch_kind_reorients_the_operator_into_dispatch() {
    let mut app = App {
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,
            tick_rate: Duration::from_millis(250),
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![],
        selected: 0,
        active_tab: AppTab::Controls.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 2,
        launch_prompt: "custom prompt".to_string(),
        launch_runtime: LaunchRuntime::Terminal,
        dispatch_selected: DispatchFocus::Runtime as usize,
        focus: LaunchFocus::Help,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        filter_active_only: false,
    };

    app.set_launch_kind(LaunchKind::Review);

    assert_eq!(app.active_tab(), AppTab::Dispatch);
    assert_eq!(app.dispatch_focus(), DispatchFocus::Kind);
    assert_eq!(app.focus, LaunchFocus::Browse);
    assert!(app.launch_prompt.contains("Review"));
}

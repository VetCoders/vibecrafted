use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::Path;
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use tempfile::tempdir;
use vibecrafted_operator::app::{App, AppTab, DeepAction, DispatchFocus, LaunchFocus, QueueScope};
use vibecrafted_operator::config::AppConfig;
use vibecrafted_operator::launch::{
    LaunchKind, LaunchRequest, LaunchRuntime, build_launch_command,
};
use vibecrafted_operator::skills_catalog::CATALOG;
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
fn archived_run_markers_hide_runs_from_operator_board() {
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::create_dir_all(root.join("runs/.archived")).unwrap();
    fs::write(
        root.join("runs/run-a.json"),
        r#"{"run_id":"run-a","state":"active","updated_at":"2026-04-16T10:00:00Z"}"#,
    )
    .unwrap();
    fs::write(
        root.join("runs/run-b.json"),
        r#"{"run_id":"run-b","state":"active","updated_at":"2026-04-16T10:00:00Z"}"#,
    )
    .unwrap();
    fs::write(
        root.join("runs/.archived/run-a.json"),
        r#"{"run_id":"run-a"}"#,
    )
    .unwrap();

    let state = ControlPlaneState::load(root).unwrap();

    assert_eq!(state.archived_run_ids.len(), 1);
    assert_eq!(state.runs.len(), 1);
    assert_eq!(state.runs[0].run_id, "run-b");
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
        terminal_binary: Some("zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: None,
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
        terminal_binary: Some("zellij".into()),
        env: BTreeMap::new(),
        count: Some(4),
        depth: Some(7),
        session_name: None,
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
        terminal_binary: Some("zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: None,
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
fn terminal_launch_carries_named_session_before_subcommand() {
    let _guard = env_lock().lock().unwrap();
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    unsafe {
        env::remove_var("ZELLIJ_CONFIG_DIR");
    }
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "claude".to_string(),
        prompt: "Ship the launcher.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/workspace".into()),
        terminal_binary: Some("zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: Some("vc-op-workflow-42".to_string()),
    };

    let command = build_launch_command(deck, &request);
    let args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();

    let session_idx = args
        .iter()
        .position(|value| value == "--session")
        .expect("--session flag present when session_name is provided");
    assert_eq!(
        args.get(session_idx + 1).map(String::as_str),
        Some("vc-op-workflow-42")
    );

    let options_idx = args
        .iter()
        .position(|value| value == "options")
        .expect("options subcommand present");
    assert!(
        session_idx < options_idx,
        "--session must precede the options subcommand: args={args:?}"
    );

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
fn terminal_launch_exposes_named_session_readiness_probe() {
    let _guard = env_lock().lock().unwrap();
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    unsafe {
        env::remove_var("ZELLIJ_CONFIG_DIR");
    }
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "claude".to_string(),
        prompt: "Ship the launcher.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/workspace".into()),
        terminal_binary: Some("/opt/bin/zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: Some("vc-op-workflow-42".to_string()),
    };

    let command = build_launch_command(deck, &request);
    let probe = command
        .readiness_probe()
        .expect("named terminal launch should expose a readiness probe");
    let probe_args = probe
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();

    assert_eq!(probe.program, Path::new("/opt/bin/zellij"));
    assert_eq!(probe.session_name, "vc-op-workflow-42");
    assert_eq!(
        probe_args,
        vec!["list-sessions", "--short", "--no-formatting"]
    );

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
fn terminal_launch_omits_session_flag_when_session_name_is_none() {
    let _guard = env_lock().lock().unwrap();
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    unsafe {
        env::remove_var("ZELLIJ_CONFIG_DIR");
    }
    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "claude".to_string(),
        prompt: "Ship the launcher.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/workspace".into()),
        terminal_binary: Some("zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: None,
    };

    let command = build_launch_command(deck, &request);
    let args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();

    assert!(
        !args.iter().any(|value| value == "--session"),
        "no --session flag expected when session_name is None: args={args:?}"
    );
    assert!(
        command.readiness_probe().is_none(),
        "anonymous terminal launches cannot be healthchecked by name"
    );

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
fn terminal_launch_probe_inherits_config_dir_from_launch_command() {
    let _guard = env_lock().lock().unwrap();
    let previous = env::var_os("ZELLIJ_CONFIG_DIR");
    unsafe {
        env::remove_var("ZELLIJ_CONFIG_DIR");
    }
    let workspace = tempdir().unwrap();
    let zellij_dir = workspace.path().join("config/zellij");
    fs::create_dir_all(&zellij_dir).unwrap();
    fs::write(zellij_dir.join("config.kdl"), "// repo-local zellij\n").unwrap();
    let canonical_zellij_dir = zellij_dir.canonicalize().unwrap_or(zellij_dir.clone());

    let deck = Path::new("/usr/bin/vibecrafted");
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "claude".to_string(),
        prompt: "Ship the launcher.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some(workspace.path().to_path_buf()),
        terminal_binary: Some("/opt/bin/zellij".into()),
        env: BTreeMap::new(),
        count: Some(3),
        depth: Some(3),
        session_name: Some("vc-op-workflow-77".to_string()),
    };

    let command = build_launch_command(deck, &request);
    let launch_args = command
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();
    let launch_config_idx = launch_args
        .iter()
        .position(|value| value == "--config-dir")
        .expect("launch should carry --config-dir when repo has config/zellij/config.kdl");
    let launch_config_dir = launch_args
        .get(launch_config_idx + 1)
        .expect("--config-dir flag must be followed by a path");

    let probe = command
        .readiness_probe()
        .expect("named terminal launch should expose a readiness probe");
    let probe_args = probe
        .args
        .iter()
        .map(|value| value.to_string_lossy().into_owned())
        .collect::<Vec<_>>();

    let probe_config_idx = probe_args
        .iter()
        .position(|value| value == "--config-dir")
        .expect("probe must carry --config-dir to match launch namespace (P1-01)");
    let probe_config_dir = probe_args
        .get(probe_config_idx + 1)
        .expect("probe --config-dir flag must be followed by a path");
    let list_sessions_idx = probe_args
        .iter()
        .position(|value| value == "list-sessions")
        .expect("probe must invoke list-sessions");

    assert_eq!(probe_config_dir, launch_config_dir);
    assert!(
        probe_config_dir.contains(&canonical_zellij_dir.to_string_lossy().into_owned())
            || probe_config_dir == &zellij_dir.to_string_lossy().into_owned(),
        "probe config dir should match the repo-local namespace: probe={probe_config_dir:?} expected={canonical_zellij_dir:?}"
    );
    assert!(
        probe_config_idx < list_sessions_idx,
        "--config-dir must precede the list-sessions subcommand: args={probe_args:?}"
    );

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
fn mux_health_deep_actions_surface_per_known_service() {
    use std::path::PathBuf;
    use vibecrafted_operator::mux::{MuxStatusSnapshot, MuxSummary};

    let healthy_json = r#"{
        "service_name": "general-memory",
        "server_status": "Running",
        "restarts": 0,
        "connected_clients": 1,
        "active_clients": 0,
        "max_active_clients": 5,
        "pending_requests": 0,
        "cached_initialize": true,
        "initializing": false,
        "queue_depth": 0,
        "max_request_bytes": 1048576,
        "restart_backoff_ms": 1000,
        "restart_backoff_max_ms": 30000,
        "max_restarts": 5
    }"#;
    let failed_json = r#"{
        "service_name": "brave-search",
        "server_status": {"Failed": "max restarts reached"},
        "restarts": 5,
        "connected_clients": 0,
        "active_clients": 0,
        "max_active_clients": 5,
        "pending_requests": 0,
        "cached_initialize": false,
        "initializing": false,
        "queue_depth": 0,
        "max_request_bytes": 1048576,
        "restart_backoff_ms": 1000,
        "restart_backoff_max_ms": 30000,
        "max_restarts": 5
    }"#;

    // Run with full surface so we get the expected per-run actions too.
    let snapshot = RunSnapshot {
        run_id: "run-7".to_string(),
        session_id: Some("sess-7".to_string()),
        agent: Some("codex".to_string()),
        skill: Some("workflow".to_string()),
        mode: Some("implement".to_string()),
        state: Some("running".to_string()),
        status: None,
        started_at: Some("2026-04-30T10:00:00Z".to_string()),
        updated_at: Some("2026-04-30T10:02:00Z".to_string()),
        last_heartbeat: Some("2026-04-30T10:03:00Z".to_string()),
        root: Some("/tmp/repo".to_string()),
        operator_session: Some("repo-run-7".to_string()),
        latest_report: Some("/tmp/repo/report.md".to_string()),
        latest_transcript: None,
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
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![run],
        selected: 0,
        active_tab: AppTab::Controls.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,

        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 0,
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    // No mux summaries → only per-run actions. Existing surface preserved.
    let actions_no_mux = app.deep_actions();
    assert!(
        !actions_no_mux
            .iter()
            .any(|action| matches!(action, DeepAction::MuxHealth { .. })),
        "no MuxHealth without summaries: {actions_no_mux:?}"
    );

    // With one healthy + one failed summary → one MuxHealth action per service,
    // appended after the per-run actions.
    app.mux_summaries = vec![
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/memory.json"),
            MuxStatusSnapshot::from_json(healthy_json),
        ),
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/brave.json"),
            MuxStatusSnapshot::from_json(failed_json),
        ),
    ];
    let actions = app.deep_actions();
    let mux_actions: Vec<&DeepAction> = actions
        .iter()
        .filter(|action| matches!(action, DeepAction::MuxHealth { .. }))
        .collect();
    assert_eq!(mux_actions.len(), 2, "one MuxHealth per service");

    let services: Vec<&str> = actions
        .iter()
        .filter_map(|action| match action {
            DeepAction::MuxHealth { service } => Some(service.as_str()),
            _ => None,
        })
        .collect();
    assert!(services.contains(&"general-memory"));
    assert!(services.contains(&"brave-search"));

    // Label must surface the rust-mux invocation so the operator knows
    // exactly what will run when they hit Enter.
    let label = mux_actions[0].label();
    assert!(label.contains("rust-mux health --service"));
    assert!(label.contains("general-memory") || label.contains("brave-search"));

    // MuxHealth is available even with no run selected (the operator should
    // be able to health-check the supervisor even when nothing else is up).
    app.runs.clear();
    app.selected = 0;
    let actions_no_run = app.deep_actions();
    let mux_only: Vec<&DeepAction> = actions_no_run
        .iter()
        .filter(|action| matches!(action, DeepAction::MuxHealth { .. }))
        .collect();
    assert_eq!(
        mux_only.len(),
        2,
        "MuxHealth should not depend on selected_run"
    );
}

#[test]
fn mux_status_lines_render_healthy_and_attention_headers() {
    use std::path::PathBuf;
    use vibecrafted_operator::mux::{MuxStatusSnapshot, MuxSummary, MuxSummaryState};

    let healthy_json = r#"{
        "service_name": "general-memory",
        "server_status": "Running",
        "restarts": 0,
        "connected_clients": 2,
        "active_clients": 1,
        "max_active_clients": 5,
        "pending_requests": 0,
        "cached_initialize": true,
        "initializing": false,
        "queue_depth": 0,
        "child_pid": 4242,
        "max_request_bytes": 1048576,
        "restart_backoff_ms": 1000,
        "restart_backoff_max_ms": 30000,
        "max_restarts": 5
    }"#;
    let failed_json = r#"{
        "service_name": "brave-search",
        "server_status": {"Failed": "max restarts reached"},
        "restarts": 5,
        "connected_clients": 0,
        "active_clients": 0,
        "max_active_clients": 5,
        "pending_requests": 0,
        "cached_initialize": false,
        "initializing": false,
        "queue_depth": 0,
        "max_request_bytes": 1048576,
        "restart_backoff_ms": 1000,
        "restart_backoff_max_ms": 30000,
        "max_restarts": 5
    }"#;

    let mut app = App {
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    // No mux services → empty render, never a misleading "0 healthy" header.
    assert!(app.mux_status_lines().is_empty());

    // Two healthy services → "MCP daemons (2 healthy):" header + bullet rows.
    app.mux_summaries = vec![
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/memory.json"),
            MuxStatusSnapshot::from_json(healthy_json),
        ),
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/memory2.json"),
            MuxStatusSnapshot::from_json(healthy_json),
        ),
    ];
    let lines = app.mux_status_lines();
    assert_eq!(lines[0], "MCP daemons (2 healthy):");
    assert!(lines.iter().filter(|l| l.contains("• ")).count() == 2);
    assert!(!lines.iter().any(|l| l.contains("! ")));

    // Mixed healthy + failed → header switches to "x/n need attention".
    app.mux_summaries = vec![
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/memory.json"),
            MuxStatusSnapshot::from_json(healthy_json),
        ),
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/brave.json"),
            MuxStatusSnapshot::from_json(failed_json),
        ),
        MuxSummary::from_path_and_result(
            PathBuf::from("/tmp/loctree-broken.json"),
            Err(anyhow::anyhow!("not json")),
        ),
    ];
    let lines = app.mux_status_lines();
    assert_eq!(lines[0], "MCP daemons (2/3 need attention):");
    assert!(
        lines
            .iter()
            .any(|l| l.contains("• ") && l.contains("Running"))
    );
    assert!(
        lines
            .iter()
            .any(|l| l.contains("! ") && l.contains("Failed"))
    );
    assert!(
        lines
            .iter()
            .any(|l| l.contains("! ") && l.contains("unreadable"))
    );

    // Sanity-check the marker classes.
    assert!(matches!(
        app.mux_summaries[0].state,
        MuxSummaryState::Healthy(_)
    ));
    assert!(matches!(
        app.mux_summaries[1].state,
        MuxSummaryState::Unhealthy(_)
    ));
    assert!(matches!(
        app.mux_summaries[2].state,
        MuxSummaryState::Unreadable { .. }
    ));
}

#[test]
fn launch_commands_propagate_operator_env_and_custom_terminal_binary() {
    let deck = Path::new("/usr/bin/vibecrafted");
    let mut env = BTreeMap::new();
    env.insert("VIBECRAFTED_ROOT".to_string(), "/tmp/repo".into());
    env.insert(
        "VIBECRAFT_OPERATOR_STATE_ROOT".to_string(),
        "/tmp/state".into(),
    );
    let request = LaunchRequest {
        kind: LaunchKind::Workflow,
        agent: "codex".to_string(),
        prompt: "Ship launch env.".to_string(),
        runtime: LaunchRuntime::Terminal,
        root: Some("/tmp/repo".into()),
        terminal_binary: Some("/opt/bin/zellij".into()),
        env,
        count: Some(3),
        depth: Some(3),
        session_name: None,
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

    assert_eq!(command.program, Path::new("/opt/bin/zellij"));
    assert_eq!(
        command
            .env
            .get("VIBECRAFTED_ROOT")
            .map(|value| value.as_os_str()),
        Some(std::ffi::OsStr::new("/tmp/repo"))
    );
    assert!(layout.contains("export VIBECRAFTED_ROOT='/tmp/repo'"));
    assert!(layout.contains("starship init bash"));
    assert!(layout.contains("zoxide init bash"));
    assert!(layout.contains("atuin init bash --disable-up-arrow"));
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
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    let actions = app.deep_actions();
    assert_eq!(
        &actions[..5],
        &[
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
    assert_eq!(actions.len(), 5 + CATALOG.len());
}

#[test]
fn native_artifact_viewer_reads_files_and_clipboard_payload_prefers_resume_command() {
    let dir = tempdir().unwrap();
    let report = dir.path().join("report.md");
    fs::write(&report, "line one\nline two\n").unwrap();
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
        root: Some(dir.path().to_string_lossy().into_owned()),
        operator_session: Some("repo-run-42".to_string()),
        latest_report: Some(report.to_string_lossy().into_owned()),
        latest_transcript: None,
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
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
        },
        state: ControlPlaneState::empty("/tmp/state"),
        runs: vec![run],
        selected: 0,
        active_tab: AppTab::Controls.index(),
        launch_kind: LaunchKind::Workflow,
        launch_agent: 0,
        launch_prompt: "Ship it".to_string(),
        launch_runtime: LaunchRuntime::Terminal,

        dispatch_selected: DispatchFocus::Kind as usize,
        focus: LaunchFocus::Browse,
        status_line: String::new(),
        launch_history: Vec::new(),
        deep_selected: 2,
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    assert_eq!(
        app.clipboard_payload().as_deref(),
        Some("vibecrafted resume codex --session sess-42")
    );
    app.open_artifact(&DeepAction::OpenReport(report)).unwrap();
    assert_eq!(app.focus, LaunchFocus::Artifact);
    assert!(app.artifact_lines().iter().any(|line| line == "line one"));
}

#[test]
fn empty_state_detail_lines_offer_human_quick_start() {
    let app = App {
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    let lines = app.detail_lines();
    assert!(lines.iter().any(|line| line.contains("Start here:")));
    assert!(lines.iter().any(|line| line.contains("Workflow")));
    assert!(lines.iter().any(|line| line.contains("Press ?")));
}

#[test]
fn prompt_lines_include_human_kind_copy_and_command_preview() {
    let app = App {
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
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
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    app.previous_tab();
    assert_eq!(app.active_tab(), AppTab::MissionControl);

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
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    let labels = app.tab_labels();
    assert_eq!(labels[0], "Monitor live 1");
    assert_eq!(labels[1], "Dispatch marbles/gemini");
    assert_eq!(labels[2], format!("Controls {}", 5 + CATALOG.len()));

    app.selected = 1;
    let labels = app.tab_labels();
    assert_eq!(labels[2], format!("Controls {}", CATALOG.len()));
}

#[tokio::test]
async fn queue_scope_and_search_filter_the_visible_run_list() {
    let dir = tempdir().unwrap();
    let root = dir.path();
    fs::create_dir_all(root.join("runs")).unwrap();
    let now = chrono::Utc::now().to_rfc3339();
    fs::write(
        root.join("runs/active-codex.json"),
        format!(
            r#"{{
                "run_id":"active-codex",
                "agent":"codex",
                "state":"active",
                "updated_at":"{now}",
                "last_heartbeat":"{now}"
            }}"#
        ),
    )
    .unwrap();
    fs::write(
        root.join("runs/done-claude.json"),
        r#"{
            "run_id":"done-claude",
            "agent":"claude",
            "state":"completed",
            "updated_at":"2026-04-16T10:00:00Z"
        }"#,
    )
    .unwrap();

    let mut app = App::new(AppConfig {
        state_root: root.into(),
        command_deck: "/usr/bin/vibecrafted".into(),
        launch_root: "/tmp/repo".into(),
        launch_runtime: LaunchRuntime::Terminal,

        terminal_binary: "zellij".into(),
        tick_rate: Duration::from_millis(250),
        no_verify_gate: false,
    })
    .unwrap();
    assert_eq!(app.runs.len(), 1);
    assert_eq!(app.runs[0].snapshot.run_id, "active-codex");

    app.toggle_filter();
    assert_eq!(app.queue_scope, QueueScope::History);
    assert_eq!(app.runs.len(), 1);
    assert_eq!(app.runs[0].snapshot.run_id, "done-claude");

    app.set_search_query("codex");
    assert!(app.runs.is_empty());

    app.toggle_filter();
    assert_eq!(app.queue_scope, QueueScope::All);
    assert_eq!(app.runs.len(), 1);
    assert_eq!(app.runs[0].snapshot.run_id, "active-codex");
}

#[test]
fn changing_launch_kind_reorients_the_operator_into_dispatch() {
    let mut app = App {
        mux_subscriber: None,
        config: AppConfig {
            state_root: "/tmp/state".into(),
            command_deck: "/usr/bin/vibecrafted".into(),
            launch_root: "/tmp/repo".into(),
            launch_runtime: LaunchRuntime::Terminal,

            terminal_binary: "zellij".into(),
            tick_rate: Duration::from_millis(250),
            no_verify_gate: false,
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
        queue_scope: QueueScope::Live,
        search_query: String::new(),
        error_title: String::new(),
        error_lines: Vec::new(),
        artifact_title: String::new(),
        artifact_lines: Vec::new(),
        mux_summaries: Vec::new(),
        polarize_intents: Vec::new(),
        mission_control: vibecrafted_operator::mission_control::MissionControlState::default(),
        mission_focus: 0,
        mission_artifact_root: std::path::PathBuf::from("/tmp/vc-op-mission-test"),
    };

    app.set_launch_kind(LaunchKind::Review);

    assert_eq!(app.active_tab(), AppTab::Dispatch);
    assert_eq!(app.dispatch_focus(), DispatchFocus::Kind);
    assert_eq!(app.focus, LaunchFocus::Browse);
    assert!(app.launch_prompt.contains("Review"));
}

/// `AppTab` contract — Mission Control is a first-class fourth tab and
/// must be reachable through the standard Tab/Shift+Tab rotation, with a
/// stable index and label. This locks PLAN_23 Wave A acceptance.
#[test]
fn mission_control_tab_is_addressable_and_reachable_via_rotation() {
    assert_eq!(AppTab::TITLES.len(), 4);
    assert_eq!(AppTab::MissionControl.label(), "Mission Control");
    assert_eq!(AppTab::MissionControl.index(), 3);
    assert_eq!(AppTab::from_index(3), AppTab::MissionControl);
    assert_eq!(AppTab::from_index(7), AppTab::MissionControl);
}

/// Mission Control aggregation over a fixture artifact tree: agent and
/// skill stats hydrate from `*.meta.json`, the wave atlas groups by
/// `prompt_id`, and the action queue surfaces the freshly completed
/// report. Mirror of PLAN_23 §4 acceptance for the seven-panel surface.
#[test]
fn mission_control_aggregates_real_meta_json_fixtures() {
    use vibecrafted_operator::mission_control::{ActionQueueKind, MissionControlState};
    let dir = tempdir().unwrap();
    let artifact = dir.path().join("artifacts");
    let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
    fs::create_dir_all(&bucket).unwrap();

    fs::write(
        bucket.join("just-001.meta.json"),
        r#"{
            "run_id": "just-001",
            "agent": "claude",
            "skill_code": "just",
            "exit_code": 0,
            "model": "claude-opus-4-7",
            "duration_s": 90.0,
            "completed_at": "2026-05-19T12:30:00Z",
            "prompt_id": "wave-a",
            "report": "/tmp/just-001/report.md"
        }"#,
    )
    .unwrap();
    fs::write(
        bucket.join("just-002.meta.json"),
        r#"{
            "run_id": "just-002",
            "agent": "codex",
            "skill_code": "marb",
            "exit_code": 1,
            "model": "unknown",
            "completed_at": "2026-05-19T12:45:00Z",
            "prompt_id": "wave-a"
        }"#,
    )
    .unwrap();
    fs::write(
        bucket.join("just-003.meta.json"),
        r#"{
            "run_id": "just-003",
            "agent": "claude",
            "skill_code": "just",
            "exit_code": 0,
            "model": "claude-opus-4-7",
            "duration_s": 45.5,
            "completed_at": "2026-05-19T12:50:00Z",
            "prompt_id": "wave-b",
            "report": "/tmp/just-003/report.md"
        }"#,
    )
    .unwrap();

    let state = ControlPlaneState::empty(dir.path());
    let now = chrono::DateTime::parse_from_rfc3339("2026-05-19T13:00:00Z")
        .unwrap()
        .with_timezone(&chrono::Utc);
    let mission = MissionControlState::build_at(&state, &artifact, now);

    // Per-agent stats: claude with 2 runs ✓✓, codex with 1 run ✗.
    let claude = mission
        .agent_stats
        .iter()
        .find(|row| row.agent == "claude")
        .expect("claude row present in fixture");
    assert_eq!(claude.total_runs, 2);
    assert_eq!(claude.completed, 2);
    assert!((claude.success_rate - 1.0).abs() < 1e-3);
    let codex = mission
        .agent_stats
        .iter()
        .find(|row| row.agent == "codex")
        .expect("codex row present in fixture");
    assert_eq!(codex.failed, 1);

    // Per-skill stats: `just` invoked twice, `marb` once.
    let just = mission
        .skill_stats
        .iter()
        .find(|row| row.skill == "just")
        .expect("just skill row");
    assert_eq!(just.invocations, 2);

    // Wave atlas: two groups derived from prompt_id.
    assert!(mission.wave_atlas.iter().any(|seg| seg.wave_id == "wave-a"));
    assert!(mission.wave_atlas.iter().any(|seg| seg.wave_id == "wave-b"));

    // Failure board: only one failure in the 24h window.
    assert_eq!(mission.failures.len(), 1);
    assert_eq!(mission.failures[0].run_id, "just-002");

    // Action queue: at least one ReportReady entry from the recent
    // completions and one Failure entry from the failed codex run.
    assert!(
        mission
            .action_queue
            .iter()
            .any(|item| item.kind == ActionQueueKind::Failure)
    );
    assert!(
        mission
            .action_queue
            .iter()
            .any(|item| item.kind == ActionQueueKind::ReportReady)
    );

    // Data quality: missing model + duration counters honest.
    assert_eq!(mission.data_quality.scanned_meta_files, 3);
    assert_eq!(mission.data_quality.missing_model, 1);
    assert_eq!(mission.data_quality.missing_duration, 1);
    assert!(mission.data_quality.artifact_root_present);
}

#[test]
fn mission_control_action_queue_includes_polarize_intents_with_band_priority() {
    use std::path::PathBuf;
    use vibecrafted_operator::mission_control::{
        ActionPriority, ActionQueueKind, MissionControlState,
    };
    use vibecrafted_operator::polarize::{PolarizeBand, PolarizeIntent};

    let dir = tempdir().unwrap();
    let artifact = dir.path().join("artifacts");
    fs::create_dir_all(&artifact).unwrap();

    let state = ControlPlaneState::empty(dir.path());
    let intents = vec![
        PolarizeIntent {
            band: PolarizeBand::Doctrine,
            score: 13,
            run_id: "polr-doctrine".to_string(),
            prism_path: PathBuf::from("/tmp/polarize/polr-doctrine/prism.json"),
        },
        PolarizeIntent {
            band: PolarizeBand::Abort,
            score: 3,
            run_id: "polr-abort".to_string(),
            prism_path: PathBuf::from("/tmp/polarize/polr-abort/prism.json"),
        },
        PolarizeIntent {
            band: PolarizeBand::Pass,
            score: 10,
            run_id: "polr-pass".to_string(),
            prism_path: PathBuf::from("/tmp/polarize/polr-pass/prism.json"),
        },
        PolarizeIntent {
            band: PolarizeBand::Memo,
            score: 6,
            run_id: "polr-memo".to_string(),
            prism_path: PathBuf::from("/tmp/polarize/polr-memo/prism.json"),
        },
    ];

    let now = chrono::DateTime::parse_from_rfc3339("2026-05-19T13:00:00Z")
        .unwrap()
        .with_timezone(&chrono::Utc);
    let mission = MissionControlState::build_at_with_intents(&state, &artifact, &intents, now);

    assert_eq!(mission.action_queue.len(), intents.len());
    assert_eq!(
        mission
            .action_queue
            .iter()
            .map(|item| item.priority)
            .collect::<Vec<_>>(),
        vec![
            ActionPriority::Critical,
            ActionPriority::Critical,
            ActionPriority::High,
            ActionPriority::Normal,
        ]
    );

    for intent in intents {
        let item = mission
            .action_queue
            .iter()
            .find(|entry| entry.source_path.as_ref() == Some(&intent.prism_path))
            .expect("polarize intent must produce action-queue item");
        assert_eq!(item.kind, ActionQueueKind::Polarize);
        assert!(item.summary.contains(&intent.run_id));
    }
}

/// Failure board windowing: meta entries older than the 24h cutoff must
/// be excluded from the failure panel even when their exit_code is
/// non-zero. Mirrors PLAN_23 §4 "Failure board (24h)".
#[test]
fn mission_control_failure_board_respects_24h_window() {
    use vibecrafted_operator::mission_control::MissionControlState;
    let dir = tempdir().unwrap();
    let artifact = dir.path().join("artifacts");
    let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
    fs::create_dir_all(&bucket).unwrap();

    fs::write(
        bucket.join("old-fail.meta.json"),
        r#"{
            "run_id": "old-fail",
            "agent": "gemini",
            "skill_code": "rev",
            "exit_code": 2,
            "completed_at": "2026-05-15T08:00:00Z"
        }"#,
    )
    .unwrap();
    fs::write(
        bucket.join("fresh-fail.meta.json"),
        r#"{
            "run_id": "fresh-fail",
            "agent": "gemini",
            "skill_code": "rev",
            "exit_code": 2,
            "completed_at": "2026-05-19T11:00:00Z"
        }"#,
    )
    .unwrap();

    let state = ControlPlaneState::empty(dir.path());
    let now = chrono::DateTime::parse_from_rfc3339("2026-05-19T13:00:00Z")
        .unwrap()
        .with_timezone(&chrono::Utc);
    let mission = MissionControlState::build_at(&state, &artifact, now);

    assert_eq!(mission.failures.len(), 1);
    assert_eq!(mission.failures[0].run_id, "fresh-fail");
}

/// Malformed `*.meta.json` files must be skipped without poisoning the
/// dashboard, and the count must surface in `data_quality.parse_failures`
/// so the operator sees the truth instead of a false-success aggregate.
#[test]
fn mission_control_skips_malformed_meta_json_without_panic() {
    use vibecrafted_operator::mission_control::MissionControlState;
    let dir = tempdir().unwrap();
    let artifact = dir.path().join("artifacts");
    let bucket = artifact.join("vetcoders/vc-operator/2026_0519/reports");
    fs::create_dir_all(&bucket).unwrap();
    fs::write(
        bucket.join("ok.meta.json"),
        r#"{
        "run_id": "ok-1",
        "agent": "claude",
        "skill_code": "just",
        "exit_code": 0,
        "completed_at": "2026-05-19T12:30:00Z"
    }"#,
    )
    .unwrap();
    fs::write(bucket.join("broken.meta.json"), "{this is not json").unwrap();

    let state = ControlPlaneState::empty(dir.path());
    let now = chrono::DateTime::parse_from_rfc3339("2026-05-19T13:00:00Z")
        .unwrap()
        .with_timezone(&chrono::Utc);
    let mission = MissionControlState::build_at(&state, &artifact, now);

    assert_eq!(mission.data_quality.scanned_meta_files, 1);
    assert_eq!(mission.data_quality.parse_failures, 1);
    assert_eq!(mission.agent_stats.len(), 1);
}

/// Mission Control panel focus navigation wraps around exactly the
/// seven panels documented in PLAN_23 §4. Locks the navigation
/// contract so future panel additions adjust both the constant and
/// the test together.
#[tokio::test]
async fn mission_control_focus_wraps_across_seven_panels() {
    use vibecrafted_operator::app::MISSION_PANEL_COUNT;
    assert_eq!(MISSION_PANEL_COUNT, 7);

    let mut app = App::new(AppConfig {
        state_root: std::path::PathBuf::from("/tmp/vc-op-mission-nav"),
        command_deck: "/usr/bin/vibecrafted".into(),
        launch_root: "/tmp/repo".into(),
        launch_runtime: LaunchRuntime::Terminal,
        terminal_binary: "zellij".into(),
        tick_rate: Duration::from_millis(250),
        no_verify_gate: false,
    })
    .unwrap();
    app.set_active_tab(AppTab::MissionControl);
    assert_eq!(app.mission_focus, 0);
    app.move_mission_focus(1);
    assert_eq!(app.mission_focus, 1);
    for _ in 0..MISSION_PANEL_COUNT {
        app.move_mission_focus(1);
    }
    assert_eq!(app.mission_focus, 1);
    app.move_mission_focus(-2);
    assert_eq!(app.mission_focus, MISSION_PANEL_COUNT - 1);
}

#[tokio::test]
async fn mission_queue_preselects_matching_deep_action_for_controls_handoff() {
    use vibecrafted_operator::mission_control::{
        ActionPriority, ActionQueueItem, ActionQueueKind, MissionControlState,
    };
    use vibecrafted_operator::polarize::{PolarizeBand, PolarizeIntent};

    let prism_path = std::path::PathBuf::from("/tmp/polarize/just-777/prism.json");
    let mut app = App::new(AppConfig {
        state_root: std::path::PathBuf::from("/tmp/vc-op-mission-handoff"),
        command_deck: "/usr/bin/vibecrafted".into(),
        launch_root: "/tmp/repo".into(),
        launch_runtime: LaunchRuntime::Terminal,
        terminal_binary: "zellij".into(),
        tick_rate: Duration::from_millis(250),
        no_verify_gate: false,
    })
    .unwrap();

    app.polarize_intents = vec![PolarizeIntent {
        band: PolarizeBand::Doctrine,
        score: 14,
        run_id: "just-777".to_string(),
        prism_path: prism_path.clone(),
    }];

    app.mission_control = MissionControlState {
        action_queue: vec![ActionQueueItem {
            kind: ActionQueueKind::Polarize,
            summary: "polarize just-777 (doctrine / score 14)".to_string(),
            source_path: Some(prism_path),
            priority: ActionPriority::Critical,
        }],
        ..Default::default()
    };

    app.deep_selected = 5;
    assert_eq!(
        app.deep_action_index_for_primary_mission_queue_item(),
        Some(0)
    );
    assert!(app.preselect_controls_from_mission_queue());
    assert_eq!(app.deep_selected, 0);
}

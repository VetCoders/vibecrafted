use mux_agent::ipc::{IpcEvent, MuxControlResponse};
use tray_agent::ipc_client::from_mux_response;
use tray_agent::types::TrayUpdate;

#[test]
fn spawn_update_response_renders_badge_update() {
    let update = from_mux_response(MuxControlResponse::Event(IpcEvent::SpawnUpdate {
        run_id: "run-render-1".to_string(),
        agent: "codex".to_string(),
        skill: "implement".to_string(),
        mode: "wave".to_string(),
        state: "running".to_string(),
        session_id: Some("sess-render-1".to_string()),
        exit_code: None,
        launcher_pid: Some(773),
        transcript: Some("/tmp/run-render-1.log".into()),
        report: None,
        ts: "2026-05-24T12:00:00Z".to_string(),
    }));

    assert_eq!(
        update,
        TrayUpdate::SpawnBadge {
            active: 1,
            last_agent: "codex".to_string(),
            last_state: "running".to_string(),
            last_run_id: "run-render-1".to_string(),
        }
    );
}

use mux_agent::ipc::command::{NonMuxEntry, VerifyResult};
use tray_agent::ipc_client::{ClientKind, IpcEvent, MuxControlCommand, MuxControlResponse};

#[tokio::test]
async fn serde_roundtrip_subscribe_command_matches_mux_agent_schema() {
    let cmd = MuxControlCommand::Subscribe;
    let json = serde_json::to_string(&cmd).unwrap();
    assert_eq!(json, r#"{"cmd":"Subscribe"}"#);
    let decoded: MuxControlCommand = serde_json::from_str(&json).unwrap();
    assert_eq!(cmd, decoded);
}

#[tokio::test]
async fn serde_roundtrip_verify_command_with_client_kind() {
    let cmd = MuxControlCommand::Verify {
        client_kind: ClientKind::Claude,
    };
    let json = serde_json::to_string(&cmd).unwrap();
    assert_eq!(json, r#"{"cmd":"Verify","args":{"client_kind":"claude"}}"#);
    let decoded: MuxControlCommand = serde_json::from_str(&json).unwrap();
    assert_eq!(cmd, decoded);
}

#[tokio::test]
async fn decode_mux_event_state_change() {
    let event = IpcEvent::StateChange {
        service: "test-service".to_string(),
        from: "idle".to_string(),
        to: "failed".to_string(),
    };
    let response = MuxControlResponse::Event(event);
    let json = serde_json::to_string(&response).unwrap();
    let decoded: MuxControlResponse = serde_json::from_str(&json).unwrap();
    if let MuxControlResponse::Event(IpcEvent::StateChange { to, .. }) = decoded {
        assert_eq!(to, "failed");
    } else {
        panic!("Decoding failed");
    }
}

#[tokio::test]
async fn decode_mux_event_route_update_updates_tray() {
    let event = IpcEvent::RouteUpdate {
        client: "claude".to_string(),
        server: "test-server".to_string(),
        count: 5,
        p99_ms: 120,
    };
    let response = MuxControlResponse::Event(event);
    let json = serde_json::to_string(&response).unwrap();
    let decoded: MuxControlResponse = serde_json::from_str(&json).unwrap();
    if let MuxControlResponse::Event(IpcEvent::RouteUpdate { client, .. }) = decoded {
        assert_eq!(client, "claude");
    } else {
        panic!("Decoding failed");
    }
}

#[tokio::test]
async fn decode_mux_event_client_drift_emits_tray_alert() {
    let event = IpcEvent::ClientDrift {
        client: "codex".to_string(),
        non_mux_paths: vec!["/path/to/bad/unix.sock".to_string()],
    };
    let response = MuxControlResponse::Event(event);
    let json = serde_json::to_string(&response).unwrap();
    let decoded: MuxControlResponse = serde_json::from_str(&json).unwrap();
    if let MuxControlResponse::Event(IpcEvent::ClientDrift { client, .. }) = decoded {
        assert_eq!(client, "codex");
    } else {
        panic!("Decoding failed");
    }
}

#[tokio::test]
async fn verify_client_returns_drift_on_non_mux_servers() {
    let response = MuxControlResponse::VerifyResult(VerifyResult {
        ok: false,
        non_mux_servers: vec![NonMuxEntry {
            client: "gemini".to_string(),
            path: "/tmp/old.sock".to_string(),
            line: 42,
            server_name: "test".to_string(),
        }],
    });
    let json = serde_json::to_string(&response).unwrap();
    let decoded: MuxControlResponse = serde_json::from_str(&json).unwrap();
    if let MuxControlResponse::VerifyResult(res) = decoded {
        assert!(!res.ok);
        assert_eq!(res.non_mux_servers.len(), 1);
    } else {
        panic!("Decoding failed");
    }
}

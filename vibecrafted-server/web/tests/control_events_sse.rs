//! Integration tests for `GET /api/control/events` (SSE).
//!
//! Run with:
//! ```text
//! cargo test -p vibecrafted-server-web --features ssr --test control_events_sse
//! ```
//!
//! Each test uses an isolated `VIBECRAFTED_HOME` tmp dir so the read-only
//! control-plane contract is exercised against a real `events.jsonl` path.

#![cfg(feature = "ssr")]

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;

use std::net::SocketAddr;

use axum::body::Body;
use axum::http::{Request, StatusCode, header};
use futures_util::StreamExt;
use leptos::config::{Env, LeptosOptions};
use tower::ServiceExt;
use vibecrafted_server_web::control::api::control_routes;

/// Serialise env mutation — `VIBECRAFTED_HOME` is process-global.
static ENV_LOCK: Mutex<()> = Mutex::new(());

struct TempHome {
    path: PathBuf,
    _guard: std::sync::MutexGuard<'static, ()>,
}

impl TempHome {
    fn new(label: &str) -> Self {
        let guard = ENV_LOCK.lock().unwrap_or_else(|p| p.into_inner());
        let path = std::env::temp_dir().join(format!(
            "vc-sse-{}-{}-{}",
            label,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        let control = path.join("control_plane");
        fs::create_dir_all(&control).expect("create control_plane");
        // Safety: single-threaded under ENV_LOCK for the test body lifetime.
        unsafe {
            std::env::set_var("VIBECRAFTED_HOME", &path);
            // Fast poll / keepalive so silence tests finish well under 30s.
            std::env::set_var("VC_CONTROL_SSE_POLL_MS", "50");
            std::env::set_var("VC_CONTROL_SSE_KEEPALIVE_MS", "200");
        }
        Self {
            path,
            _guard: guard,
        }
    }

    fn control_plane(&self) -> PathBuf {
        self.path.join("control_plane")
    }

    fn events_path(&self) -> PathBuf {
        self.control_plane().join("events.jsonl")
    }

    fn append_event_line(&self, line: &str) {
        use std::io::Write;
        let mut f = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.events_path())
            .expect("open events.jsonl");
        writeln!(f, "{line}").expect("append event line");
    }

    fn snapshot_tree(&self) -> Vec<PathBuf> {
        let mut out = Vec::new();
        walk(&self.path, &mut out);
        out.sort();
        out
    }
}

impl Drop for TempHome {
    fn drop(&mut self) {
        unsafe {
            std::env::remove_var("VIBECRAFTED_HOME");
            std::env::remove_var("VC_CONTROL_SSE_POLL_MS");
            std::env::remove_var("VC_CONTROL_SSE_KEEPALIVE_MS");
        }
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        if p.is_dir() {
            walk(&p, out);
        }
        out.push(p);
    }
}

fn test_app() -> axum::Router {
    let opts = LeptosOptions::builder()
        .output_name("vibecrafted-server-web-test")
        .site_root("target/site-test")
        .site_pkg_dir("pkg")
        .env(Env::PROD)
        .site_addr("127.0.0.1:0".parse::<SocketAddr>().expect("addr"))
        .reload_port(0)
        .build();
    control_routes().with_state(opts)
}

async fn collect_sse_until(
    body: Body,
    mut pred: impl FnMut(&str) -> bool,
    timeout: Duration,
) -> String {
    let mut collected = String::new();
    let mut stream = body.into_data_stream();
    let deadline = tokio::time::Instant::now() + timeout;
    loop {
        let remaining = deadline.saturating_duration_since(tokio::time::Instant::now());
        if remaining.is_zero() {
            break;
        }
        match tokio::time::timeout(remaining, stream.next()).await {
            Ok(Some(Ok(chunk))) => {
                let text = String::from_utf8_lossy(&chunk);
                collected.push_str(&text);
                if pred(&collected) {
                    break;
                }
            }
            Ok(Some(Err(err))) => panic!("body stream error: {err}"),
            Ok(None) => break,
            Err(_) => break,
        }
    }
    collected
}

fn event_line(run_id: &str, kind: &str, message: &str) -> String {
    format!(
        r#"{{"ts":"2026-07-21T06:00:00+00:00","run_id":"{run_id}","kind":"{kind}","message":"{message}","payload":{{}}}}"#
    )
}

/// Parse SSE `id:` fields in order of appearance.
fn sse_ids(body: &str) -> Vec<String> {
    body.lines()
        .filter_map(|line| line.strip_prefix("id: ").map(str::to_string))
        .collect()
}

fn sse_data_payloads(body: &str) -> Vec<String> {
    body.lines()
        .filter_map(|line| line.strip_prefix("data: ").map(str::to_string))
        .collect()
}

#[tokio::test]
async fn sse_streams_appended_event_with_id_and_json_data() {
    let home = TempHome::new("append");
    let line_a = event_line("run-a", "spawn", "started");
    home.append_event_line(&line_a);

    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events?since=0")
                .header(header::ACCEPT, "text/event-stream")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot");

    assert_eq!(response.status(), StatusCode::OK);
    let ct = response
        .headers()
        .get(header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    assert!(
        ct.starts_with("text/event-stream"),
        "content-type must be text/event-stream, got {ct:?}"
    );

    let body = collect_sse_until(
        response.into_body(),
        |s| s.contains("data: ") && s.contains("run-a"),
        Duration::from_secs(3),
    )
    .await;

    assert!(
        body.contains("id: "),
        "SSE frame must carry id: cursor\n{body}"
    );
    let data = sse_data_payloads(&body);
    assert!(!data.is_empty(), "expected data: frames\n{body}");
    let parsed: serde_json::Value = serde_json::from_str(&data[0]).expect("data JSON must parse");
    assert_eq!(parsed["run_id"], "run-a");
    assert_eq!(parsed["kind"], "spawn");
    assert_eq!(parsed["message"], "started");
}

#[tokio::test]
async fn sse_reconnect_with_since_cursor_does_not_duplicate_or_skip() {
    let home = TempHome::new("reconnect");
    let line_a = event_line("run-1", "spawn", "one");
    let line_b = event_line("run-1", "progress", "two");
    let line_c = event_line("run-1", "done", "three");
    home.append_event_line(&line_a);
    home.append_event_line(&line_b);
    home.append_event_line(&line_c);

    // Full drain first to learn middle cursor (after event B).
    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events?since=0")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot full");
    let full = collect_sse_until(
        response.into_body(),
        |s| sse_ids(s).len() >= 3,
        Duration::from_secs(3),
    )
    .await;
    let ids = sse_ids(&full);
    assert_eq!(ids.len(), 3, "expected three id frames\n{full}");
    let mid_cursor = &ids[1]; // after event B

    // Reconnect from middle cursor: should see only event C (no A/B, no dup of B).
    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri(format!("/api/control/events?since={mid_cursor}"))
                .header("Last-Event-ID", mid_cursor.as_str())
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot resume");
    let resumed = collect_sse_until(
        response.into_body(),
        |s| s.contains("\"message\":\"three\""),
        Duration::from_secs(3),
    )
    .await;

    let messages: Vec<_> = sse_data_payloads(&resumed)
        .into_iter()
        .filter_map(|d| {
            serde_json::from_str::<serde_json::Value>(&d)
                .ok()
                .and_then(|v| v["message"].as_str().map(str::to_string))
        })
        .collect();
    assert_eq!(
        messages,
        vec!["three".to_string()],
        "reconnect must emit only events after mid cursor\n{resumed}"
    );
    assert!(
        !resumed.contains("\"message\":\"one\"") && !resumed.contains("\"message\":\"two\""),
        "must not re-emit earlier events\n{resumed}"
    );
}

#[tokio::test]
async fn sse_last_event_id_header_resumes_without_query() {
    let home = TempHome::new("last-event-id");
    let line_a = event_line("run-x", "spawn", "alpha");
    let line_b = event_line("run-x", "done", "beta");
    home.append_event_line(&line_a);
    home.append_event_line(&line_b);

    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events?since=0")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot");
    let full = collect_sse_until(
        response.into_body(),
        |s| sse_ids(s).len() >= 2,
        Duration::from_secs(3),
    )
    .await;
    let first_id = sse_ids(&full).into_iter().next().expect("first id");

    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events")
                .header("Last-Event-ID", first_id.as_str())
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot last-event-id");
    let resumed = collect_sse_until(
        response.into_body(),
        |s| s.contains("\"message\":\"beta\""),
        Duration::from_secs(3),
    )
    .await;
    let messages: Vec<_> = sse_data_payloads(&resumed)
        .into_iter()
        .filter_map(|d| {
            serde_json::from_str::<serde_json::Value>(&d)
                .ok()
                .and_then(|v| v["message"].as_str().map(str::to_string))
        })
        .collect();
    assert_eq!(messages, vec!["beta".to_string()], "body:\n{resumed}");
}

#[tokio::test]
async fn sse_heartbeat_comment_on_empty_stream() {
    let _home = TempHome::new("heartbeat");
    // No events.jsonl — pure silence; keepalive must still fire.
    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events?since=0")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot empty");

    assert_eq!(response.status(), StatusCode::OK);
    let body = collect_sse_until(
        response.into_body(),
        |s| s.contains(": ping") || s.contains(":ping"),
        Duration::from_secs(3),
    )
    .await;
    assert!(
        body.contains(": ping") || body.contains(":ping"),
        "expected SSE comment heartbeat `: ping` under silence\n{body:?}"
    );
}

#[tokio::test]
async fn sse_session_writes_nothing_to_control_plane() {
    let home = TempHome::new("readonly");
    home.append_event_line(&event_line("run-ro", "spawn", "hi"));
    let before = home.snapshot_tree();
    let before_meta: Vec<_> = before
        .iter()
        .filter_map(|p| {
            fs::metadata(p)
                .ok()
                .map(|m| (p.clone(), m.len(), m.modified().ok()))
        })
        .collect();

    let app = test_app();
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/control/events?since=0")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .expect("oneshot");
    let _body = collect_sse_until(
        response.into_body(),
        |s| s.contains("run-ro"),
        Duration::from_secs(3),
    )
    .await;

    // Drop response so stream task ends; give a beat for any deferred write.
    tokio::time::sleep(Duration::from_millis(100)).await;

    let after = home.snapshot_tree();
    assert_eq!(
        before, after,
        "server must not create new files under control-plane during SSE"
    );
    for (path, len, mtime) in &before_meta {
        let meta = fs::metadata(path).expect("metadata after");
        assert_eq!(meta.len(), *len, "file size changed: {}", path.display());
        // events.jsonl is only read — mtime must not advance from a write.
        if path.file_name().and_then(|n| n.to_str()) == Some("events.jsonl") {
            assert_eq!(
                meta.modified().ok(),
                *mtime,
                "events.jsonl mtime changed (server wrote?): {}",
                path.display()
            );
        }
    }
}

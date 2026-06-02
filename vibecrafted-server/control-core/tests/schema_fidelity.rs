//! Golden-JSON drift guard.
//!
//! These tests pin `control-core`'s serde model to **real** on-disk samples
//! captured from `~/.vibecrafted/control_plane/` on 2026-05-31, so a future
//! schema change in the Python writer (`control_plane.py`) that this crate
//! does not mirror fails loudly here instead of silently dropping a field.
//!
//! Documented field drift vs the Python types (see also the design doc):
//! * `cursor` — present on the Rust `Event` (byte offset), absent from on-disk
//!   `events.jsonl` lines. It defaults to 0 on deserialize and is stamped by
//!   the reader. Excluded from the line round-trip assertion below.
//! * `_coerce_int` — Rust strips a single leading `-`; Python's `lstrip("-")`
//!   strips all. Both reject bools and accept digit-strings; the difference is
//!   only the pathological `"--5"` input, which never occurs on disk.

use std::collections::BTreeSet;

use chrono::Duration;
use control_core::model::{coerce_int_value, AgentMeta, Health};
use control_core::{parse_iso, state_health, EventStream, RunStatus};

/// Real `runs/marb-000.json` — a terminal run (exit_code present, lock absent).
const GOLDEN_RUN_FINAL: &str = r#"{
  "run_id": "marb-000",
  "state": "completed",
  "agent": "codex",
  "skill": "marbles",
  "mode": "implement",
  "root": "/Users/maciejgad/hosted/VetCoders/vista",
  "operator_session": "vista-marb-000",
  "latest_report": "/Users/maciejgad/.vibecrafted/artifacts/VetCoders/Vista/2026_0329/reports/report.md",
  "latest_transcript": "/Users/maciejgad/.vibecrafted/artifacts/VetCoders/Vista/2026_0329/reports/report.transcript.log",
  "last_error": "",
  "updated_at": "2026-03-29T09:21:15.681613+00:00",
  "started_at": "2026-03-29T09:21:15.681613+00:00",
  "health": "final",
  "source": "agent-meta",
  "lock_present": false,
  "exit_code": 0,
  "liveness": "",
  "launcher_pid": null,
  "completed_at": "2026-03-29T09:21:15.681613+00:00",
  "session_id": "",
  "current_loop": null,
  "total_loops": null
}"#;

/// Real `runs/just-194457-58333.json` — an in-flight run with null Options and
/// a live lock.
const GOLDEN_RUN_ACTIVE: &str = r#"{
  "run_id": "just-194457-58333",
  "state": "launching",
  "agent": "claude",
  "skill": "justdo",
  "mode": "implement",
  "root": "/Users/maciejgad/vc-workspace/VetCoders/vibecrafted",
  "operator_session": "vibecrafted-just-194457-58333",
  "latest_report": "/Users/maciejgad/.vibecrafted/artifacts/report.md",
  "latest_transcript": "/Users/maciejgad/.vibecrafted/artifacts/report.transcript.log",
  "last_error": "",
  "updated_at": "2026-06-01T01:45:09.807447+00:00",
  "started_at": "2026-06-01T01:45:09.807447+00:00",
  "health": "active",
  "source": "agent-meta",
  "lock_present": true,
  "exit_code": null,
  "liveness": "pid_alive",
  "launcher_pid": 59321,
  "completed_at": "",
  "session_id": "",
  "current_loop": null,
  "total_loops": null
}"#;

/// Real `*.meta.json` for the same `just-...` run — the raw merge source whose
/// field names differ from `RunStatus`.
const GOLDEN_META: &str = r#"{
  "updated_at": "2026-06-01T01:45:09.807447+00:00",
  "status": "launching",
  "agent": "claude",
  "mode": "implement",
  "root": "/Users/maciejgad/vc-workspace/VetCoders/vibecrafted",
  "input": "/tmp/prompt.md",
  "report": "/Users/maciejgad/.vibecrafted/artifacts/report.md",
  "transcript": "/Users/maciejgad/.vibecrafted/artifacts/report.transcript.log",
  "launcher": "/tmp/launch.sh",
  "prompt_id": "20260531_1944_demo",
  "run_id": "just-194457-58333",
  "loop_nr": 0,
  "skill_code": "just",
  "framework_version": "3.0.0",
  "exit_code": null,
  "launcher_pid": 59321,
  "liveness": "pid_alive"
}"#;

/// A real `events.jsonl` line — note it has no `cursor` field.
const GOLDEN_EVENT_LINE: &str = r#"{"ts": "2026-04-18T14:52:42.135162+00:00", "run_id": "marb-000618-001", "kind": "state", "message": "marb-000618-001 entered failed", "payload": {"previous_state": "", "state": "failed", "agent": "gemini", "skill": "marbles", "mode": "marbles", "health": "final"}}"#;

fn assert_run_roundtrips_without_loss(golden: &str) -> RunStatus {
    let run: RunStatus = serde_json::from_str(golden).expect("RunStatus deserialises");
    let reserialised = serde_json::to_value(&run).expect("RunStatus serialises");
    let original: serde_json::Value = serde_json::from_str(golden).expect("golden is valid JSON");

    // No field gained or lost: the key set is identical.
    let original_keys: BTreeSet<&String> =
        original.as_object().expect("object").keys().collect();
    let reserialised_keys: BTreeSet<&String> =
        reserialised.as_object().expect("object").keys().collect();
    assert_eq!(
        original_keys, reserialised_keys,
        "RunStatus key set drifted from on-disk schema"
    );

    // No value changed: full structural equality (order-independent).
    assert_eq!(
        reserialised, original,
        "RunStatus value drifted on round-trip"
    );
    run
}

#[test]
fn final_run_snapshot_roundtrips() {
    let run = assert_run_roundtrips_without_loss(GOLDEN_RUN_FINAL);
    assert_eq!(run.run_id, "marb-000");
    assert_eq!(run.exit_code, Some(0));
    assert_eq!(run.launcher_pid, None);
    assert!(run.is_terminal(), "completed + exit_code should be terminal");
    assert_eq!(run.health, "final");
}

#[test]
fn active_run_snapshot_roundtrips() {
    let run = assert_run_roundtrips_without_loss(GOLDEN_RUN_ACTIVE);
    assert_eq!(run.run_id, "just-194457-58333");
    // Null Options survive the round-trip as null, not "missing".
    assert_eq!(run.exit_code, None);
    assert_eq!(run.current_loop, None);
    assert_eq!(run.launcher_pid, Some(59321));
    assert!(run.lock_present);
    assert!(!run.is_terminal(), "launching run is not terminal");
}

#[test]
fn meta_normalizes_to_runstatus() {
    let meta: AgentMeta = serde_json::from_str(GOLDEN_META).expect("AgentMeta deserialises");
    let updated = parse_iso("2026-06-01T01:45:09.807447+00:00").expect("parse updated_at");

    // now == updated + 100s → still active.
    let fresh = meta
        .normalize(updated + Duration::seconds(100))
        .expect("normalises");
    assert_eq!(fresh.run_id, "just-194457-58333");
    assert_eq!(fresh.skill, "justdo", "skill_code 'just' maps to 'justdo'");
    assert_eq!(fresh.state, "launching");
    assert_eq!(fresh.source, "agent-meta");
    assert_eq!(fresh.operator_session, "vibecrafted-just-194457-58333");
    assert_eq!(fresh.latest_report, "/Users/maciejgad/.vibecrafted/artifacts/report.md");
    assert_eq!(fresh.exit_code, None);
    assert_eq!(fresh.launcher_pid, Some(59321));
    assert!(!fresh.lock_present, "meta source never sets lock_present");
    assert_eq!(fresh.health, "active");

    // now == updated + 2000s (> 1200s stall threshold) → stalled.
    let stale = meta
        .normalize(updated + Duration::seconds(2000))
        .expect("normalises");
    assert_eq!(stale.health, "stalled");
}

#[test]
fn health_derivation_matches_python() {
    let updated = "2026-06-01T01:45:09.807447+00:00";
    let base = parse_iso(updated).unwrap();

    // Final state ignores the clock.
    assert_eq!(
        state_health("completed", updated, base + Duration::seconds(99_999)),
        Health::Final
    );
    // Active just under the 1200s threshold.
    assert_eq!(
        state_health("running", updated, base + Duration::seconds(1200)),
        Health::Active
    );
    // Stalled just over it.
    assert_eq!(
        state_health("running", updated, base + Duration::seconds(1201)),
        Health::Stalled
    );
    // Unparseable timestamp → unknown.
    assert_eq!(state_health("running", "", base), Health::Unknown);
}

#[test]
fn coerce_int_matches_python_rules() {
    use serde_json::json;
    assert_eq!(coerce_int_value(&json!(7)), Some(7));
    assert_eq!(coerce_int_value(&json!("7")), Some(7));
    assert_eq!(coerce_int_value(&json!("-7")), Some(-7));
    assert_eq!(coerce_int_value(&json!(true)), None, "bools rejected");
    assert_eq!(coerce_int_value(&json!("abc")), None);
    assert_eq!(coerce_int_value(&json!(null)), None);
}

#[test]
fn event_line_parses_with_default_cursor() {
    let event: control_core::Event =
        serde_json::from_str(GOLDEN_EVENT_LINE).expect("Event line deserialises");
    assert_eq!(event.run_id, "marb-000618-001");
    assert_eq!(event.kind, "state");
    assert_eq!(event.cursor, 0, "absent cursor defaults to 0");
    assert_eq!(
        event.payload.get("state").and_then(|v| v.as_str()),
        Some("failed")
    );
}

#[test]
fn event_cursor_advances_and_skips_partial_tail() {
    // Two complete lines + one partial (mid-write) trailing line.
    let line_a = format!("{GOLDEN_EVENT_LINE}\n");
    let line_b = format!("{GOLDEN_EVENT_LINE}\n");
    let partial = "{\"ts\": \"2026-04-18T14:52:43"; // no newline — simulated mid-append
    let body = format!("{line_a}{line_b}{partial}");

    let dir = std::env::temp_dir().join("control-core-fidelity-events");
    std::fs::create_dir_all(&dir).expect("mkdir temp");
    let path = dir.join("events.jsonl");
    std::fs::write(&path, &body).expect("write events");

    let stream = EventStream::new(&path);
    let batch = stream.read_since(0, &[]).expect("drain");

    // Only the two complete lines are emitted.
    assert_eq!(batch.events.len(), 2);
    // Cursor stops before the partial line so it is re-read once complete.
    let expected_cursor = (line_a.len() + line_b.len()) as u64;
    assert_eq!(batch.cursor, expected_cursor);
    // Each event is stamped with its resume offset.
    assert_eq!(batch.events[0].cursor, line_a.len() as u64);
    assert_eq!(batch.events[1].cursor, expected_cursor);

    // Resuming from the cursor yields nothing new until the line completes.
    let empty = stream.read_since(batch.cursor, &[]).expect("resume drain");
    assert!(empty.events.is_empty());
    assert_eq!(empty.cursor, batch.cursor);

    // Kind filter that matches nothing returns no events but still advances.
    let filtered = stream
        .read_since(0, &["nonexistent".to_string()])
        .expect("filtered drain");
    assert!(filtered.events.is_empty());
    assert_eq!(filtered.cursor, expected_cursor);

    std::fs::remove_file(&path).ok();
}

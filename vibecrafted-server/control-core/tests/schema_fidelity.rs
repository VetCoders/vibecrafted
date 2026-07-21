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
use control_core::model::{
    AgentMeta, DeliveryAxes, DeliverySealRef, DeliveryState, ExecutionState, Health, ProofState,
    coerce_int_value, delivery_axes_for_receipt,
};
use control_core::{EventStream, LifecycleRun, RunStatus, parse_iso, state_health};

// ---------------------------------------------------------------------------
// Delivery-proof kernel axes — fixtures produced by the Python kernel
// (PYTHONPATH=vibecrafted-core python -c with delivery.model / DeliveryAxes /
// lifecycle_runner.delivery_axes_for_receipt). Do not hand-author these
// string values; they are the on-wire contract from the Python source of truth.
// ---------------------------------------------------------------------------

/// `DeliveryAxes(ExecutionState.EXITED, ProofState.PASSED, DeliveryState.SEALED).to_payload()`
const PYTHON_KERNEL_AXES_SEALED: &str = r#"{
  "execution_state": "exited",
  "proof_state": "passed",
  "delivery_state": "sealed"
}"#;

/// Enum value inventory from `list(ExecutionState|ProofState|DeliveryState)`.
const PYTHON_EXECUTION_STATES: &[&str] = &[
    "created",
    "launched",
    "running",
    "exited",
    "interrupted",
    "timed_out",
    "failed",
];
const PYTHON_PROOF_STATES: &[&str] = &[
    "undeclared",
    "declared",
    "running",
    "passed",
    "failed",
    "invalid",
    "stale",
];
const PYTHON_DELIVERY_STATES: &[&str] = &["unverified", "delivered", "sealed", "invalidated"];

/// `delivery_axes_for_receipt("completed", {})` — completed is execution only.
const PYTHON_COMPLETED_RECEIPT_AXES: &str = r#"{
  "execution_state": "exited",
  "proof_state": "undeclared",
  "delivery_state": "unverified"
}"#;

/// Run snapshot with kernel axes present (Python `_project_run_payload` shape).
const GOLDEN_RUN_WITH_DELIVERY_AXES: &str = r#"{
  "run_id": "impl-axes-001",
  "state": "completed",
  "agent": "codex",
  "skill": "implement",
  "mode": "implement",
  "root": "/Users/you/vc-workspace/vetcoders/vibecrafted",
  "operator_session": "vibecrafted-impl-axes-001",
  "latest_report": "/Users/you/.vibecrafted/artifacts/report.md",
  "latest_transcript": "/Users/you/.vibecrafted/artifacts/report.transcript.log",
  "last_error": "",
  "updated_at": "2026-07-21T06:00:00.000000+00:00",
  "started_at": "2026-07-21T05:55:00.000000+00:00",
  "health": "final",
  "source": "agent-meta",
  "lock_present": false,
  "exit_code": 0,
  "liveness": "terminal",
  "launcher_pid": null,
  "completed_at": "2026-07-21T06:00:00.000000+00:00",
  "session_id": "",
  "current_loop": null,
  "total_loops": null,
  "execution_state": "exited",
  "proof_state": "passed",
  "delivery_state": "sealed",
  "seal": {
    "schema": "vibecrafted.delivery-seal.v1",
    "seal_id": "seal-impl-axes-001",
    "issued_at": "2026-07-21T06:00:01.000000+00:00",
    "issuer": "vibecrafted_core.ship",
    "run_id": "impl-axes-001",
    "lifecycle_id": "",
    "cut_id": "cut-1",
    "proof_id": "proof-1",
    "repo": "VetCoders/vibecrafted",
    "branch": "feat/reduce-wrong-assumptions",
    "final_head": "deadbeef",
    "report_sha256": "sha256:abc"
  }
}"#;

/// Real `runs/marb-000.json` — a terminal run (exit_code present, lock absent).
const GOLDEN_RUN_FINAL: &str = r#"{
  "run_id": "marb-000",
  "state": "completed",
  "agent": "codex",
  "skill": "marbles",
  "mode": "implement",
  "root": "/Users/you/hosted/vetcoders/example-app",
  "operator_session": "example-app-marb-000",
  "latest_report": "/Users/you/.vibecrafted/artifacts/vetcoders/example-app/2026_0329/reports/report.md",
  "latest_transcript": "/Users/you/.vibecrafted/artifacts/vetcoders/example-app/2026_0329/reports/report.transcript.log",
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
  "root": "/Users/you/vc-workspace/vetcoders/vibecrafted",
  "operator_session": "vibecrafted-just-194457-58333",
  "latest_report": "/Users/you/.vibecrafted/artifacts/report.md",
  "latest_transcript": "/Users/you/.vibecrafted/artifacts/report.transcript.log",
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
  "root": "/Users/you/vc-workspace/vetcoders/vibecrafted",
  "input": "/tmp/prompt.md",
  "report": "/Users/you/.vibecrafted/artifacts/report.md",
  "transcript": "/Users/you/.vibecrafted/artifacts/report.transcript.log",
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

/// Representative lifecycle `state.json` captured from the Python writer shape
/// on 2026-07-02. Lifecycle state is intentionally nested and must not be folded
/// into the flat `RunStatus` golden schema above.
const GOLDEN_LIFECYCLE_STATE: &str = r#"{
  "schema": "vibecrafted.lifecycle.v1",
  "run_id": "life-ship-260702-123238-24000",
  "workflow": "vc-ship",
  "agent": "codex",
  "root": "/Users/you/vc-workspace/vetcoders/vibecrafted",
  "status": "launching",
  "await_stages": false,
  "parent_run_id": null,
  "operator_actions": [],
  "spec": {"workflow_id": "vc-ship", "agent": "codex"},
  "supervisor": "vibecrafted_core.lifecycle_runner.LifecycleSupervisor",
  "human_controls": [
    "approve_transition",
    "interrupt_workflow",
    "force_audit",
    "accept_dou",
    "choose_fallback_stage"
  ],
  "state_path": "/Users/you/.vibecrafted/control_plane/lifecycle_runs/life-ship-260702-123238-24000/state.json",
  "report_path": "/Users/you/.vibecrafted/control_plane/lifecycle_runs/life-ship-260702-123238-24000/report.md",
  "transcript_path": "/Users/you/.vibecrafted/control_plane/lifecycle_runs/life-ship-260702-123238-24000/transcript.log",
  "context_atlas": {"ok": true},
  "manifest": {"id": "vc-ship"},
  "baton": {
    "from_stage": "scaffold",
    "from_phase": "read",
    "next_stage": "implement",
    "next_agent": "codex",
    "reason": "stage_launched_without_await",
    "previous_reports": ["/Users/you/.vibecrafted/artifacts/report.md"],
    "dou_index": null,
    "audit_after": "",
    "fallback_stage": ""
  },
  "stages": [{
    "id": "scaffold",
    "name": "VC Scaffold",
    "workflow": "scaffold",
    "phase": "read",
    "agent": "codex",
    "status": "completed",
    "launch": {"report": "/Users/you/.vibecrafted/artifacts/report.md"},
    "await": {},
    "commit_before": "abc123",
    "commit_after": "def456",
    "changed_files": [],
    "new_commits": [],
    "transition": {
      "next_stage": "implement",
      "requested_next_stage": "",
      "next_agent": "codex",
      "requested_next_agent": "",
      "conditions": ["stage_completed"],
      "fallback_stage": "",
      "audit_after": ""
    }
  }],
  "dou_index": {"value": 0, "stage": "audit", "report": "/Users/you/.vibecrafted/artifacts/report.md"},
  "accepted_dou": 1,
  "accepted_dou_findings": [{"id": "accepted-1"}]
}"#;

fn assert_run_roundtrips_without_loss(golden: &str) -> RunStatus {
    let run: RunStatus = serde_json::from_str(golden).expect("RunStatus deserialises");
    let reserialised = serde_json::to_value(&run).expect("RunStatus serialises");
    let original: serde_json::Value = serde_json::from_str(golden).expect("golden is valid JSON");

    // No field gained or lost: the key set is identical.
    let original_keys: BTreeSet<&String> = original.as_object().expect("object").keys().collect();
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
    assert!(
        run.is_terminal(),
        "completed + exit_code should be terminal"
    );
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
    assert_eq!(
        fresh.latest_report,
        "/Users/you/.vibecrafted/artifacts/report.md"
    );
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
fn lifecycle_state_parses_and_projects_without_runstatus_schema_drift() {
    let lifecycle: LifecycleRun =
        serde_json::from_str(GOLDEN_LIFECYCLE_STATE).expect("LifecycleRun deserialises");
    let summary = lifecycle.summary("2026-07-02T19:32:38Z".to_string(), None);

    assert_eq!(lifecycle.run_id, "life-ship-260702-123238-24000");
    assert_eq!(
        lifecycle.schema.as_deref(),
        Some("vibecrafted.lifecycle.v1")
    );
    assert_eq!(summary.schema.as_deref(), Some("vibecrafted.lifecycle.v1"));
    assert_eq!(summary.workflow, "vc-ship");
    assert_eq!(summary.current_stage, "scaffold");
    assert_eq!(summary.next_stage, "implement");
    assert_eq!(summary.dou_index, Some(0));
    assert_eq!(summary.dou_readiness, "zero");
    assert_eq!(summary.accepted_dou, 1);

    let projected = lifecycle.to_run_status("2026-07-02T19:32:38Z".to_string(), None);
    assert_eq!(projected.source, "lifecycle_runs");
    assert_eq!(projected.skill, "vc-ship");
    assert_eq!(projected.mode, "lifecycle");
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

// ---------------------------------------------------------------------------
// G1 — three-axis delivery projection fidelity (Python kernel = source of truth)
// ---------------------------------------------------------------------------

#[test]
fn python_kernel_axes_payload_deserialises_1_to_1() {
    let axes: DeliveryAxes =
        serde_json::from_str(PYTHON_KERNEL_AXES_SEALED).expect("kernel axes payload");
    assert_eq!(axes.execution_state, ExecutionState::Exited);
    assert_eq!(axes.proof_state, ProofState::Passed);
    assert_eq!(axes.delivery_state, DeliveryState::Sealed);

    let reserialised = serde_json::to_value(&axes).expect("serialize");
    let original: serde_json::Value =
        serde_json::from_str(PYTHON_KERNEL_AXES_SEALED).expect("original");
    assert_eq!(
        reserialised, original,
        "DeliveryAxes must round-trip the Python to_payload() shape"
    );
}

#[test]
fn python_enum_variants_match_string_wire_values() {
    for raw in PYTHON_EXECUTION_STATES {
        let parsed: ExecutionState =
            serde_json::from_value(serde_json::Value::String((*raw).to_string()))
                .unwrap_or_else(|e| panic!("ExecutionState::{raw}: {e}"));
        assert_eq!(parsed.as_str(), *raw);
    }
    for raw in PYTHON_PROOF_STATES {
        let parsed: ProofState =
            serde_json::from_value(serde_json::Value::String((*raw).to_string()))
                .unwrap_or_else(|e| panic!("ProofState::{raw}: {e}"));
        assert_eq!(parsed.as_str(), *raw);
    }
    for raw in PYTHON_DELIVERY_STATES {
        let parsed: DeliveryState =
            serde_json::from_value(serde_json::Value::String((*raw).to_string()))
                .unwrap_or_else(|e| panic!("DeliveryState::{raw}: {e}"));
        assert_eq!(parsed.as_str(), *raw);
    }
}

#[test]
fn run_with_kernel_axes_and_seal_deserialises() {
    let run: RunStatus =
        serde_json::from_str(GOLDEN_RUN_WITH_DELIVERY_AXES).expect("run with axes");
    assert_eq!(run.execution_state, Some(ExecutionState::Exited));
    assert_eq!(run.proof_state, Some(ProofState::Passed));
    assert_eq!(run.delivery_state, Some(DeliveryState::Sealed));
    let seal = run.seal.expect("seal present");
    assert_eq!(seal.seal_id, "seal-impl-axes-001");
    assert_eq!(seal.schema, "vibecrafted.delivery-seal.v1");
    assert_eq!(seal.run_id, "impl-axes-001");
    // completed + exit 0 must not be misread as inventing delivery: delivery
    // comes from the explicit field (sealed), not from state.
    assert_eq!(run.state, "completed");
    assert_eq!(run.delivery_state, Some(DeliveryState::Sealed));
}

#[test]
fn legacy_run_without_delivery_section_has_absent_axes() {
    // GOLDEN_RUN_FINAL is a pre-kernel snapshot: no execution_state/proof/delivery.
    let run: RunStatus = serde_json::from_str(GOLDEN_RUN_FINAL).expect("legacy final");
    assert_eq!(run.state, "completed");
    assert_eq!(run.exit_code, Some(0));
    assert_eq!(
        run.execution_state, None,
        "legacy snapshot must not invent execution_state"
    );
    assert_eq!(
        run.proof_state, None,
        "legacy snapshot must not invent proof_state"
    );
    assert_eq!(
        run.delivery_state, None,
        "legacy snapshot must not invent delivery_state from completed"
    );
    assert_eq!(run.seal, None);

    // Round-trip must not inject null axes keys (skip_serializing_if).
    let reserialised = serde_json::to_value(&run).expect("serialize");
    let obj = reserialised.as_object().expect("object");
    assert!(
        !obj.contains_key("execution_state")
            && !obj.contains_key("proof_state")
            && !obj.contains_key("delivery_state")
            && !obj.contains_key("seal"),
        "absent axes must stay absent on serialise, got keys {:?}",
        obj.keys().collect::<Vec<_>>()
    );
}

#[test]
fn delivery_axes_for_receipt_never_promotes_completed_to_delivered() {
    // Verbatim Python: delivery_axes_for_receipt("completed", {}) →
    // execution=exited, proof=undeclared, delivery=unverified.
    let expected: DeliveryAxes =
        serde_json::from_str(PYTHON_COMPLETED_RECEIPT_AXES).expect("python fixture");
    let projected = delivery_axes_for_receipt("completed", None, None, None);
    assert_eq!(projected, expected);
    assert_ne!(projected.delivery_state, DeliveryState::Delivered);
    assert_ne!(projected.delivery_state, DeliveryState::Sealed);

    // artifact_ok is not a delivery signal — explicit None axes only.
    let with_artifact_hint = delivery_axes_for_receipt("completed", None, None, None);
    assert_eq!(with_artifact_hint.delivery_state, DeliveryState::Unverified);
    assert_eq!(with_artifact_hint.proof_state, ProofState::Undeclared);

    // Explicit seal fields on the receipt win.
    let explicit = delivery_axes_for_receipt(
        "completed",
        Some(ExecutionState::Exited),
        Some(ProofState::Passed),
        Some(DeliveryState::Sealed),
    );
    assert_eq!(explicit.delivery_state, DeliveryState::Sealed);
    assert_eq!(explicit.proof_state, ProofState::Passed);
}

#[test]
fn lifecycle_state_projects_axes_per_stage_and_run() {
    let mut lifecycle: LifecycleRun =
        serde_json::from_str(GOLDEN_LIFECYCLE_STATE).expect("LifecycleRun");
    // On-disk lifecycle state has no axes section (verified against real
    // control_plane/lifecycle_runs/*/state.json). Projection fills them.
    assert_eq!(lifecycle.execution_state, None);
    assert_eq!(lifecycle.stages[0].execution_state, None);

    lifecycle.project_delivery_axes();

    // Run status "launching" → execution launched; proof/delivery stay safe defaults.
    assert_eq!(lifecycle.execution_state, Some(ExecutionState::Launched));
    assert_eq!(lifecycle.proof_state, Some(ProofState::Undeclared));
    assert_eq!(lifecycle.delivery_state, Some(DeliveryState::Unverified));

    // Stage status "completed" → execution exited, NOT delivery sealed.
    let stage = &lifecycle.stages[0];
    assert_eq!(stage.status, "completed");
    assert_eq!(stage.execution_state, Some(ExecutionState::Exited));
    assert_eq!(stage.proof_state, Some(ProofState::Undeclared));
    assert_eq!(stage.delivery_state, Some(DeliveryState::Unverified));
}

#[test]
fn seal_ref_deserialises_kernel_subset() {
    let seal: DeliverySealRef = serde_json::from_str(
        r#"{
          "schema": "vibecrafted.delivery-seal.v1",
          "seal_id": "s1",
          "issued_at": "2026-07-21T00:00:00+00:00",
          "issuer": "ship",
          "run_id": "r1",
          "lifecycle_id": "life-1",
          "cut_id": "c1",
          "proof_id": "p1",
          "repo": "VetCoders/vibecrafted",
          "branch": "main",
          "final_head": "abc",
          "report_sha256": "sha256:x"
        }"#,
    )
    .expect("seal ref");
    assert_eq!(seal.seal_id, "s1");
    assert_eq!(seal.lifecycle_id, "life-1");
}

#[test]
fn source_has_no_completed_to_delivery_mapping() {
    // Grep-gate: control-core must never map completed → delivered/sealed.
    let model = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/src/model.rs"));
    let read = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/src/read.rs"));
    for (name, src) in [("model.rs", model), ("read.rs", read)] {
        for bad in [
            "completed\" => DeliveryState::Delivered",
            "completed\" => DeliveryState::Sealed",
            "\"completed\" => Some(DeliveryState::Delivered)",
            "\"completed\" => Some(DeliveryState::Sealed)",
            "state == \"completed\" && delivery",
            "DeliveryState::Delivered // completed",
            "DeliveryState::Sealed // completed",
        ] {
            assert!(
                !src.contains(bad),
                "{name} must not contain completed→delivery mapping: {bad}"
            );
        }
    }
}

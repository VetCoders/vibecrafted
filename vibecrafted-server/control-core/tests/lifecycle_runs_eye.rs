//! Read-only Rust eye on lifecycle runs written by the Python lifecycle runner.

use std::fs;
use std::path::{Path, PathBuf};

use chrono::Utc;
use control_core::ControlPlane;
use serde_json::json;

fn temp_home(name: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    std::env::temp_dir().join(format!("control-core-{name}-{nanos}"))
}

fn write_lifecycle_run(home: &Path, run_id: &str, state_dou: Option<i64>) {
    let run_dir = home
        .join("control_plane")
        .join("lifecycle_runs")
        .join(run_id);
    fs::create_dir_all(&run_dir).expect("lifecycle run dir");

    let state_path = run_dir.join("state.json");
    let report_path = run_dir.join("report.md");
    let transcript_path = run_dir.join("transcript.log");
    fs::write(&report_path, "---\ndou_index: 0\n---\n# lifecycle report\n").expect("report");
    fs::write(&transcript_path, "stage transcript\n").expect("transcript");

    let mut state = json!({
        "run_id": run_id,
        "workflow": "vc-ship",
        "agent": "codex",
        "root": "/tmp/vibecrafted-lifecycle",
        "status": "launching",
        "await_stages": false,
        "parent_run_id": null,
        "operator_actions": [
            {"action": "approve_transition", "at": "2026-07-02T12:00:00-0700", "details": {"next_stage": "implement"}}
        ],
        "spec": {"workflow_id": "vc-ship", "agent": "codex"},
        "supervisor": "vibecrafted_core.lifecycle_runner.LifecycleSupervisor",
        "human_controls": ["approve_transition", "interrupt_workflow", "accept_dou"],
        "state_path": state_path.to_string_lossy(),
        "report_path": report_path.to_string_lossy(),
        "transcript_path": transcript_path.to_string_lossy(),
        "context_atlas": {"ok": true},
        "manifest": {"id": "vc-ship"},
        "baton": {
            "from_stage": "scaffold",
            "from_phase": "read",
            "next_stage": "implement",
            "next_agent": "codex",
            "reason": "stage_launched_without_await",
            "previous_reports": [report_path.to_string_lossy()],
            "dou_index": null
        },
        "stages": [{
            "id": "scaffold",
            "name": "VC Scaffold",
            "workflow": "scaffold",
            "phase": "read",
            "agent": "codex",
            "status": "completed",
            "launch": {"report": report_path.to_string_lossy()},
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
        "accepted_dou": 2,
        "accepted_dou_findings": [{"id": "accepted-1"}]
    });

    if let Some(value) = state_dou {
        state["dou_index"] = json!({
            "value": value,
            "stage": "audit",
            "report": report_path.to_string_lossy()
        });
    }

    fs::write(
        &state_path,
        serde_json::to_string_pretty(&state).expect("serialise state"),
    )
    .expect("state");
}

#[test]
fn resolve_lifecycle_run_returns_full_nested_state() {
    let home = temp_home("lifecycle-full");
    let run_id = "life-ship-smoke-full";
    write_lifecycle_run(&home, run_id, Some(0));

    let plane = ControlPlane::new(&home);
    let run = plane
        .resolve_lifecycle_run(run_id)
        .expect("lifecycle run resolved");

    assert_eq!(run.run_id, run_id);
    assert_eq!(run.workflow, "vc-ship");
    assert_eq!(run.baton.next_stage, "implement");
    assert_eq!(run.stages[0].id, "scaffold");
    assert_eq!(run.dou_index.and_then(|dou| dou.value), Some(0));
}

#[test]
fn lookup_run_projects_lifecycle_run_into_flat_status() {
    let home = temp_home("lifecycle-lookup");
    let run_id = "life-ship-smoke-lookup";
    write_lifecycle_run(&home, run_id, Some(0));

    let plane = ControlPlane::new(&home);
    let run = plane.lookup_run(run_id).expect("flat projection resolved");

    assert_eq!(run.run_id, run_id);
    assert_eq!(run.state, "launching");
    assert_eq!(run.skill, "vc-ship");
    assert_eq!(run.mode, "lifecycle");
    assert_eq!(run.source, "lifecycle_runs");
    assert!(run.latest_report.ends_with("report.md"));
    assert!(run.latest_transcript.ends_with("transcript.log"));
}

#[test]
fn compute_view_surfaces_lifecycle_projection() {
    let home = temp_home("lifecycle-view");
    let run_id = "life-ship-smoke-view";
    write_lifecycle_run(&home, run_id, Some(0));

    let plane = ControlPlane::new(&home);
    let view = plane.compute_view(Utc::now());

    assert!(
        view.active_runs
            .iter()
            .chain(view.recent_runs.iter())
            .any(|run| run.run_id == run_id && run.source == "lifecycle_runs"),
        "compute_view includes lifecycle run projections"
    );
}

#[test]
fn lifecycle_summaries_surface_baton_and_report_dou_fallback() {
    let home = temp_home("lifecycle-summary");
    let run_id = "life-ship-smoke-summary";
    write_lifecycle_run(&home, run_id, None);

    let plane = ControlPlane::new(&home);
    let summaries = plane.load_lifecycle_run_summaries();
    let summary = summaries
        .iter()
        .find(|summary| summary.run_id == run_id)
        .expect("summary present");

    assert_eq!(summary.workflow, "vc-ship");
    assert_eq!(summary.current_stage, "scaffold");
    assert_eq!(summary.next_stage, "implement");
    assert_eq!(summary.next_agent, "codex");
    assert_eq!(summary.human_controls_count, 3);
    assert_eq!(summary.operator_actions_count, 1);
    assert_eq!(summary.dou_index, Some(0));
    assert_eq!(summary.dou_readiness, "zero");
    assert_eq!(summary.accepted_dou, 2, "explicit accepted_dou wins");
}

#[test]
fn lifecycle_summary_reads_live_dou_from_latest_stage_report() {
    let home = temp_home("lifecycle-stage-report");
    let run_id = "life-ship-smoke-stage-report";
    write_lifecycle_run(&home, run_id, None);

    let run_dir = home
        .join("control_plane")
        .join("lifecycle_runs")
        .join(run_id);
    let state_path = run_dir.join("state.json");
    let lifecycle_report_path = run_dir.join("report.md");
    let worker_report_path = run_dir.join("worker-report.md");
    fs::write(&lifecycle_report_path, "# lifecycle report without DoU\n")
        .expect("lifecycle report");
    fs::write(
        &worker_report_path,
        "---\ndou_index: 0\n---\n# worker ZERO DoU report\n",
    )
    .expect("worker report");

    let mut state: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&state_path).expect("state text"))
            .expect("state json");
    state["dou_index"] = serde_json::Value::Null;
    state["stages"][0]["launch"]["report"] = json!(worker_report_path.to_string_lossy());
    fs::write(
        &state_path,
        serde_json::to_string_pretty(&state).expect("serialise state"),
    )
    .expect("rewrite state");

    let plane = ControlPlane::new(&home);
    let summary = plane
        .load_lifecycle_run_summaries()
        .into_iter()
        .find(|summary| summary.run_id == run_id)
        .expect("summary present");

    assert_eq!(
        summary.dou_index,
        Some(0),
        "no-await lifecycle status reads the launched worker report before the lifecycle report"
    );
    assert_eq!(summary.dou_readiness, "zero");
}

#[test]
fn lifecycle_summary_falls_back_to_canonical_files_when_embedded_paths_are_stale() {
    let home = temp_home("lifecycle-stale-paths");
    let run_id = "life-ship-smoke-stale-paths";
    write_lifecycle_run(&home, run_id, None);

    let state_path = home
        .join("control_plane")
        .join("lifecycle_runs")
        .join(run_id)
        .join("state.json");
    let mut state: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&state_path).expect("state text"))
            .expect("state json");
    state["state_path"] = json!("/tmp/vibecrafted-missing-state.json");
    state["report_path"] = json!("/tmp/vibecrafted-missing-report.md");
    fs::write(
        &state_path,
        serde_json::to_string_pretty(&state).expect("serialise stale-path state"),
    )
    .expect("rewrite state");

    let plane = ControlPlane::new(&home);
    let summary = plane
        .load_lifecycle_run_summaries()
        .into_iter()
        .find(|summary| summary.run_id == run_id)
        .expect("summary present");

    assert_eq!(
        summary.dou_index,
        Some(0),
        "canonical report.md remains the DoU fallback when embedded report_path is stale"
    );
    assert!(
        !summary.updated_at.is_empty(),
        "canonical state.json mtime remains the summary timestamp when embedded state_path is stale"
    );
}

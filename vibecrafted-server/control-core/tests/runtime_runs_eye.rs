//! The frontend (Rust) eye on the runtime-state contract: a still-launching run
//! lives in `runtime_runs/<id>/` before the snapshot sync merges it into
//! `runs/<id>.json`. `lookup_run` must resolve it there (Niezmiennik 3 — one
//! contract, many eyes) instead of a silent miss, mirroring
//! `control_plane.resolve_run` on the Python side.

use std::fs;
use std::path::PathBuf;

use control_core::ControlPlane;

fn temp_home(name: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    std::env::temp_dir().join(format!("control-core-{name}-{nanos}"))
}

#[test]
fn lookup_run_resolves_a_launching_run_from_runtime_runs() {
    let home = temp_home("runtime-runs-eye");
    let run_id = "marb-260615-194454-80000";
    let run_dir = home.join("control_plane").join("runtime_runs").join(run_id);
    fs::create_dir_all(&run_dir).expect("run dir");
    // The runtime writes transcript.log at launch; meta.json is often absent.
    fs::write(run_dir.join("transcript.log"), "launching-bytes\n").expect("transcript");
    // Deliberately no runs/<id>.json snapshot — the sync has not merged it yet.

    let plane = ControlPlane::new(&home);
    let run = plane
        .lookup_run(run_id)
        .expect("run resolved from runtime_runs");

    assert_eq!(run.run_id, run_id);
    assert_eq!(run.state, "launching");
    assert_eq!(run.source, "runtime_runs");
    assert!(!run.is_terminal(), "a launching run is not terminal");
    assert!(
        run.latest_transcript.ends_with("transcript.log"),
        "carries the runtime transcript path: {}",
        run.latest_transcript
    );
}

#[test]
fn lookup_run_returns_none_when_run_not_on_disk_yet() {
    let home = temp_home("runtime-runs-eye-miss");
    fs::create_dir_all(home.join("control_plane")).expect("cp dir");

    let plane = ControlPlane::new(&home);
    assert!(
        plane.lookup_run("ghost-run").is_none(),
        "a run with nothing on disk resolves to None (still launching -> await)"
    );
}

//! Read-only smoke for the live control plane.
//!
//! Proves the read API against real `~/.vibecrafted/control_plane/` data (or
//! `$VIBECRAFTED_HOME`). Writes nothing. A typed, read-only echo of what the
//! Python `control_plane status` CLI surfaces.
//!
//! ```text
//! cargo run -p control-core --example dump
//! ```

use chrono::Utc;
use control_core::ControlPlane;

fn main() {
    let plane = ControlPlane::from_env();
    println!("control_plane: {}", plane.control_plane_home().display());

    let snapshots = plane.load_snapshots();
    println!("\nsnapshots: {} run(s)", snapshots.len());
    for run in snapshots.iter().take(10) {
        println!(
            "  {:<22} {:<10} {:<8} {:<8} {}",
            run.run_id, run.state, run.health, run.agent, run.skill
        );
    }

    let view = plane.compute_view(Utc::now());
    println!(
        "\ncompute_view (merge-in-Rust): {} active, {} recent, {} warning(s)",
        view.active_runs.len(),
        view.recent_runs.len(),
        view.warnings.len()
    );
    for warning in &view.warnings {
        println!("  ! {warning}");
    }

    let batch = plane.events().read_all().unwrap_or_else(|err| {
        eprintln!("event read failed: {err}");
        control_core::EventBatch {
            events: Vec::new(),
            cursor: 0,
        }
    });
    println!(
        "\nevents.jsonl: {} event(s), end cursor {} (SSE resume offset)",
        batch.events.len(),
        batch.cursor
    );
    for event in batch.events.iter().rev().take(5) {
        println!("  @{:<9} {:<8} {}", event.cursor, event.kind, event.message);
    }
}

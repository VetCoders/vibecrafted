use std::fs;
use std::path::PathBuf;

use control_core::{
    ScaffoldArtifactKind, ScaffoldArtifactPatch, ScaffoldArtifactStore, ScaffoldCheckpointPatch,
};

fn temp_home(name: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    std::env::temp_dir().join(format!("control-core-{name}-{nanos}"))
}

#[test]
fn scaffold_workspace_discovers_edits_and_checkpoints_operator_artifacts() {
    let home = temp_home("scaffold");
    let operator = home
        .join("artifacts")
        .join("VetCoders")
        .join("vibecrafted")
        .join("2026_0606")
        .join("operator");
    fs::create_dir_all(operator.join("briefs")).expect("briefs dir");
    fs::create_dir_all(operator.join("designs")).expect("designs dir");
    fs::write(operator.join("master-dispatch.md"), "# Wave Atlas\n").expect("master");
    fs::write(operator.join("briefs/WS-1_cut.md"), "## Mission\n").expect("brief");
    fs::write(operator.join("designs/WS-1_design.md"), "# Design\n").expect("design");

    let store = ScaffoldArtifactStore::new(&home);
    let workspace = store
        .workspace("VetCoders", "vibecrafted", "2026_0606")
        .expect("workspace");
    assert_eq!(workspace.artifacts.len(), 3);
    assert_eq!(workspace.artifacts[0].kind, ScaffoldArtifactKind::WaveAtlas);
    assert_eq!(workspace.artifacts[1].kind, ScaffoldArtifactKind::Brief);
    assert_eq!(workspace.artifacts[2].kind, ScaffoldArtifactKind::DesignDoc);

    let brief_id = workspace.artifacts[1].id.clone();
    let edited = store
        .write_artifact(
            "VetCoders",
            "vibecrafted",
            "2026_0606",
            ScaffoldArtifactPatch {
                artifact_id: brief_id.clone(),
                content: "## Mission\nEdited by operator.\n".to_string(),
            },
        )
        .expect("write artifact");
    assert!(edited.content.contains("Edited by operator."));

    let checkpoint = store
        .checkpoint(
            "VetCoders",
            "vibecrafted",
            "2026_0606",
            ScaffoldCheckpointPatch {
                artifact_id: brief_id,
                approved: true,
                note: "ready for implement".to_string(),
            },
        )
        .expect("checkpoint");
    assert!(checkpoint.approved);

    let changes = store
        .changes("VetCoders", "vibecrafted", "2026_0606")
        .expect("changes");
    assert_eq!(changes.len(), 2);
    assert_eq!(changes[0].action, "edit");
    assert_eq!(changes[1].action, "checkpoint");
    assert!(changes[1].checkpointed);

    fs::remove_dir_all(home).ok();
}

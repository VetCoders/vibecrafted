use std::fs;
use std::path::{Path, PathBuf};

use control_core::{
    SCAFFOLD_MANIFEST_SCHEMA_JSON, ScaffoldArtifactPatch, ScaffoldArtifactRole,
    ScaffoldArtifactStore, ScaffoldCheckpointPatch, ScaffoldError, ScaffoldManifest,
};
use serde_json::json;

fn temp_home(name: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    std::env::temp_dir().join(format!("control-core-{name}-{nanos}"))
}

fn plan_root(home: &Path, plan_id: &str) -> PathBuf {
    home.join("artifacts/vetcoders/vibecrafted/2026_0720/plans")
        .join(plan_id)
}

fn write_plan(home: &Path, plan_id: &str, artifacts: serde_json::Value) -> PathBuf {
    let root = plan_root(home, plan_id);
    fs::create_dir_all(&root).expect("plan root");
    let manifest = json!({
        "schema_version": "1",
        "plan_id": plan_id,
        "org": "Vetcoders",
        "repo": "vibecrafted",
        "day": "2026_0720",
        "artifacts": artifacts,
    });
    fs::write(
        root.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).expect("manifest json"),
    )
    .expect("manifest");
    root
}

fn declarations() -> serde_json::Value {
    json!([
        {"id":"driver","role":"driver","path":"DRIVER.md","editable":true,"required":true},
        {"id":"atlas","role":"wave-atlas","path":"00_ATLAS.md","editable":true,"required":true},
        {"id":"w0-01","role":"brief","path":"briefs/arbitrary.md","editable":true,"required":true},
        {"id":"architecture","role":"design-doc","path":"notes/architecture.md","editable":true,"required":true}
    ])
}

fn populate(root: &Path) {
    fs::create_dir_all(root.join("briefs")).expect("briefs");
    fs::create_dir_all(root.join("notes")).expect("notes");
    fs::write(
        root.join("DRIVER.md"),
        "# Driver\nwhy\nvibecrafted implement\n[ ] [x]\ndou-index\n",
    )
    .expect("driver");
    fs::write(
        root.join("00_ATLAS.md"),
        "# Wave Atlas\n## Dependency graph\n",
    )
    .expect("atlas");
    fs::write(
        root.join("briefs/arbitrary.md"),
        "# Mission\n## Acceptance\n## Delivery verifier\n",
    )
    .expect("brief");
    fs::write(root.join("notes/architecture.md"), "# Architecture\n").expect("design");
}

#[test]
fn published_schema_and_fixture_match_the_typed_model() {
    let fixture = include_str!("fixtures/scaffold-manifest-v1.json");
    let manifest: ScaffoldManifest = serde_json::from_str(fixture).expect("typed fixture");
    assert_eq!(manifest.schema_version, "1");
    assert_eq!(manifest.artifacts[2].role, ScaffoldArtifactRole::Brief);
    assert_eq!(manifest.artifacts[2].dependencies, ["driver", "atlas"]);
    assert!(SCAFFOLD_MANIFEST_SCHEMA_JSON.contains("\"wave-atlas\""));
}

#[test]
fn doctor_rejects_invalid_driver_atlas_tracker_and_frontmatter_drift() {
    let home = temp_home("doctor-contracts");
    let root = write_plan(
        &home,
        "plan-a",
        json!([
            {"id":"driver","role":"driver","path":"DRIVER.md","editable":true,"required":true},
            {"id":"atlas","role":"wave-atlas","path":"00_ATLAS.md","editable":true,"required":true},
            {"id":"tracker","role":"tracker","path":"tracker.md","editable":true,"required":true},
            {"id":"w0-01","role":"brief","path":"briefs/cut.md","editable":true,"required":true}
        ]),
    );
    fs::create_dir_all(root.join("briefs")).expect("briefs");
    fs::write(root.join("DRIVER.md"), "# Decorative driver\n").expect("driver");
    fs::write(root.join("00_ATLAS.md"), "# Notes\n").expect("atlas");
    fs::write(root.join("tracker.md"), "# Tracker\n").expect("tracker");
    fs::write(
        root.join("briefs/cut.md"),
        "---\nid: wrong-id\nrole: report\n---\n# Mission\n",
    )
    .expect("brief");

    let report = ScaffoldArtifactStore::new(&home)
        .doctor("Vetcoders", "vibecrafted", "2026_0720", "plan-a")
        .expect("doctor");
    let codes = report
        .errors
        .iter()
        .map(|error| error.code.as_str())
        .collect::<Vec<_>>();
    assert!(codes.contains(&"driver_contract"));
    assert!(codes.contains(&"atlas_contract"));
    assert!(codes.contains(&"tracker_contract"));
    assert!(codes.contains(&"frontmatter_drift"));
    assert!(codes.contains(&"brief_contract"));

    fs::remove_dir_all(home).ok();
}

#[test]
fn manifest_plan_is_discovered_without_operator_mirror_and_roles_are_explicit() {
    let home = temp_home("manifest-discovery");
    let root = write_plan(&home, "plan-a", declarations());
    populate(&root);

    let store = ScaffoldArtifactStore::new(&home);
    let plans = store
        .plans("Vetcoders", "vibecrafted", "2026_0720")
        .expect("plans");
    assert_eq!(
        plans
            .iter()
            .map(|plan| plan.plan_id.as_str())
            .collect::<Vec<_>>(),
        ["plan-a"]
    );

    let workspace = store
        .workspace("Vetcoders", "vibecrafted", "2026_0720", Some("plan-a"))
        .expect("workspace");
    assert_eq!(workspace.plan_id, "plan-a");
    assert_eq!(workspace.artifacts.len(), 4);
    assert_eq!(workspace.artifacts[3].role, ScaffoldArtifactRole::DesignDoc);
    assert_eq!(
        workspace.artifacts[3].relative_path,
        "notes/architecture.md"
    );
    assert!(!root.join("../operator").exists());

    fs::remove_dir_all(home).ok();
}

#[test]
fn plan_selection_is_explicit_when_more_than_one_manifest_exists() {
    let home = temp_home("selection");
    for plan_id in ["plan-a", "plan-b"] {
        let root = write_plan(&home, plan_id, declarations());
        populate(&root);
    }
    let store = ScaffoldArtifactStore::new(&home);

    let error = store
        .workspace("Vetcoders", "vibecrafted", "2026_0720", None)
        .expect_err("ambiguous plan selection must fail");
    assert!(matches!(error, ScaffoldError::SelectionRequired { .. }));
    assert_eq!(
        store
            .workspace("Vetcoders", "vibecrafted", "2026_0720", Some("plan-b"))
            .expect("explicit plan")
            .plan_id,
        "plan-b"
    );

    fs::remove_dir_all(home).ok();
}

#[test]
fn canonical_write_requires_hash_rejects_unlisted_and_scopes_history() {
    let home = temp_home("writes");
    for plan_id in ["plan-a", "plan-b"] {
        let root = write_plan(&home, plan_id, declarations());
        populate(&root);
        fs::write(root.join("unlisted.md"), "not editable\n").expect("unlisted");
    }
    let store = ScaffoldArtifactStore::new(&home);
    let before = store
        .workspace("Vetcoders", "vibecrafted", "2026_0720", Some("plan-a"))
        .expect("workspace");
    let brief = before
        .artifacts
        .iter()
        .find(|artifact| artifact.id == "w0-01")
        .expect("brief");

    let edited = store
        .write_artifact(
            "Vetcoders",
            "vibecrafted",
            "2026_0720",
            "plan-a",
            ScaffoldArtifactPatch {
                artifact_id: "w0-01".into(),
                content: "# Canonical edit\n".into(),
                expected_hash: brief.content_hash.clone(),
            },
        )
        .expect("canonical write");
    assert_eq!(edited.content, "# Canonical edit\n");
    assert_eq!(
        fs::read_to_string(plan_root(&home, "plan-a").join("briefs/arbitrary.md"))
            .expect("physical file"),
        "# Canonical edit\n"
    );

    let conflict = store
        .write_artifact(
            "Vetcoders",
            "vibecrafted",
            "2026_0720",
            "plan-a",
            ScaffoldArtifactPatch {
                artifact_id: "w0-01".into(),
                content: "stale overwrite".into(),
                expected_hash: brief.content_hash.clone(),
            },
        )
        .expect_err("stale save");
    assert!(matches!(conflict, ScaffoldError::Conflict { .. }));

    let unlisted = store.write_artifact(
        "Vetcoders",
        "vibecrafted",
        "2026_0720",
        "plan-a",
        ScaffoldArtifactPatch {
            artifact_id: "unlisted".into(),
            content: "no".into(),
            expected_hash: String::new(),
        },
    );
    assert!(matches!(
        unlisted,
        Err(ScaffoldError::ArtifactNotFound { .. })
    ));

    assert_eq!(
        store
            .changes("Vetcoders", "vibecrafted", "2026_0720", "plan-a")
            .expect("plan-a changes")
            .len(),
        1
    );
    assert!(
        store
            .changes("Vetcoders", "vibecrafted", "2026_0720", "plan-b")
            .expect("plan-b changes")
            .is_empty()
    );

    store
        .checkpoint(
            "Vetcoders",
            "vibecrafted",
            "2026_0720",
            "plan-a",
            ScaffoldCheckpointPatch {
                artifact_id: "w0-01".into(),
                approved: true,
                note: "ready".into(),
            },
        )
        .expect("checkpoint");
    assert!(
        plan_root(&home, "plan-a")
            .join(".scaffold-checkpoints.json")
            .is_file()
    );
    assert!(
        !plan_root(&home, "plan-b")
            .join(".scaffold-checkpoints.json")
            .exists()
    );

    fs::remove_dir_all(home).ok();
}

#[cfg(unix)]
#[test]
fn writable_symlink_and_escaping_symlink_are_rejected() {
    use std::os::unix::fs::symlink;

    let home = temp_home("symlink");
    let root = write_plan(&home, "plan-a", declarations());
    populate(&root);
    let outside = home.join("outside.md");
    fs::write(&outside, "outside\n").expect("outside");
    fs::remove_file(root.join("briefs/arbitrary.md")).expect("remove brief");
    symlink(&outside, root.join("briefs/arbitrary.md")).expect("symlink");

    let store = ScaffoldArtifactStore::new(&home);
    let report = store
        .doctor("Vetcoders", "vibecrafted", "2026_0720", "plan-a")
        .expect("doctor report");
    assert!(!report.valid);
    assert!(
        report
            .errors
            .iter()
            .any(|error| error.code == "writable_symlink")
    );
    assert!(
        store
            .workspace("Vetcoders", "vibecrafted", "2026_0720", Some("plan-a"))
            .is_err()
    );

    fs::remove_dir_all(home).ok();
}

#[test]
fn doctor_and_server_return_identical_manifest_order_for_twenty_four_artifacts() {
    let home = temp_home("parity");
    let mut artifacts = vec![
        json!({"id":"driver","role":"driver","path":"DRIVER.md","editable":true,"required":true}),
        json!({"id":"atlas","role":"wave-atlas","path":"00_ATLAS.md","editable":true,"required":true}),
    ];
    for index in 1..=22 {
        artifacts.push(json!({
            "id": format!("w0-{index:02}"),
            "role": "brief",
            "path": format!("briefs/cut-{index:02}.md"),
            "editable": true,
            "required": true
        }));
    }
    let root = write_plan(&home, "aicx-product-convergence-v1", json!(artifacts));
    fs::create_dir_all(root.join("briefs")).expect("briefs");
    fs::write(
        root.join("DRIVER.md"),
        "# Driver\nwhy\nvibecrafted implement\n[ ] [x]\ndou-index\n",
    )
    .expect("driver");
    fs::write(
        root.join("00_ATLAS.md"),
        "# Wave Atlas\n## Dependency graph\n",
    )
    .expect("atlas");
    for index in 1..=22 {
        fs::write(
            root.join(format!("briefs/cut-{index:02}.md")),
            "# Mission\n## Acceptance\n## Delivery verifier\n",
        )
        .expect("brief");
    }

    let store = ScaffoldArtifactStore::new(&home);
    let workspace = store
        .workspace(
            "Vetcoders",
            "vibecrafted",
            "2026_0720",
            Some("aicx-product-convergence-v1"),
        )
        .expect("workspace");
    let doctor = store
        .doctor(
            "Vetcoders",
            "vibecrafted",
            "2026_0720",
            "aicx-product-convergence-v1",
        )
        .expect("doctor");
    assert!(doctor.valid, "{:?}", doctor.errors);
    assert_eq!(workspace.artifacts.len(), 24);
    assert_eq!(
        doctor.artifact_ids,
        workspace
            .artifacts
            .iter()
            .map(|a| a.id.clone())
            .collect::<Vec<_>>()
    );

    fs::remove_dir_all(home).ok();
}

#[test]
fn legacy_operator_workspace_is_read_only() {
    let home = temp_home("legacy");
    let operator = home.join("artifacts/vetcoders/vibecrafted/2026_0720/operator");
    fs::create_dir_all(&operator).expect("operator");
    fs::write(operator.join("master-dispatch.md"), "# Legacy\n").expect("legacy");
    let store = ScaffoldArtifactStore::new(&home);
    let workspace = store
        .workspace("Vetcoders", "vibecrafted", "2026_0720", None)
        .expect("legacy readable");
    assert!(workspace.legacy_read_only);
    assert!(!workspace.artifacts[0].editable);

    fs::remove_dir_all(home).ok();
}

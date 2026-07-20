//! Manifest-backed scaffold artifact contract shared by the doctor and server.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Component, Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const SCAFFOLD_SCHEMA_VERSION: &str = "1";
pub const SCAFFOLD_MANIFEST_SCHEMA_JSON: &str =
    include_str!("../schema/scaffold-manifest-v1.schema.json");

#[derive(Debug)]
pub enum ScaffoldError {
    Io(io::Error),
    Json(serde_json::Error),
    InvalidManifest { message: String },
    SelectionRequired { plan_ids: Vec<String> },
    ArtifactNotFound { id: String },
    Conflict { expected: String, actual: String },
    ReadOnly { message: String },
    UnsafePath { message: String },
}

impl fmt::Display for ScaffoldError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(error) => write!(formatter, "{error}"),
            Self::Json(error) => write!(formatter, "{error}"),
            Self::InvalidManifest { message }
            | Self::ReadOnly { message }
            | Self::UnsafePath { message } => formatter.write_str(message),
            Self::SelectionRequired { plan_ids } => write!(
                formatter,
                "scaffold plan selection required; available plans: {}",
                plan_ids.join(", ")
            ),
            Self::ArtifactNotFound { id } => write!(formatter, "artifact id not found: {id}"),
            Self::Conflict { expected, actual } => write!(
                formatter,
                "artifact changed since load (expected {expected}, actual {actual})"
            ),
        }
    }
}

impl std::error::Error for ScaffoldError {}

impl From<io::Error> for ScaffoldError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<serde_json::Error> for ScaffoldError {
    fn from(error: serde_json::Error) -> Self {
        Self::Json(error)
    }
}

pub type ScaffoldResult<T> = Result<T, ScaffoldError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ScaffoldArtifactRole {
    Driver,
    WaveAtlas,
    Brief,
    DesignDoc,
    Traceability,
    Tracker,
    Falsification,
    Report,
    Other,
}

impl ScaffoldArtifactRole {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Driver => "driver",
            Self::WaveAtlas => "wave-atlas",
            Self::Brief => "brief",
            Self::DesignDoc => "design-doc",
            Self::Traceability => "traceability",
            Self::Tracker => "tracker",
            Self::Falsification => "falsification",
            Self::Report => "report",
            Self::Other => "other",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldArtifactDeclaration {
    pub id: String,
    pub role: ScaffoldArtifactRole,
    pub path: String,
    pub editable: bool,
    pub required: bool,
    #[serde(default)]
    pub dependencies: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldManifest {
    pub schema_version: String,
    pub plan_id: String,
    pub org: String,
    pub repo: String,
    pub day: String,
    pub artifacts: Vec<ScaffoldArtifactDeclaration>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldPlanSummary {
    pub plan_id: String,
    pub org: String,
    pub repo: String,
    pub day: String,
    pub plan_root: String,
    pub artifact_count: usize,
    pub legacy_read_only: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ScaffoldCheckpoint {
    pub artifact_id: String,
    pub approved: bool,
    pub note: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldArtifact {
    pub id: String,
    pub title: String,
    pub role: ScaffoldArtifactRole,
    pub path: String,
    pub relative_path: String,
    pub editable: bool,
    pub required: bool,
    pub content: String,
    pub content_hash: String,
    pub bytes: usize,
    pub modified_at: String,
    pub checkpoint: ScaffoldCheckpoint,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldWorkspace {
    pub org: String,
    pub repo: String,
    pub day: String,
    pub plan_id: String,
    pub plan_root: String,
    pub legacy_read_only: bool,
    pub changes_path: String,
    pub checkpoints_path: String,
    pub artifacts: Vec<ScaffoldArtifact>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldArtifactPatch {
    pub artifact_id: String,
    pub content: String,
    pub expected_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldCheckpointPatch {
    pub artifact_id: String,
    pub approved: bool,
    pub note: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldChange {
    pub ts: String,
    pub plan_id: String,
    pub artifact_id: String,
    pub relative_path: String,
    pub role: ScaffoldArtifactRole,
    pub action: String,
    pub bytes: usize,
    pub checkpointed: bool,
    pub note: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldDoctorError {
    pub code: String,
    pub artifact_id: Option<String>,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldDoctorReport {
    pub valid: bool,
    pub plan_id: String,
    pub artifact_ids: Vec<String>,
    pub errors: Vec<ScaffoldDoctorError>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
struct CheckpointStore {
    #[serde(default)]
    artifacts: BTreeMap<String, ScaffoldCheckpoint>,
}

#[derive(Debug, Clone)]
pub struct ScaffoldArtifactStore {
    home: PathBuf,
}

impl ScaffoldArtifactStore {
    #[must_use]
    pub fn new(home: impl Into<PathBuf>) -> Self {
        Self { home: home.into() }
    }

    fn day_root(&self, org: &str, repo: &str, day: &str) -> ScaffoldResult<PathBuf> {
        validate_path_segment(org, "org")?;
        validate_path_segment(repo, "repo")?;
        validate_path_segment(day, "day")?;
        Ok(self.home.join("artifacts").join(org).join(repo).join(day))
    }

    fn plan_root(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
    ) -> ScaffoldResult<PathBuf> {
        validate_path_segment(plan_id, "plan_id")?;
        Ok(self.day_root(org, repo, day)?.join("plans").join(plan_id))
    }

    pub fn plans(
        &self,
        org: &str,
        repo: &str,
        day: &str,
    ) -> ScaffoldResult<Vec<ScaffoldPlanSummary>> {
        let plans_root = self.day_root(org, repo, day)?.join("plans");
        let mut plans = Vec::new();
        let Ok(entries) = fs::read_dir(plans_root) else {
            return Ok(plans);
        };
        for entry in entries.flatten() {
            let root = entry.path();
            if !entry.file_type().is_ok_and(|kind| kind.is_dir())
                || !root.join("manifest.json").is_file()
            {
                continue;
            }
            let manifest = read_manifest(&root)?;
            if manifest.org != org || manifest.repo != repo || manifest.day != day {
                continue;
            }
            plans.push(ScaffoldPlanSummary {
                plan_id: manifest.plan_id,
                org: org.to_string(),
                repo: repo.to_string(),
                day: day.to_string(),
                plan_root: root.display().to_string(),
                artifact_count: manifest.artifacts.len(),
                legacy_read_only: false,
            });
        }
        plans.sort_by(|left, right| left.plan_id.cmp(&right.plan_id));
        Ok(plans)
    }

    pub fn latest_workspace(&self) -> ScaffoldResult<ScaffoldWorkspace> {
        let mut manifests = Vec::new();
        collect_manifest_paths(&self.home.join("artifacts"), &mut manifests);
        if manifests.len() != 1 {
            let plan_ids = manifests
                .iter()
                .filter_map(|path| {
                    read_manifest(path.parent()?)
                        .ok()
                        .map(|manifest| manifest.plan_id)
                })
                .collect();
            return Err(ScaffoldError::SelectionRequired { plan_ids });
        }
        let root = manifests
            .remove(0)
            .parent()
            .map(Path::to_path_buf)
            .ok_or_else(|| ScaffoldError::InvalidManifest {
                message: "manifest has no plan root".into(),
            })?;
        let manifest = read_manifest(&root)?;
        self.workspace(
            &manifest.org,
            &manifest.repo,
            &manifest.day,
            Some(&manifest.plan_id),
        )
    }

    pub fn workspace(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: Option<&str>,
    ) -> ScaffoldResult<ScaffoldWorkspace> {
        let plans = self.plans(org, repo, day)?;
        let selected = match plan_id {
            Some(requested) => plans
                .iter()
                .find(|plan| plan.plan_id == requested)
                .cloned()
                .ok_or_else(|| ScaffoldError::InvalidManifest {
                    message: format!("manifest-backed scaffold plan not found: {requested}"),
                })?,
            None if plans.len() == 1 => plans[0].clone(),
            None if plans.is_empty() => return self.legacy_workspace(org, repo, day),
            None => {
                return Err(ScaffoldError::SelectionRequired {
                    plan_ids: plans.into_iter().map(|plan| plan.plan_id).collect(),
                });
            }
        };
        self.manifest_workspace(org, repo, day, &selected.plan_id)
    }

    fn manifest_workspace(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
    ) -> ScaffoldResult<ScaffoldWorkspace> {
        let root = self.plan_root(org, repo, day, plan_id)?;
        let manifest = read_manifest(&root)?;
        validate_identity(&manifest, org, repo, day, plan_id)?;
        let report = validate_manifest_plan(&root, &manifest);
        if report.errors.iter().any(workspace_fatal_error) {
            return Err(ScaffoldError::InvalidManifest {
                message: report
                    .errors
                    .iter()
                    .map(|error| error.message.as_str())
                    .collect::<Vec<_>>()
                    .join("; "),
            });
        }
        let checkpoints = read_checkpoints(&checkpoint_path(&root));
        let mut artifacts = Vec::with_capacity(manifest.artifacts.len());
        for declaration in manifest.artifacts {
            let path = declared_path(&root, &declaration)?;
            let content = fs::read_to_string(&path)?;
            let checkpoint = checkpoints
                .artifacts
                .get(&declaration.id)
                .cloned()
                .unwrap_or_else(|| ScaffoldCheckpoint {
                    artifact_id: declaration.id.clone(),
                    ..ScaffoldCheckpoint::default()
                });
            artifacts.push(ScaffoldArtifact {
                id: declaration.id.clone(),
                title: artifact_title(&declaration.path, declaration.role),
                role: declaration.role,
                path: path.display().to_string(),
                relative_path: declaration.path,
                editable: declaration.editable,
                required: declaration.required,
                bytes: content.len(),
                content_hash: content_hash(content.as_bytes()),
                content,
                modified_at: modified_at(&path),
                checkpoint,
            });
        }
        Ok(ScaffoldWorkspace {
            org: org.to_string(),
            repo: repo.to_string(),
            day: day.to_string(),
            plan_id: plan_id.to_string(),
            plan_root: root.display().to_string(),
            legacy_read_only: false,
            changes_path: changes_path(&root).display().to_string(),
            checkpoints_path: checkpoint_path(&root).display().to_string(),
            artifacts,
        })
    }

    fn legacy_workspace(
        &self,
        org: &str,
        repo: &str,
        day: &str,
    ) -> ScaffoldResult<ScaffoldWorkspace> {
        let root = self.day_root(org, repo, day)?.join("operator");
        if !root.is_dir() {
            return Err(ScaffoldError::InvalidManifest {
                message: "no manifest-backed scaffold plan found".into(),
            });
        }
        let checkpoints = read_checkpoints(&checkpoint_path(&root));
        let mut paths = discover_legacy_paths(&root);
        paths.sort();
        let mut artifacts = Vec::new();
        for path in paths {
            let relative = relative_string(&root, &path)?;
            let content = fs::read_to_string(&path)?;
            let id = legacy_artifact_id(&relative);
            let role = legacy_role(&relative);
            artifacts.push(ScaffoldArtifact {
                checkpoint: checkpoints.artifacts.get(&id).cloned().unwrap_or_default(),
                id,
                title: artifact_title(&relative, role),
                role,
                path: path.display().to_string(),
                relative_path: relative,
                editable: false,
                required: false,
                bytes: content.len(),
                content_hash: content_hash(content.as_bytes()),
                content,
                modified_at: modified_at(&path),
            });
        }
        Ok(ScaffoldWorkspace {
            org: org.to_string(),
            repo: repo.to_string(),
            day: day.to_string(),
            plan_id: "legacy-operator".into(),
            plan_root: root.display().to_string(),
            legacy_read_only: true,
            changes_path: changes_path(&root).display().to_string(),
            checkpoints_path: checkpoint_path(&root).display().to_string(),
            artifacts,
        })
    }

    pub fn doctor(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
    ) -> ScaffoldResult<ScaffoldDoctorReport> {
        let root = self.plan_root(org, repo, day, plan_id)?;
        let manifest = read_manifest(&root)?;
        validate_identity(&manifest, org, repo, day, plan_id)?;
        Ok(validate_manifest_plan(&root, &manifest))
    }

    pub fn write_artifact(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
        patch: ScaffoldArtifactPatch,
    ) -> ScaffoldResult<ScaffoldArtifact> {
        let workspace = self.workspace(org, repo, day, Some(plan_id))?;
        if workspace.legacy_read_only {
            return Err(ScaffoldError::ReadOnly {
                message: "legacy scaffold workspaces are read-only".into(),
            });
        }
        let artifact = workspace
            .artifacts
            .iter()
            .find(|artifact| artifact.id == patch.artifact_id)
            .ok_or_else(|| ScaffoldError::ArtifactNotFound {
                id: patch.artifact_id.clone(),
            })?;
        if !artifact.editable {
            return Err(ScaffoldError::ReadOnly {
                message: format!("artifact is not editable: {}", artifact.id),
            });
        }
        let actual = content_hash(fs::read(&artifact.path)?.as_slice());
        if patch.expected_hash != actual {
            return Err(ScaffoldError::Conflict {
                expected: patch.expected_hash,
                actual,
            });
        }
        let root = PathBuf::from(&workspace.plan_root);
        let path = root.join(validate_relative_markdown_path(&artifact.relative_path)?);
        reject_symlink_path(&root, &path)?;
        write_atomic(&path, patch.content.as_bytes())?;
        let refreshed = self
            .workspace(org, repo, day, Some(plan_id))?
            .artifacts
            .into_iter()
            .find(|candidate| candidate.id == artifact.id)
            .ok_or_else(|| ScaffoldError::ArtifactNotFound {
                id: artifact.id.clone(),
            })?;
        append_change(
            &root,
            ScaffoldChange {
                ts: now_ts(),
                plan_id: plan_id.to_string(),
                artifact_id: refreshed.id.clone(),
                relative_path: refreshed.relative_path.clone(),
                role: refreshed.role,
                action: "edit".into(),
                bytes: refreshed.bytes,
                checkpointed: refreshed.checkpoint.approved,
                note: String::new(),
            },
        )?;
        Ok(refreshed)
    }

    pub fn checkpoint(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
        patch: ScaffoldCheckpointPatch,
    ) -> ScaffoldResult<ScaffoldCheckpoint> {
        let workspace = self.workspace(org, repo, day, Some(plan_id))?;
        let artifact = workspace
            .artifacts
            .iter()
            .find(|artifact| artifact.id == patch.artifact_id)
            .ok_or_else(|| ScaffoldError::ArtifactNotFound {
                id: patch.artifact_id.clone(),
            })?;
        if workspace.legacy_read_only {
            return Err(ScaffoldError::ReadOnly {
                message: "legacy scaffold workspaces are read-only".into(),
            });
        }
        let root = PathBuf::from(&workspace.plan_root);
        let mut store = read_checkpoints(&checkpoint_path(&root));
        let checkpoint = ScaffoldCheckpoint {
            artifact_id: artifact.id.clone(),
            approved: patch.approved,
            note: patch.note,
            updated_at: now_ts(),
        };
        store
            .artifacts
            .insert(checkpoint.artifact_id.clone(), checkpoint.clone());
        write_checkpoints(&checkpoint_path(&root), &store)?;
        append_change(
            &root,
            ScaffoldChange {
                ts: checkpoint.updated_at.clone(),
                plan_id: plan_id.to_string(),
                artifact_id: artifact.id.clone(),
                relative_path: artifact.relative_path.clone(),
                role: artifact.role,
                action: "checkpoint".into(),
                bytes: artifact.bytes,
                checkpointed: checkpoint.approved,
                note: checkpoint.note.clone(),
            },
        )?;
        Ok(checkpoint)
    }

    pub fn changes(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
    ) -> ScaffoldResult<Vec<ScaffoldChange>> {
        let root = self.plan_root(org, repo, day, plan_id)?;
        let Ok(text) = fs::read_to_string(changes_path(&root)) else {
            return Ok(Vec::new());
        };
        Ok(text
            .lines()
            .filter_map(|line| serde_json::from_str(line).ok())
            .collect())
    }
}

fn workspace_fatal_error(error: &ScaffoldDoctorError) -> bool {
    matches!(
        error.code.as_str(),
        "duplicate_artifact_id"
            | "duplicate_artifact_path"
            | "missing_required_artifact"
            | "missing_manifest_artifact"
            | "path_escape"
            | "writable_symlink"
    )
}

fn read_manifest(root: &Path) -> ScaffoldResult<ScaffoldManifest> {
    Ok(serde_json::from_slice(&fs::read(
        root.join("manifest.json"),
    )?)?)
}

fn validate_identity(
    manifest: &ScaffoldManifest,
    org: &str,
    repo: &str,
    day: &str,
    plan_id: &str,
) -> ScaffoldResult<()> {
    if manifest.schema_version != SCAFFOLD_SCHEMA_VERSION
        || manifest.org != org
        || manifest.repo != repo
        || manifest.day != day
        || manifest.plan_id != plan_id
    {
        return Err(ScaffoldError::InvalidManifest {
            message: "manifest identity does not match its canonical plan path".into(),
        });
    }
    Ok(())
}

fn validate_manifest_plan(root: &Path, manifest: &ScaffoldManifest) -> ScaffoldDoctorReport {
    let mut errors = Vec::new();
    let mut ids = BTreeSet::new();
    let mut paths = BTreeSet::new();
    let declared_ids: BTreeSet<&str> = manifest
        .artifacts
        .iter()
        .map(|artifact| artifact.id.as_str())
        .collect();
    let mut role_counts = BTreeMap::new();
    for artifact in &manifest.artifacts {
        if !ids.insert(artifact.id.clone()) {
            doctor_error(
                &mut errors,
                "duplicate_artifact_id",
                Some(&artifact.id),
                "duplicate artifact id",
            );
        }
        if !paths.insert(artifact.path.clone()) {
            doctor_error(
                &mut errors,
                "duplicate_artifact_path",
                Some(&artifact.id),
                "duplicate artifact path",
            );
        }
        *role_counts.entry(artifact.role.as_str()).or_insert(0usize) += 1;
        for dependency in &artifact.dependencies {
            if !declared_ids.contains(dependency.as_str()) {
                doctor_error(
                    &mut errors,
                    "unknown_dependency",
                    Some(&artifact.id),
                    &format!("unknown dependency: {dependency}"),
                );
            }
        }
        match declared_path(root, artifact) {
            Ok(path) => {
                if !path.is_file() {
                    let code = if artifact.required {
                        "missing_required_artifact"
                    } else {
                        "missing_manifest_artifact"
                    };
                    doctor_error(
                        &mut errors,
                        code,
                        Some(&artifact.id),
                        "manifest artifact is missing from disk",
                    );
                } else if path.is_file() {
                    if artifact.editable && path_has_symlink(root, &path) {
                        doctor_error(
                            &mut errors,
                            "writable_symlink",
                            Some(&artifact.id),
                            "editable artifact path contains a symlink",
                        );
                    }
                    if fs::metadata(&path).is_ok_and(|metadata| metadata.len() == 0) {
                        doctor_error(
                            &mut errors,
                            "empty_contract",
                            Some(&artifact.id),
                            "declared artifact is empty",
                        );
                    }
                    if let Ok(content) = fs::read_to_string(&path) {
                        validate_frontmatter(artifact, &content, &mut errors);
                        validate_role_contract(artifact, &content, &mut errors);
                    }
                }
            }
            Err(error) => doctor_error(
                &mut errors,
                "path_escape",
                Some(&artifact.id),
                &error.to_string(),
            ),
        }
    }
    if role_counts.get("driver").copied() != Some(1) {
        doctor_error(
            &mut errors,
            "driver_contract",
            None,
            "manifest must declare exactly one driver",
        );
    }
    if role_counts.get("wave-atlas").copied() != Some(1) {
        doctor_error(
            &mut errors,
            "atlas_contract",
            None,
            "manifest must declare exactly one wave-atlas",
        );
    }
    let mut briefs_on_disk = Vec::new();
    collect_markdown(&root.join("briefs"), &mut briefs_on_disk);
    for path in briefs_on_disk {
        if let Ok(relative) = relative_string(root, &path) {
            if !paths.contains(&relative) {
                doctor_error(
                    &mut errors,
                    "brief_absent_from_manifest",
                    None,
                    &format!("brief is absent from manifest: {relative}"),
                );
            }
        }
    }
    ScaffoldDoctorReport {
        valid: errors.is_empty(),
        plan_id: manifest.plan_id.clone(),
        artifact_ids: manifest
            .artifacts
            .iter()
            .map(|artifact| artifact.id.clone())
            .collect(),
        errors,
    }
}

fn doctor_error(
    errors: &mut Vec<ScaffoldDoctorError>,
    code: &str,
    artifact_id: Option<&str>,
    message: &str,
) {
    errors.push(ScaffoldDoctorError {
        code: code.into(),
        artifact_id: artifact_id.map(str::to_string),
        message: message.into(),
    });
}

fn validate_frontmatter(
    artifact: &ScaffoldArtifactDeclaration,
    content: &str,
    errors: &mut Vec<ScaffoldDoctorError>,
) {
    if !content.starts_with("---\n") {
        return;
    }
    let Some(frontmatter) = content[4..].split("\n---").next() else {
        return;
    };
    for key in ["id", "artifact_id"] {
        if let Some(value) = frontmatter
            .lines()
            .find_map(|line| line.strip_prefix(&format!("{key}:")))
            .map(str::trim)
        {
            if value != artifact.id {
                doctor_error(
                    errors,
                    "frontmatter_drift",
                    Some(&artifact.id),
                    &format!("frontmatter {key} does not match manifest id"),
                );
            }
        }
    }
    if let Some(role) = frontmatter
        .lines()
        .find_map(|line| line.strip_prefix("role:"))
        .map(str::trim)
    {
        if role != artifact.role.as_str() {
            doctor_error(
                errors,
                "frontmatter_drift",
                Some(&artifact.id),
                "frontmatter role does not match manifest role",
            );
        }
    }
}

fn validate_role_contract(
    artifact: &ScaffoldArtifactDeclaration,
    content: &str,
    errors: &mut Vec<ScaffoldDoctorError>,
) {
    let lower = content.to_ascii_lowercase();
    let (code, required_tokens): (&str, &[&str]) = match artifact.role {
        ScaffoldArtifactRole::Driver => (
            "driver_contract",
            &["why", "vibecrafted ", "[ ]", "[x]", "dou-index"],
        ),
        ScaffoldArtifactRole::WaveAtlas => ("atlas_contract", &["wave", "dependenc"]),
        ScaffoldArtifactRole::Brief => ("brief_contract", &["mission", "acceptance", "verifier"]),
        ScaffoldArtifactRole::Tracker => ("tracker_contract", &["state", "[ ]"]),
        _ => return,
    };
    let missing = required_tokens
        .iter()
        .filter(|token| !lower.contains(**token))
        .copied()
        .collect::<Vec<_>>();
    if !missing.is_empty() {
        doctor_error(
            errors,
            code,
            Some(&artifact.id),
            &format!(
                "{} is missing contract markers: {}",
                artifact.role.as_str(),
                missing.join(", ")
            ),
        );
    }
}

fn declared_path(root: &Path, artifact: &ScaffoldArtifactDeclaration) -> ScaffoldResult<PathBuf> {
    Ok(root.join(validate_relative_markdown_path(&artifact.path)?))
}

fn validate_relative_markdown_path(relative: &str) -> ScaffoldResult<PathBuf> {
    if relative.is_empty() || Path::new(relative).is_absolute() || relative.contains('\\') {
        return Err(ScaffoldError::UnsafePath {
            message: "refusing unsafe scaffold artifact path".into(),
        });
    }
    let path = Path::new(relative);
    if path
        .components()
        .any(|component| !matches!(component, Component::Normal(_)))
        || path.extension().and_then(|extension| extension.to_str()) != Some("md")
    {
        return Err(ScaffoldError::UnsafePath {
            message: "refusing unsafe or non-Markdown scaffold artifact path".into(),
        });
    }
    Ok(path.to_path_buf())
}

fn reject_symlink_path(root: &Path, path: &Path) -> ScaffoldResult<()> {
    if path_has_symlink(root, path) {
        return Err(ScaffoldError::UnsafePath {
            message: "refusing symlinked scaffold artifact path".into(),
        });
    }
    Ok(())
}

fn path_has_symlink(root: &Path, path: &Path) -> bool {
    let Ok(relative) = path.strip_prefix(root) else {
        return true;
    };
    let mut cursor = root.to_path_buf();
    for component in relative.components() {
        cursor.push(component.as_os_str());
        if fs::symlink_metadata(&cursor).is_ok_and(|metadata| metadata.file_type().is_symlink()) {
            return true;
        }
    }
    false
}

fn validate_path_segment(value: &str, label: &str) -> ScaffoldResult<()> {
    if value.is_empty() || value == "." || value == ".." || value.contains(['/', '\\']) {
        return Err(ScaffoldError::UnsafePath {
            message: format!("invalid scaffold {label} path segment"),
        });
    }
    Ok(())
}

fn collect_manifest_paths(root: &Path, output: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if entry.file_type().is_ok_and(|kind| kind.is_dir()) {
            collect_manifest_paths(&path, output);
        } else if path.file_name().and_then(|name| name.to_str()) == Some("manifest.json") {
            output.push(path);
        }
    }
}

fn discover_legacy_paths(root: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let master = root.join("master-dispatch.md");
    if master.is_file() {
        paths.push(master);
    }
    for directory in ["briefs", "designs", "design-docs"] {
        collect_markdown(&root.join(directory), &mut paths);
    }
    paths
}

fn collect_markdown(root: &Path, output: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        match entry.file_type() {
            Ok(kind) if kind.is_dir() => collect_markdown(&path, output),
            Ok(kind)
                if kind.is_file()
                    && path.extension().and_then(|extension| extension.to_str()) == Some("md") =>
            {
                output.push(path)
            }
            _ => {}
        }
    }
}

fn relative_string(root: &Path, path: &Path) -> ScaffoldResult<String> {
    Ok(path
        .strip_prefix(root)
        .map_err(|_| ScaffoldError::UnsafePath {
            message: "artifact outside scaffold root".into(),
        })?
        .to_string_lossy()
        .replace('\\', "/"))
}

fn legacy_artifact_id(relative: &str) -> String {
    relative
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '.' | '-' | '_') {
                character
            } else {
                '_'
            }
        })
        .collect()
}

fn legacy_role(relative: &str) -> ScaffoldArtifactRole {
    let lower = relative.to_ascii_lowercase();
    if lower == "master-dispatch.md" {
        ScaffoldArtifactRole::WaveAtlas
    } else if lower.starts_with("briefs/") {
        ScaffoldArtifactRole::Brief
    } else if lower.contains("design") {
        ScaffoldArtifactRole::DesignDoc
    } else {
        ScaffoldArtifactRole::Other
    }
}

fn artifact_title(relative: &str, role: ScaffoldArtifactRole) -> String {
    if role == ScaffoldArtifactRole::WaveAtlas {
        return "Wave atlas".into();
    }
    let file = relative.rsplit('/').next().unwrap_or(relative);
    file.strip_suffix(".md")
        .unwrap_or(file)
        .replace(['_', '-'], " ")
}

fn content_hash(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}

fn modified_at(path: &Path) -> String {
    fs::metadata(path)
        .and_then(|metadata| metadata.modified())
        .map(|modified| {
            let value: chrono::DateTime<Utc> = modified.into();
            value.to_rfc3339()
        })
        .unwrap_or_default()
}

fn checkpoint_path(root: &Path) -> PathBuf {
    root.join(".scaffold-checkpoints.json")
}
fn changes_path(root: &Path) -> PathBuf {
    root.join(".scaffold-changes.jsonl")
}

fn read_checkpoints(path: &Path) -> CheckpointStore {
    fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

fn write_checkpoints(path: &Path, store: &CheckpointStore) -> ScaffoldResult<()> {
    write_atomic(path, &serde_json::to_vec_pretty(store)?)
}

fn write_atomic(path: &Path, bytes: &[u8]) -> ScaffoldResult<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let file = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("scaffold");
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let temporary = parent.join(format!(".{file}.tmp.{}.{nonce}", std::process::id()));
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    output.write_all(bytes)?;
    output.sync_all()?;
    drop(output);
    if let Err(error) = fs::rename(&temporary, path) {
        let _ = fs::remove_file(&temporary);
        return Err(error.into());
    }
    Ok(())
}

fn append_change(root: &Path, change: ScaffoldChange) -> ScaffoldResult<()> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(changes_path(root))?;
    writeln!(file, "{}", serde_json::to_string(&change)?)?;
    Ok(())
}

fn now_ts() -> String {
    Utc::now().to_rfc3339()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relative_paths_reject_traversal_absolute_and_non_markdown() {
        for path in [
            "",
            "/brief.md",
            "../brief.md",
            "briefs/../brief.md",
            "brief.txt",
            "briefs\\brief.md",
        ] {
            assert!(validate_relative_markdown_path(path).is_err(), "{path}");
        }
        assert_eq!(
            validate_relative_markdown_path("briefs/cut.md").expect("safe"),
            PathBuf::from("briefs/cut.md")
        );
    }
}

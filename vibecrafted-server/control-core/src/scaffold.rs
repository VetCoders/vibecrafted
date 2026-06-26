//! Typed scaffold-artifact editor contract.
//!
//! This is intentionally scoped to Markdown artifacts produced by
//! `vc-scaffold` under `artifacts/<org>/<repo>/<day>/operator/`. The Python
//! control-plane writer remains the source of truth for run state; this module
//! only reads/writes operator review artifacts and sidecars in the artifact
//! directory itself.

use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Component, Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};

/// Markdown artifact role in the scaffold review surface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ScaffoldArtifactKind {
    WaveAtlas,
    Brief,
    DesignDoc,
    Other,
}

impl ScaffoldArtifactKind {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            ScaffoldArtifactKind::WaveAtlas => "wave-atlas",
            ScaffoldArtifactKind::Brief => "brief",
            ScaffoldArtifactKind::DesignDoc => "design-doc",
            ScaffoldArtifactKind::Other => "other",
        }
    }
}

/// Per-artifact approve/checkpoint state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ScaffoldCheckpoint {
    pub artifact_id: String,
    pub approved: bool,
    pub note: String,
    pub updated_at: String,
}

/// A single editable Markdown artifact.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldArtifact {
    pub id: String,
    pub title: String,
    pub kind: ScaffoldArtifactKind,
    pub path: String,
    pub relative_path: String,
    pub content: String,
    pub bytes: usize,
    pub modified_at: String,
    pub checkpoint: ScaffoldCheckpoint,
}

/// Batch review workspace served to the browser and agent endpoints.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldWorkspace {
    pub org: String,
    pub repo: String,
    pub day: String,
    pub operator_dir: String,
    pub changes_path: String,
    pub checkpoints_path: String,
    pub artifacts: Vec<ScaffoldArtifact>,
}

/// Persist an operator edit to an existing discovered artifact.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldArtifactPatch {
    pub artifact_id: String,
    pub content: String,
}

/// Persist an approve/checkpoint decision for an artifact.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldCheckpointPatch {
    pub artifact_id: String,
    pub approved: bool,
    pub note: String,
}

/// Append-only agent-readable edit/checkpoint feed.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScaffoldChange {
    pub ts: String,
    pub artifact_id: String,
    pub relative_path: String,
    pub kind: ScaffoldArtifactKind,
    pub action: String,
    pub bytes: usize,
    pub checkpointed: bool,
    pub note: String,
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

    #[must_use]
    pub fn operator_dir(&self, org: &str, repo: &str, day: &str) -> PathBuf {
        self.home
            .join("artifacts")
            .join(org)
            .join(repo)
            .join(day)
            .join("operator")
    }

    fn checked_operator_dir(&self, org: &str, repo: &str, day: &str) -> io::Result<PathBuf> {
        validate_path_segment(org, "org")?;
        validate_path_segment(repo, "repo")?;
        validate_path_segment(day, "day")?;
        Ok(self.operator_dir(org, repo, day))
    }

    pub fn latest_workspace(&self) -> io::Result<ScaffoldWorkspace> {
        let mut candidates = Vec::new();
        collect_operator_dirs(&self.home.join("artifacts"), &mut candidates);
        candidates.sort();
        let Some(path) = candidates.pop() else {
            return Err(io::Error::new(
                io::ErrorKind::NotFound,
                "no scaffold operator artifact directory found",
            ));
        };
        let (org, repo, day) = split_operator_dir(&self.home, &path)?;
        self.workspace(&org, &repo, &day)
    }

    pub fn workspace(&self, org: &str, repo: &str, day: &str) -> io::Result<ScaffoldWorkspace> {
        let operator_dir = self.checked_operator_dir(org, repo, day)?;
        let checkpoints = read_checkpoints(&checkpoint_path(&operator_dir));
        let mut paths = discover_artifact_paths(&operator_dir);
        paths.sort_by(|a, b| {
            artifact_sort_key(&operator_dir, a).cmp(&artifact_sort_key(&operator_dir, b))
        });

        let mut artifacts = Vec::new();
        for path in paths {
            let relative = relative_string(&operator_dir, &path)?;
            let content = fs::read_to_string(&path)?;
            let id = artifact_id(&relative);
            let kind = classify_artifact(&relative);
            let modified_at = modified_at(&path);
            let checkpoint =
                checkpoints
                    .artifacts
                    .get(&id)
                    .cloned()
                    .unwrap_or_else(|| ScaffoldCheckpoint {
                        artifact_id: id.clone(),
                        approved: false,
                        note: String::new(),
                        updated_at: String::new(),
                    });
            artifacts.push(ScaffoldArtifact {
                id,
                title: artifact_title(&relative, kind),
                kind,
                path: path.display().to_string(),
                relative_path: relative,
                bytes: content.len(),
                content,
                modified_at,
                checkpoint,
            });
        }

        Ok(ScaffoldWorkspace {
            org: org.to_string(),
            repo: repo.to_string(),
            day: day.to_string(),
            operator_dir: operator_dir.display().to_string(),
            changes_path: changes_path(&operator_dir).display().to_string(),
            checkpoints_path: checkpoint_path(&operator_dir).display().to_string(),
            artifacts,
        })
    }

    pub fn write_artifact(
        &self,
        org: &str,
        repo: &str,
        day: &str,
        patch: ScaffoldArtifactPatch,
    ) -> io::Result<ScaffoldArtifact> {
        let operator_dir = self.checked_operator_dir(org, repo, day)?;
        let workspace = self.workspace(org, repo, day)?;
        let artifact = workspace
            .artifacts
            .iter()
            .find(|artifact| artifact.id == patch.artifact_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "artifact id not found"))?;
        let path = artifact_write_path(&operator_dir, artifact)?;
        write_atomic(&path, patch.content.as_bytes())?;
        let refreshed = self
            .workspace(org, repo, day)?
            .artifacts
            .into_iter()
            .find(|candidate| candidate.id == artifact.id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "artifact vanished"))?;
        append_change(
            &operator_dir,
            ScaffoldChange {
                ts: now_ts(),
                artifact_id: refreshed.id.clone(),
                relative_path: refreshed.relative_path.clone(),
                kind: refreshed.kind,
                action: "edit".to_string(),
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
        patch: ScaffoldCheckpointPatch,
    ) -> io::Result<ScaffoldCheckpoint> {
        let operator_dir = self.checked_operator_dir(org, repo, day)?;
        let workspace = self.workspace(org, repo, day)?;
        let artifact = workspace
            .artifacts
            .iter()
            .find(|artifact| artifact.id == patch.artifact_id)
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "artifact id not found"))?;
        let mut store = read_checkpoints(&checkpoint_path(&operator_dir));
        let checkpoint = ScaffoldCheckpoint {
            artifact_id: artifact.id.clone(),
            approved: patch.approved,
            note: patch.note,
            updated_at: now_ts(),
        };
        store
            .artifacts
            .insert(checkpoint.artifact_id.clone(), checkpoint.clone());
        write_checkpoints(&checkpoint_path(&operator_dir), &store)?;
        append_change(
            &operator_dir,
            ScaffoldChange {
                ts: checkpoint.updated_at.clone(),
                artifact_id: artifact.id.clone(),
                relative_path: artifact.relative_path.clone(),
                kind: artifact.kind,
                action: "checkpoint".to_string(),
                bytes: artifact.bytes,
                checkpointed: checkpoint.approved,
                note: checkpoint.note.clone(),
            },
        )?;
        Ok(checkpoint)
    }

    pub fn changes(&self, org: &str, repo: &str, day: &str) -> io::Result<Vec<ScaffoldChange>> {
        let operator_dir = self.checked_operator_dir(org, repo, day)?;
        let path = changes_path(&operator_dir);
        let Ok(text) = fs::read_to_string(path) else {
            return Ok(Vec::new());
        };
        Ok(text
            .lines()
            .filter_map(|line| serde_json::from_str::<ScaffoldChange>(line).ok())
            .collect())
    }
}

fn collect_operator_dirs(root: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if entry.file_type().is_ok_and(|ft| ft.is_dir()) {
            if path.file_name().and_then(|name| name.to_str()) == Some("operator") {
                out.push(path);
            } else {
                collect_operator_dirs(&path, out);
            }
        }
    }
}

fn split_operator_dir(home: &Path, operator_dir: &Path) -> io::Result<(String, String, String)> {
    let relative = operator_dir
        .strip_prefix(home.join("artifacts"))
        .map_err(|_| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                "operator dir outside artifacts",
            )
        })?;
    let parts: Vec<String> = relative
        .components()
        .filter_map(|component| match component {
            Component::Normal(part) => part.to_str().map(ToString::to_string),
            _ => None,
        })
        .collect();
    if parts.len() < 4 || parts[3] != "operator" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "operator dir must be artifacts/<org>/<repo>/<day>/operator",
        ));
    }
    Ok((parts[0].clone(), parts[1].clone(), parts[2].clone()))
}

fn discover_artifact_paths(operator_dir: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let master = operator_dir.join("master-dispatch.md");
    if master.is_file() {
        paths.push(master);
    }
    collect_markdown(&operator_dir.join("briefs"), &mut paths);
    collect_markdown(&operator_dir.join("designs"), &mut paths);
    collect_markdown(&operator_dir.join("design-docs"), &mut paths);
    collect_top_level_design_docs(operator_dir, &mut paths);
    paths
}

fn collect_markdown(root: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        match entry.file_type() {
            Ok(ft) if ft.is_dir() => collect_markdown(&path, out),
            Ok(ft)
                if ft.is_file() && path.extension().and_then(|ext| ext.to_str()) == Some("md") =>
            {
                out.push(path);
            }
            _ => {}
        }
    }
}

fn collect_top_level_design_docs(operator_dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(operator_dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if !entry.file_type().is_ok_and(|ft| ft.is_file()) {
            continue;
        }
        if path.extension().and_then(|ext| ext.to_str()) != Some("md") {
            continue;
        }
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or_default()
            .to_ascii_lowercase();
        if name.contains("design") {
            out.push(path);
        }
    }
}

fn artifact_sort_key(operator_dir: &Path, path: &Path) -> (u8, String) {
    let relative =
        relative_string(operator_dir, path).unwrap_or_else(|_| path.display().to_string());
    let kind = classify_artifact(&relative);
    let rank = match kind {
        ScaffoldArtifactKind::WaveAtlas => 0,
        ScaffoldArtifactKind::Brief => 1,
        ScaffoldArtifactKind::DesignDoc => 2,
        ScaffoldArtifactKind::Other => 3,
    };
    (rank, relative)
}

fn relative_string(root: &Path, path: &Path) -> io::Result<String> {
    path.strip_prefix(root)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "artifact outside operator dir"))
        .map(|relative| relative.to_string_lossy().replace('\\', "/"))
}

fn validate_path_segment(value: &str, label: &str) -> io::Result<()> {
    let invalid = value.is_empty()
        || value == "."
        || value == ".."
        || value.contains('/')
        || value.contains('\\');
    if invalid {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid scaffold {label} path segment"),
        ));
    }
    Ok(())
}

fn artifact_write_path(operator_dir: &Path, artifact: &ScaffoldArtifact) -> io::Result<PathBuf> {
    let relative = safe_relative_markdown_path(&artifact.relative_path)?;
    let path = operator_dir.join(relative);
    reject_unsafe_artifact_path(operator_dir, &path)?;
    Ok(path)
}

fn safe_relative_markdown_path(relative: &str) -> io::Result<PathBuf> {
    if relative.is_empty() || relative.starts_with('/') || relative.starts_with('\\') {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "refusing unsafe scaffold artifact path",
        ));
    }
    let mut clean = PathBuf::new();
    for part in relative.split('/') {
        let invalid = part.is_empty() || part == "." || part == ".." || part.contains('\\');
        if invalid {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "refusing unsafe scaffold artifact path",
            ));
        }
        clean.push(part);
    }
    if clean.extension().and_then(|ext| ext.to_str()) != Some("md") {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "refusing to write non-Markdown scaffold artifact",
        ));
    }
    Ok(clean)
}

fn artifact_id(relative: &str) -> String {
    relative
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_') {
                c
            } else {
                '_'
            }
        })
        .collect()
}

fn classify_artifact(relative: &str) -> ScaffoldArtifactKind {
    let lower = relative.to_ascii_lowercase();
    if lower == "master-dispatch.md" {
        ScaffoldArtifactKind::WaveAtlas
    } else if lower.starts_with("briefs/") {
        ScaffoldArtifactKind::Brief
    } else if lower.contains("design") {
        ScaffoldArtifactKind::DesignDoc
    } else {
        ScaffoldArtifactKind::Other
    }
}

fn artifact_title(relative: &str, kind: ScaffoldArtifactKind) -> String {
    if kind == ScaffoldArtifactKind::WaveAtlas {
        return "Wave atlas".to_string();
    }
    let file_name = relative
        .rsplit('/')
        .next()
        .filter(|part| !part.is_empty())
        .unwrap_or(relative);
    let stem = file_name.strip_suffix(".md").unwrap_or(file_name);
    stem.replace(['_', '-'], " ")
}

fn modified_at(path: &Path) -> String {
    let Ok(modified) = fs::metadata(path).and_then(|metadata| metadata.modified()) else {
        return String::new();
    };
    let dt: chrono::DateTime<Utc> = modified.into();
    dt.to_rfc3339()
}

fn checkpoint_path(operator_dir: &Path) -> PathBuf {
    operator_dir.join(".scaffold-checkpoints.json")
}

fn changes_path(operator_dir: &Path) -> PathBuf {
    operator_dir.join(".scaffold-changes.jsonl")
}

fn read_checkpoints(path: &Path) -> CheckpointStore {
    fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<CheckpointStore>(&text).ok())
        .unwrap_or_default()
}

fn write_checkpoints(path: &Path, store: &CheckpointStore) -> io::Result<()> {
    let bytes = serde_json::to_vec_pretty(store).map_err(io::Error::other)?;
    write_atomic(path, &bytes)
}

/// Atomic write: stage into a sibling temp file then rename over the target.
/// A same-directory rename is atomic on POSIX, so a crash mid-write or a
/// concurrent reader never observes a truncated artifact or checkpoint store —
/// `read_checkpoints` silently degrades a corrupt file to `default()`, and a
/// half-written artifact is lost operator work (the only editable surface).
fn write_atomic(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("scaffold");
    let tmp = parent.join(format!(".{file_name}.tmp.{}", std::process::id()));
    fs::write(&tmp, bytes)?;
    match fs::rename(&tmp, path) {
        Ok(()) => Ok(()),
        Err(err) => {
            let _ = fs::remove_file(&tmp);
            Err(err)
        }
    }
}

fn append_change(operator_dir: &Path, change: ScaffoldChange) -> io::Result<()> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(changes_path(operator_dir))?;
    let line = serde_json::to_string(&change).map_err(io::Error::other)?;
    writeln!(file, "{line}")
}

fn reject_unsafe_artifact_path(operator_dir: &Path, path: &Path) -> io::Result<()> {
    if !path.starts_with(operator_dir) {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "refusing to write outside operator artifact dir",
        ));
    }
    if path.extension().and_then(|ext| ext.to_str()) != Some("md") {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "refusing to write non-Markdown scaffold artifact",
        ));
    }
    Ok(())
}

fn now_ts() -> String {
    Utc::now().to_rfc3339()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_relative_markdown_path_rejects_traversal_and_absolute_paths() {
        for relative in [
            "",
            "/brief.md",
            "\\brief.md",
            "../brief.md",
            "briefs/../brief.md",
            "briefs/./brief.md",
            "briefs\\brief.md",
            "briefs/brief.txt",
        ] {
            assert!(
                safe_relative_markdown_path(relative).is_err(),
                "{relative} should be rejected"
            );
        }
    }

    #[test]
    fn safe_relative_markdown_path_accepts_nested_markdown_paths() {
        let path = safe_relative_markdown_path("briefs/WS-1_cut.md").expect("safe path");
        assert_eq!(path, PathBuf::from("briefs").join("WS-1_cut.md"));
    }

    #[test]
    fn artifact_title_uses_string_segments_not_filesystem_resolution() {
        assert_eq!(
            artifact_title("briefs/WS-1_design.md", ScaffoldArtifactKind::Brief),
            "WS 1 design"
        );
        assert_eq!(
            artifact_title("../escape.md", ScaffoldArtifactKind::Other),
            "escape"
        );
    }
}

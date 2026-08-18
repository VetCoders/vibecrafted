//! AICX memory pane for `voc`.
//!
//! `aicx wizard` stays the interactive search surface. This pane is the
//! always-on continuity strip so observation and intent live in one console.

use std::process::{Command, Stdio};
use std::time::Duration;

/// PATH for the `aicx` subprocess: the inherited entries minus anything that
/// is an implicit current-directory lookup (empty segments, relative paths),
/// with the system set as the fallback when nothing sane survives.
fn sane_tool_path() -> String {
    let inherited = std::env::var("PATH").unwrap_or_default();
    let mut entries: Vec<&str> = inherited
        .split(':')
        .filter(|entry| !entry.is_empty() && entry.starts_with('/'))
        .collect();
    entries.dedup();
    if entries.is_empty() {
        return "/usr/local/bin:/usr/bin:/bin".to_string();
    }
    entries.join(":")
}

fn aicx() -> Command {
    let mut command = Command::new("aicx");
    command.env("PATH", sane_tool_path());
    command
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct MemoryState {
    pub project: String,
    pub lines: Vec<String>,
    pub error: Option<String>,
}

pub fn default_project(launch_root: &std::path::Path) -> String {
    launch_root
        .file_name()
        .and_then(|name| name.to_str())
        .map(|name| format!("/{name}"))
        .unwrap_or_else(|| "/vibecrafted".to_string())
}

pub fn load_continuity(project: &str) -> MemoryState {
    let output = aicx()
        .args(["continuity", "show", "-p", project, "-H", "24"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();

    match output {
        Ok(result) if result.status.success() => {
            let text = String::from_utf8_lossy(&result.stdout);
            let lines: Vec<String> = text
                .lines()
                .filter(|line| !line.trim().is_empty())
                .take(80)
                .map(ToOwned::to_owned)
                .collect();
            MemoryState {
                project: project.to_string(),
                lines: if lines.is_empty() {
                    vec!["no continuity in the last 24h".to_string()]
                } else {
                    lines
                },
                error: None,
            }
        }
        Ok(result) => MemoryState {
            project: project.to_string(),
            lines: Vec::new(),
            error: Some(
                String::from_utf8_lossy(&result.stderr)
                    .lines()
                    .next()
                    .unwrap_or("aicx continuity failed")
                    .to_string(),
            ),
        },
        Err(error) => MemoryState {
            project: project.to_string(),
            lines: Vec::new(),
            error: Some(format!("aicx not available: {error}")),
        },
    }
}

pub fn launch_wizard(project: &str) -> anyhow::Result<()> {
    let status = aicx()
        .args(["wizard", "--view", "search", "-p", project])
        .status()?;
    if !status.success() {
        anyhow::bail!("aicx wizard exited {status}");
    }
    Ok(())
}

pub fn wizard_hint() -> &'static str {
    "w  aicx wizard   ·   m  refresh memory   ·   server is the donor"
}

#[allow(dead_code)]
const _REFRESH_HINT: Duration = Duration::from_secs(30);

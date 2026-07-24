//! Delegate destructive signals to `vibecrafted procs terminate`.

use std::process::Command;

use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct TerminateRequest {
    pub pid: u32,
    pub expected_start: String,
    pub expected_command_sha256: String,
    pub expected_run_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TerminateResult {
    pub ok: bool,
    pub outcome: String,
    #[serde(default)]
    pub detail: String,
}

pub fn terminate_via_cli(req: &TerminateRequest) -> anyhow::Result<TerminateResult> {
    let output = Command::new("vibecrafted")
        .args([
            "procs",
            "terminate",
            "--pid",
            &req.pid.to_string(),
            "--expected-start",
            &req.expected_start,
            "--expected-command-sha256",
            &req.expected_command_sha256,
            "--expected-run-id",
            &req.expected_run_id,
        ])
        .output()?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: TerminateResult = serde_json::from_str(stdout.trim()).unwrap_or(TerminateResult {
        ok: output.status.success(),
        outcome: if output.status.success() {
            "ok".into()
        } else {
            "error".into()
        },
        detail: String::from_utf8_lossy(&output.stderr).trim().to_string(),
    });
    Ok(parsed)
}

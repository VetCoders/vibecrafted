use anyhow::Context;
use std::collections::BTreeMap;
use std::env;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchKind {
    Workflow,
    Research,
    Review,
    Marbles,
}

impl LaunchKind {
    pub fn label(self) -> &'static str {
        match self {
            LaunchKind::Workflow => "workflow",
            LaunchKind::Research => "research",
            LaunchKind::Review => "review",
            LaunchKind::Marbles => "marbles",
        }
    }

    pub fn human_title(self) -> &'static str {
        match self {
            LaunchKind::Workflow => "Workflow",
            LaunchKind::Research => "Research swarm",
            LaunchKind::Review => "Review",
            LaunchKind::Marbles => "Marbles loop",
        }
    }

    pub fn human_description(self) -> &'static str {
        match self {
            LaunchKind::Workflow => {
                "Best default. Examine the surface, plan the cut, then implement."
            }
            LaunchKind::Research => "Send a research pass first when the shape is still unclear.",
            LaunchKind::Review => {
                "Audit an existing surface for risk, regressions, and weak claims."
            }
            LaunchKind::Marbles => {
                "Run convergence loops when the code works but still lies or drifts."
            }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum LaunchRuntime {
    Headless,
    #[default]
    Terminal,
    Visible,
}

impl LaunchRuntime {
    pub fn label(self) -> &'static str {
        match self {
            LaunchRuntime::Headless => "headless",
            LaunchRuntime::Terminal => "terminal",
            LaunchRuntime::Visible => "visible",
        }
    }

    pub fn cycle(self) -> Self {
        match self {
            LaunchRuntime::Headless => LaunchRuntime::Terminal,
            LaunchRuntime::Terminal => LaunchRuntime::Visible,
            LaunchRuntime::Visible => LaunchRuntime::Headless,
        }
    }
}

impl FromStr for LaunchRuntime {
    type Err = anyhow::Error;

    fn from_str(raw: &str) -> Result<Self, Self::Err> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "headless" => Ok(Self::Headless),
            "terminal" => Ok(Self::Terminal),
            "visible" => Ok(Self::Visible),
            other => Err(anyhow::anyhow!(
                "unsupported runtime: {other} (expected headless|terminal|visible)"
            )),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LaunchRequest {
    pub kind: LaunchKind,
    pub agent: String,
    pub prompt: String,
    pub runtime: LaunchRuntime,
    pub root: Option<PathBuf>,
    pub terminal_binary: Option<PathBuf>,
    pub env: BTreeMap<String, OsString>,
    pub count: Option<u32>,
    pub depth: Option<u32>,
    pub session_name: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LaunchCommand {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub env: BTreeMap<String, OsString>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LaunchReadinessProbe {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub env: BTreeMap<String, OsString>,
    pub session_name: String,
}

impl LaunchCommand {
    pub fn command_line(&self) -> String {
        let mut parts = vec![self.program.to_string_lossy().into_owned()];
        parts.extend(
            self.args
                .iter()
                .map(|value| value.to_string_lossy().into_owned()),
        );
        parts.join(" ")
    }

    pub fn spawn(&self) -> anyhow::Result<std::process::Child> {
        let mut command = Command::new(&self.program);
        command.args(&self.args);
        command.envs(&self.env);
        command.stdin(Stdio::inherit());
        command.stdout(Stdio::inherit());
        command.stderr(Stdio::inherit());
        command.spawn().context("failed to spawn launch command")
    }

    pub fn spawn_detached(&self) -> anyhow::Result<std::process::Child> {
        let mut command = Command::new(&self.program);
        command.args(&self.args);
        command.envs(&self.env);
        command.stdin(Stdio::null());
        command.stdout(Stdio::null());
        command.stderr(Stdio::null());
        command.spawn().context("failed to spawn launch command")
    }

    pub fn spawn_interactive_with_stderr(&self) -> anyhow::Result<std::process::Child> {
        let mut command = Command::new(&self.program);
        command.args(&self.args);
        command.envs(&self.env);
        command.stdin(Stdio::inherit());
        command.stdout(Stdio::inherit());
        command.stderr(Stdio::piped());
        command.spawn().context("failed to spawn launch command")
    }

    pub fn readiness_probe(&self) -> Option<LaunchReadinessProbe> {
        let session_name = self
            .args
            .windows(2)
            .find(|pair| pair.first().is_some_and(|value| value == "--session"))
            .and_then(|pair| pair.get(1))
            .map(|value| value.to_string_lossy().into_owned())?;
        // The launch command may carry a top-level `--config-dir <dir>` flag so
        // that zellij talks to the repo-local namespace under
        // `<root>/config/zellij`. The readiness probe MUST inspect the same
        // namespace, otherwise it can succeed/fail against a completely
        // different socket directory and report nonsense to the operator.
        let config_dir = self
            .args
            .windows(2)
            .find(|pair| pair.first().is_some_and(|value| value == "--config-dir"))
            .and_then(|pair| pair.get(1))
            .cloned();
        let mut args: Vec<OsString> = Vec::new();
        if let Some(dir) = config_dir {
            args.push("--config-dir".into());
            args.push(dir);
        }
        args.push("list-sessions".into());
        args.push("--short".into());
        args.push("--no-formatting".into());
        Some(LaunchReadinessProbe {
            program: self.program.clone(),
            args,
            env: self.env.clone(),
            session_name,
        })
    }
}

impl LaunchReadinessProbe {
    pub fn is_session_visible(&self) -> anyhow::Result<bool> {
        let output = Command::new(&self.program)
            .args(&self.args)
            .envs(&self.env)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .context("failed to run zellij readiness probe")?;
        if !output.status.success() {
            // A non-zero exit with diagnostic stderr is a real probe error
            // (bad flags, broken config, permission denied, missing socket
            // root, etc.) and must surface to the operator overlay rather
            // than collapsing into "session not visible". A non-zero exit
            // with empty stderr is treated as a benign "no sessions yet"
            // signal so we keep polling. zellij itself prints the
            // "No active zellij sessions found." message on stderr, so the
            // empty-stderr branch is only reached for stripped/quiet
            // implementations or wrappers that intentionally silence
            // diagnostics.
            let stderr = String::from_utf8_lossy(&output.stderr);
            if !stderr.trim().is_empty() {
                anyhow::bail!(
                    "zellij readiness probe exited with {}: {}",
                    output.status,
                    stderr.trim()
                );
            }
            return Ok(false);
        }
        let stdout = String::from_utf8_lossy(&output.stdout);
        Ok(stdout.lines().any(|line| line.trim() == self.session_name))
    }
}

pub fn build_launch_command(deck: impl AsRef<Path>, request: &LaunchRequest) -> LaunchCommand {
    let deck = deck.as_ref();
    if matches!(
        request.runtime,
        LaunchRuntime::Terminal | LaunchRuntime::Visible
    ) {
        return build_terminal_launch_command(deck, request);
    }
    build_deck_launch_command(deck, request)
}

fn build_deck_launch_command(deck: &Path, request: &LaunchRequest) -> LaunchCommand {
    let mut args: Vec<OsString> = vec![request.kind.label().into()];
    match request.kind {
        LaunchKind::Workflow | LaunchKind::Review => {
            args.push(request.agent.clone().into());
            if !request.prompt.trim().is_empty() {
                args.push("--prompt".into());
                args.push(request.prompt.clone().into());
            }
        }
        LaunchKind::Research => {
            if !request.prompt.trim().is_empty() {
                args.push("--prompt".into());
                args.push(request.prompt.clone().into());
            }
        }
        LaunchKind::Marbles => {
            args.push(request.agent.clone().into());
            args.push("--count".into());
            args.push(request.count.unwrap_or(3).to_string().into());
            args.push("--depth".into());
            args.push(request.depth.unwrap_or(3).to_string().into());
            if !request.prompt.trim().is_empty() {
                args.push("--prompt".into());
                args.push(request.prompt.clone().into());
            }
        }
    }
    args.push("--runtime".into());
    args.push(request.runtime.label().into());
    if let Some(root) = request.root.as_ref() {
        args.push("--root".into());
        args.push(root.as_os_str().to_os_string());
    }
    LaunchCommand {
        program: deck.to_path_buf(),
        args,
        env: request.env.clone(),
    }
}

fn build_terminal_launch_command(deck: &Path, request: &LaunchRequest) -> LaunchCommand {
    let zellij_layout = build_zellij_layout_string(deck, request);
    let zellij_config_dir = resolved_zellij_config_dir(request.root.as_deref());

    let mut args = Vec::new();

    // Stable session name (when provided) goes before the subcommand so the
    // operator can `zellij attach <name>` from another terminal and so future
    // healthcheck paths can target the named socket.
    if let Some(name) = request.session_name.as_deref() {
        args.push("--session".into());
        args.push(name.into());
    }

    // We are running zellij in-place.
    args.push("options".into());

    if let Some(config_dir) = zellij_config_dir {
        args.push("--config-dir".into());
        args.push(config_dir.into_os_string());
    }

    args.push("--layout-string".into());
    args.push(zellij_layout.into());

    LaunchCommand {
        program: request
            .terminal_binary
            .clone()
            .unwrap_or_else(|| PathBuf::from("zellij")),
        args,
        env: request.env.clone(),
    }
}

fn build_zellij_layout_string(deck: &Path, request: &LaunchRequest) -> String {
    let mut layout = format!(
        "layout {{ tab name={} focus=true {{ pane name={} focus=true command={} ",
        kdl_quote(&format!("Operator {}", request.kind.human_title())),
        kdl_quote("launch"),
        kdl_quote("bash"),
    );
    if let Some(root) = request.root.as_deref() {
        layout.push_str(&format!("cwd={} ", kdl_quote(&root.to_string_lossy())));
    }
    layout.push_str("{ args ");
    layout.push_str(&kdl_quote("-lc"));
    layout.push(' ');
    layout.push_str(&kdl_quote(&build_pane_shell_command(deck, request)));
    layout.push_str(" } } } }");
    layout
}

fn build_pane_shell_command(deck: &Path, request: &LaunchRequest) -> String {
    let mut parts = Vec::new();
    if let Some(config_dir) = resolved_zellij_config_dir(request.root.as_deref()) {
        parts.push(format!(
            "export ZELLIJ_CONFIG_DIR={}",
            shell_quote(&config_dir.to_string_lossy())
        ));
    }
    for (key, value) in &request.env {
        parts.push(format!(
            "export {}={}",
            shell_name(key),
            shell_quote(&value.to_string_lossy())
        ));
    }
    parts.extend(tooling_profile_snippets());
    parts.push(format!(
        "exec {}",
        shell_join(deck, &build_deck_launch_command(deck, request).args)
    ));
    parts.join("; ")
}

fn resolved_zellij_config_dir(root: Option<&Path>) -> Option<PathBuf> {
    if let Some(explicit) = env::var_os("ZELLIJ_CONFIG_DIR").filter(|value| !value.is_empty()) {
        return Some(PathBuf::from(explicit));
    }
    let root = root?;
    let repo_config_dir = root.join("config/zellij");
    repo_config_dir
        .join("config.kdl")
        .is_file()
        .then_some(repo_config_dir)
}

fn shell_join(program: &Path, args: &[OsString]) -> String {
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push(shell_quote(&program.to_string_lossy()));
    parts.extend(
        args.iter()
            .map(|value| shell_quote(&value.to_string_lossy())),
    );
    parts.join(" ")
}

fn shell_quote(raw: &str) -> String {
    format!("'{}'", raw.replace('\'', "'\"'\"'"))
}

fn shell_name(raw: &str) -> String {
    raw.chars()
        .filter(|ch| ch.is_ascii_alphanumeric() || *ch == '_')
        .collect()
}

fn tooling_profile_snippets() -> Vec<String> {
    vec![
        "if command -v starship >/dev/null 2>&1; then eval \"$(starship init bash)\"; fi"
            .to_string(),
        "if command -v zoxide >/dev/null 2>&1; then eval \"$(zoxide init bash)\"; fi".to_string(),
        "if command -v atuin >/dev/null 2>&1; then eval \"$(atuin init bash --disable-up-arrow)\"; fi"
            .to_string(),
    ]
}

fn kdl_quote(raw: &str) -> String {
    let escaped = raw
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n");
    format!("\"{escaped}\"")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VerifyHalt {
    Drift(Vec<rust_mux::ipc::command::NonMuxEntry>),
    Timeout,
}

pub fn pre_launch_verify(client_kind: rust_mux::ipc::ClientKind) -> Result<(), VerifyHalt> {
    use std::io::{BufRead, BufReader, Write};
    use std::os::unix::net::UnixStream;
    use std::time::Duration;

    let path = rust_mux::ipc::socket_path();
    let stream = match UnixStream::connect(&path) {
        Ok(s) => s,
        Err(_) => return Ok(()),
    };

    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(5)));

    let cmd = rust_mux::ipc::MuxControlCommand::Verify { client_kind };
    let Ok(json) = serde_json::to_string(&cmd) else {
        return Ok(());
    };

    let mut writer = &stream;
    if writeln!(writer, "{json}").is_err() {
        return Err(VerifyHalt::Timeout);
    }

    let mut reader = BufReader::new(stream);
    let mut response_line = String::new();
    if reader.read_line(&mut response_line).is_err() || response_line.is_empty() {
        return Err(VerifyHalt::Timeout);
    }

    if let Ok(rust_mux::ipc::MuxControlResponse::VerifyResult(res)) =
        serde_json::from_str(&response_line)
        && !res.ok
    {
        return Err(VerifyHalt::Drift(res.non_mux_servers));
    }
    Ok(())
}

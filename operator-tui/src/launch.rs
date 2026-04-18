use anyhow::Context;
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
    pub count: Option<u32>,
    pub depth: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LaunchCommand {
    pub program: PathBuf,
    pub args: Vec<OsString>,
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
        command.stdin(Stdio::inherit());
        command.stdout(Stdio::inherit());
        command.stderr(Stdio::inherit());
        command.spawn().context("failed to launch command deck")
    }
}

pub fn build_launch_command(deck: impl AsRef<Path>, request: &LaunchRequest) -> LaunchCommand {
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
        program: deck.as_ref().to_path_buf(),
        args,
    }
}

use crate::launch::LaunchRuntime;
use std::env;
use std::path::{Path, PathBuf};
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CliOptions {
    pub state_root: Option<PathBuf>,
    pub command_deck: Option<PathBuf>,
    pub launch_root: Option<PathBuf>,
    pub launch_runtime: Option<LaunchRuntime>,
    pub tick_ms: u64,
}

impl Default for CliOptions {
    fn default() -> Self {
        Self {
            state_root: None,
            command_deck: None,
            launch_root: None,
            launch_runtime: None,
            tick_ms: 250,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppConfig {
    pub state_root: PathBuf,
    pub command_deck: PathBuf,
    pub launch_root: PathBuf,
    pub launch_runtime: LaunchRuntime,
    pub tick_rate: Duration,
}

pub fn parse_args() -> anyhow::Result<CliOptions> {
    let mut options = CliOptions::default();
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => {
                print_help();
                std::process::exit(0);
            }
            "--state-root" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow::anyhow!("--state-root requires a value"))?;
                options.state_root = Some(PathBuf::from(value));
            }
            _ if arg.starts_with("--state-root=") => {
                options.state_root = Some(PathBuf::from(arg.trim_start_matches("--state-root=")));
            }
            "--deck" | "--command-deck" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow::anyhow!("--deck requires a value"))?;
                options.command_deck = Some(PathBuf::from(value));
            }
            _ if arg.starts_with("--deck=") || arg.starts_with("--command-deck=") => {
                let value = arg
                    .split_once('=')
                    .map(|(_, value)| value)
                    .unwrap_or_default();
                options.command_deck = Some(PathBuf::from(value));
            }
            "--root" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow::anyhow!("--root requires a value"))?;
                options.launch_root = Some(PathBuf::from(value));
            }
            _ if arg.starts_with("--root=") => {
                options.launch_root = Some(PathBuf::from(arg.trim_start_matches("--root=")));
            }
            "--runtime" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow::anyhow!("--runtime requires a value"))?;
                options.launch_runtime = Some(value.parse::<LaunchRuntime>()?);
            }
            _ if arg.starts_with("--runtime=") => {
                let value = arg
                    .split_once('=')
                    .map(|(_, value)| value)
                    .unwrap_or_default();
                options.launch_runtime = Some(value.parse::<LaunchRuntime>()?);
            }
            "--tick-ms" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow::anyhow!("--tick-ms requires a value"))?;
                options.tick_ms = value.parse::<u64>()?;
            }
            _ => {
                return Err(anyhow::anyhow!("unknown argument: {arg}"));
            }
        }
    }
    Ok(options)
}

pub fn build_config(options: CliOptions) -> AppConfig {
    let command_deck = options.command_deck.unwrap_or_else(default_command_deck);
    AppConfig {
        state_root: options.state_root.unwrap_or_else(default_state_root),
        launch_root: options
            .launch_root
            .unwrap_or_else(|| default_launch_root(&command_deck)),
        launch_runtime: options.launch_runtime.unwrap_or_default(),
        command_deck,
        tick_rate: Duration::from_millis(options.tick_ms.max(50)),
    }
}

pub fn default_vibecrafted_home() -> PathBuf {
    env::var_os("VIBECRAFTED_HOME")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(home_dir()).join(".vibecrafted"))
}

pub fn default_state_root() -> PathBuf {
    let home = default_vibecrafted_home();
    for candidate in [
        home.join("control_plane"),
        home.join("state/control-plane"),
        home.join("state"),
        home.join("control-plane"),
    ] {
        if candidate.exists() {
            return candidate;
        }
    }
    home.join("control_plane")
}

pub fn default_command_deck() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_candidate = manifest_dir.join("../scripts/vibecrafted");
    if repo_candidate.exists() {
        return repo_candidate;
    }
    PathBuf::from("vibecrafted")
}

pub fn default_launch_root(command_deck: &Path) -> PathBuf {
    if let Some(value) = env::var_os("VIBECRAFTED_ROOT").filter(|value| !value.is_empty()) {
        return PathBuf::from(value);
    }
    if command_deck.file_name().and_then(|name| name.to_str()) == Some("vibecrafted")
        && command_deck
            .parent()
            .and_then(|parent| parent.file_name())
            .and_then(|name| name.to_str())
            == Some("scripts")
        && let Some(root) = command_deck.parent().and_then(Path::parent)
    {
        return root.to_path_buf();
    }
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn home_dir() -> String {
    env::var("HOME").unwrap_or_else(|_| ".".to_string())
}

fn print_help() {
    println!("Vibecrafted operator console");
    println!();
    println!("Usage:");
    println!(
        "  vibecrafted-operator [--state-root <dir>] [--deck <path>] [--root <path>] [--runtime <headless|terminal|visible>] [--tick-ms <ms>]"
    );
    println!(
        "  vc-operator           [--state-root <dir>] [--deck <path>] [--root <path>] [--runtime <headless|terminal|visible>] [--tick-ms <ms>]"
    );
    println!();
    println!("Options:");
    println!("  --state-root <dir>   Control-plane state root under VIBECRAFTED_HOME");
    println!("  --deck <path>        Command deck binary or script to launch workflows");
    println!("  --root <path>        Workspace root passed through to launched workflows");
    println!("  --runtime <kind>     Launch runtime (headless|terminal|visible)");
    println!("  --tick-ms <ms>       Refresh cadence for the TUI (default: 250)");
}

pub fn path_display(path: &Path) -> String {
    path.to_string_lossy().into_owned()
}

use std::env;
use std::path::{Path, PathBuf};
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CliOptions {
    pub state_root: Option<PathBuf>,
    pub command_deck: Option<PathBuf>,
    pub tick_ms: u64,
}

impl Default for CliOptions {
    fn default() -> Self {
        Self {
            state_root: None,
            command_deck: None,
            tick_ms: 250,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppConfig {
    pub state_root: PathBuf,
    pub command_deck: PathBuf,
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
    AppConfig {
        state_root: options.state_root.unwrap_or_else(default_state_root),
        command_deck: options.command_deck.unwrap_or_else(default_command_deck),
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

fn home_dir() -> String {
    env::var("HOME").unwrap_or_else(|_| ".".to_string())
}

fn print_help() {
    println!("Vibecrafted operator console");
    println!();
    println!("Usage:");
    println!("  vibecrafted-operator [--state-root <dir>] [--deck <path>] [--tick-ms <ms>]");
    println!();
    println!("Options:");
    println!("  --state-root <dir>   Control-plane state root under VIBECRAFTED_HOME");
    println!("  --deck <path>        Command deck binary or script to launch workflows");
    println!("  --tick-ms <ms>       Refresh cadence for the TUI (default: 250)");
}

pub fn path_display(path: &Path) -> String {
    path.to_string_lossy().into_owned()
}

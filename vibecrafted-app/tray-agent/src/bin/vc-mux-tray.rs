use std::path::PathBuf;

use clap::Parser;
use tracing_subscriber::EnvFilter;

#[derive(Debug, Parser)]
#[command(name = "vc-mux-tray")]
struct Args {
    #[arg(long, default_value = "~/.rust-mux/ipc/control.sock")]
    socket: String,
    #[arg(long, default_value = "info")]
    log_level: String,
    #[arg(long, default_value_t = false)]
    show_dock_icon: bool,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let filter = EnvFilter::try_new(&args.log_level).unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(std::io::stderr)
        .init();
    if args.show_dock_icon {
        tracing::info!("--show-dock-icon requested; dock policy is delegated to the app bundle");
    }
    tray_agent::run_with_ipc(expand_home(&args.socket))
}

fn expand_home(raw: &str) -> PathBuf {
    if let Some(stripped) = raw.strip_prefix("~/")
        && let Some(home) = std::env::var_os("HOME")
    {
        return PathBuf::from(home).join(stripped);
    }
    PathBuf::from(raw)
}

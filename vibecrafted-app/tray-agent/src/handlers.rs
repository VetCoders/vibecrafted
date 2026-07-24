use std::path::{Path, PathBuf};
use std::process::Command;

use crate::ipc_client::{ClientKind, MuxControlResponse};
use arboard::Clipboard;
use muda::MenuId;
use tracing::{debug, warn};

use crate::ipc_client;
use crate::state::{recent_spawns, send_menu_event};
use crate::types::{MenuIds, TrayMenuEvent};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MenuRoute {
    ShowDashboard,
    OpenLogs,
    CopyRoutingTable,
    CopyDiagnostics,
    ContinueOnboarding,
    OpenSettings,
    Help,
    About,
    Quit,
    RestartService(String),
    VerifyClient(ClientKind),
    OpenRecentRun(usize),
}

pub fn resolve_menu_route(event_id: &MenuId, menu_ids: &MenuIds) -> Option<MenuRoute> {
    if event_id == &menu_ids.show_dashboard {
        Some(MenuRoute::ShowDashboard)
    } else if event_id == &menu_ids.open_logs {
        Some(MenuRoute::OpenLogs)
    } else if event_id == &menu_ids.copy_routing_table {
        Some(MenuRoute::CopyRoutingTable)
    } else if event_id == &menu_ids.copy_diagnostics {
        Some(MenuRoute::CopyDiagnostics)
    } else if menu_ids
        .continue_onboarding
        .as_ref()
        .is_some_and(|id| event_id == id)
    {
        Some(MenuRoute::ContinueOnboarding)
    } else if event_id == &menu_ids.open_settings {
        Some(MenuRoute::OpenSettings)
    } else if event_id == &menu_ids.help {
        Some(MenuRoute::Help)
    } else if event_id == &menu_ids.about {
        Some(MenuRoute::About)
    } else if event_id == &menu_ids.quit {
        Some(MenuRoute::Quit)
    } else if let Some(name) = menu_ids.resolve_restart_service(event_id) {
        Some(MenuRoute::RestartService(name))
    } else if let Some(index) = menu_ids.resolve_recent_run(event_id) {
        Some(MenuRoute::OpenRecentRun(index))
    } else {
        menu_ids
            .resolve_verify_client(event_id)
            .map(MenuRoute::VerifyClient)
    }
}

pub fn handle_menu_event(event_id: &MenuId, menu_ids: &MenuIds, socket_path: &Path) {
    match resolve_menu_route(event_id, menu_ids) {
        Some(MenuRoute::ShowDashboard) => {
            send_menu_event(TrayMenuEvent::ShowMuxDashboard);
            let _ = Command::new("sh")
                .arg("-lc")
                .arg("command -v voc >/dev/null 2>&1 && open -a Terminal voc")
                .spawn();
        }
        Some(MenuRoute::OpenLogs) => {
            send_menu_event(TrayMenuEvent::OpenMuxLogs);
            let path = home_path(".rmcp-mux/logs");
            let _ = std::fs::create_dir_all(&path);
            let _ = Command::new("open").arg(&path).spawn();
        }
        Some(MenuRoute::CopyRoutingTable) => {
            run_ipc_copy(socket_path, ipc_client::route_snapshot, "routing table")
        }
        Some(MenuRoute::CopyDiagnostics) => {
            run_ipc_copy(socket_path, ipc_client::diagnostics, "diagnostics")
        }
        Some(MenuRoute::ContinueOnboarding) => {
            send_menu_event(TrayMenuEvent::ContinueOnboarding);
            let _ = Command::new("open")
                .arg("https://vibecrafted.io/en/install")
                .spawn();
        }
        Some(MenuRoute::OpenSettings) => {
            send_menu_event(TrayMenuEvent::OpenSettings);
            let path = home_path(".config/mux/config.toml");
            let editor = std::env::var("EDITOR").unwrap_or_else(|_| "open".to_string());
            let _ = Command::new(editor).arg(path).spawn();
        }
        Some(MenuRoute::Help) => {
            send_menu_event(TrayMenuEvent::OpenHelp);
            let _ = Command::new("open")
                .arg("https://github.com/vetcoders/vibecrafted#readme")
                .spawn();
        }
        Some(MenuRoute::About) => {
            send_menu_event(TrayMenuEvent::ShowAbout);
            notify(
                "About Vibecrafted",
                &format!("vc-mux-tray {}", env!("CARGO_PKG_VERSION")),
            );
        }
        Some(MenuRoute::Quit) => send_menu_event(TrayMenuEvent::Quit),
        Some(MenuRoute::RestartService(name)) => restart_service(socket_path, name),
        Some(MenuRoute::VerifyClient(kind)) => verify_client(socket_path, kind),
        Some(MenuRoute::OpenRecentRun(index)) => open_recent_run(index),
        None => debug!("unknown tray menu event id: {event_id:?}"),
    }
}

fn open_recent_run(index: usize) {
    let Some(entry) = recent_spawns().get(index).cloned() else {
        notify("Vibecrafted", "Recent run is no longer available");
        return;
    };
    send_menu_event(TrayMenuEvent::OpenRecentRun(entry.run_id.clone()));
    if let Some(path) = entry.report.or(entry.transcript) {
        open_path(&path);
    } else {
        notify(
            "Vibecrafted",
            &format!("{} {} is {}", entry.agent, entry.skill, entry.state),
        );
    }
}

fn run_ipc_copy<F, Fut>(socket_path: &Path, call: F, label: &'static str)
where
    F: FnOnce(PathBuf) -> Fut + Send + 'static,
    Fut: std::future::Future<Output = anyhow::Result<String>> + Send + 'static,
{
    let socket = socket_path.to_path_buf();
    std::thread::spawn(move || {
        let result = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(anyhow::Error::from)
            .and_then(|runtime| runtime.block_on(call(socket)));
        match result {
            Ok(text) => {
                if let Err(error) = Clipboard::new().and_then(|mut cb| cb.set_text(text)) {
                    warn!("failed to copy {label}: {error}");
                } else {
                    notify("Vibecrafted", &format!("Copied {label} to clipboard"));
                }
            }
            Err(error) => notify("Vibecrafted", &format!("Could not copy {label}: {error}")),
        }
    });
}

fn restart_service(socket_path: &Path, name: String) {
    send_menu_event(TrayMenuEvent::RestartService(name.clone()));
    let socket = socket_path.to_path_buf();
    std::thread::spawn(move || {
        let result = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(anyhow::Error::from)
            .and_then(|runtime| runtime.block_on(ipc_client::restart_service(&socket, &name)));
        match result {
            Ok(MuxControlResponse::Error(message)) => {
                notify("Vibecrafted", &format!("Restart {name}: {message}"))
            }
            Ok(_) => notify("Vibecrafted", &format!("Restart request sent for {name}")),
            Err(error) => notify("Vibecrafted", &format!("Restart {name} failed: {error}")),
        }
    });
}

fn verify_client(socket_path: &Path, kind: ClientKind) {
    send_menu_event(TrayMenuEvent::VerifyClient(kind.clone()));
    let socket = socket_path.to_path_buf();
    std::thread::spawn(move || {
        let result = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(anyhow::Error::from)
            .and_then(|runtime| runtime.block_on(ipc_client::verify_client(&socket, kind)));
        match result {
            Ok(response) => notify("Vibecrafted", &response),
            Err(error) => notify("Vibecrafted", &format!("Verify failed: {error}")),
        }
    });
}

pub(crate) fn notify_spawn_update(agent: &str, state: &str, run_id: &str) {
    if matches!(state, "completed" | "failed") {
        notify("Vibecrafted run", &format!("{agent} {state}: {run_id}"));
    }
}

pub fn notify_user(title: &str, message: &str) {
    #[cfg(feature = "native-notifications")]
    if let Err(error) = notify_rust::Notification::new()
        .summary(title)
        .body(message)
        .show()
    {
        warn!("failed to show notification: {error}");
    }
    tracing::info!("{title}: {message}");
}

fn notify(title: &str, message: &str) {
    notify_user(title, message);
}

fn open_path(path: &Path) {
    #[cfg(target_os = "macos")]
    let command = "open";
    #[cfg(not(target_os = "macos"))]
    let command = "xdg-open";
    let _ = Command::new(command).arg(path).spawn();
}

fn home_path(path: &str) -> PathBuf {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
        .join(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_dynamic_menu_ids() {
        let ids = MenuIds {
            show_dashboard: MenuId::new("show-dashboard"),
            open_logs: MenuId::new("open-logs"),
            copy_routing_table: MenuId::new("copy-routing"),
            copy_diagnostics: MenuId::new("copy-diagnostics"),
            continue_onboarding: Some(MenuId::new("onboarding")),
            open_settings: MenuId::new("settings"),
            help: MenuId::new("help"),
            about: MenuId::new("about"),
            quit: MenuId::new("quit"),
            restart_services: vec![("memex".to_string(), MenuId::new("restart-memex"))],
            verify_clients: vec![(ClientKind::Claude, MenuId::new("verify-claude"))],
            recent_runs: vec![MenuId::new("recent-run-0")],
        };
        assert_eq!(
            resolve_menu_route(&MenuId::new("restart-memex"), &ids),
            Some(MenuRoute::RestartService("memex".to_string()))
        );
        assert_eq!(
            resolve_menu_route(&MenuId::new("verify-claude"), &ids),
            Some(MenuRoute::VerifyClient(ClientKind::Claude))
        );
    }
}

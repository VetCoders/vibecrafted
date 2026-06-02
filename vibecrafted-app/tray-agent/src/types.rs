use crate::ipc_client::ClientKind;
use anyhow::Result;
use muda::MenuId;
use std::path::PathBuf;
use tracing::debug;
use tray_icon::Icon;

use crate::icons::{create_fallback_icon, load_custom_icon};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayStatus {
    Idle,
    Routing,
    Saturated,
    Restarting,
    Spawning { count: u32 },
    Failed,
}

impl TrayStatus {
    pub fn tooltip(&self) -> String {
        format!("Vibecrafted mux - {}", self.label())
    }

    pub fn label(&self) -> String {
        match self {
            Self::Idle => "Idle".to_string(),
            Self::Routing => "Routing".to_string(),
            Self::Saturated => "Saturated".to_string(),
            Self::Restarting => "Restarting".to_string(),
            Self::Spawning { count } => format!("Spawning ({count})"),
            Self::Failed => "Failed".to_string(),
        }
    }

    pub fn menu_label(&self, service_count: usize) -> String {
        format!("Status: {} ({} services)", self.label(), service_count)
    }

    pub fn to_icon(self) -> Result<Icon> {
        load_custom_icon(self).or_else(|error| {
            debug!("custom tray icon failed, using fallback: {error}");
            create_fallback_icon(self)
        })
    }
}

pub fn silver_label_for_status(status: TrayStatus) -> String {
    status.label()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpawnEntry {
    pub run_id: String,
    pub agent: String,
    pub skill: String,
    pub mode: String,
    pub state: String,
    pub session_id: Option<String>,
    pub exit_code: Option<i32>,
    pub launcher_pid: Option<u32>,
    pub transcript: Option<PathBuf>,
    pub report: Option<PathBuf>,
    pub ts: String,
}

impl SpawnEntry {
    pub fn is_active(&self) -> bool {
        matches!(self.state.as_str(), "launching" | "running")
    }

    pub fn menu_label(&self) -> String {
        format!("{} {} {}", self.agent, self.skill, self.state)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TrayUpdate {
    Status(TrayStatus),
    SpawnBadge {
        active: u32,
        last_agent: String,
        last_state: String,
        last_run_id: String,
    },
    Alert(String),
    None,
}

#[derive(Debug, Clone)]
pub enum TrayMenuEvent {
    ShowMuxDashboard,
    OpenMuxLogs,
    CopyRoutingTable,
    CopyDiagnostics,
    RestartService(String),
    VerifyClient(ClientKind),
    OpenRecentRun(String),
    ContinueOnboarding,
    OpenSettings,
    OpenHelp,
    ShowAbout,
    Quit,
}

pub struct MenuIds {
    pub show_dashboard: MenuId,
    pub open_logs: MenuId,
    pub copy_routing_table: MenuId,
    pub copy_diagnostics: MenuId,
    pub continue_onboarding: Option<MenuId>,
    pub open_settings: MenuId,
    pub help: MenuId,
    pub about: MenuId,
    pub quit: MenuId,
    pub restart_services: Vec<(String, MenuId)>,
    pub verify_clients: Vec<(ClientKind, MenuId)>,
    pub recent_runs: Vec<MenuId>,
}

impl MenuIds {
    pub fn resolve_restart_service(&self, id: &MenuId) -> Option<String> {
        self.restart_services
            .iter()
            .find_map(|(name, item_id)| (item_id == id).then(|| name.clone()))
    }

    pub fn resolve_verify_client(&self, id: &MenuId) -> Option<ClientKind> {
        self.verify_clients
            .iter()
            .find_map(|(kind, item_id)| (item_id == id).then(|| kind.clone()))
    }

    pub fn resolve_recent_run(&self, id: &MenuId) -> Option<usize> {
        self.recent_runs.iter().position(|item_id| item_id == id)
    }
}

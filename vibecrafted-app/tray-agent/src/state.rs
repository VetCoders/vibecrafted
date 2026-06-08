use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

use crossbeam_channel::{Receiver, Sender, unbounded};
use tracing::debug;

use crate::types::{SpawnEntry, TrayMenuEvent, TrayStatus};

// `state` owns the channel primitives (status + menu events) and nothing
// else. Menu-label rendering used to live here as `apply_status_update`,
// which pulled `crate::menu` into `crate::state`. Combined with
// `ipc_client → state` (for `update_tray_status`) and `menu → ipc_client`
// (for `ClientKind`), that closed a `state → menu → ipc_client → state`
// cycle. Render is now applied at the event-loop callsite in `lib.rs` so
// state stays a leaf in the dependency DAG.

pub static STATUS_CHANNEL: OnceLock<Sender<TrayStatus>> = OnceLock::new();
pub static MENU_EVENT_CHANNEL: OnceLock<Sender<TrayMenuEvent>> = OnceLock::new();
pub static RECENT_SPAWNS: OnceLock<Arc<Mutex<VecDeque<SpawnEntry>>>> = OnceLock::new();

pub fn update_tray_status(status: TrayStatus) -> anyhow::Result<()> {
    if let Some(sender) = STATUS_CHANNEL.get() {
        sender
            .send(status)
            .map_err(|error| anyhow::anyhow!("failed to send tray status: {error}"))?;
        debug!("tray status update sent: {status:?}");
    }
    Ok(())
}

pub fn menu_event_receiver() -> anyhow::Result<Receiver<TrayMenuEvent>> {
    let (tx, rx) = unbounded();
    MENU_EVENT_CHANNEL
        .set(tx)
        .map_err(|_| anyhow::anyhow!("menu event channel already initialized"))?;
    Ok(rx)
}

pub fn send_menu_event(event: TrayMenuEvent) {
    if let Some(sender) = MENU_EVENT_CHANNEL.get() {
        let _ = sender.send(event);
    }
}

pub fn record_spawn_entry(entry: SpawnEntry) -> u32 {
    let recent = RECENT_SPAWNS
        .get_or_init(|| Arc::new(Mutex::new(VecDeque::with_capacity(50))))
        .clone();
    let mut guard = recent.lock().expect("recent spawn store poisoned");
    guard.push_front(entry);
    while guard.len() > 50 {
        guard.pop_back();
    }
    active_count(&guard)
}

pub fn recent_spawns() -> Vec<SpawnEntry> {
    RECENT_SPAWNS
        .get_or_init(|| Arc::new(Mutex::new(VecDeque::with_capacity(50))))
        .lock()
        .expect("recent spawn store poisoned")
        .iter()
        .cloned()
        .collect()
}

fn active_count(entries: &VecDeque<SpawnEntry>) -> u32 {
    let mut latest_by_run = HashMap::<&str, &SpawnEntry>::new();
    for entry in entries {
        latest_by_run.entry(&entry.run_id).or_insert(entry);
    }
    latest_by_run
        .values()
        .filter(|entry| entry.is_active())
        .count() as u32
}

pub fn init_channels() -> anyhow::Result<Receiver<TrayStatus>> {
    let (status_tx, status_rx) = unbounded();
    STATUS_CHANNEL
        .set(status_tx)
        .map_err(|_| anyhow::anyhow!("status channel already initialized"))?;
    Ok(status_rx)
}

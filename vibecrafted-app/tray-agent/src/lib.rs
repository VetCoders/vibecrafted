pub mod handlers;
pub mod icons;
pub mod ipc_client;
pub mod menu;
pub mod state;
pub mod types;

use anyhow::Result;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tracing::{debug, info, warn};
use tray_icon::{TrayIconBuilder, menu::MenuEvent};

pub use state::{menu_event_receiver, send_menu_event, update_tray_status};
pub use types::{MenuIds, TrayMenuEvent, TrayStatus};

static SHUTDOWN_REQUESTED: OnceLock<AtomicBool> = OnceLock::new();

pub fn request_shutdown() {
    if let Some(flag) = SHUTDOWN_REQUESTED.get() {
        flag.store(true, Ordering::SeqCst);
    }
}

pub fn is_shutdown_requested() -> bool {
    SHUTDOWN_REQUESTED
        .get()
        .is_some_and(|flag| flag.load(Ordering::SeqCst))
}

pub fn run() -> Result<()> {
    run_with_ipc(ipc_client::default_socket_path())
}

pub fn run_with_ipc(socket_path: PathBuf) -> Result<()> {
    SHUTDOWN_REQUESTED.get_or_init(|| AtomicBool::new(false));
    let status_rx = state::init_channels()?;
    let socket_for_ipc = socket_path.clone();
    thread::spawn(move || {
        match tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .worker_threads(2)
            .build()
        {
            Ok(runtime) => runtime.block_on(ipc_client::subscribe_loop(socket_for_ipc)),
            Err(error) => warn!("failed to start tray IPC runtime: {error}"),
        }
    });
    let event_loop = EventLoopBuilder::new().build();
    let (menu, menu_ids) = menu::build_menu()?;
    let initial_status = TrayStatus::Idle;
    let tray_icon = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip(initial_status.tooltip())
        .with_icon(initial_status.to_icon()?)
        .build()?;
    let menu_channel = MenuEvent::receiver();
    let poll_interval = Duration::from_millis(100);
    let mut last_menu_refresh = Instant::now();
    info!("vc-mux-tray running; socket={}", socket_path.display());
    event_loop.run(move |_, _, control_flow| {
        *control_flow = ControlFlow::WaitUntil(Instant::now() + poll_interval);
        if is_shutdown_requested() {
            let socket = socket_path.clone();
            thread::spawn(move || {
                if let Ok(runtime) = tokio::runtime::Builder::new_current_thread()
                    .enable_all()
                    .build()
                {
                    let _ = runtime.block_on(ipc_client::stop_mux_daemon(&socket));
                }
            });
            *control_flow = ControlFlow::Exit;
            return;
        }
        if last_menu_refresh.elapsed() >= Duration::from_secs(2) {
            menu::update_service_count_label();
            menu::update_recent_runs_menu();
            menu::update_onboarding_item();
            last_menu_refresh = Instant::now();
        }
        match status_rx.try_recv() {
            Ok(status) => {
                state::apply_status_update(status);
                let _ = tray_icon.set_tooltip(Some(status.tooltip()));
                if let Ok(icon) = status.to_icon()
                    && let Err(error) = tray_icon.set_icon(Some(icon))
                {
                    debug!("failed to update tray icon: {error}");
                }
            }
            Err(crossbeam_channel::TryRecvError::Empty) => {}
            Err(crossbeam_channel::TryRecvError::Disconnected) => *control_flow = ControlFlow::Exit,
        }
        if let Ok(event) = menu_channel.try_recv() {
            handlers::handle_menu_event(&event.id, &menu_ids, &socket_path);
            if event.id == menu_ids.quit {
                request_shutdown();
            }
        }
    });
}

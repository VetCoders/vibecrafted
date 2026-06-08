use std::sync::Arc;

use tokio::sync::broadcast;

use crate::ipc::event::IpcEvent;

// Shared handle threaded through every IPC server task and command handler.
// Lives in its own module so the import graph stays `context -> {server, handlers}`
// instead of the historical `server <-> handlers` cycle, which made it
// impossible to read either file without already knowing the other.
pub struct MuxControlContext {
    pub state: Arc<tokio::sync::Mutex<crate::state::MuxState>>,
    pub event_tx: Option<broadcast::Sender<IpcEvent>>,
}

impl MuxControlContext {
    pub fn new(
        state: Arc<tokio::sync::Mutex<crate::state::MuxState>>,
        event_tx: Option<broadcast::Sender<IpcEvent>>,
    ) -> Self {
        Self { state, event_tx }
    }
}

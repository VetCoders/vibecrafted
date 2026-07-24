//! vc-procs: process monitor model + TUI for Vibecrafted fleets.
//!
//! Clean-room sampler inspired by rust-memex monitor shape (not BUSL source).

pub mod action;
pub mod app;
pub mod gpu;
pub mod model;
pub mod sampler;
pub mod ui;

pub use action::{TerminateRequest, TerminateResult, terminate_via_cli};
pub use app::ProcsApp;
pub use model::{FamilyTag, MonitorSnapshot, ProcessRow, format_bytes};
pub use sampler::Sampler;

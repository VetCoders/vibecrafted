//! vc-procs — fleet process monitor for Vibecrafted / vc-frame panes.

use voc::procs::ProcsApp;

fn main() -> anyhow::Result<()> {
    ProcsApp::new().run()
}

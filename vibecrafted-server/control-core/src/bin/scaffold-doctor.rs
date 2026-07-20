use std::process::ExitCode;

use control_core::ScaffoldArtifactStore;

fn main() -> ExitCode {
    // argv[0] is skipped; these values select local inputs and never establish executable trust.
    let arguments = std::env::args_os().skip(1).collect::<Vec<_>>(); // nosemgrep: rust.lang.security.args-os.args-os
    if arguments.len() != 5 {
        eprintln!("usage: scaffold-doctor <vibecrafted-home> <org> <repo> <day> <plan-id>");
        return ExitCode::from(2);
    }
    let store = ScaffoldArtifactStore::new(&arguments[0]);
    let values = arguments[1..]
        .iter()
        .map(|value| value.to_string_lossy())
        .collect::<Vec<_>>();
    match store.doctor(&values[0], &values[1], &values[2], &values[3]) {
        Ok(report) => {
            println!(
                "{}",
                serde_json::to_string_pretty(&report).expect("report serializes")
            );
            if report.valid {
                ExitCode::SUCCESS
            } else {
                ExitCode::from(1)
            }
        }
        Err(error) => {
            eprintln!("scaffold-doctor: {error}");
            ExitCode::from(2)
        }
    }
}

//! Hermetic product entrypoint for the bundled Vibecrafted runtime.
//!
//! This executable deliberately does not read a login shell profile. It locates
//! the runtime carried inside Vibecrafted.app, adds only that runtime bin plus
//! the system path, sources the shipped shell facade, and enters `vc-start`.

use std::env;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

const SYSTEM_PATH: &str = "/usr/bin:/bin:/usr/sbin:/sbin";

fn app_root_from_executable(executable: &Path) -> Option<PathBuf> {
    let root = executable.ancestors().nth(5)?;
    (root.extension().is_some_and(|extension| extension == "app")).then(|| root.to_path_buf())
}

fn app_root() -> Result<PathBuf, String> {
    if let Some(explicit) = env::var_os("VIBECRAFTED_APP_ROOT") {
        let root = PathBuf::from(explicit);
        if root.is_absolute() && root.extension().is_some_and(|ext| ext == "app") {
            return Ok(root);
        }
        return Err("VIBECRAFTED_APP_ROOT must be an absolute .app path".into());
    }
    let executable = env::current_exe().map_err(|error| error.to_string())?;
    app_root_from_executable(&executable)
        .ok_or_else(|| "vc-start is not inside Vibecrafted.app".to_string())
}

fn run() -> Result<(), String> {
    let app = app_root()?;
    let resources = app.join("Contents/Resources");
    let runtime = resources.join("runtime");
    let shell = runtime.join("runtime/shell/vetcoders.sh");
    let frame = app.join("Contents/Helpers/vc-frame");
    if !shell.is_file() {
        return Err(format!(
            "bundled runtime shell is missing: {}",
            shell.display()
        ));
    }
    if !frame.is_file() {
        return Err(format!("bundled vc-frame is missing: {}", frame.display()));
    }

    let runtime_path = format!("{}:{SYSTEM_PATH}", runtime.join("bin").display());
    let mut command = Command::new("/bin/bash");
    command
        .args([
            "--noprofile",
            "--norc",
            "-c",
            r#"source "$1"; shift; vc-start "$@""#,
            "vc-start",
        ])
        .arg(&shell)
        .args(env::args_os().skip(1))
        .env("PATH", runtime_path)
        .env("VIBECRAFTED_PYTHON", runtime.join("bin/python3"))
        .env("VIBECRAFTED_APP_ROOT", &app)
        .env("VIBECRAFTED_ROOT", &runtime)
        .env("VIBECRAFTED_VC_FRAME_BIN", &frame);

    let error = command.exec();
    Err(format!("could not enter bundled vc-start: {error}"))
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("vc-start: {error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_only_the_canonical_bundle_location() {
        let executable =
            Path::new("/Applications/Vibecrafted.app/Contents/Resources/runtime/bin/vc-start");
        assert_eq!(
            app_root_from_executable(executable),
            Some(PathBuf::from("/Applications/Vibecrafted.app"))
        );
        assert_eq!(app_root_from_executable(Path::new("/tmp/vc-start")), None);
    }
}

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

fn runtime_root(app: Option<&Path>) -> Result<PathBuf, String> {
    if let Some(explicit) = env::var_os("VIBECRAFTED_RUNTIME_ROOT") {
        let root = PathBuf::from(explicit);
        if root.is_absolute() {
            return Ok(root);
        }
        return Err("VIBECRAFTED_RUNTIME_ROOT must be absolute".into());
    }
    let app = app.ok_or_else(|| {
        "vc-start needs VIBECRAFTED_RUNTIME_ROOT outside Vibecrafted.app".to_string()
    })?;
    Ok(app.join("Contents/Resources/runtime"))
}

fn frame_binary(app: Option<&Path>, runtime: &Path) -> Result<PathBuf, String> {
    if let Some(explicit) = env::var_os("VIBECRAFTED_VC_FRAME_BIN") {
        let path = PathBuf::from(explicit);
        if path.is_absolute() {
            return Ok(path);
        }
        return Err("VIBECRAFTED_VC_FRAME_BIN must be absolute".into());
    }
    Ok(app
        .map(|root| root.join("Contents/Helpers/vc-frame"))
        .unwrap_or_else(|| runtime.join("bin/vc-frame")))
}

fn runtime_shell(runtime: &Path) -> PathBuf {
    runtime.join("vibecrafted-core/vibecrafted_core/runtime/shell/vetcoders.sh")
}

fn run() -> Result<(), String> {
    let app = app_root().ok();
    let runtime = runtime_root(app.as_deref())?;
    let shell = runtime_shell(&runtime);
    let frame = frame_binary(app.as_deref(), &runtime)?;
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
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("VIBECRAFTED_PYTHON", runtime.join("bin/python3"))
        .env("VIBECRAFTED_ROOT", &runtime)
        .env("VIBECRAFTED_RUNTIME_ROOT", &runtime)
        .env("VIBECRAFTED_VC_FRAME_BIN", &frame);

    if let Some(app) = app {
        command.env("VIBECRAFTED_APP_ROOT", app);
    }

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

    #[test]
    fn accepts_an_explicit_canonical_runtime_without_an_app() {
        let runtime = Path::new("/tmp/vibecrafted/releases/3.7.1+g12345678");
        assert_eq!(
            runtime.join("bin/vc-frame"),
            PathBuf::from("/tmp/vibecrafted/releases/3.7.1+g12345678/bin/vc-frame")
        );
        assert_eq!(
            runtime_shell(runtime),
            PathBuf::from(
                "/tmp/vibecrafted/releases/3.7.1+g12345678/vibecrafted-core/vibecrafted_core/runtime/shell/vetcoders.sh"
            )
        );
    }
}

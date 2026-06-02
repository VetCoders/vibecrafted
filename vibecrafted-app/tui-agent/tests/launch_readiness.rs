//! Integration tests for `wait_for_interactive_launch`.
//!
//! Drives the readiness loop through a fake `zellij`-shaped shell script so
//! the operator-visible behavior (success / "session exited before probe" /
//! "session never appeared" / probe error preservation) is exercised end to
//! end instead of just verified at command-shape level. Closes vc-review
//! P2-03.

#![cfg(unix)]

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
fn get_message(e: &vibecrafted_operator::LaunchRunError) -> String {
    if let vibecrafted_operator::LaunchRunError::Exec { message, .. } = e {
        message.clone()
    } else {
        panic!()
    }
}
fn get_probe_error(e: &vibecrafted_operator::LaunchRunError) -> Option<String> {
    if let vibecrafted_operator::LaunchRunError::Exec { probe_error, .. } = e {
        probe_error.clone()
    } else {
        panic!()
    }
}
fn get_probe_error_at_deadline(e: &vibecrafted_operator::LaunchRunError) -> Option<String> {
    if let vibecrafted_operator::LaunchRunError::Exec {
        probe_error_at_deadline,
        ..
    } = e
    {
        probe_error_at_deadline.clone()
    } else {
        panic!()
    }
}

use std::time::{Duration, Instant};

use tempfile::TempDir;
use vibecrafted_operator::launch::LaunchCommand;
use vibecrafted_operator::{READINESS_DEADLINE, wait_for_interactive_launch};

static ENV_LOCK: std::sync::OnceLock<std::sync::Mutex<()>> = std::sync::OnceLock::new();
fn env_guard() -> std::sync::MutexGuard<'static, ()> {
    ENV_LOCK
        .get_or_init(|| std::sync::Mutex::new(()))
        .lock()
        .unwrap_or_else(|err| err.into_inner())
}

const FAKE_SCRIPT: &str = r#"#!/bin/sh
# Skip the optional top-level `--config-dir <dir>` flag so the same script
# can stand in for both the launch invocation and the readiness probe.
if [ "${1:-}" = "--config-dir" ]; then
  shift 2
fi
case "${1:-}" in
  list-sessions)
    if [ -n "${FAKE_VISIBLE_FILE:-}" ] && [ -f "${FAKE_VISIBLE_FILE}" ]; then
      cat "${FAKE_VISIBLE_FILE}"
    fi
    case "${FAKE_PROBE_BEHAVIOR:-ok}" in
      err) echo "probe config not found" >&2; exit 2 ;;
      *) exit 0 ;;
    esac
    ;;
  --session)
    NAME="$2"
    case "${FAKE_INTERACTIVE_BEHAVIOR:-hang}" in
      quick-success) exit 0 ;;
      quick-failure) echo "interactive boom" >&2; exit 7 ;;
      slow-visibility)
        sleep 0.25
        if [ -n "${FAKE_VISIBLE_FILE:-}" ]; then
          echo "$NAME" > "${FAKE_VISIBLE_FILE}"
        fi
        sleep 0.30
        exit 0
        ;;
      *) sleep 30 ;;
    esac
    ;;
  *) exit 0 ;;
esac
"#;

struct FakeZellij {
    _tmp: TempDir,
    program: PathBuf,
    visible_file: PathBuf,
}

fn fake_zellij() -> FakeZellij {
    let tmp = tempfile::tempdir().expect("tempdir");
    let program = tmp.path().join("zellij.sh");
    let visible_file = tmp.path().join("visible.txt");
    fs::write(&program, FAKE_SCRIPT).expect("write fake zellij");
    let mut perms = fs::metadata(&program).expect("metadata").permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&program, perms).expect("chmod +x");
    FakeZellij {
        _tmp: tmp,
        program,
        visible_file,
    }
}

fn build_command(
    program: &Path,
    session: &str,
    visible_file: &Path,
    interactive: &str,
    probe: &str,
) -> LaunchCommand {
    let mut env: BTreeMap<String, OsString> = BTreeMap::new();
    env.insert(
        "FAKE_VISIBLE_FILE".to_string(),
        visible_file.as_os_str().to_owned(),
    );
    env.insert("FAKE_INTERACTIVE_BEHAVIOR".to_string(), interactive.into());
    env.insert("FAKE_PROBE_BEHAVIOR".to_string(), probe.into());
    LaunchCommand {
        program: program.to_path_buf(),
        args: vec![
            "--session".into(),
            session.into(),
            "options".into(),
            "--layout-string".into(),
            "noop".into(),
        ],
        env,
    }
}

#[test]
fn quick_child_exit_before_visibility_reports_session_exited() {
    let fake = fake_zellij();
    let session = "vc-op-fake-quickexit";
    let command = build_command(
        &fake.program,
        session,
        &fake.visible_file,
        "quick-success",
        "ok",
    );
    let child = command
        .spawn_interactive_with_stderr()
        .expect("spawn fake zellij");
    let result = wait_for_interactive_launch(&command, child);
    let error = result.expect_err("quick-exit should fail readiness check");
    assert!(
        get_message(&error).contains("exited before the readiness probe saw it"),
        "unexpected message: {}",
        get_message(&error)
    );
    assert!(
        get_message(&error).contains(session),
        "session name must appear in the error: {}",
        get_message(&error)
    );
}

#[test]
fn slow_visibility_then_child_exits_returns_success() {
    let fake = fake_zellij();
    let session = "vc-op-fake-slow";
    let command = build_command(
        &fake.program,
        session,
        &fake.visible_file,
        "slow-visibility",
        "ok",
    );
    let child = command
        .spawn_interactive_with_stderr()
        .expect("spawn fake zellij");
    let started = Instant::now();
    let result = wait_for_interactive_launch(&command, child);
    let elapsed = started.elapsed();
    let output = result.expect("slow-visibility should converge to success");
    assert!(output.status.success(), "fake child should exit zero");
    assert!(
        elapsed < READINESS_DEADLINE + Duration::from_secs(2),
        "slow-visibility test took too long: {elapsed:?}"
    );
}

#[test]
fn deadline_kills_child_when_session_never_visible() {
    let fake = fake_zellij();
    let session = "vc-op-fake-hang";
    let command = build_command(&fake.program, session, &fake.visible_file, "hang", "ok");
    let child = command
        .spawn_interactive_with_stderr()
        .expect("spawn fake zellij");
    let started = Instant::now();
    let result = wait_for_interactive_launch(&command, child);
    let elapsed = started.elapsed();
    let error = result.expect_err("hanging child past deadline must be a failure");
    assert!(
        get_message(&error).contains("did not appear within"),
        "unexpected message: {}",
        get_message(&error)
    );
    assert!(
        get_message(&error).contains(session),
        "session name must appear in the error: {}",
        get_message(&error)
    );
    // Deadline is 2s; killing must release us soon after. Allow 5s slack
    // for slow CI runners.
    assert!(
        elapsed < READINESS_DEADLINE + Duration::from_secs(5),
        "deadline test should not hang for the full 30s sleep: {elapsed:?}"
    );
}

#[test]
fn probe_failure_surfaces_in_launch_error() {
    let fake = fake_zellij();
    let session = "vc-op-fake-probe-err";
    let command = build_command(&fake.program, session, &fake.visible_file, "hang", "err");
    let child = command
        .spawn_interactive_with_stderr()
        .expect("spawn fake zellij");
    let result = wait_for_interactive_launch(&command, child);
    let error = result.expect_err("probe error + hang must produce a failure");
    let probe_error = get_probe_error(&error)
        .clone()
        .expect("probe error must be preserved when probe exits non-zero with stderr");
    assert!(
        probe_error.contains("probe config not found"),
        "probe stderr should be surfaced verbatim: {probe_error}"
    );
    let deadline_probe = get_probe_error_at_deadline(&error)
        .clone()
        .expect("deadline kill must preserve the last probe diagnostic");
    assert!(
        deadline_probe.contains("killed after 2000ms")
            && deadline_probe.contains("last probe error:")
            && deadline_probe.contains("probe config not found"),
        "deadline diagnostic should include kill timing and last probe error: {deadline_probe}"
    );
    // Detail lines render the probe diagnostic in the operator overlay.
    let detail = error.detail_lines("zellij ...".to_string());
    assert!(
        detail
            .iter()
            .any(|line| line.starts_with("readiness probe:")
                && line.contains("probe config not found")),
        "probe error must show in the overlay detail block: {detail:?}"
    );
    assert!(
        detail
            .iter()
            .any(|line| line.starts_with("readiness timeout probe:")
                && line.contains("probe config not found")),
        "deadline probe error must show in the overlay detail block: {detail:?}"
    );
}

#[test]
fn pre_launch_verify_passes_on_clean_config() {
    let _guard = env_guard();
    let dir = tempfile::tempdir().unwrap();
    unsafe {
        std::env::set_var("HOME", dir.path());
    }
    let socket_dir = dir.path().join(".rust-mux/ipc");
    std::fs::create_dir_all(&socket_dir).unwrap();
    let socket_path = socket_dir.join("control.sock");

    let listener = std::os::unix::net::UnixListener::bind(&socket_path).unwrap();

    std::thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            use std::io::{BufRead, Write};
            let mut reader = std::io::BufReader::new(&stream);
            let mut line = String::new();
            if reader.read_line(&mut line).is_ok() {
                let resp = rust_mux::ipc::MuxControlResponse::VerifyResult(
                    rust_mux::ipc::command::VerifyResult {
                        ok: true,
                        non_mux_servers: vec![],
                    },
                );
                let payload = serde_json::to_string(&resp).unwrap();
                let _ = stream.write_all(format!("{payload}\n").as_bytes());
            }
        }
    });

    let res = vibecrafted_operator::launch::pre_launch_verify(rust_mux::ipc::ClientKind::Codex);
    assert!(res.is_ok(), "Verify should pass");
}

#[test]
fn pre_launch_verify_blocks_dispatch_on_drift() {
    let _guard = env_guard();
    let dir = tempfile::tempdir().unwrap();
    unsafe {
        std::env::set_var("HOME", dir.path());
    }
    let socket_dir = dir.path().join(".rust-mux/ipc");
    std::fs::create_dir_all(&socket_dir).unwrap();
    let socket_path = socket_dir.join("control.sock");

    let listener = std::os::unix::net::UnixListener::bind(&socket_path).unwrap();

    std::thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            use std::io::{BufRead, Write};
            let mut reader = std::io::BufReader::new(&stream);
            let mut line = String::new();
            if reader.read_line(&mut line).is_ok() {
                let resp = rust_mux::ipc::MuxControlResponse::VerifyResult(
                    rust_mux::ipc::command::VerifyResult {
                        ok: false,
                        non_mux_servers: vec![rust_mux::ipc::command::NonMuxEntry {
                            client: "codex".into(),
                            path: "/tmp/config".into(),
                            line: 12,
                            server_name: "codex".into(),
                        }],
                    },
                );
                let payload = serde_json::to_string(&resp).unwrap();
                let _ = stream.write_all(format!("{payload}\n").as_bytes());
            }
        }
    });

    let res = vibecrafted_operator::launch::pre_launch_verify(rust_mux::ipc::ClientKind::Codex);
    let err = res.expect_err("Should block dispatch");
    match err {
        vibecrafted_operator::launch::VerifyHalt::Drift(servers) => {
            assert_eq!(servers.len(), 1);
            assert_eq!(servers[0].client, "codex");
        }
        _ => panic!("Expected Drift error"),
    }
}

#[test]
fn pre_launch_verify_falls_back_to_polling_when_socket_down() {
    let _guard = env_guard();
    let dir = tempfile::tempdir().unwrap();
    unsafe {
        std::env::set_var("HOME", dir.path());
    }
    // Socket doesn't exist. Should return Ok(()).
    let res = vibecrafted_operator::launch::pre_launch_verify(rust_mux::ipc::ClientKind::Codex);
    assert!(
        res.is_ok(),
        "Verify should fall back gracefully if socket is down"
    );
}

#[test]
fn client_drift_overlay_carries_non_mux_paths_to_fix_action() {
    let halt = vibecrafted_operator::launch::VerifyHalt::Drift(vec![
        rust_mux::ipc::command::NonMuxEntry {
            client: "claude".into(),
            path: "/Users/x/.claude/config.toml".into(),
            line: 42,
            server_name: "claude".into(),
        },
    ]);
    let err = vibecrafted_operator::LaunchRunError::ClientDrift(halt);
    let details = err.detail_lines("".into());
    assert!(
        details
            .iter()
            .any(|l| l.contains("Client drift detected. Dispatch halted."))
    );
    assert!(
        details
            .iter()
            .any(|l| l.contains("/Users/x/.claude/config.toml:42"))
    );
    assert!(details.iter().any(|l| l.contains("Press F to auto-fix")));
}

use std::process::Command;

const VALID_NONCE: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

fn server_command() -> Command {
    Command::new(env!("CARGO_BIN_EXE_vibecrafted-server-web"))
}

#[test]
fn lifecycle_nonce_requires_a_value() {
    let output = server_command()
        .arg("--lifecycle-nonce")
        .output()
        .expect("run vc-server");

    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("requires a value"));
}

#[test]
fn lifecycle_nonce_rejects_non_canonical_values() {
    for value in [
        "short",
        "A123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    ] {
        let output = server_command()
            .args(["--lifecycle-nonce", value])
            .output()
            .expect("run vc-server");

        assert_eq!(output.status.code(), Some(2));
        assert!(String::from_utf8_lossy(&output.stderr).contains("invalid lifecycle nonce"));
    }
}

#[test]
fn lifecycle_nonce_accepts_canonical_value_forms() {
    for args in [
        vec!["--lifecycle-nonce", VALID_NONCE, "--version"],
        vec![
            "--lifecycle-nonce=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "--version",
        ],
    ] {
        let output = server_command().args(args).output().expect("run vc-server");

        assert!(output.status.success());
        assert!(String::from_utf8_lossy(&output.stdout).starts_with("vc-server "));
    }
}

//! Stamp the product version into the server binary at build time.
//!
//! The rest of the product ships `X.Y.Z+g<sha>` (uv-tool wheels, deck
//! `_version`); the server carries the SAME identity so `vc-server --version`,
//! `/api/health`, and the console topbar all agree with `vibecrafted
//! --version`. Single source: the repo-root `VERSION` file (mirrored into
//! `Cargo.toml [package] version` by `scripts/version_bump.py`), plus the git
//! HEAD short sha. Out-of-repo builds (vendored source, no `.git`) fall back to
//! `CARGO_PKG_VERSION` and the `VIBECRAFTED_SOURCE_REVISION` env, so the stamp
//! degrades to honest partial identity instead of failing the build.

use std::path::Path;
use std::process::Command;

fn repo_version(manifest_dir: &Path) -> Option<String> {
    let version_file = manifest_dir.parent()?.parent()?.join("VERSION");
    println!("cargo:rerun-if-changed={}", version_file.display());
    let version = std::fs::read_to_string(version_file).ok()?;
    let version = version.trim();
    (!version.is_empty()).then(|| version.to_string())
}

fn git_short_sha(manifest_dir: &Path) -> Option<String> {
    let git_dir = manifest_dir.parent()?.parent()?.join(".git");
    let head = git_dir.join("HEAD");
    if head.exists() {
        println!("cargo:rerun-if-changed={}", head.display());
        if let Ok(contents) = std::fs::read_to_string(&head)
            && let Some(reference) = contents.trim().strip_prefix("ref: ")
        {
            let reference_path = git_dir.join(reference);
            if reference_path.exists() {
                println!("cargo:rerun-if-changed={}", reference_path.display());
            }
        }
    }
    let packed_refs = git_dir.join("packed-refs");
    if packed_refs.exists() {
        println!("cargo:rerun-if-changed={}", packed_refs.display());
    }
    let output = Command::new("git")
        .args(["rev-parse", "--short=8", "HEAD"])
        .current_dir(manifest_dir)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let sha = String::from_utf8(output.stdout).ok()?;
    let sha = sha.trim();
    (!sha.is_empty()).then(|| sha.to_string())
}

fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR");
    let manifest_dir = Path::new(&manifest_dir);

    let version = repo_version(manifest_dir)
        .unwrap_or_else(|| std::env::var("CARGO_PKG_VERSION").expect("CARGO_PKG_VERSION"));
    println!("cargo:rerun-if-env-changed=VIBECRAFTED_SOURCE_REVISION");
    let sha = git_short_sha(manifest_dir)
        .or_else(|| std::env::var("VIBECRAFTED_SOURCE_REVISION").ok())
        .filter(|value| !value.trim().is_empty());

    let stamp = match sha {
        Some(sha) => format!("{version}+g{sha}"),
        None => version,
    };
    println!("cargo:rustc-env=VC_SERVER_VERSION={stamp}");
}

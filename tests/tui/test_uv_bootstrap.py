"""Smoke tests for the uv-bootstrap path in the Makefile and install.sh.

P1-01 regression: `make vibecrafted` and `make install` used to split the
`uv` bootstrap `if` block and the `uv run ...` invocation across two
separate `@`-prefixed recipe lines. Make spawns a fresh shell per line,
so `export PATH="$HOME/.local/bin:$PATH"` never reached the `uv run` leg
and the recipe silently failed on hosts without preinstalled `uv`.

P3-01 regression: install.sh used `grep -oP 'VERSION\\s*:?=\\s*\\K\\S+'`
against Makefile, but the Makefile never defined `VERSION :=`. Result:
the post-install banner fell back to `basename archive_url .tar.gz`
(often `main`) and lied about the installed version. Repo truth lives
in the `VERSION` file at the root.

This module verifies:
1. Makefile's `vibecrafted` and `install` recipes keep bootstrap + PATH
   export + `uv run` in one continuous shell (single recipe line with
   backslash continuations).
2. Simulated no-uv PATH + `make -n vibecrafted` / `make -n install`
   prints the exported PATH before the `uv run` invocation, proving the
   shell boundary is respected.
3. install.sh reads `VERSION` directly, does not use `grep -oP`, and
   the staged banner reflects the repo's canonical version string.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
INSTALL_SH = REPO_ROOT / "install.sh"
VERSION_FILE = REPO_ROOT / "VERSION"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


# ---------------------------------------------------------------------------
# P1-01: Makefile shell-boundary fix
# ---------------------------------------------------------------------------


def _extract_recipe_body(text: str, target: str) -> str:
    """Return the recipe body (TAB-indented lines) for ``target:``.

    Stops at the first non-indented, non-empty line.
    """
    pattern = re.compile(
        rf"^{re.escape(target)}:[^\n]*\n((?:(?:\t[^\n]*|\s*)\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        raise AssertionError(f"Recipe {target!r} not found in Makefile")
    return m.group(1)


def test_makefile_vibecrafted_bootstrap_is_single_shell_stanza() -> None:
    """The bootstrap `if` and the `uv run` must live in ONE shell.

    In make, every line of a recipe not joined by a trailing backslash
    runs in its own shell. Environment changes (like an `export PATH`)
    performed in one line do NOT carry to the next.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    body = _extract_recipe_body(text, "vibecrafted")

    # The `if ! command -v uv` block should be followed by `fi; \`
    # (continuation), NOT by `fi\n` (shell boundary).
    assert "fi; \\" in body, (
        "vibecrafted recipe must continue the shell past the `fi` so the "
        "PATH export reaches `uv run`"
    )
    # PATH export must be present and happen AFTER the bootstrap but
    # BEFORE `uv run`, all within the same continued line.
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in body
    assert "uv run --project $(INSTALLER_DIR)" in body
    # Sanity: make sure we did NOT regress to two @-prefixed recipe lines.
    recipe_lines = [ln for ln in body.splitlines() if ln.startswith("\t@")]
    assert len(recipe_lines) <= 1, (
        "vibecrafted recipe regressed to multiple @-prefixed lines; each "
        "is a separate shell so PATH export will not survive."
    )


def test_makefile_install_bootstrap_is_single_shell_stanza() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    body = _extract_recipe_body(text, "install")

    assert "fi; \\" in body, (
        "install recipe must continue the shell past the `fi` so the "
        "PATH export reaches `uv run`"
    )
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in body
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer "
        "$(MANIFEST) --yes"
    ) in body
    recipe_lines = [ln for ln in body.splitlines() if ln.startswith("\t@")]
    assert len(recipe_lines) <= 1, (
        "install recipe regressed to multiple @-prefixed lines; each "
        "is a separate shell so PATH export will not survive."
    )


def _make_dry_run(target: str, env: dict[str, str]) -> str:
    """Run `make -n <target>` and return combined stdout+stderr."""
    result = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr


def _build_no_uv_env(tmp_path: Path, *, fake_uv: bool = False) -> dict[str, str]:
    """Return an environment where `uv` is either missing from PATH or
    shimmed to a no-op script under ``tmp_path/bin``.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)

    # Minimal system binaries the Makefile might call during dry-run.
    # `make -n` does NOT execute the recipe, but `make` evaluates any
    # `$(shell ...)` at parse time — we don't have any for these targets,
    # so a bare PATH is fine. We still populate sh, bash, awk, grep, sed,
    # env via symlinks to /bin/* or /usr/bin/* so that if make does try to
    # run anything, it can.
    for tool in (
        "sh",
        "bash",
        "make",
        "env",
        "awk",
        "grep",
        "sed",
        "tr",
        "cat",
        "echo",
        "printf",
        "test",
        "true",
        "false",
        "command",
        "rm",
        "chmod",
        "mkdir",
        "git",
    ):
        system = shutil.which(tool)
        if system:
            dst = fake_bin / tool
            if not dst.exists():
                os.symlink(system, dst)

    if fake_uv:
        _write_executable(
            fake_bin / "uv",
            "#!/usr/bin/env bash\nexit 0\n",
        )

    env = os.environ.copy()
    env["PATH"] = str(fake_bin)
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(exist_ok=True)
    return env


def test_makefile_vibecrafted_dry_run_keeps_path_before_uv_run(
    tmp_path: Path,
) -> None:
    """`make -n vibecrafted` output must show the PATH export and the
    `uv run` invocation in the same shell line (backslash-continued),
    proving the recipe survives the no-uv bootstrap path.
    """
    env = _build_no_uv_env(tmp_path, fake_uv=False)
    out = _make_dry_run("vibecrafted", env)

    # `make -n` emits the recipe text with continuations collapsed via
    # trailing `\`. Find the recipe block and confirm PATH export and
    # `uv run` are on the same continued line.
    assert "export PATH=" in out, out
    assert "uv run --project" in out, out

    # The PATH export and `uv run` must stay in a single shell chunk.
    idx_export = out.find("export PATH=")
    idx_uv = out.find("uv run --project")
    assert idx_export != -1 and idx_uv != -1
    assert idx_export < idx_uv
    # No blank line between `export PATH` and `uv run` — same shell.
    segment = out[idx_export:idx_uv]
    assert "\n\n" not in segment, (
        "Detected shell boundary between `export PATH` and `uv run` in make -n "
        f"output; PATH export would not survive. Segment:\n{segment!r}"
    )


def test_makefile_install_dry_run_keeps_path_before_uv_run(
    tmp_path: Path,
) -> None:
    env = _build_no_uv_env(tmp_path, fake_uv=False)
    out = _make_dry_run("install", env)

    assert "export PATH=" in out, out
    assert "uv run --project" in out, out
    assert "--yes" in out, out

    idx_export = out.find("export PATH=")
    idx_uv = out.find("uv run --project")
    assert idx_export != -1 and idx_uv != -1
    assert idx_export < idx_uv
    segment = out[idx_export:idx_uv]
    assert "\n\n" not in segment, (
        "Detected shell boundary between `export PATH` and `uv run` in install "
        f"recipe make -n output. Segment:\n{segment!r}"
    )


# ---------------------------------------------------------------------------
# P3-01: install.sh VERSION truth
# ---------------------------------------------------------------------------


def test_install_sh_does_not_use_grep_dash_p() -> None:
    """`grep -oP` is GNU-only; BSD grep on macOS does not accept it.

    Dropping -P is a correctness AND portability fix.
    """
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "grep -oP" not in text, (
        "install.sh must not rely on GNU grep -P (BSD grep on macOS "
        "rejects it silently)"
    )


def test_install_sh_reads_canonical_version_file() -> None:
    """install.sh must extract the installed version from the staged
    VERSION file, not from the Makefile (which never defined VERSION).
    """
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "staged_dir/VERSION" in text, (
        "install.sh must read VERSION directly from the staged source tree"
    )
    # No more archive_url fallback — the banner truth is the repo VERSION
    # file, not a tarball filename.
    assert 'basename "$archive_url" .tar.gz' not in text


def test_install_sh_reports_version_from_staged_tree(tmp_path: Path) -> None:
    """End-to-end: build a fake tarball with a VERSION file, run install.sh
    in archive-file mode, and verify the post-install banner prints that
    exact version string.
    """
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-main.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-args.txt"
    python_capture = tmp_path / "python-called.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text(
        ".DEFAULT_GOAL := help\ninstall:\n\t@echo ok\n",
        encoding="utf-8",
    )
    (source_dir / "VERSION").write_text("9.9.9-test\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'printf "%s\\n" "$@" > "$MAKE_CAPTURE"\n',
    )
    _write_executable(
        fake_bin / "python3",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'printf "unexpected\\n" > "$PYTHON_CAPTURE"\nexit 97\n',
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["MAKE_CAPTURE"] = str(make_capture)
    env["PYTHON_CAPTURE"] = str(python_capture)

    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--archive-file", str(archive_path), "install"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    banner = result.stdout + result.stderr
    assert "vibecrafted 9.9.9-test" in banner, (
        "install.sh banner should reflect the staged VERSION file content; "
        f"got:\n{banner}"
    )
    # Must not fall back to the archive basename.
    assert "vibecrafted vibecrafted-main" not in banner


def test_install_sh_banner_falls_back_when_version_absent(tmp_path: Path) -> None:
    """If the staged tree has no VERSION file, the banner must say
    'unknown', not the archive basename.
    """
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-exotic.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-args.txt"
    python_capture = tmp_path / "python-called.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text(
        ".DEFAULT_GOAL := help\ninstall:\n\t@echo ok\n",
        encoding="utf-8",
    )
    # No VERSION file on purpose.
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-exotic")

    _write_executable(
        fake_bin / "make",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'printf "%s\\n" "$@" > "$MAKE_CAPTURE"\n',
    )
    _write_executable(
        fake_bin / "python3",
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'printf "unexpected\\n" > "$PYTHON_CAPTURE"\nexit 97\n',
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["MAKE_CAPTURE"] = str(make_capture)
    env["PYTHON_CAPTURE"] = str(python_capture)

    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--archive-file", str(archive_path), "install"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    banner = result.stdout + result.stderr
    assert "vibecrafted unknown" in banner, (
        "missing VERSION file should degrade to 'unknown', not to "
        f"archive basename; got:\n{banner}"
    )


def test_repo_version_file_exists_and_is_non_empty() -> None:
    """Sanity: if this test fails, the repo lost its canonical VERSION
    string and the real install.sh banner will read 'unknown'.
    """
    assert VERSION_FILE.is_file(), (
        "Repo must ship a VERSION file at the root; install.sh reads it "
        "directly for the post-install banner"
    )
    content = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert content, "VERSION file must not be empty"
    # Loose semver-ish check: digits and dots with optional suffix.
    assert re.match(r"^\d+\.\d+\.\d+", content), (
        f"VERSION content does not look like a semver string: {content!r}"
    )


# ---------------------------------------------------------------------------
# Opt-in end-to-end no-uv bootstrap (slow, network + installer side effects)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("VIBECRAFTED_RUN_NO_UV_E2E") != "1",
    reason=(
        "End-to-end `make vibecrafted` without uv downloads the uv "
        "installer from astral.sh and mutates HOME. Set "
        "VIBECRAFTED_RUN_NO_UV_E2E=1 to opt in."
    ),
)
def test_make_vibecrafted_no_uv_e2e(tmp_path: Path) -> None:  # pragma: no cover
    env = _build_no_uv_env(tmp_path, fake_uv=False)
    result = subprocess.run(
        ["make", "vibecrafted"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert "bootstrapping uv" in (result.stdout + result.stderr)
    # We accept non-zero (the installer may exit based on its own logic),
    # but we REQUIRE that the `uv run` leg ran, i.e. the PATH export
    # survived. Look for installer-side output.
    combined = result.stdout + result.stderr
    assert "uv run" in combined or "vetcoders-installer" in combined, combined

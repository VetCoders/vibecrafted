from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_install_sh_fallback_prefers_github_source_snapshot_when_channel_missing() -> (
    None
):
    text = INSTALL_SH.read_text(encoding="utf-8")

    assert 'channel_url="https://vibecrafted.io/channel/${ref}.json"' in text
    assert (
        'archive_url="https://github.com/VetCoders/vibecrafted/archive/refs/heads/${ref}.tar.gz"'
        in text
    )
    assert "using GitHub source snapshot for ${ref}" in text
    assert "frozen v1.2.1 URL" not in text


def test_install_sh_archive_install_runs_local_make_target(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-args.txt"
    python_capture = tmp_path / "python-called.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text("install:\n\t@echo ok\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$MAKE_CAPTURE"',
            ]
        )
        + "\n",
    )
    _write_executable(
        fake_bin / "python3",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "unexpected\\n" > "$PYTHON_CAPTURE"',
                "exit 97",
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["MAKE_CAPTURE"] = str(make_capture)
    env["PYTHON_CAPTURE"] = str(python_capture)

    subprocess.run(
        ["bash", str(INSTALL_SH), "--archive-file", str(archive_path), "install"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    staged_root = home / ".vibecrafted" / "tools" / "vibecrafted-current"
    assert staged_root.is_symlink()
    assert make_capture.read_text(encoding="utf-8").splitlines() == [
        "-C",
        str(staged_root),
        "install",
    ]
    assert not python_capture.exists()


def test_install_sh_gui_bootstrap_runs_local_guided_installer(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    python_capture = tmp_path / "python-args.txt"
    make_capture = tmp_path / "make-args.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text("install:\n\t@echo ok\n", encoding="utf-8")
    (scripts_dir / "installer_gui.py").write_text("# gui\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$MAKE_CAPTURE"',
            ]
        )
        + "\n",
    )
    _write_executable(
        fake_bin / "python3",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$PYTHON_CAPTURE"',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["PYTHON_CAPTURE"] = str(python_capture)
    env["MAKE_CAPTURE"] = str(make_capture)

    subprocess.run(
        ["bash", str(INSTALL_SH), "--archive-file", str(archive_path), "--gui"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    staged_root = home / ".vibecrafted" / "tools" / "vibecrafted-current"
    assert staged_root.is_symlink()
    assert python_capture.read_text(encoding="utf-8").splitlines() == [
        str(staged_root / "scripts" / "installer_gui.py"),
        "--source",
        str(staged_root),
    ]
    assert not make_capture.exists()

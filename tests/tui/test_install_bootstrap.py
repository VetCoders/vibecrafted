from __future__ import annotations

import errno
import os
import pty
import select
import shlex
import signal
import subprocess
import tarfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_with_tty(
    command: str, *, response: str | None = None, timeout: float = 10.0
) -> tuple[int, str]:
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp("bash", "bash", "-lc", command)

    output = bytearray()
    sent_response = response is None
    deadline = time.monotonic() + timeout
    wait_status: int | None = None

    while wait_status is None:
        if time.monotonic() > deadline:
            os.kill(pid, signal.SIGKILL)
            _, wait_status = os.waitpid(pid, 0)
            raise AssertionError(f"Timed out waiting for command: {command}")

        finished_pid, status = os.waitpid(pid, os.WNOHANG)
        if finished_pid == pid:
            wait_status = status
            break

        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            continue

        try:
            chunk = os.read(fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                continue
            raise

        if not chunk:
            continue

        output.extend(chunk)
        if not sent_response and b"Proceed? [y/N]" in output:
            os.write(fd, f"{response}\n".encode("utf-8"))
            sent_response = True

    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        output.extend(chunk)

    os.close(fd)
    assert wait_status is not None
    return os.waitstatus_to_exitcode(wait_status), output.decode("utf-8", "replace")


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


def test_install_sh_attended_pipe_requires_explicit_yes_before_staging(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    home = tmp_path / "home"

    scripts_dir.mkdir(parents=True)
    home.mkdir()

    (source_dir / "Makefile").write_text("install:\n\t@echo ok\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    command = " ; ".join(
        [
            f"export HOME={shlex.quote(str(home))}",
            f"export XDG_CONFIG_HOME={shlex.quote(str(home / '.config'))}",
            f"export VIBECRAFTED_HOME={shlex.quote(str(home / '.vibecrafted'))}",
            "export PATH=/usr/bin:/bin:/usr/sbin:/sbin",
            (
                f"printf '' | bash {shlex.quote(str(INSTALL_SH))}"
                f" --archive-file {shlex.quote(str(archive_path))}"
            ),
        ]
    )

    exit_code, output = _run_with_tty(command, response="n")

    staged_root = home / ".vibecrafted" / "tools" / "vibecrafted-current"
    assert exit_code == 0
    assert "Nothing will be staged or installed until you say yes." in output
    assert "Proceed? [y/N]" in output
    assert "Cancelled. Nothing was staged or installed." in output
    assert not staged_root.exists()


def test_install_sh_yes_skips_attended_prompt_for_pipe_bootstrap(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    python_capture = tmp_path / "python-args.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text("install:\n\t@echo ok\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")
    (scripts_dir / "vetcoders_install.py").write_text("# compact\n", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

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

    command = " ; ".join(
        [
            f"export HOME={shlex.quote(str(home))}",
            f"export XDG_CONFIG_HOME={shlex.quote(str(home / '.config'))}",
            f"export VIBECRAFTED_HOME={shlex.quote(str(home / '.vibecrafted'))}",
            f"export PATH={shlex.quote(f'{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin')}",
            f"export PYTHON_CAPTURE={shlex.quote(str(python_capture))}",
            (
                f"printf '' | bash {shlex.quote(str(INSTALL_SH))}"
                f" --archive-file {shlex.quote(str(archive_path))} --yes"
            ),
        ]
    )

    exit_code, output = _run_with_tty(command)

    staged_root = home / ".vibecrafted" / "tools" / "vibecrafted-current"
    assert exit_code == 0
    assert "Proceed? [y/N]" not in output
    assert staged_root.is_symlink()
    assert python_capture.read_text(encoding="utf-8").splitlines() == [
        str(staged_root / "scripts" / "vetcoders_install.py"),
        "install",
        "--source",
        str(staged_root),
        "--with-shell",
        "--compact",
        "--non-interactive",
    ]


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

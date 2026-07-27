from __future__ import annotations

import errno
import os
import pty
import select
import shlex
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _write_distribution_manifest_stub(source_dir: Path) -> None:
    path = source_dir / "scripts" / "distribution_manifest.py"
    path.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

if sys.argv[1] == "check":
    raise SystemExit(0)
if sys.argv[1] != "stage":
    raise SystemExit(2)
source = Path(sys.argv[sys.argv.index("--source") + 1])
destination = Path(sys.argv[sys.argv.index("--destination") + 1])
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination, symlinks=True)
""",
        encoding="utf-8",
    )


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
            os.write(fd, f"{response}\n".encode())
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
        'archive_url="https://github.com/vetcoders/vibecrafted/archive/refs/heads/${ref}.tar.gz"'
        in text
    )
    assert "using GitHub source snapshot for ${ref}" in text
    assert "frozen v1.2.1 URL" not in text


def test_install_sh_help_documents_runtime_flag() -> None:
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--help"],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert "--runtime <horse>" in result.stdout
    assert "wezterm, vc-apprt, locterm, microsandbox, or none" in result.stdout


def test_install_sh_quiets_tar_xattr_noise_and_hides_make_directory_trace() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")

    assert "tar --warning=no-unknown-keyword" in text
    assert "COPYFILE_DISABLE=1 tar" in text
    assert "make --no-print-directory -C" in text


def test_install_sh_stages_archives_through_distribution_manifest() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")

    assert 'manifest_helper="$source_dir/scripts/distribution_manifest.py"' in text
    assert '"$manifest_helper" stage' in text
    assert '--source "$source_dir"' in text
    assert 'candidate_root="$tmpdir/candidate"' in text
    assert '--destination "$candidate_root"' in text
    assert 'ln -sfn "$staged_dir" "$current_link"' not in text
    assert 'rm -rf "$staged_dir"' not in text
    assert 'mv "$source_dir"' not in text


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
    _write_distribution_manifest_stub(source_dir)

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

    staged_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    assert exit_code == 0
    assert "⚒ 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. →" in output
    assert "unpack · verify · transact ·" in output
    assert "Proceed? [y/N]" in output
    assert "Cancelled." in output
    assert not staged_root.exists()


def test_install_sh_yes_skips_attended_prompt_for_pipe_bootstrap(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-ran.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text(
        "install-auto:\n\t@printf 'install-auto RUNTIME=$(RUNTIME)\\n' > $(MAKE_CAPTURE)\n",
        encoding="utf-8",
    )
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")
    (scripts_dir / "vetcoders_install.py").write_text("# compact\n", encoding="utf-8")
    _write_distribution_manifest_stub(source_dir)

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    command = " ; ".join(
        [
            f"export HOME={shlex.quote(str(home))}",
            f"export XDG_CONFIG_HOME={shlex.quote(str(home / '.config'))}",
            f"export VIBECRAFTED_HOME={shlex.quote(str(home / '.vibecrafted'))}",
            f"export PATH={shlex.quote(f'{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin')}",
            f"export MAKE_CAPTURE={shlex.quote(str(make_capture))}",
            (
                f"printf '' | bash {shlex.quote(str(INSTALL_SH))}"
                f" --archive-file {shlex.quote(str(archive_path))} --yes"
            ),
        ]
    )

    exit_code, output = _run_with_tty(command)

    staged_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    assert exit_code == 0
    assert "Proceed? [y/N]" not in output
    assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. bootstrap" not in output
    assert "Running     compact installer" not in output
    assert "Non-interactive bootstrap detected" not in output
    assert "Launching installer:" not in output
    assert not staged_root.exists()
    assert make_capture.read_text(encoding="utf-8") == "install-auto RUNTIME=none\n"


def test_install_sh_runtime_flag_dispatches_staged_runtime_helper(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-ran.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    (source_dir / "Makefile").write_text(
        "install-auto:\n\t@printf 'install-auto RUNTIME=$(RUNTIME)\\n' > $(MAKE_CAPTURE)\n",
        encoding="utf-8",
    )
    (scripts_dir / "vetcoders_install.py").write_text("# compact\n", encoding="utf-8")
    (scripts_dir / "install-runtime.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\n" "$@" > "$RUNTIME_CAPTURE"\n',
        encoding="utf-8",
    )
    _write_distribution_manifest_stub(source_dir)

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["MAKE_CAPTURE"] = str(make_capture)

    subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "--archive-file",
            str(archive_path),
            "--runtime",
            "wezterm",
            "--yes",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    staged_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    assert not staged_root.exists()
    assert make_capture.read_text(encoding="utf-8") == "install-auto RUNTIME=wezterm\n"


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
    _write_distribution_manifest_stub(source_dir)

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        '#!/usr/bin/env bash\nset -euo pipefail\nprintf "%s\\n" "$@" > "$MAKE_CAPTURE"'
        + "\n",
    )
    _write_executable(
        fake_bin / "python3",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'if [[ "$1" == */distribution_manifest.py ]]; then exec {shlex.quote(sys.executable)} "$@"; fi',
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

    staged_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    make_args = make_capture.read_text(encoding="utf-8").splitlines()
    assert make_args[:2] == ["--no-print-directory", "-C"]
    candidate_root = Path(make_args[2])
    assert candidate_root.name == "candidate"
    assert candidate_root.parent.name.startswith("vibecrafted-bootstrap.")
    assert make_args[3:] == ["install"]
    assert not candidate_root.exists()
    assert not staged_root.exists()
    assert not python_capture.exists()


def test_install_sh_same_ref_handoff_never_mutates_live_pointer(
    tmp_path: Path,
) -> None:
    """A bootstrap candidate must stay private until the leased installer
    publishes it.

    Block the candidate command at the transaction handoff, then prove that a
    same-ref live generation and `vibecrafted-current` remain byte-for-byte
    available both while the handoff is blocked and after it fails.
    """
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    live_target = tools / "vibecrafted-main"
    current = tools / "vibecrafted-current"
    ready = tmp_path / "make-ready"
    release = tmp_path / "make-release"
    candidate_capture = tmp_path / "candidate-root.txt"

    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    live_target.mkdir(parents=True)
    (live_target / "identity.txt").write_text("still-live\n", encoding="utf-8")
    current.symlink_to(live_target)

    (source_dir / "Makefile").write_text("install:\n\t@echo no\n", encoding="utf-8")
    (scripts_dir / "placeholder").write_text("", encoding="utf-8")
    _write_distribution_manifest_stub(source_dir)
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        """#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == "--no-print-directory" && "$2" == "-C" ]]
printf '%s\\n' "$3" > "$CANDIDATE_CAPTURE"
: > "$MAKE_READY"
while [[ ! -e "$MAKE_RELEASE" ]]; do
  sleep 0.02
done
exit 73
""",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["CANDIDATE_CAPTURE"] = str(candidate_capture)
    env["MAKE_READY"] = str(ready)
    env["MAKE_RELEASE"] = str(release)

    process = subprocess.Popen(
        ["bash", str(INSTALL_SH), "--archive-file", str(archive_path), "install"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None:
            assert time.monotonic() < deadline, "bootstrap never reached handoff"
            time.sleep(0.02)

        assert process.poll() is None, process.communicate()
        candidate_root = Path(candidate_capture.read_text(encoding="utf-8").strip())
        assert candidate_root.name == "candidate"
        assert candidate_root.is_dir()
        assert current.is_symlink()
        assert current.resolve() == live_target.resolve()
        assert (current / "identity.txt").read_text(encoding="utf-8") == "still-live\n"

        release.touch()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 73, stdout + stderr
        assert current.is_symlink()
        assert current.resolve() == live_target.resolve()
        assert (live_target / "identity.txt").read_text(
            encoding="utf-8"
        ) == "still-live\n"
        assert not candidate_root.exists()
    finally:
        release.touch(exist_ok=True)
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


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
    _write_distribution_manifest_stub(source_dir)

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname="vibecrafted-main")

    _write_executable(
        fake_bin / "make",
        '#!/usr/bin/env bash\nset -euo pipefail\nprintf "%s\\n" "$@" > "$MAKE_CAPTURE"'
        + "\n",
    )
    _write_executable(
        fake_bin / "python3",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'if [[ "$1" == */distribution_manifest.py ]]; then exec {shlex.quote(sys.executable)} "$@"; fi',
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

    staged_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    python_args = python_capture.read_text(encoding="utf-8").splitlines()
    candidate_root = Path(python_args[2])
    assert Path(python_args[0]) == candidate_root / "scripts" / "installer_gui.py"
    assert python_args[1] == "--source"
    assert candidate_root.name == "candidate"
    assert candidate_root.parent.name.startswith("vibecrafted-bootstrap.")
    assert not candidate_root.exists()
    assert not staged_root.exists()
    assert not make_capture.exists()


# ---------------------------------------------------------------------------
# W3-A — installer storytelling contract: calm default, VERBOSE=1 superset
# ---------------------------------------------------------------------------


def _run_storytelling_bootstrap(
    tmp_path: Path, *, verbose: bool
) -> subprocess.CompletedProcess:
    """Run install.sh end-to-end in archive-file mode with a stubbed `make`.

    Reuses one HOME across calls so the default and VERBOSE runs emit
    line-for-line comparable output (identical paths, idempotent staging).
    """
    source_dir = tmp_path / "source"
    scripts_dir = source_dir / "scripts"
    archive_path = tmp_path / "vibecrafted-bootstrap.tar.gz"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    make_capture = tmp_path / "make-args.txt"

    if not archive_path.exists():
        scripts_dir.mkdir(parents=True)
        fake_bin.mkdir()
        home.mkdir()
        (source_dir / "Makefile").write_text("install:\n\t@echo ok\n", encoding="utf-8")
        (source_dir / "VERSION").write_text("9.9.9-test\n", encoding="utf-8")
        (scripts_dir / "placeholder").write_text("", encoding="utf-8")
        _write_distribution_manifest_stub(source_dir)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source_dir, arcname="vibecrafted-main")
        _write_executable(
            fake_bin / "make",
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            'printf "%s\\n" "$@" > "$MAKE_CAPTURE"\n',
        )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["MAKE_CAPTURE"] = str(make_capture)
    env.pop("VERBOSE", None)
    if verbose:
        env["VERBOSE"] = "1"

    return subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "--yes",
            "--archive-file",
            str(archive_path),
            "install",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_install_sh_default_output_fits_the_ten_line_budget(tmp_path: Path) -> None:
    """Operator contract (W3-A): the default bootstrap view is storytelling —
    ≤10 lines total, each section adding ≤2 lines. The bazaar is VERBOSE=1."""
    result = _run_storytelling_bootstrap(tmp_path, verbose=False)

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) <= 10, (
        "default install.sh output must stay within the 10-line budget; "
        f"got {len(lines)} lines:\n" + "\n".join(lines)
    )
    # The staging truth still lands in the calm view.
    assert any("vibecrafted 9.9.9-test" in line for line in lines)


def test_install_sh_verbose_output_is_a_superset_of_default(tmp_path: Path) -> None:
    """VERBOSE=1 restores the full detail without losing a single line of the
    default storytelling view."""
    default_out = _run_storytelling_bootstrap(tmp_path, verbose=False).stdout
    verbose_out = _run_storytelling_bootstrap(tmp_path, verbose=True).stdout

    default_lines = {line for line in default_out.splitlines() if line.strip()}
    verbose_lines = {line for line in verbose_out.splitlines() if line.strip()}

    missing = default_lines - verbose_lines
    assert not missing, f"VERBOSE=1 dropped default storytelling lines: {missing}"
    assert len(verbose_lines) > len(default_lines), (
        "VERBOSE=1 must restore the gated detail (strict superset)"
    )


def test_compact_onboarding_ends_with_finish_card_not_log_tail() -> None:
    """CLI_PRODUCT_SPEC §6.1: the compact install ends with the bounded finish
    card (result · key facts · one next step). The 12-line inner log viewer is
    retired — the full transaction log stays on disk and errors point at it."""
    text = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(encoding="utf-8")
    assert "_tail[-12:]" not in text
    assert "Finish card (CLI_PRODUCT_SPEC §6.1)" in text
    assert "vibecrafted init claude" in text

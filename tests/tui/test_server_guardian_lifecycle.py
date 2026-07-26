from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "vibecrafted"
PACKAGED_LAUNCHER = (
    REPO_ROOT / "vibecrafted-core" / "vibecrafted_core" / "deck" / "vibecrafted"
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_until_dead(pid: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} did not exit within {timeout} seconds")


def _wait_for_text(path: Path, expected: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and expected in path.read_text(encoding="utf-8"):
            return
        time.sleep(0.05)
    raise AssertionError(
        f"{expected!r} did not appear in {path} within {timeout} seconds"
    )


def _run_launcher(
    env: dict[str, str], *args: str, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(LAUNCHER), *args],
        check=check,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.fixture
def isolated_server_runtime(
    tmp_path: Path,
) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    site_root = runtime_home / "server" / "site"
    lifecycle_log = tmp_path / "lifecycle.log"
    state_dir = home / ".vibecrafted" / "server"
    (site_root / "fonts").mkdir(parents=True)
    (site_root / "fonts" / "fixture.woff2").write_bytes(b"fixture")
    (home / ".vibecrafted" / "control_plane").mkdir(parents=True)

    _write_executable(
        bin_dir / "vc-server",
        """#!/usr/bin/env python3
import http.server
import json
import os
import signal

host, raw_port = os.environ["VC_SERVER_ADDR"].rsplit(":", 1)
log_path = os.environ["LIFECYCLE_LOG"]

def record(message):
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(message + "\\n")

def stop(_signum, _frame):
    record("server-stop")
    raise SystemExit(0)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/control/state":
            payload = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format, *_args):
        return

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
record("server-start")
http.server.ThreadingHTTPServer((host, int(raw_port)), Handler).serve_forever()
""",
    )
    _write_executable(
        bin_dir / "vc-guardian",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'guardian-start %s\n' "$*" >> "$LIFECYCLE_LOG"
trap 'printf "guardian-stop\n" >> "$LIFECYCLE_LOG"; exit 0' TERM INT
while :; do
  sleep 0.1
done
""",
    )
    (bin_dir / "python3").symlink_to(Path(sys.executable).resolve())

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
            "VIBECRAFTED_HOME": str(home / ".vibecrafted"),
            "VIBECRAFTED_RUNTIME_HOME": str(runtime_home),
            "LIFECYCLE_LOG": str(lifecycle_log),
        }
    )

    yield env, state_dir, lifecycle_log

    for pid_name, marker in (
        ("guardian.pid", "vc-guardian"),
        ("server.pid", "vc-server"),
    ):
        pid_file = state_dir / pid_name
        if not pid_file.is_file():
            continue
        raw_pid = pid_file.read_text(encoding="utf-8").strip()
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        if _process_alive(pid) and marker in command:
            os.kill(pid, signal.SIGKILL)


def test_server_lifecycle_starts_heals_and_stops_guardian(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    port = _free_port()

    started = _run_launcher(
        env, "server", "start", "--host", "127.0.0.1", "--port", str(port)
    )
    assert started.returncode == 0, started.stderr
    assert "Server is up and healthy" in started.stdout
    assert "Guardian is running" in started.stdout

    server_pid = int((state_dir / "server.pid").read_text(encoding="utf-8"))
    guardian_pid = int((state_dir / "guardian.pid").read_text(encoding="utf-8"))
    assert _process_alive(server_pid)
    assert _process_alive(guardian_pid)
    _wait_for_text(
        lifecycle_log,
        f"guardian-start --server-url http://127.0.0.1:{port}",
    )

    status = _run_launcher(env, "server", "status")
    assert status.returncode == 0, status.stderr
    assert f"Server: RUNNING (PID {server_pid}" in status.stdout
    assert f"Guardian: RUNNING (PID {guardian_pid}" in status.stdout

    doctor = _run_launcher(env, "server", "doctor")
    assert doctor.returncode == 0, doctor.stderr
    assert "Guardian entrypoint present and executable" in doctor.stdout
    assert "Guardian PID" in doctor.stdout
    assert "Server and guardian doctor check passed" in doctor.stdout

    os.kill(guardian_pid, signal.SIGTERM)
    _wait_until_dead(guardian_pid)
    stale = _run_launcher(env, "server", "status")
    assert stale.returncode != 0
    assert "Guardian: STALE-PID" in stale.stdout

    healed = _run_launcher(env, "server", "start")
    assert healed.returncode == 0, healed.stderr
    healed_guardian_pid = int((state_dir / "guardian.pid").read_text(encoding="utf-8"))
    assert healed_guardian_pid != guardian_pid
    assert "Server is already running" in healed.stdout
    assert "Healing sidecar" in healed.stdout
    assert "Guardian is running" in healed.stdout

    stopped = _run_launcher(env, "server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert stopped.stdout.index("Stopping guardian") < stopped.stdout.index(
        "Stopping server"
    )
    assert not (state_dir / "guardian.pid").exists()
    assert not (state_dir / "server.pid").exists()
    _wait_until_dead(healed_guardian_pid)
    _wait_until_dead(server_pid)
    lifecycle_lines = lifecycle_log.read_text(encoding="utf-8").splitlines()
    assert lifecycle_lines.index("guardian-stop", 2) < lifecycle_lines.index(
        "server-stop"
    )


def test_server_start_rolls_back_when_guardian_entrypoint_is_missing(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    (Path(env["HOME"]) / ".local" / "bin" / "vc-guardian").unlink()
    assert shutil.which("vc-guardian", path=env["PATH"]) is None
    port = _free_port()

    result = _run_launcher(env, "server", "start", "--port", str(port))

    assert result.returncode != 0
    assert "vc-guardian entrypoint not found" in result.stderr
    assert "rolling back the newly started server" in result.stderr
    assert not (state_dir / "server.pid").exists()
    status = json.loads((state_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["pid"] is None
    assert "server-stop" in lifecycle_log.read_text(encoding="utf-8")


def test_server_start_retargets_live_guardian_after_server_endpoint_changes(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    first_port = _free_port()
    first = _run_launcher(env, "server", "start", "--port", str(first_port))
    assert first.returncode == 0, first.stderr
    first_server_pid = int((state_dir / "server.pid").read_text(encoding="utf-8"))
    first_guardian_pid = int((state_dir / "guardian.pid").read_text(encoding="utf-8"))
    _wait_for_text(
        lifecycle_log,
        f"guardian-start --server-url http://127.0.0.1:{first_port}",
    )

    os.kill(first_server_pid, signal.SIGTERM)
    _wait_until_dead(first_server_pid)
    second_port = _free_port()
    second = _run_launcher(env, "server", "start", "--port", str(second_port))

    assert second.returncode == 0, second.stderr
    assert "Guardian endpoint changed" in second.stdout
    second_guardian_pid = int((state_dir / "guardian.pid").read_text(encoding="utf-8"))
    assert second_guardian_pid != first_guardian_pid
    assert (state_dir / "guardian.url").read_text(
        encoding="utf-8"
    ).strip() == f"http://127.0.0.1:{second_port}"
    _wait_until_dead(first_guardian_pid)
    _wait_for_text(
        lifecycle_log,
        f"guardian-start --server-url http://127.0.0.1:{second_port}",
    )

    stopped = _run_launcher(env, "server", "stop")
    assert stopped.returncode == 0, stopped.stderr


def test_server_status_and_doctor_report_stale_guardian_pid(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, _ = isolated_server_runtime
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "guardian.pid").write_text("99999999\n", encoding="utf-8")

    status = _run_launcher(env, "server", "status")
    doctor = _run_launcher(env, "server", "doctor")

    assert status.returncode != 0
    assert "Server: STOPPED" in status.stdout
    assert "Guardian: STALE-PID (stale: 99999999)" in status.stdout
    assert doctor.returncode != 0
    assert "Stale guardian PID file (stale: 99999999)" in doctor.stdout


def test_server_stop_refuses_to_signal_pid_mismatch(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, _ = isolated_server_runtime
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "guardian.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

    result = _run_launcher(env, "server", "stop")

    assert result.returncode != 0
    assert "different live process" in result.stderr
    assert _process_alive(os.getpid())


def test_packaged_launcher_matches_repo_launcher() -> None:
    assert PACKAGED_LAUNCHER.read_bytes() == LAUNCHER.read_bytes()

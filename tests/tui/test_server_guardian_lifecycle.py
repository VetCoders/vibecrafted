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
import time

host, raw_port = os.environ["VC_SERVER_ADDR"].rsplit(":", 1)
log_path = os.environ["LIFECYCLE_LOG"]

def record(message):
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(message + "\\n")

def stop(_signum, _frame):
    if os.environ.get("SERVER_IGNORE_TERM") == "1":
        record("server-term-ignored")
        return
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
        if self.path.startswith("/api/control/events"):
            if os.environ.get("SSE_STATUS") == "404":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b": ping\\n\\n")
            self.wfile.flush()
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
        """#!/usr/bin/env python3
import argparse
import json
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--server-url", required=True)
parser.add_argument("--ready-file", type=Path, required=True)
parser.add_argument("--ready-nonce", required=True)
args = parser.parse_args()
log_path = Path(os.environ["LIFECYCLE_LOG"])

def record(message):
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\\n")

def ready_payload():
    return {
        "schema": "vibecrafted.guardian-ready.v1",
        "nonce": args.ready_nonce,
        "pid": os.getpid(),
        "server_url": args.server_url,
    }

def remove_ready_if_owned():
    try:
        payload = json.loads(args.ready_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    if payload == ready_payload():
        args.ready_file.unlink(missing_ok=True)

def stop(_signum, _frame):
    record("guardian-stop")
    remove_ready_if_owned()
    raise SystemExit(0)

record("guardian-start " + " ".join(sys.argv[1:]))
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
request = urllib.request.Request(
    args.server_url + "/api/control/events?since=0",
    headers={"Accept": "text/event-stream"},
)
with urllib.request.urlopen(request, timeout=2.0) as response:
    if response.status != 200:
        raise SystemExit(2)
    content_type = response.headers.get("Content-Type", "").lower()
    if not content_type.startswith("text/event-stream"):
        raise SystemExit(3)
temporary = args.ready_file.with_name("." + args.ready_file.name + ".tmp")
temporary.write_text(json.dumps(ready_payload()) + "\\n", encoding="utf-8")
os.replace(temporary, args.ready_file)
while True:
    time.sleep(0.1)
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

    for pid_name in ("guardian.pid", "server.pid"):
        pid_file = state_dir / pid_name
        if not pid_file.is_file():
            continue
        raw_pid = pid_file.read_text(encoding="utf-8").strip()
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        identity_file = state_dir / pid_name.replace(".pid", ".identity.json")
        try:
            identity = json.loads(identity_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if identity.get("pid") == pid and _process_alive(pid):
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
    assert "unverified live process" in result.stderr
    assert _process_alive(os.getpid())


def test_server_stop_does_not_signal_decoy_with_guardian_marker(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, _ = isolated_server_runtime
    state_dir.mkdir(parents=True, exist_ok=True)
    decoy = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            "vc-guardian-decoy",
        ],
        env=env,
    )
    try:
        (state_dir / "guardian.pid").write_text(
            f"{decoy.pid}\n",
            encoding="utf-8",
        )

        result = _run_launcher(env, "server", "stop")

        assert result.returncode != 0
        assert "unverified live process" in result.stderr
        assert _process_alive(decoy.pid)
        assert (state_dir / "guardian.pid").is_file()
    finally:
        if _process_alive(decoy.pid):
            decoy.kill()
        decoy.wait(timeout=5)


def test_concurrent_server_starts_create_exactly_one_managed_pair(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    port = _free_port()
    argv = [
        str(LAUNCHER),
        "server",
        "start",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    first = subprocess.Popen(
        argv,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    second = subprocess.Popen(
        argv,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_stdout, first_stderr = first.communicate(timeout=20)
    second_stdout, second_stderr = second.communicate(timeout=20)

    assert first.returncode == 0, first_stderr
    assert second.returncode == 0, second_stderr
    assert "Server is up and healthy" in first_stdout + second_stdout
    assert "Server is already running" in first_stdout + second_stdout
    lines = lifecycle_log.read_text(encoding="utf-8").splitlines()
    assert lines.count("server-start") == 1
    assert sum(line.startswith("guardian-start ") for line in lines) == 1
    assert (state_dir / "server.identity.json").is_file()
    assert (state_dir / "guardian.identity.json").is_file()
    assert (state_dir / "guardian.ready-path").is_file()

    stopped = _run_launcher(env, "server", "stop")
    assert stopped.returncode == 0, stopped.stderr


def test_short_lived_guardian_fails_readiness_and_rolls_back_server(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    guardian = Path(env["HOME"]) / ".local" / "bin" / "vc-guardian"
    _write_executable(
        guardian,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )

    result = _run_launcher(
        env,
        "server",
        "start",
        "--port",
        str(_free_port()),
    )

    assert result.returncode != 0
    assert "Guardian startup failed" in result.stderr
    assert not (state_dir / "server.pid").exists()
    status = json.loads((state_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["pid"] is None
    assert "server-stop" in lifecycle_log.read_text(encoding="utf-8")


def test_guardian_404_fails_readiness_and_rolls_back_server(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    env["SSE_STATUS"] = "404"

    result = _run_launcher(
        env,
        "server",
        "start",
        "--port",
        str(_free_port()),
    )

    assert result.returncode != 0
    assert "Guardian failed SSE readiness" in result.stderr
    assert "Guardian startup failed" in result.stderr
    assert not (state_dir / "server.pid").exists()
    assert not (state_dir / "guardian.pid").exists()
    assert "server-stop" in lifecycle_log.read_text(encoding="utf-8")


def test_term_ignoring_server_remains_tracked_until_confirmed_sigkill(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, state_dir, lifecycle_log = isolated_server_runtime
    env["SERVER_IGNORE_TERM"] = "1"
    env["VIBECRAFTED_STOP_TERM_WAIT_TICKS"] = "10"
    started = _run_launcher(
        env,
        "server",
        "start",
        "--port",
        str(_free_port()),
    )
    assert started.returncode == 0, started.stderr
    server_pid = int((state_dir / "server.pid").read_text(encoding="utf-8"))

    stopper = subprocess.Popen(
        [str(LAUNCHER), "server", "stop"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _wait_for_text(lifecycle_log, "server-term-ignored")
    assert (state_dir / "server.pid").is_file()
    assert (state_dir / "server.identity.json").is_file()
    stdout, stderr = stopper.communicate(timeout=15)

    assert stopper.returncode == 0, stderr
    assert "sending SIGKILL" in stdout
    assert not (state_dir / "server.pid").exists()
    assert not (state_dir / "server.identity.json").exists()
    _wait_until_dead(server_pid)


def test_server_runtime_uses_custom_vibecrafted_home(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
) -> None:
    env, default_state_dir, _ = isolated_server_runtime
    custom_home = Path(env["HOME"]).parent / "custom-vibecrafted-home"
    env["VIBECRAFTED_HOME"] = str(custom_home)
    custom_state_dir = custom_home / "server"

    started = _run_launcher(
        env,
        "server",
        "start",
        "--port",
        str(_free_port()),
    )

    assert started.returncode == 0, started.stderr
    assert (custom_state_dir / "server.pid").is_file()
    assert (custom_state_dir / "guardian.pid").is_file()
    assert not default_state_dir.exists()
    status = _run_launcher(env, "server", "status")
    doctor = _run_launcher(env, "server", "doctor")
    assert status.returncode == 0, status.stderr
    assert doctor.returncode == 0, doctor.stderr
    stopped = _run_launcher(env, "server", "stop")
    assert stopped.returncode == 0, stopped.stderr


def test_malicious_cli_host_and_status_json_are_never_executed(
    isolated_server_runtime: tuple[dict[str, str], Path, Path],
    tmp_path: Path,
) -> None:
    env, state_dir, _ = isolated_server_runtime
    cli_pwn = tmp_path / "cli-pwn"
    status_pwn = tmp_path / "status-pwn"
    malicious_cli_host = (
        "127.0.0.1');__import__('pathlib').Path("
        f"{str(cli_pwn)!r}).write_text('owned');#"
    )

    cli_result = _run_launcher(
        env,
        "server",
        "start",
        "--host",
        malicious_cli_host,
        "--port",
        str(_free_port()),
    )

    assert cli_result.returncode != 0
    assert "Invalid server endpoint" in cli_result.stderr
    assert not cli_pwn.exists()

    state_dir.mkdir(parents=True, exist_ok=True)
    malicious_status_host = (
        "127.0.0.1');__import__('pathlib').Path("
        f"{str(status_pwn)!r}).write_text('owned');#"
    )
    (state_dir / "status.json").write_text(
        json.dumps({"host": malicious_status_host, "port": 3024}),
        encoding="utf-8",
    )
    status = _run_launcher(env, "server", "status")
    opened = _run_launcher(env, "server", "open")
    doctor = _run_launcher(env, "server", "doctor")

    assert status.returncode != 0
    assert "INVALID-ENDPOINT" in status.stdout
    assert opened.returncode != 0
    assert "invalid endpoint" in opened.stderr
    assert doctor.returncode != 0
    assert "status.json contains an invalid endpoint" in doctor.stdout
    assert not status_pwn.exists()


def test_packaged_launcher_matches_repo_launcher() -> None:
    assert PACKAGED_LAUNCHER.read_bytes() == LAUNCHER.read_bytes()

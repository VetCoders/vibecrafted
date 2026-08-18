"""Fixtures for G6 lifecycle → server e2e (real server binary, real stub worker)."""

from __future__ import annotations

import http.client
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_DIR = Path(__file__).resolve().parent
FIXTURES = E2E_DIR / "fixtures"
STUB_WORKER = FIXTURES / "stub_worker.py"

# Candidate release binaries produced by cargo / install-server.
_SERVER_CANDIDATES = (
    REPO_ROOT / "vibecrafted-server" / "target" / "release" / "vibecrafted-server-web",
    Path.home() / ".local" / "bin" / "vc-server",
    Path.home() / ".local" / "bin" / "vibecrafted-server-web",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_launcher_wrapper(candidate: Path) -> bool:
    """True when the candidate is a generated shell launcher, not a real binary.

    `make install` publishes `~/.local/bin/vc-server` as a wrapper that exports
    the operator's own `VIBECRAFTED_HOME` before exec'ing the release binary.
    Running that wrapper silently overrides the isolated `vc_home` this suite
    builds, so the server reads the operator's real control plane and answers
    404 for the run the test just wrote. That reads as a product failure when it
    is a harness failure — refuse the wrapper instead.
    """
    try:
        with candidate.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return True


def resolve_server_binary() -> Path | None:
    for candidate in _SERVER_CANDIDATES:
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            continue
        if _is_launcher_wrapper(candidate):
            continue
        return candidate
    return None


@pytest.fixture
def server_binary() -> Path:
    binary = resolve_server_binary()
    if binary is None:
        pytest.skip(
            "no real vibecrafted-server binary (launcher wrappers are refused: "
            "they pin the operator's VIBECRAFTED_HOME and break test isolation) "
            "— run: cargo build --manifest-path vibecrafted-server/Cargo.toml "
            "--release"
        )
    return binary


@pytest.fixture
def stub_worker_script() -> Path:
    assert STUB_WORKER.is_file(), f"missing stub worker: {STUB_WORKER}"
    return STUB_WORKER


@pytest.fixture
def vc_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated VIBECRAFTED_HOME with control_plane dirs ready for writers + server."""
    home = tmp_path / ".vibecrafted"
    (home / "control_plane" / "runs").mkdir(parents=True)
    (home / "control_plane" / "lifecycle_runs").mkdir(parents=True)
    (home / "control_plane" / "runtime_runs").mkdir(parents=True)
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    # Isolate from ambient runtime that may have leaked into the parent process.
    for key in list(os.environ):
        if key.startswith("VIBECRAFTED_") and key != "VIBECRAFTED_HOME":
            monkeypatch.delenv(key, raising=False)
    return home


@pytest.fixture
def live_server(server_binary: Path, vc_home: Path, tmp_path: Path):
    """Spawn vibecrafted-server-web against ``vc_home`` on an ephemeral port.

    Yields ``(base_url, proc)``. Tears down with SIGTERM then SIGKILL.
    """
    port = _free_port()
    site_root = tmp_path / "site"
    site_root.mkdir()
    # Minimal site tree so the Leptos static fallback has somewhere to point;
    # control routes do not depend on assets.
    public = REPO_ROOT / "vibecrafted-server" / "web" / "public"
    if public.is_dir():
        for item in public.iterdir():
            target = site_root / item.name
            if item.is_file():
                target.write_bytes(item.read_bytes())

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(vc_home)
    env["VC_SERVER_ADDR"] = f"127.0.0.1:{port}"
    env["VC_SERVER_SITE_ROOT"] = str(site_root)
    env["VC_CONTROL_SSE_POLL_MS"] = "50"
    env["VC_CONTROL_SSE_KEEPALIVE_MS"] = "500"
    # Drop LEPTOS_* so the binary uses VC_SERVER_ADDR only.
    for key in list(env):
        if key.startswith("LEPTOS_"):
            del env[key]

    log_path = tmp_path / "server.log"
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(server_binary)],
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=str(tmp_path),
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15.0
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            log_handle.flush()
            body = log_path.read_text(encoding="utf-8", errors="replace")
            pytest.fail(f"server died before ready (exit={proc.returncode}):\n{body}")
        # Speak HTTP to the loopback port directly. urllib would also resolve
        # file:// and other schemes from a composed string, which is a finding
        # this suite has no reason to carry for a readiness poll.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
        try:
            conn.request("GET", "/api/control/state")
            if conn.getresponse().status == 200:
                ready = True
                break
        except OSError:
            time.sleep(0.1)
        finally:
            conn.close()
    if not ready:
        proc.kill()
        log_handle.flush()
        body = log_path.read_text(encoding="utf-8", errors="replace")
        pytest.fail(f"server health timeout:\n{body}")

    try:
        yield base, proc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        log_handle.close()

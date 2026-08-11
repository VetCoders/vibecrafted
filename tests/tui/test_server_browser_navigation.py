"""Browser regression for vc-server route data surviving navigation.

Run explicitly against an installed or foreground server:

    VC_SERVER_BROWSER_E2E=1 \
    VC_SERVER_BROWSER_URL=http://127.0.0.1:3025 \
    pytest -q tests/tui/test_server_browser_navigation.py

The test intentionally clicks links in one browser tab. Endpoint-only HTTP
smokes cannot detect the hydrate-build fallback that used to replace live
control-plane data with ``DashboardData::default()`` after SPA navigation.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


def _chrome_binary() -> str | None:
    configured = os.environ.get("VC_SERVER_CHROME_BIN")
    candidates = [
        configured,
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return next(
        (
            candidate
            for candidate in candidates
            if candidate and Path(candidate).is_file()
        ),
        None,
    )


class BrowserNavigationProbe:
    """Small CDP client; keeps the test dependency-free beyond Chrome."""

    def __init__(self, websocket_url: str) -> None:
        prefix = "ws://"
        if not websocket_url.startswith(prefix):
            raise ValueError(f"unsupported DevTools URL: {websocket_url}")
        authority, path = websocket_url[len(prefix) :].split("/", 1)
        host, raw_port = authority.rsplit(":", 1)
        self._socket = socket.create_connection((host, int(raw_port)), timeout=5)
        self._next_id = 0
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {authority}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._socket.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += self._socket.recv(4096)
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(
                f"DevTools websocket refused upgrade: {response[:120]!r}"
            )

    def close(self) -> None:
        self._socket.close()

    def _read_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self._socket.recv(length - len(chunks))
            if not chunk:
                raise ConnectionError("DevTools websocket closed")
            chunks.extend(chunk)
        return bytes(chunks)

    def _send(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        mask = secrets.token_bytes(4)
        length = len(body)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
        self._socket.sendall(bytes(header) + mask + masked)

    def _receive(self) -> dict[str, object]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if second & 0x80:
            mask = self._read_exact(4)
            body = bytes(
                byte ^ mask[index % 4]
                for index, byte in enumerate(self._read_exact(length))
            )
        else:
            body = self._read_exact(length)
        if opcode == 0x9:
            self._send({})
            return self._receive()
        if opcode != 0x1:
            return self._receive()
        return json.loads(body)

    def call(
        self, method: str, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        self._next_id += 1
        request_id = self._next_id
        self._send({"id": request_id, "method": method, "params": params or {}})
        while True:
            message = self._receive()
            if message.get("id") == request_id:
                return message

    def evaluate(self, expression: str) -> object:
        response = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "error" in response:
            raise RuntimeError(response["error"])
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise TypeError(f"malformed Runtime.evaluate response: {response}")
        remote = result.get("result", {})
        if not isinstance(remote, dict):
            raise TypeError(f"malformed remote object: {response}")
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return remote.get("value")


def _wait_for(
    probe: BrowserNavigationProbe, expression: str, timeout: float = 15
) -> object:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = probe.evaluate(expression)
            if value:
                return value
        except (TimeoutError, ConnectionError, RuntimeError) as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError(
        f"browser condition timed out: {expression}; last error={last_error}"
    )


@pytest.mark.skipif(
    os.environ.get("VC_SERVER_BROWSER_E2E") != "1",
    reason="set VC_SERVER_BROWSER_E2E=1 for the live browser navigation contract",
)
def test_server_navigation_preserves_runtime_truth_without_manual_refresh() -> None:
    chrome = _chrome_binary()
    if chrome is None:
        pytest.fail("Chrome/Chromium is required when VC_SERVER_BROWSER_E2E=1")

    server_url = os.environ.get(
        "VC_SERVER_BROWSER_URL", "http://127.0.0.1:3025"
    ).rstrip("/")
    with urlopen(f"{server_url}/api/health", timeout=5) as response:
        assert json.load(response)["status"] == "ok"

    profile = Path(tempfile.mkdtemp(prefix="vc-server-browser-e2e-"))
    process = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            server_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    probe: BrowserNavigationProbe | None = None
    try:
        active_port = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        while not active_port.is_file() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert active_port.is_file(), "Chrome did not expose DevToolsActivePort"
        port = active_port.read_text().splitlines()[0]

        pages: list[dict[str, object]] = []
        deadline = time.monotonic() + 10
        while not pages and time.monotonic() < deadline:
            with urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                pages = [
                    page for page in json.load(response) if page.get("type") == "page"
                ]
            if not pages:
                time.sleep(0.1)
        assert pages, "Chrome exposed no page target"
        probe = BrowserNavigationProbe(str(pages[0]["webSocketDebuggerUrl"]))

        _wait_for(
            probe, "document.readyState === 'complete' && location.pathname === '/'"
        )
        initial_alive = int(
            _wait_for(
                probe,
                "Number([...document.querySelectorAll('.operator-now-cells .operator-summary-cell')].find(x => x.querySelector('dt').textContent.trim() === 'alive').querySelector('dd').textContent)",
            )
        )
        assert initial_alive > 0, (
            "live browser contract requires at least one active run"
        )

        probe.evaluate(
            "document.querySelector('a.server-nav-link[href=\"/runs\"]').click(); true"
        )
        _wait_for(
            probe, "location.pathname === '/runs' && document.readyState === 'complete'"
        )
        current_agents = int(
            _wait_for(
                probe,
                "Number(document.querySelector('[aria-label=\"Active runs\"] .control-panel-head span').textContent)",
            )
        )
        assert current_agents == initial_alive

        run_href = str(
            _wait_for(
                probe,
                "document.querySelector('[aria-label=\"Active runs\"] a.control-run-id').getAttribute('href')",
            )
        )
        probe.evaluate(
            "document.querySelector('[aria-label=\"Active runs\"] a.control-run-id').click(); true"
        )
        _wait_for(
            probe,
            f"location.pathname === {json.dumps(run_href)} && document.readyState === 'complete'",
        )
        assert probe.evaluate(
            "Boolean(document.querySelector('.run-detail-title').textContent.trim())"
        )
        assert probe.evaluate(
            "Boolean(document.querySelector('[data-live-transcript]'))"
        )

        probe.evaluate(
            "document.querySelector('a.server-nav-link[href=\"/\"]').click(); true"
        )
        _wait_for(
            probe, "location.pathname === '/' && document.readyState === 'complete'"
        )
        final_alive = int(
            _wait_for(
                probe,
                "Number([...document.querySelectorAll('.operator-now-cells .operator-summary-cell')].find(x => x.querySelector('dt').textContent.trim() === 'alive').querySelector('dd').textContent)",
            )
        )
        assert final_alive == initial_alive
    finally:
        if probe is not None:
            probe.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(profile, ignore_errors=True)

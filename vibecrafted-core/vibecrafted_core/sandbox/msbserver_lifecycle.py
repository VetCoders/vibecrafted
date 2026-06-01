from __future__ import annotations

import http.client
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from vibecrafted_core.runtime_paths import vibecrafted_home


class MsbserverLifecycle:
    def __init__(
        self,
        *,
        server_url: str | None = None,
        host: str = "127.0.0.1",
        port: int = 5555,
        home: str | os.PathLike[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.server_url = (server_url or os.environ.get("MSB_SERVER_URL") or "").rstrip(
            "/"
        )
        if not self.server_url:
            self.server_url = f"http://{host}:{port}"
        self.home = Path(home).expanduser() if home else vibecrafted_home() / "sandbox"
        self.pid_file = self.home / "msbserver.pid"
        self.log_file = self.home / "msbserver.log"

    def ensure_running(
        self, api_key_path: str | os.PathLike[str] | None = None
    ) -> bool:
        if self.is_running():
            return True
        binary = os.environ.get("MSBSERVER_EXE") or shutil.which("msbserver")
        if not binary:
            return False

        self.home.mkdir(parents=True, exist_ok=True)
        key = self._read_server_key(api_key_path)
        command = [binary, "--host", self.host, "--port", str(self.port)]
        if key:
            command.extend(["--key", key])
        else:
            command.append("--dev")

        env = os.environ.copy()
        env.setdefault("MICROSANDBOX_HOME", str(self.home / "microsandbox-home"))
        with self.log_file.open("ab") as log:
            process = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
        self.pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
        return self._wait_for_health(timeout=10.0)

    def is_running(self) -> bool:
        if not self._health_ok():
            self._cleanup_stale_pid()
            return False
        return True

    def stop(self, timeout: float = 5.0) -> None:
        pid = self._read_pid()
        if pid is None:
            self.pid_file.unlink(missing_ok=True)
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self.pid_file.unlink(missing_ok=True)
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                self.pid_file.unlink(missing_ok=True)
                return
            time.sleep(0.1)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.pid_file.unlink(missing_ok=True)

    def _wait_for_health(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._health_ok():
                return True
            if (pid := self._read_pid()) is not None and not _pid_alive(pid):
                return False
            time.sleep(0.2)
        return False

    def _health_ok(self) -> bool:
        match = re.fullmatch(r"(https?)://([^/:]+)(?::([0-9]+))?", self.server_url)
        if not match:
            return False
        scheme, host, port_raw = match.groups()
        port = int(port_raw) if port_raw else (443 if scheme == "https" else 80)
        connection_cls = (
            http.client.HTTPSConnection
            if scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_cls(host, port=port, timeout=1.0)
        try:
            connection.request("GET", "/api/v1/health")
            response = connection.getresponse()
            return 200 <= response.status < 300
        except OSError:
            return False
        finally:
            connection.close()

    def _read_pid(self) -> int | None:
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _cleanup_stale_pid(self) -> None:
        pid = self._read_pid()
        if pid is None or not _pid_alive(pid):
            self.pid_file.unlink(missing_ok=True)

    def _read_server_key(
        self, api_key_path: str | os.PathLike[str] | None = None
    ) -> str:
        candidate = (
            Path(api_key_path).expanduser()
            if api_key_path
            else self.home / "msbserver.key"
        )
        if not candidate.is_file():
            return ""
        value = candidate.read_text(encoding="utf-8").strip()
        return value if value.startswith("msb_") else ""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

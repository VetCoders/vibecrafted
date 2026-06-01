from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from vibecrafted_core import control_plane
from vibecrafted_core.sandbox import SandboxAdapter, SandboxPolicy
from vibecrafted_core.sandbox import adapter as adapter_module
from vibecrafted_core.sandbox import msbserver_lifecycle as lifecycle_module
from vibecrafted_core.sandbox.msbserver_lifecycle import MsbserverLifecycle
from vibecrafted_core.sandbox.policy import default_policy_path


class FakeLifecycle:
    server_url = "http://127.0.0.1:5555"

    def ensure_running(self, api_key_path: object = None) -> bool:
        return True


class FakeSession:
    async def close(self) -> None:
        return None


class FakeExecution:
    exit_code = 0

    async def output(self) -> str:
        return "ok"

    async def error(self) -> str:
        return ""


class FakeCommand:
    async def run(
        self, command: str, args: list[str] | None = None, timeout: int | None = None
    ) -> FakeExecution:
        FakeSandbox.last_command = command
        FakeSandbox.last_args = args or []
        FakeSandbox.last_timeout = timeout
        return FakeExecution()


class FakeSandbox:
    last_command = ""
    last_args: list[str] = []
    last_timeout: int | None = None
    started_with: dict[str, object] = {}

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self._session = None
        self._is_started = False

    async def start(self, **kwargs: object) -> None:
        self._is_started = True
        FakeSandbox.started_with = kwargs

    async def stop(self) -> None:
        self._is_started = False

    @property
    def command(self) -> FakeCommand:
        return FakeCommand()


@pytest.fixture(autouse=True)
def fake_microsandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.SimpleNamespace(PythonSandbox=FakeSandbox, NodeSandbox=FakeSandbox)
    monkeypatch.setitem(sys.modules, "microsandbox", module)

    async def fake_client_session() -> FakeSession:
        return FakeSession()

    monkeypatch.setattr(adapter_module, "_client_session", fake_client_session)


def test_policy_default_is_deny_with_readonly_project_mount(tmp_path: Path) -> None:
    policy = SandboxPolicy.default(tmp_path)

    assert policy.network == "deny"
    assert policy.filesystem_root_readonly is True
    assert f"{tmp_path.resolve()}:/workspace:ro" in policy.mounts
    assert "/tmp:/tmp:rw" in policy.mounts


def test_policy_loads_operator_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    path = default_policy_path()
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                "cpu: 2",
                "memory_mb: 1024",
                "network: allow",
                "allow_hosts:",
                "  - example.com",
            ]
        ),
        encoding="utf-8",
    )

    policy = SandboxPolicy.load(root=tmp_path)

    assert policy.cpu == 2.0
    assert policy.memory_mb == 1024
    assert policy.network == "allow"
    assert policy.allow_hosts == ("example.com",)


def test_lifecycle_reports_not_running_for_dead_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(lifecycle_module, "_pid_alive", lambda pid: False)
    lifecycle = MsbserverLifecycle(home=tmp_path / "sandbox")
    lifecycle.home.mkdir(parents=True)
    lifecycle.pid_file.write_text("999999\n", encoding="utf-8")

    assert lifecycle.is_running() is False
    assert not lifecycle.pid_file.exists()


def test_lifecycle_rejects_non_http_health_url(tmp_path: Path) -> None:
    lifecycle = MsbserverLifecycle(
        server_url="file:///etc/passwd",
        home=tmp_path / "sandbox",
    )

    assert lifecycle.is_running() is False


def test_lifecycle_reads_valid_msbserver_key(tmp_path: Path) -> None:
    key_file = tmp_path / "msbserver.key"
    key_file.write_text("msb_valid\n", encoding="utf-8")
    lifecycle = MsbserverLifecycle(home=tmp_path / "sandbox")

    assert lifecycle._read_server_key(key_file) == "msb_valid"


def test_lifecycle_ignores_invalid_msbserver_key(tmp_path: Path) -> None:
    key_file = tmp_path / "msbserver.key"
    key_file.write_text("not-a-msb-key\n", encoding="utf-8")
    lifecycle = MsbserverLifecycle(home=tmp_path / "sandbox")

    assert lifecycle._read_server_key(key_file) == ""


def test_adapter_executes_command_and_emits_spawn_updates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    policy = SandboxPolicy(memory_mb=768, mounts=("/tmp:/tmp:rw",))
    adapter = SandboxAdapter(lifecycle=FakeLifecycle(), policy=policy)

    result = adapter.execute_sync(
        ["true"],
        env={"VIBECRAFTED_RUN_ID": "run-1"},
        cwd=tmp_path,
        timeout=3,
        run_id="run-1",
        agent="command",
        skill="implement",
        mode="raw",
    )

    assert result.exit_code == 0
    assert FakeSandbox.started_with["memory"] == 768
    assert FakeSandbox.last_command == "sh"
    assert FakeSandbox.last_timeout == 3
    assert "cd " in FakeSandbox.last_args[1]
    kinds = [event["kind"] for event in control_plane.read_event_tail(10)]
    assert kinds.count("spawn-update") >= 3


def test_adapter_shell_script_exports_env_before_exec(tmp_path: Path) -> None:
    script = adapter_module._shell_script(
        ["true"],
        env={"FOO": "bar baz"},
        cwd=tmp_path,
    )

    assert "FOO='bar baz' exec true" in script
    assert "exec FOO=" not in script


def test_adapter_can_use_local_microsandbox_sdk_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sdk_root = tmp_path / "sdk" / "python"
    (sdk_root / "microsandbox").mkdir(parents=True)
    monkeypatch.setenv("MICROSANDBOX_PYTHON_SDK", str(sdk_root))
    monkeypatch.setattr(adapter_module.sys, "path", [])

    adapter_module._ensure_microsandbox_sdk_path()

    assert str(sdk_root) in adapter_module.sys.path


def test_real_msbserver_absence_is_skip_not_failure() -> None:
    lifecycle = MsbserverLifecycle(port=65534)
    if lifecycle.is_running():
        pytest.xfail("operator has a real msbserver on the test port")
    assert lifecycle.is_running() is False

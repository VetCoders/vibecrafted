from __future__ import annotations

import json
import os
import plistlib
import subprocess
import threading
import time
from pathlib import Path

import pytest
from vibecrafted_core import server_supervisor as supervisor


def _executable(path: Path, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path.resolve()


def _config(tmp_path: Path, launcher: Path) -> supervisor.SupervisorConfig:
    operator_home = tmp_path / "operator"
    home = operator_home / ".vibecrafted"
    runtime_home = operator_home / ".local" / "share" / "vibecrafted"
    return supervisor.SupervisorConfig(
        paths=supervisor.SupervisorPaths.create(
            home=home.resolve(),
            runtime_home=runtime_home.resolve(),
            operator_home=operator_home.resolve(),
        ),
        launcher=launcher.resolve(),
        host="127.0.0.1",
        port=3024,
        interval=0.05,
        maximum_backoff=0.2,
        command_timeout=2,
    )


def test_plistlib_renderer_preserves_metacharacters_without_xml_injection(
    tmp_path: Path,
) -> None:
    special = tmp_path / 'owned & <path> "quoted"'
    launcher = _executable(special / "vibecrafted")
    supervisor_binary = _executable(special / "vc-server-supervisor")
    config = _config(special, launcher)

    rendered = supervisor.render_launch_agent_plist(
        config,
        supervisor_binary=supervisor_binary,
    )
    payload = plistlib.loads(rendered)

    assert payload["Label"] == supervisor.LAUNCH_AGENT_LABEL
    assert payload["ProgramArguments"][0] == str(supervisor_binary)
    assert payload["ProgramArguments"][3] == str(launcher)
    assert payload["ProgramArguments"][5] == str(config.paths.home)
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert set(payload["EnvironmentVariables"]) == {
        "HOME",
        "PATH",
        "VIBECRAFTED_HOME",
        "VIBECRAFTED_RUNTIME_HOME",
        "VIBECRAFTED_SERVER_SERVICE",
    }
    assert b"&amp;" in rendered
    assert b"<path>" not in rendered


def test_service_install_is_idempotent_and_refuses_symlink_destination(
    tmp_path: Path,
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    supervisor_binary = _executable(tmp_path / "bin" / "vc-server-supervisor")
    config = _config(tmp_path, launcher)

    assert supervisor.install_service(
        config,
        supervisor_binary=supervisor_binary,
    )
    first = config.paths.launch_agent_file.read_bytes()
    assert not supervisor.install_service(
        config,
        supervisor_binary=supervisor_binary,
    )
    assert config.paths.launch_agent_file.read_bytes() == first
    assert config.paths.launch_agent_file.stat().st_mode & 0o777 == 0o600

    config.paths.launch_agent_file.unlink()
    decoy = tmp_path / "decoy.plist"
    decoy.write_text("untouched", encoding="utf-8")
    config.paths.launch_agent_file.symlink_to(decoy)
    with pytest.raises(supervisor.SupervisorError, match="refusing to replace"):
        supervisor.install_service(
            config,
            supervisor_binary=supervisor_binary,
        )
    assert decoy.read_text(encoding="utf-8") == "untouched"


def test_foreground_supervisor_lock_and_receipt_are_truthful(
    tmp_path: Path,
) -> None:
    lifecycle_log = tmp_path / "lifecycle.log"
    launcher = _executable(
        tmp_path / "bin" / "vibecrafted",
        f"""#!/bin/sh
printf '%s\n' "$2" >> {str(lifecycle_log)!r}
exit 0
""",
    )
    config = _config(tmp_path, launcher)
    stop_event = threading.Event()
    result: list[int] = []
    worker = threading.Thread(
        target=lambda: result.append(
            supervisor.run_supervisor(config, stop_event=stop_event)
        ),
        daemon=True,
    )
    worker.start()

    deadline = time.monotonic() + 5
    probe = supervisor.probe_supervisor(config.paths)
    while not probe.verified and time.monotonic() < deadline:
        time.sleep(0.02)
        probe = supervisor.probe_supervisor(config.paths)
    assert probe.live and probe.verified and probe.pid == os.getpid()

    receipt = json.loads(config.paths.receipt_file.read_text(encoding="utf-8"))
    while not receipt["last_success_at"] and time.monotonic() < deadline:
        time.sleep(0.02)
        receipt = json.loads(config.paths.receipt_file.read_text(encoding="utf-8"))
    assert receipt["schema"] == supervisor.SUPERVISOR_SCHEMA
    assert receipt["endpoint"]["url"] == "http://127.0.0.1:3024"
    assert receipt["last_success_at"]
    assert receipt["consecutive_failures"] == 0

    stop_event.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result == [0]
    assert not supervisor.probe_supervisor(config.paths).live
    stopped = json.loads(config.paths.receipt_file.read_text(encoding="utf-8"))
    assert stopped["state"] == "stopped"
    assert lifecycle_log.read_text(encoding="utf-8").splitlines()[-1] == "stop"


def test_start_service_bootstraps_and_kickstarts_only_when_needed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    supervisor_binary = _executable(tmp_path / "bin" / "vc-server-supervisor")
    config = _config(tmp_path, launcher)
    supervisor.install_service(config, supervisor_binary=supervisor_binary)
    monkeypatch.setattr(supervisor.sys, "platform", "darwin")

    calls: list[list[str]] = []
    loaded = False

    def fake_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal loaded
        calls.append(list(args))
        if args[0] == "bootstrap":
            loaded = True
        return subprocess.CompletedProcess(args, 0, "", "")

    probes = iter(
        [
            supervisor.SupervisorProbe(False, False, None, None),
            supervisor.SupervisorProbe(False, False, None, None),
        ]
    )
    monkeypatch.setattr(supervisor, "_launchctl", fake_launchctl)
    monkeypatch.setattr(supervisor, "_launchctl_loaded", lambda: loaded)
    monkeypatch.setattr(supervisor, "probe_supervisor", lambda _paths: next(probes))
    monkeypatch.setattr(
        supervisor,
        "_wait_for_supervisor",
        lambda _paths, *, live: supervisor.SupervisorProbe(
            live,
            live,
            1234 if live else None,
            True if live else None,
        ),
    )

    supervisor.start_service(config)
    assert [call[0] for call in calls] == ["bootstrap", "kickstart"]

    calls.clear()
    monkeypatch.setattr(
        supervisor,
        "probe_supervisor",
        lambda _paths: supervisor.SupervisorProbe(True, True, 1234, True),
    )
    supervisor.start_service(config)
    assert calls == []


def test_service_status_distinguishes_all_runtime_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    supervisor_binary = _executable(tmp_path / "bin" / "vc-server-supervisor")
    config = _config(tmp_path, launcher)
    supervisor.install_service(config, supervisor_binary=supervisor_binary)
    monkeypatch.setattr(supervisor.sys, "platform", "darwin")
    monkeypatch.setattr(supervisor, "_launchctl_loaded", lambda: True)
    monkeypatch.setattr(
        supervisor,
        "probe_supervisor",
        lambda _paths: supervisor.SupervisorProbe(True, True, 9876, True),
    )
    monkeypatch.setattr(supervisor, "_pair_healthy", lambda _launcher, _env: True)

    status = supervisor.service_status(config)

    assert status == supervisor.ServiceStatus(
        installed=True,
        loaded=True,
        supervisor_live=True,
        supervisor_verified=True,
        pair_healthy=True,
        supervisor_pid=9876,
    )


def test_linux_service_command_fails_closed_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    monkeypatch.setattr(supervisor.sys, "platform", "linux")

    result = supervisor.main(
        [
            "service",
            "status",
            "--launcher",
            str(launcher),
            "--home",
            str((tmp_path / "home").resolve()),
            "--runtime-home",
            str((tmp_path / "runtime").resolve()),
            "--operator-home",
            str((tmp_path / "operator").resolve()),
        ]
    )

    assert result == supervisor.EX_CONFIG
    assert "macOS launchd-only" in capsys.readouterr().err
    assert not (tmp_path / "operator" / "Library" / "LaunchAgents").exists()


def test_child_environment_is_a_minimal_nonsecret_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    config = _config(tmp_path, launcher)
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-cross")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross")
    monkeypatch.setenv("VIBECRAFTED_STOP_TERM_WAIT_TICKS", "9")

    environment = supervisor._child_environment(config.paths)

    assert "GITHUB_TOKEN" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["VIBECRAFTED_STOP_TERM_WAIT_TICKS"] == "9"
    assert environment["VIBECRAFTED_HOME"] == str(config.paths.home)
    assert environment["VIBECRAFTED_RUNTIME_HOME"] == str(config.paths.runtime_home)


def test_manual_stop_guard_refuses_loaded_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    supervisor_binary = _executable(tmp_path / "bin" / "vc-server-supervisor")
    config = _config(tmp_path, launcher)
    supervisor.install_service(config, supervisor_binary=supervisor_binary)
    monkeypatch.setattr(supervisor.sys, "platform", "darwin")
    monkeypatch.setattr(supervisor, "_launchctl_loaded", lambda: True)
    monkeypatch.setattr(
        supervisor,
        "probe_supervisor",
        lambda _paths: supervisor.SupervisorProbe(False, False, None, None),
    )

    with pytest.raises(
        supervisor.SupervisorError,
        match="vibecrafted server service stop",
    ) as failure:
        supervisor.manual_stop_guard(config.paths)
    assert failure.value.exit_code == supervisor.EX_TEMPFAIL


def test_invalid_held_kernel_lock_remains_fail_closed(tmp_path: Path) -> None:
    launcher = _executable(tmp_path / "bin" / "vibecrafted")
    config = _config(tmp_path, launcher)

    with supervisor._SupervisorLease(config.paths, service_managed=False):
        config.paths.lock_file.write_text("{invalid", encoding="utf-8")
        probe = supervisor.probe_supervisor(config.paths)
        assert probe.live
        assert not probe.verified
        assert probe.pid is None
        with pytest.raises(
            supervisor.SupervisorError,
            match="active foreground supervisor",
        ) as failure:
            supervisor.manual_stop_guard(config.paths)
        assert failure.value.exit_code == supervisor.EX_TEMPFAIL

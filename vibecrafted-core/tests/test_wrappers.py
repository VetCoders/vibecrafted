from __future__ import annotations

import subprocess

import pytest

from vibecrafted_core import wrappers
from vibecrafted_core import workflow


def test_resume_main_routes_captured_session_through_zellij_aware_resume_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        wrappers.control_plane,
        "lookup_run",
        lambda run_id: {"run_id": run_id, "session_id": "sess-codex-123"},
    )

    def fake_call(command: list[str]) -> int:
        calls.append(command)
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert (
        wrappers.resume_main(
            [
                "--run-id",
                "impl-080608-14038",
                "--agent",
                "codex",
                "--prompt",
                "Continue the fix",
            ]
        )
        == 0
    )

    assert calls == [
        [
            str(wrappers.deck_path()),
            "resume",
            "codex",
            "--session",
            "sess-codex-123",
            "--prompt",
            "Continue the fix",
        ]
    ]


def test_stop_main_prints_success_for_stopped_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        workflow,
        "stop_run",
        lambda run_id, *, reason, grace_seconds: {
            "accepted": True,
            "run_id": run_id,
            "target": "launcher_pid",
            "target_pid": 1234,
            "target_pgid": 1234,
            "already_dead": False,
            "run": {"state": "stopped"},
        },
    )

    code = wrappers.stop_main(
        ["--agent", "codex", "--run-id", "wflw-010101-0001", "--grace-seconds", "0"]
    )

    assert code == 0
    assert (
        "run_id=wflw-010101-0001 state=stopped "
        "target=launcher_pid:1234 pgid=1234 TERM sent"
    ) in capsys.readouterr().out


def test_stop_main_terminal_noop_is_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        workflow,
        "stop_run",
        lambda run_id, *, reason, grace_seconds: {
            "accepted": False,
            "run_id": run_id,
            "reason": "run_terminal",
            "run": {"state": "completed"},
        },
    )

    code = wrappers.stop_main(["--run-id", "wflw-terminal"])

    assert code == 0
    assert "already terminal state=completed; no-op" in capsys.readouterr().out

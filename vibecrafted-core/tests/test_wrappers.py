from __future__ import annotations

import subprocess

import pytest

from vibecrafted_core import wrappers


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

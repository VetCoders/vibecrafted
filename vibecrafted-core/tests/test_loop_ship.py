from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from vibecrafted_core import loop, ship


def test_loop_start_next_complete_round_trip(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state_file = tmp_path / "operator-loop.local.md"
    monkeypatch.chdir(tmp_path)

    assert (
        loop.main(
            [
                "start",
                "--state-file",
                str(state_file),
                "--prompt",
                "keep going",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "2",
            ]
        )
        == 0
    )
    assert state_file.is_file()
    assert "active: true" in state_file.read_text(encoding="utf-8")

    assert loop.main(["next", "--state-file", str(state_file)]) == 0
    out = capsys.readouterr().out
    assert "CONTINUE: operator loop iteration 2" in out
    assert "keep going" in out

    assert loop.main(["next", "--state-file", str(state_file)]) == 0
    assert "STOP: max iterations reached (2)" in capsys.readouterr().out


def test_ship_loop_only_creates_vc_ship_contract(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    input_file = tmp_path / "plan.md"
    state_file = tmp_path / "state.md"
    input_file.write_text("dispatch this", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECRAFTED_LOOP_STATE_FILE", str(state_file))

    assert (
        ship.main(
            [
                "codex",
                "--checkpoint",
                "workflow",
                "--file",
                str(input_file),
                "--loop-only",
            ]
        )
        == 0
    )

    assert "operator loop activated" in capsys.readouterr().out
    content = state_file.read_text(encoding="utf-8")
    assert "VC-SHIP interactive supervisor loop." in content
    assert "checkpoint: workflow" in content
    assert "dispatch this" in content


def test_spanko_awaits_verifies_flips_tracker_and_runs_then(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    report = tmp_path / "worker-report.md"
    report.write_text(
        "# Worker Report\ncommit: abc1234\ngates: pytest green",
        encoding="utf-8",
    )
    tracker = tmp_path / "tracker.md"
    tracker.write_text(
        "| Cut | Wave | Agent | Brief | State | Evidence |\n"
        "| C7 | 1 | codex | brief.md | [~] | run_id=impl-1 |\n",
        encoding="utf-8",
    )
    then_marker = tmp_path / "then.json"
    heartbeat_calls: list[Path] = []
    await_calls: list[tuple[str, float, float]] = []

    def fake_heartbeat(*, root: Path, run_id: str, then_cmd: str = "") -> int:
        heartbeat_calls.append(root)
        return 0

    def fake_await_run(
        run_id: str, *, timeout_seconds: float, interval_seconds: float
    ) -> dict[str, object]:
        await_calls.append((run_id, timeout_seconds, interval_seconds))
        return {
            "run_id": run_id,
            "completed": True,
            "timed_out": False,
            "run": {
                "run_id": run_id,
                "state": "report_validated",
                "artifact_ok": True,
                "artifact_errors": [],
                "latest_report": str(report),
                "commit": "abc1234",
            },
        }

    monkeypatch.setattr(loop, "_framework_heartbeat", fake_heartbeat)
    monkeypatch.setattr(loop.control_plane, "await_run", fake_await_run)

    rc = loop.main(
        [
            "spanko",
            "--run-id",
            "impl-1",
            "--agent",
            "codex",
            "--root",
            str(root),
            "--verify",
            subprocess.list2cmdline(["python3", "-c", 'print("verified")']),
            "--tracker",
            str(tracker),
            "--cut-id",
            "C7",
            "--then",
            subprocess.list2cmdline(
                [
                    "python3",
                    "-c",
                    (
                        "import json, os, pathlib; "
                        f"pathlib.Path({str(then_marker)!r}).write_text("
                        "json.dumps({'baton': os.environ['VIBECRAFTED_BATON']}),"
                        "encoding='utf-8')"
                    ),
                ]
            ),
            "--timeout-seconds",
            "0",
            "--interval-seconds",
            "0.1",
        ]
    )

    assert rc == 0
    assert await_calls == [("impl-1", 0.0, 0.1)]
    assert heartbeat_calls == [root]
    tracker_text = tracker.read_text(encoding="utf-8")
    assert "| C7 |" in tracker_text
    assert "[x]" in tracker_text
    assert "abc1234" in tracker_text
    baton = json.loads(then_marker.read_text(encoding="utf-8"))["baton"]
    assert "impl-1" in baton
    assert "abc1234" in baton
    out = capsys.readouterr().out
    assert "harness /loop" not in out


def test_spanko_does_not_flip_tracker_when_verify_fails(
    tmp_path: Path, monkeypatch
) -> None:
    tracker = tmp_path / "tracker.md"
    tracker.write_text("| Cut | State | Evidence |\n| C8 | [~] | run_id=impl-2 |\n")

    monkeypatch.setattr(loop, "_framework_heartbeat", lambda **_: 0)
    monkeypatch.setattr(
        loop.control_plane,
        "await_run",
        lambda *_, **__: {
            "completed": True,
            "timed_out": False,
            "run": {
                "run_id": "impl-2",
                "state": "report_validated",
                "artifact_ok": True,
                "artifact_errors": [],
            },
        },
    )

    rc = loop.main(
        [
            "spanko",
            "--run-id",
            "impl-2",
            "--verify",
            "python3 -c 'raise SystemExit(7)'",
            "--tracker",
            str(tracker),
            "--cut-id",
            "C8",
            "--timeout-seconds",
            "0",
        ]
    )

    assert rc == 7
    assert "[~]" in tracker.read_text(encoding="utf-8")


def test_spanko_resolves_runtime_run_when_await_projection_misses(
    tmp_path: Path, monkeypatch
) -> None:
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.md"
    tracker = tmp_path / "tracker.md"
    report.write_text("commit: runtime123\ngates: green\n", encoding="utf-8")
    meta.write_text(
        json.dumps(
            {
                "run_id": "impl-runtime",
                "state": "report_validated",
                "status": "completed",
                "agent": "codex",
                "root": str(tmp_path),
                "report": str(report),
                "latest_report": str(report),
                "exit_code": "0",
                "liveness": "terminal",
                "artifact_ok": True,
                "artifact_errors": [],
                "commit": "runtime123",
            }
        ),
        encoding="utf-8",
    )
    tracker.write_text(
        "| Cut | State | Evidence |\n| C10 | [~] | run_id=impl-runtime |\n"
    )

    monkeypatch.setattr(loop, "_framework_heartbeat", lambda **_: 0)
    monkeypatch.setattr(
        loop.control_plane,
        "await_run",
        lambda *_, **__: {"completed": False, "timed_out": True, "run": None},
    )
    monkeypatch.setattr(
        loop.control_plane,
        "resolve_run",
        lambda run_id: SimpleNamespace(run_id=run_id, meta=meta, report=report),
    )

    rc = loop.main(
        [
            "spanko",
            "--run-id",
            "impl-runtime",
            "--verify",
            "python3 -c 'print(1)'",
            "--tracker",
            str(tracker),
            "--cut-id",
            "C10",
            "--timeout-seconds",
            "0",
        ]
    )

    assert rc == 0
    text = tracker.read_text(encoding="utf-8")
    assert "[x]" in text
    assert "runtime123" in text


def test_spanko_stall_routes_stop_through_identity_authority_and_runs_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    tracker = tmp_path / "tracker.md"
    tracker.write_text("| Cut | State | Evidence |\n| C9 | [~] | run_id=impl-3 |\n")
    stopped: list[str] = []
    recoveries: list[str] = []

    monkeypatch.setattr(loop, "_framework_heartbeat", lambda **_: 0)
    monkeypatch.setattr(
        loop.control_plane,
        "await_run",
        lambda *_, **__: {
            "completed": False,
            "timed_out": True,
            "run": {
                "run_id": "impl-3",
                "state": "stalled",
                "launcher_pid": 4242,
                "operator_state": "stalled",
                "artifact_ok": False,
                "artifact_errors": ["stalled"],
            },
        },
    )
    def fake_stop(run_id: str) -> dict[str, object]:
        stopped.append(run_id)
        return {
            "accepted": False,
            "reason": "identity_unproven",
            "error": "identity_unproven:environment_birth_mismatch",
        }

    monkeypatch.setattr(loop, "_stop_stalled_run", fake_stop)

    def fake_run(cmd, **kwargs):
        recoveries.append(" ".join(cmd) if isinstance(cmd, list) else str(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(loop.subprocess, "run", fake_run)

    rc = loop.main(
        [
            "spanko",
            "--run-id",
            "impl-3",
            "--tracker",
            str(tracker),
            "--cut-id",
            "C9",
            "--then",
            "vibecrafted implement codex --file recovery.md",
            "--timeout-seconds",
            "0",
        ]
    )

    assert rc == 4
    assert stopped == ["impl-3"]
    assert recoveries == ["vibecrafted implement codex --file recovery.md"]
    text = tracker.read_text(encoding="utf-8")
    assert "[!]" in text
    assert "stall" in text
    assert "stop=refused:identity_unproven:environment_birth_mismatch" in text

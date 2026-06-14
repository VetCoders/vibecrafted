from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vibecrafted_core import cli


def _accepted_launch_payload() -> dict[str, object]:
    return {
        "accepted": True,
        "message": "Launched implement via Vibecrafted core runtime.",
        "run_id": "impl-260613-145127-33000",
        "agent": "codex",
        "skill": "implement",
        "root": "/repo",
        "dispatch": 0,
        "status": "launching",
        "control": "/home/.vibecrafted/control_plane/runs/impl-260613.json",
        "report": "/home/.vibecrafted/artifacts/report.md",
        "transcript": "/home/.vibecrafted/artifacts/report.transcript.log",
    }


def test_root_cli_vc_help_alias_returns_help_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["vc-help"])

    assert cli.main() == 0

    assert "Vibecrafted core command surface" in capsys.readouterr().out


def test_root_cli_accepts_justdo_alias(monkeypatch, capsys) -> None:
    seen = {}

    def fake_launch(spec, source_dir):
        seen["skill"] = spec.skill
        seen["agent"] = spec.agent
        seen["source_dir"] = source_dir
        return _accepted_launch_payload()

    monkeypatch.setattr(cli, "launch_workflow", fake_launch)

    assert cli.main(["justdo", "codex", "--prompt", "ship it"]) == 0

    assert seen["skill"] == "implement"
    assert seen["agent"] == "codex"
    assert "VIBECRAFTED LAUNCH RECEIPT" in capsys.readouterr().out


def test_root_cli_uses_terminal_runtime_when_operator_session_exists(
    monkeypatch, capsys
) -> None:
    seen = {}
    monkeypatch.setenv("VIBECRAFTED_OPERATOR_SESSION", "vc-frame")

    def fake_launch(spec, _source_dir):
        seen["runtime"] = spec.runtime
        return _accepted_launch_payload()

    monkeypatch.setattr(cli, "launch_workflow", fake_launch)

    assert cli.main(["implement", "codex", "--prompt", "ship it"]) == 0

    assert seen["runtime"] == "terminal"
    assert "VIBECRAFTED LAUNCH RECEIPT" in capsys.readouterr().out


def test_root_cli_prints_full_launch_receipt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "launch_workflow", lambda _spec, _source: _accepted_launch_payload()
    )

    assert cli.main(["implement", "codex", "--prompt", "ship it"]) == 0

    out = capsys.readouterr().out
    assert "==================== VIBECRAFTED LAUNCH RECEIPT ====================" in out
    assert "run_id:     impl-260613-145127-33000" in out
    assert "agent:      codex" in out
    assert "skill:      implement" in out
    assert "root:       /repo" in out
    assert "dispatch:   0" in out
    assert "status:     launching" in out
    assert "control:    /home/.vibecrafted/control_plane/runs/impl-260613.json" in out
    assert "report:     /home/.vibecrafted/artifacts/report.md" in out
    assert "transcript: /home/.vibecrafted/artifacts/report.transcript.log" in out
    assert (
        "observe:    vibecrafted codex observe --run-id impl-260613-145127-33000" in out
    )
    assert (
        "await:      vibecrafted codex await --run-id impl-260613-145127-33000" in out
    )


def test_root_cli_agent_observe_accepts_receipt_command(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "process_spawned",
            "agent": "codex",
            "skill": "implement",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": "/tmp/transcript.log",
        },
    )

    assert cli.main(["codex", "observe", "--run-id", "impl-1"]) == 0

    out = capsys.readouterr().out
    assert "run_id:     impl-1" in out
    assert "report:     /tmp/report.md" in out


def test_root_cli_swarm_observe_accepts_research_receipt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "process_spawned",
            "agent": "swarm",
            "skill": "research",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": "/tmp/transcript.log",
        },
    )

    assert cli.main(["swarm", "observe", "--run-id", "rese-1"]) == 0

    assert "agent:      swarm" in capsys.readouterr().out


def test_root_cli_agent_observe_prints_transcript_tail(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    transcript = tmp_path / "transcript.log"
    transcript.write_text(
        "\n".join(f"line {idx}" for idx in range(1, 66)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "stalled",
            "agent": "codex",
            "skill": "implement",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": str(transcript),
        },
    )

    assert cli.main(["codex", "observe", "--run-id", "impl-1"]) == 0

    out = capsys.readouterr().out
    assert "state:      stalled" in out
    assert "transcript_tail:" in out
    assert "line 65" in out
    assert "line 1" not in out


def test_root_cli_agent_observe_renders_json_transcript_tail(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    transcript = tmp_path / "transcript.log"
    transcript.write_text(
        "\n".join(
            [
                '{"type":"system","subtype":"hook_response","session_id":"claude-sess","output":"very noisy hook payload"}',
                '{"type":"system","subtype":"init","session_id":"claude-sess","model":"claude-opus-4-8"}',
                '{"type":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}',
                '{"type":"result","result":"done","usage":{"input_tokens":10,"cache_read_input_tokens":4,"output_tokens":2},"total_cost_usd":0.01}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "report_validated",
            "agent": "claude",
            "skill": "implement",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": str(transcript),
        },
    )

    assert cli.main(["claude", "observe", "--run-id", "impl-1"]) == 0

    out = capsys.readouterr().out
    assert "transcript_tail:" in out
    assert "session: claude-sess" in out
    assert "model: claude-opus-4-8" in out
    assert "ok" in out
    assert "hook_response" not in out
    assert "very noisy hook payload" not in out


def test_root_cli_agent_observe_recovers_model_when_tail_starts_after_init(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    transcript = tmp_path / "transcript.log"
    transcript.write_text(
        "\n".join(
            [
                '{"type":"system","subtype":"hook_response","session_id":"claude-sess","output":"noise"}',
                '{"type":"assistant","session_id":"claude-sess","message":{"model":"claude-opus-4-8","content":[{"type":"text","text":"late body"}]}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "report_validated",
            "agent": "claude",
            "skill": "implement",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": str(transcript),
        },
    )

    assert cli.main(["claude", "observe", "--run-id", "impl-1"]) == 0

    out = capsys.readouterr().out
    assert "session: claude-sess model: claude-opus-4-8" in out
    assert "late body" in out
    assert "noise" not in out


def test_root_cli_agent_observe_uses_codex_config_model(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.5"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    transcript = tmp_path / "transcript.log"
    transcript.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"codex-thread"}',
                '{"type":"item.completed","item":{"type":"agent_message","text":"codex body"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "report_validated",
            "agent": "codex",
            "skill": "implement",
            "root": "/repo",
            "latest_report": "/tmp/report.md",
            "latest_transcript": str(transcript),
        },
    )

    assert cli.main(["codex", "observe", "--run-id", "impl-1"]) == 0

    out = capsys.readouterr().out
    assert "session: codex-thread model: gpt-5.5" in out
    assert "codex body" in out


def test_root_cli_agent_await_accepts_receipt_command(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(
        cli,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "agent": "codex",
            "state": "report_validated",
            "skill": "implement",
            "root": "/repo",
            "artifact_ok": True,
            "latest_report": "/tmp/report.md",
            "latest_transcript": "/tmp/transcript.log",
        },
    )

    assert cli.main(["codex", "await", "--run-id", "impl-1", "--timeout", "0"]) == 0

    out = capsys.readouterr().out
    assert "await: initial status" in out
    assert "await: completed" in out
    assert "state:      report_validated" in out


def test_root_cli_agent_await_fails_dead_stale_worker(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    transcript = tmp_path / "transcript.log"
    transcript.write_text("last useful line\n", encoding="utf-8")
    run = {
        "run_id": "impl-1",
        "agent": "codex",
        "state": "stalled",
        "liveness": "pid_gone",
        "skill": "implement",
        "root": "/repo",
        "updated_at": "2000-01-01T00:00:00+00:00",
        "latest_report": "/tmp/report.md",
        "latest_transcript": str(transcript),
    }
    monkeypatch.setattr(
        cli, "sync_state", lambda: {"active_runs": [], "recent_runs": []}
    )
    monkeypatch.setattr(cli, "lookup_run", lambda _run_id: run)

    rc = cli.main(
        [
            "codex",
            "await",
            "--run-id",
            "impl-1",
            "--timeout",
            "30",
            "--stale-after",
            "600",
        ]
    )

    assert rc == 1
    captured = capsys.readouterr()
    assert "await: worker dead or stale" in captured.out
    assert "state:      stalled" in captured.out
    assert "last useful line" in captured.out


def test_root_cli_doctor_routes_to_installer_doctor(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.doctor_module,
        "doctor_run",
        lambda: [SimpleNamespace(level="ok", component="runtime", message="ready")],
    )

    assert cli.main(["doctor", "--json"]) == 0

    out = capsys.readouterr().out
    assert '"component": "runtime"' in out
    assert '"failures": 0' in out


def test_root_cli_doctor_returns_failure_for_failed_findings(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.doctor_module,
        "doctor_run",
        lambda: [SimpleNamespace(level="fail", component="runtime", message="broken")],
    )

    assert cli.main(["doctor"]) == 1

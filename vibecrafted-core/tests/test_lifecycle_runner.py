from __future__ import annotations

import asyncio
from pathlib import Path

from vibecrafted_core import ship
from vibecrafted_core.lifecycle_runner import (
    LifecycleRunSpec,
    LifecycleRunner,
)


def test_lifecycle_runner_triggers_audit_after_marbles(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    calls: list[str] = []

    def fake_launcher(spec, _source_dir):
        calls.append(spec.skill)
        report = tmp_path / f"{spec.skill}.md"
        report.write_text(f"{spec.skill} ok\n", encoding="utf-8")
        return {
            "accepted": True,
            "run_id": f"{spec.skill}-run",
            "report": str(report),
            "transcript": str(tmp_path / f"{spec.skill}.log"),
            "meta": str(tmp_path / f"{spec.skill}.json"),
        }

    def fake_awaiter(payload):
        return {
            "completed": True,
            "artifact_ok": True,
            "report": payload["report"],
        }

    runner = LifecycleRunner(launcher=fake_launcher, awaiter=fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-marbles",
                agent="codex",
                prompt="close the gaps",
                root=str(tmp_path),
                await_stages=True,
            )
        )
    )

    assert calls == ["marbles", "audit"]
    assert state["status"] == "completed"
    assert [stage["phase"] for stage in state["stages"]] == ["write", "read"]
    assert Path(state["state_path"]).is_file()
    assert (
        Path(state["report_path"])
        .read_text(encoding="utf-8")
        .startswith("# Lifecycle run")
    )
    assert (
        len(Path(state["transcript_path"]).read_text(encoding="utf-8").splitlines())
        == 2
    )


def test_lifecycle_runner_records_first_stage_without_await(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )

    def fake_launcher(spec, _source_dir):
        return {
            "accepted": True,
            "run_id": "dou-run",
            "skill": spec.skill,
            "report": str(tmp_path / "dou.md"),
        }

    runner = LifecycleRunner(launcher=fake_launcher)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-dou",
                agent="codex",
                prompt="audit readiness",
                root=str(tmp_path),
            )
        )
    )

    assert state["status"] == "launching"
    assert state["next_stage"] == ""
    assert state["stages"][0]["workflow"] == "dou"
    assert state["stages"][0]["can_modify_code"] is False


def test_vc_ship_routes_to_lifecycle_runner(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    captured: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec):
        captured.append(spec)
        return {
            "run_id": "life-ship-test",
            "workflow": spec.workflow_id,
            "status": "launching",
            "state_path": str(tmp_path / "state.json"),
            "report_path": str(tmp_path / "report.md"),
        }

    monkeypatch.setattr(ship, "run_lifecycle", fake_run_lifecycle)
    rc = ship.main(["codex", "--prompt", "ship it"])

    assert rc == 0
    assert captured[0].workflow_id == "vc-ship"
    assert captured[0].start_stage == "scaffold"
    assert "VC-SHIP LIFECYCLE RECEIPT" in capsys.readouterr().out

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from vibecrafted_core import ship, wrappers
from vibecrafted_core.lifecycle_runner import (
    LifecycleRunSpec,
    LifecycleRunner,
    LifecycleSupervisor,
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
    loop_options: list[tuple[int | None, int | None]] = []

    def fake_launcher(spec, _source_dir):
        calls.append(spec.skill)
        if spec.skill == "marbles":
            loop_options.append((spec.count, spec.depth))
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
                count=2,
                depth=4,
            )
        )
    )

    assert calls == ["marbles", "audit"]
    assert loop_options == [(2, 4)]
    assert state["status"] == "completed"
    assert (
        state["supervisor"] == "vibecrafted_core.lifecycle_runner.LifecycleSupervisor"
    )
    assert state["human_controls"] == ["interrupt_workflow", "force_audit"]
    assert state["baton"]["from_stage"] == "audit"
    assert state["baton"]["next_stage"] == ""
    assert [stage["phase"] for stage in state["stages"]] == ["write", "read"]
    assert "changed_files_reported" in state["stages"][0]["transition_conditions"]
    assert "code" in state["stages"][0]["allowed_artifacts"]
    assert "no_code_mutation" in state["stages"][1]["transition_conditions"]
    assert Path(state["state_path"]).is_file()
    report = Path(state["report_path"]).read_text(encoding="utf-8")
    assert report.startswith("# Lifecycle run")
    assert "## Baton" in report
    assert "transition_conditions:" in report
    assert (
        len(Path(state["transcript_path"]).read_text(encoding="utf-8").splitlines())
        == 2
    )


def test_lifecycle_runner_honours_worker_requested_next_stage(
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
        report = tmp_path / f"{spec.skill}-{len(calls)}.md"
        report.write_text(f"{spec.skill} ok\n", encoding="utf-8")
        return {
            "accepted": True,
            "run_id": f"{spec.skill}-run-{len(calls)}",
            "report": str(report),
            "transcript": str(tmp_path / f"{spec.skill}.log"),
            "meta": str(tmp_path / f"{spec.skill}.json"),
        }

    steering = iter(["marbles"])

    def fake_awaiter(payload):
        result = {
            "completed": True,
            "artifact_ok": True,
            "report": payload["report"],
        }
        if payload["run_id"].startswith("audit"):
            result["next_stage"] = next(steering, "")
        return result

    runner = LifecycleRunner(launcher=fake_launcher, awaiter=fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-marbles",
                agent="codex",
                prompt="steer back once",
                root=str(tmp_path),
                await_stages=True,
            )
        )
    )

    assert calls == ["marbles", "audit", "marbles", "audit"]
    assert state["status"] == "completed"
    steered = state["stages"][1]["transition"]
    assert steered["requested_next_stage"] == "marbles"
    assert steered["next_stage"] == "marbles"
    assert state["stages"][3]["transition"]["next_stage"] == ""


def test_lifecycle_runner_stage_cap_stops_runaway_steering(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setenv("VIBECRAFTED_LIFECYCLE_MAX_STAGES", "5")
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    calls: list[str] = []

    def fake_launcher(spec, _source_dir):
        calls.append(spec.skill)
        report = tmp_path / f"{spec.skill}-{len(calls)}.md"
        report.write_text(f"{spec.skill} ok\n", encoding="utf-8")
        return {
            "accepted": True,
            "run_id": f"{spec.skill}-run-{len(calls)}",
            "report": str(report),
            "transcript": str(tmp_path / f"{spec.skill}.log"),
            "meta": str(tmp_path / f"{spec.skill}.json"),
        }

    def fake_awaiter(payload):
        return {
            "completed": True,
            "artifact_ok": True,
            "report": payload["report"],
            "next_stage": "marbles",
        }

    runner = LifecycleRunner(launcher=fake_launcher, awaiter=fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-marbles",
                agent="codex",
                prompt="steer forever",
                root=str(tmp_path),
                await_stages=True,
            )
        )
    )

    assert state["status"] == "failed"
    assert "stage cap reached" in state["error"]
    assert len(state["stages"]) == 5
    assert len(calls) == 5


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
    assert state["baton"]["reason"] == "stage_launched_without_await"
    assert state["stages"][0]["workflow"] == "dou"
    assert state["stages"][0]["can_modify_code"] is False


def test_lifecycle_runner_injects_context_atlas_into_stage_prompt(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {
            "ok": True,
            "command": ["loct", "context"],
            "stdout": "Context Atlas says: runtime owner is lifecycle_runner.py",
        },
    )
    prompts: list[str] = []

    def fake_launcher(spec, _source_dir):
        prompts.append(spec.prompt)
        return {
            "accepted": True,
            "run_id": "dou-run",
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

    assert state["context_atlas"]["ok"] is True
    assert "Context Atlas says: runtime owner" in prompts[0]
    assert (
        "Transition conditions: launch_accepted, stage_completed, no_code_mutation"
        in prompts[0]
    )
    assert "Allowed artifacts: reports, cache, run_state, transcripts" in prompts[0]
    assert "Human controls: accept_dou, force_audit, interrupt_workflow" in prompts[0]


def test_read_stage_detects_mutation_to_preexisting_dirty_file(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=VC Test",
            "-c",
            "user.email=vc@example.test",
            "commit",
            "-m",
            "initial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    tracked.write_text("base\ndirty before read\n", encoding="utf-8")

    def fake_launcher(_spec, _source_dir):
        with tracked.open("a", encoding="utf-8") as handle:
            handle.write("mutated by read stage\n")
        return {
            "accepted": True,
            "run_id": "dou-run",
            "report": str(tmp_path / "dou.md"),
        }

    def fake_awaiter(payload):
        return {"completed": True, "artifact_ok": True, "report": payload["report"]}

    runner = LifecycleRunner(launcher=fake_launcher, awaiter=fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-dou",
                agent="codex",
                prompt="audit readiness",
                root=str(tmp_path),
                await_stages=True,
            )
        )
    )

    assert state["status"] == "failed"
    assert state["stages"][0]["read_phase_violation"] is True
    assert state["stages"][0]["changed_files"] == ["tracked.txt"]


def test_lifecycle_runner_records_commits_created_during_stage(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=VC Test",
            "-c",
            "user.email=vc@example.test",
            "commit",
            "-m",
            "initial",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    def fake_launcher(_spec, _source_dir):
        tracked.write_text("base\nwrite stage commit\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=VC Test",
                "-c",
                "user.email=vc@example.test",
                "commit",
                "-m",
                "stage commit",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        return {
            "accepted": True,
            "run_id": "hydrate-run",
            "report": str(tmp_path / "hydrate.md"),
        }

    def fake_awaiter(payload):
        return {
            "completed": True,
            "artifact_ok": True,
            "exit_code": 0,
            "report": payload["report"],
        }

    runner = LifecycleRunner(launcher=fake_launcher, awaiter=fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id="vc-hydrate",
                agent="codex",
                prompt="preflight",
                root=str(tmp_path),
                await_stages=True,
            )
        )
    )

    stage = state["stages"][0]
    assert state["status"] == "completed"
    assert len(stage["new_commits"]) == 1
    assert stage["commit_before"] != stage["commit_after"]
    assert stage["changed_files"] == ["tracked.txt"]
    assert "exit_code: 0" in Path(state["report_path"]).read_text(encoding="utf-8")


def test_lifecycle_supervisor_reports_status(monkeypatch, tmp_path: Path) -> None:
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

    supervisor = LifecycleSupervisor(runner=LifecycleRunner(launcher=fake_launcher))
    state = asyncio.run(
        supervisor.start(
            LifecycleRunSpec(
                workflow_id="vc-dou",
                agent="codex",
                prompt="audit readiness",
                root=str(tmp_path),
            )
        )
    )

    loaded = supervisor.read_state(state["state_path"])
    status = supervisor.status(loaded)

    assert loaded["run_id"] == state["run_id"]
    assert status["workflow"] == "vc-dou"
    assert status["status"] == "launching"
    assert status["current_stage"] == "dou"
    assert status["next_stage"] == ""


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


def test_vc_ship_can_start_with_default_lifecycle_prompt(
    monkeypatch, tmp_path: Path
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

    assert ship.main(["codex"]) == 0
    assert captured[0].workflow_id == "vc-ship"
    assert captured[0].prompt
    assert "full Vibecrafted lifecycle" in captured[0].prompt


def test_vc_dou_wrapper_routes_to_lifecycle_runner(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    captured: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec):
        captured.append(spec)
        return {
            "run_id": "life-dou-test",
            "workflow": spec.workflow_id,
            "status": "launching",
            "state_path": str(tmp_path / "state.json"),
            "report_path": str(tmp_path / "report.md"),
        }

    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.run_lifecycle", fake_run_lifecycle
    )
    rc = wrappers.dou_main(["codex", "--prompt", "audit readiness"])

    assert rc == 0
    assert captured[0].workflow_id == "vc-dou"
    assert captured[0].agent == "codex"
    assert captured[0].prompt == "audit readiness"
    assert "VC-DOU LIFECYCLE RECEIPT" in capsys.readouterr().out


def test_vc_marbles_wrapper_uses_lifecycle_runner_with_loop_options(
    monkeypatch, tmp_path: Path
) -> None:
    captured: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec):
        captured.append(spec)
        return {
            "run_id": "life-marbles-test",
            "workflow": spec.workflow_id,
            "status": "launching",
            "state_path": str(tmp_path / "state.json"),
            "report_path": str(tmp_path / "report.md"),
        }

    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.run_lifecycle", fake_run_lifecycle
    )
    rc = wrappers.marbles_main(["codex", "--count", "5", "--depth", "7"])

    assert rc == 0
    assert captured[0].workflow_id == "vc-marbles"
    assert captured[0].count == 5
    assert captured[0].depth == 7


def test_lifecycle_console_scripts_are_packaged() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    for name in (
        "vc-audit",
        "vc-dou",
        "vc-hydrate",
        "vc-polarize",
        "vc-marbles",
        "vc-ship",
    ):
        assert f"{name} = " in pyproject

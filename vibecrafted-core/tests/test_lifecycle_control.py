from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vibecrafted_core import ship
from vibecrafted_core.lifecycle_control import lifecycle_control_main
from vibecrafted_core.lifecycle_runner import (
    LifecycleRunSpec,
    LifecycleRunner,
    lifecycle_main,
)
from tests.lifecycle_schema_assertions import (
    assert_lifecycle_state_matches_packaged_schema,
)


def _fake_launcher(tmp_path: Path):
    def launcher(spec, _source_dir):
        report = tmp_path / f"{spec.skill}.md"
        report.write_text(f"{spec.skill} ok\n", encoding="utf-8")
        return {
            "accepted": True,
            "run_id": f"{spec.skill}-run",
            "report": str(report),
            "transcript": str(tmp_path / f"{spec.skill}.log"),
            "meta": str(tmp_path / f"{spec.skill}.json"),
        }

    return launcher


def _fake_awaiter(payload):
    return {"completed": True, "artifact_ok": True, "report": payload["report"]}


def _make_lifecycle_run(
    tmp_path: Path,
    monkeypatch,
    *,
    workflow_id: str,
    await_stages: bool = False,
    prompt: str = "operator prompt",
) -> dict:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_runner.load_context_atlas",
        lambda *_args, **_kwargs: {"ok": True, "command": ["loct", "context"]},
    )
    runner = LifecycleRunner(launcher=_fake_launcher(tmp_path), awaiter=_fake_awaiter)
    state = asyncio.run(
        runner.run(
            LifecycleRunSpec(
                workflow_id=workflow_id,
                agent="codex",
                prompt=prompt,
                root=str(tmp_path),
                await_stages=await_stages,
            )
        )
    )
    assert_lifecycle_state_matches_packaged_schema(state)
    return state


def _reload_state(state: dict) -> dict:
    return json.loads(Path(state["state_path"]).read_text(encoding="utf-8"))


def _reload_contract_state(state: dict) -> dict:
    reloaded = _reload_state(state)
    assert_lifecycle_state_matches_packaged_schema(reloaded)
    return reloaded


def test_status_and_runs_surface_lifecycle_state(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-marbles")

    assert (
        lifecycle_control_main(
            ["status", state["run_id"], "--json"], workflow_id="vc-marbles"
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == state["run_id"]
    assert payload["workflow"] == "vc-marbles"
    assert payload["next_stage"] == "audit"
    assert payload["operator_actions"] == 0

    assert lifecycle_control_main(["runs", "--json"], workflow_id="vc-marbles") == 0
    listed = json.loads(capsys.readouterr().out)
    assert [entry["run_id"] for entry in listed] == [state["run_id"]]


def test_approve_launches_continuation_from_baton(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-ship")
    launched: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec) -> dict:
        launched.append(spec)
        return {"run_id": "life-cont-1", "status": "launching"}

    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_control.run_lifecycle", fake_run_lifecycle
    )

    assert (
        lifecycle_control_main(
            ["approve", state["run_id"], "--json"], workflow_id="vc-ship"
        )
        == 0
    )
    assert len(launched) == 1
    spec = launched[0]
    assert spec.workflow_id == "vc-ship"
    assert spec.start_stage == "implement"
    assert spec.agent == "codex"
    assert spec.prompt == "operator prompt"
    assert spec.parent_run_id == state["run_id"]
    # The baton cargo: the scaffold report rides into the implement continuation.
    assert spec.previous_reports == (str(tmp_path / "scaffold.md"),)

    reloaded = _reload_contract_state(state)
    actions = reloaded["operator_actions"]
    assert [action["action"] for action in actions] == ["approve_transition"]
    assert actions[0]["details"]["continuation_run_id"] == "life-cont-1"
    report = Path(state["report_path"]).read_text(encoding="utf-8")
    assert "## Operator actions" in report
    assert "approve_transition" in report
    transcript = Path(state["transcript_path"]).read_text(encoding="utf-8")
    assert any(
        json.loads(line).get("kind") == "operator_action"
        for line in transcript.splitlines()
    )


def test_approve_gates_on_missing_baton_report_until_forced(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-ship")
    launched: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec) -> dict:
        launched.append(spec)
        return {"run_id": "life-cont-forced", "status": "launching"}

    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_control.run_lifecycle", fake_run_lifecycle
    )
    # The worker has not finished writing: the baton path exists in state
    # but the file is gone (same truth as not-yet-written or truncated).
    scaffold_report = tmp_path / "scaffold.md"
    scaffold_report.unlink()

    assert (
        lifecycle_control_main(["approve", state["run_id"]], workflow_id="vc-ship") == 1
    )
    err = capsys.readouterr().err
    assert "baton cargo not ready" in err
    assert str(scaffold_report) in err
    assert "--force" in err
    assert launched == []

    # Empty file is equally not-ready.
    scaffold_report.write_text("", encoding="utf-8")
    assert (
        lifecycle_control_main(["approve", state["run_id"]], workflow_id="vc-ship") == 1
    )
    assert "baton cargo not ready" in capsys.readouterr().err

    # --force is the conscious override and must leave a trace.
    assert (
        lifecycle_control_main(
            ["approve", state["run_id"], "--force", "--json"], workflow_id="vc-ship"
        )
        == 0
    )
    assert len(launched) == 1
    reloaded = _reload_contract_state(state)
    details = reloaded["operator_actions"][0]["details"]
    assert details["forced_missing_reports"] == [str(scaffold_report)]


def test_approve_rejected_when_nothing_pending(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(
        tmp_path, monkeypatch, workflow_id="vc-implement", await_stages=True
    )
    assert state["baton"]["next_stage"] == ""

    assert (
        lifecycle_control_main(["approve", state["run_id"]], workflow_id="vc-implement")
        == 1
    )
    assert "nothing to approve" in capsys.readouterr().err


def test_interrupt_stops_stage_and_marks_state(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-marbles")
    stopped: list[str] = []

    def fake_stop_run(run_id: str, *, reason: str = "") -> dict:
        stopped.append(run_id)
        return {"accepted": True, "run_id": run_id, "reason": reason}

    monkeypatch.setattr("vibecrafted_core.workflow.stop_run", fake_stop_run)

    assert (
        lifecycle_control_main(
            ["interrupt", state["run_id"], "--json"], workflow_id="vc-marbles"
        )
        == 0
    )
    assert stopped == ["marbles-run"]
    reloaded = _reload_contract_state(state)
    assert reloaded["status"] == "interrupted"
    assert [action["action"] for action in reloaded["operator_actions"]] == [
        "interrupt_workflow"
    ]
    assert reloaded["operator_actions"][0]["details"]["stop_accepted"] is True


def test_control_verbs_validate_human_controls(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-hydrate")

    assert (
        lifecycle_control_main(
            ["force-audit", state["run_id"]], workflow_id="vc-hydrate"
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "force_audit" in err
    assert "human" in err

    assert (
        lifecycle_control_main(
            ["fallback", state["run_id"], "--stage", "hydrate"],
            workflow_id="vc-hydrate",
        )
        == 1
    )
    assert "choose_fallback_stage" in capsys.readouterr().err


def test_force_audit_steers_baton_when_manifest_has_audit_stage(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-ship")
    assert state["baton"]["next_stage"] == "implement"

    assert (
        lifecycle_control_main(
            ["force-audit", state["run_id"], "--json"], workflow_id="vc-ship"
        )
        == 0
    )
    reloaded = _reload_contract_state(state)
    assert reloaded["baton"]["next_stage"] == "audit"
    assert reloaded["baton"]["reason"] == "operator_forced_audit"
    details = reloaded["operator_actions"][0]["details"]
    assert details["mode"] == "steered_baton"
    assert details["displaced_next_stage"] == "implement"


def test_force_audit_dispatches_vc_audit_for_single_stage_manifest(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-implement")
    launched: list[LifecycleRunSpec] = []

    def fake_run_lifecycle(spec: LifecycleRunSpec) -> dict:
        launched.append(spec)
        return {"run_id": "life-audi-1", "status": "launching"}

    monkeypatch.setattr(
        "vibecrafted_core.lifecycle_control.run_lifecycle", fake_run_lifecycle
    )

    assert (
        lifecycle_control_main(
            ["force-audit", state["run_id"], "--json"], workflow_id="vc-implement"
        )
        == 0
    )
    assert len(launched) == 1
    assert launched[0].workflow_id == "vc-audit"
    assert launched[0].parent_run_id == state["run_id"]
    reloaded = _reload_contract_state(state)
    details = reloaded["operator_actions"][0]["details"]
    assert details["mode"] == "dispatched_vc_audit"
    assert details["continuation_run_id"] == "life-audi-1"


def test_fallback_validates_stage_and_steers_backwards(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-ship")

    assert (
        lifecycle_control_main(
            ["fallback", state["run_id"], "--stage", "bogus"], workflow_id="vc-ship"
        )
        == 1
    )
    assert "unknown stage 'bogus'" in capsys.readouterr().err

    assert (
        lifecycle_control_main(
            ["fallback", state["run_id"], "--stage", "polarize", "--json"],
            workflow_id="vc-ship",
        )
        == 0
    )
    reloaded = _reload_contract_state(state)
    assert reloaded["baton"]["next_stage"] == "polarize"
    assert reloaded["baton"]["reason"] == "operator_chose_fallback"


def test_accept_dou_records_finding(monkeypatch, tmp_path: Path, capsys) -> None:
    state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-dou")

    assert (
        lifecycle_control_main(
            [
                "accept-dou",
                state["run_id"],
                "--finding",
                "install path unverified — accepted for this release",
            ],
            workflow_id="vc-dou",
        )
        == 0
    )
    reloaded = _reload_state(state)
    assert reloaded["accepted_dou_findings"][0]["finding"].startswith(
        "install path unverified"
    )
    assert [action["action"] for action in reloaded["operator_actions"]] == [
        "accept_dou"
    ]
    report = Path(state["report_path"]).read_text(encoding="utf-8")
    assert "accept_dou" in report
    assert "- accepted_dou_findings: 1" in report

    # The accepted-gap counter pairs with the reported dou_index in status.
    capsys.readouterr()  # drop the accept-dou print before parsing status JSON
    assert (
        lifecycle_control_main(
            ["status", state["run_id"], "--json"], workflow_id="vc-dou"
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted_dou"] == 1
    assert payload["dou_index"] is None


def test_ship_and_wrapper_clis_route_control_verbs(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    dou_state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-dou")
    ship_state = _make_lifecycle_run(tmp_path, monkeypatch, workflow_id="vc-ship")

    assert ship.main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == ship_state["run_id"]
    assert payload["workflow"] == "vc-ship"

    assert lifecycle_main("vc-dou", ["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == dou_state["run_id"]
    assert payload["workflow"] == "vc-dou"

    assert lifecycle_main("vc-dou", ["runs", "--all", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert {entry["workflow"] for entry in listed} == {"vc-dou", "vc-ship"}

"""End-to-end regression coverage for the control-plane resume lane.

The incident being prevented (2026-07-17, run ``revi-260717-201752-39000``):
a vc-ship review worker died mid-stage (provider-side turn failure, exit 1,
``report_missing``) and the deck offered no way to continue the recorded agent
session under the same run identity. ``resume_run`` must:

- relaunch through the dispatcher with the SAME run id, meta, transcript, and
  canonical report path;
- continue the recorded agent session (``codex exec resume <session>``);
- record resume lineage in meta.json;
- heal a previously recorded lifecycle worker_exit failure on success so the
  lifecycle state and the report agree (observe/await read one truth).
"""

from __future__ import annotations

import json
import stat
import time
from pathlib import Path
from typing import Any

import pytest

from vibecrafted_core import workflow
from vibecrafted_core import control_plane


RUN_ID = "revi-000101-000000-00001"
SESSION_ID = "0d9f0000-dead-beef-a421-000000000001"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _seed_failed_run(home: Path, root: Path, report_path: Path) -> tuple[Path, Path]:
    run_dir = home / "control_plane" / "runtime_runs" / RUN_ID
    run_dir.mkdir(parents=True)
    meta_path = run_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "agent": "codex",
                "agent_session_id": SESSION_ID,
                "session_id": SESSION_ID,
                "status": "failed",
                "exit_code": 1,
                "root": str(root),
                "report": str(report_path),
                "transcript": str(run_dir / "transcript.log"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "transcript.log").write_text("first attempt died\n", encoding="utf-8")
    control_plane.append_event = getattr(control_plane, "append_event", None)
    # Project the failed run into the control plane the same way production
    # does: through the event stream.
    from vibecrafted_core.events import append_event

    append_event(
        kind="state",
        run_id=RUN_ID,
        message=f"{RUN_ID} entered failed",
        payload={
            "state": "failed",
            "agent": "codex",
            "skill": "review",
            "mode": "review",
            "root": str(root),
            "session_id": SESSION_ID,
            "exit_code": 1,
            "liveness": "terminal",
            "report": str(report_path),
            "transcript": str(run_dir / "transcript.log"),
        },
    )
    return run_dir, meta_path


def _seed_lifecycle_state(home: Path) -> Path:
    lifecycle_dir = home / "control_plane" / "lifecycle_runs" / "life-ship-test"
    lifecycle_dir.mkdir(parents=True)
    state_path = lifecycle_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "run_id": "life-ship-test",
                "status": "launching",
                "stage_worker_exit": {
                    "run_id": RUN_ID,
                    "stage": "review",
                    "state": "report_missing",
                    "exit_code": 1,
                    "artifact_ok": False,
                    "artifact_errors": ["report_missing"],
                },
                "stages": [
                    {
                        "id": "review",
                        "launch": {"run_id": RUN_ID},
                        "worker_exit": {
                            "state": "report_missing",
                            "exit_code": 1,
                            "artifact_ok": False,
                            "artifact_errors": ["report_missing"],
                        },
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return state_path


@pytest.fixture()
def resume_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    home = tmp_path / "vibecrafted-home"
    home.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    report_path = tmp_path / "artifacts" / "review" / "2026-07-17_codex_report.md"
    report_path.parent.mkdir(parents=True)

    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    # Force the headless transport: no vc-frame in the fake PATH.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "codex-argv.txt"
    _write_executable(
        fake_bin / "codex",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > ' + json.dumps(str(capture)),
                "cat > /dev/null",
                'printf "resumed report body\\n" > "$VIBECRAFTED_REPORT_PATH"',
                'printf "second attempt lives\\n"',
            ]
        )
        + "\n",
    )
    path_value = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    monkeypatch.setenv("PATH", path_value)
    monkeypatch.delenv("VIBECRAFTED_OPERATOR_SESSION", raising=False)
    monkeypatch.delenv("VC_FRAME_SESSION_NAME", raising=False)
    monkeypatch.delenv("ZELLIJ_SESSION_NAME", raising=False)

    run_dir, meta_path = _seed_failed_run(home, root, report_path)
    state_path = _seed_lifecycle_state(home)
    return {
        "home": home,
        "root": root,
        "report_path": report_path,
        "run_dir": run_dir,
        "meta_path": meta_path,
        "state_path": state_path,
        "capture": capture,
        "path": path_value,
    }


def _wait_for(predicate, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.25)
    return False


def test_resume_run_e2e_same_run_same_report_healed_lifecycle(
    resume_env: dict[str, Any],
) -> None:
    payload = workflow.resume_run(
        RUN_ID,
        resume_env["root"],
        prompt="Finish the review report.",
        runtime="headless",
        env={"PATH": resume_env["path"]},
    )

    assert payload["accepted"] is True, payload
    assert payload["run_id"] == RUN_ID
    assert payload["agent"] == "codex"
    assert payload["session_id"] == SESSION_ID
    assert payload["report"] == str(resume_env["report_path"])
    assert payload["transport"] == "headless"

    # The dispatcher runs detached; wait for the worker to finish and the
    # supervisor to close the run.
    assert _wait_for(resume_env["capture"].exists), "worker was never spawned"
    assert _wait_for(resume_env["report_path"].exists), "report never landed"

    argv = resume_env["capture"].read_text(encoding="utf-8").split()
    assert "resume" in argv and SESSION_ID in argv, argv
    assert argv[argv.index("resume") + 1] == SESSION_ID

    # Report is at the ORIGINAL canonical path — not a fresh retry path.
    assert (
        resume_env["report_path"].read_text(encoding="utf-8") == "resumed report body\n"
    )

    def _meta_terminal() -> bool:
        try:
            meta = json.loads(resume_env["meta_path"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return str(meta.get("status") or "") not in {"", "resuming", "running"}

    assert _wait_for(_meta_terminal), "meta.json never reached a terminal state"
    meta = json.loads(resume_env["meta_path"].read_text(encoding="utf-8"))
    history = meta.get("resume_history") or []
    assert history and history[0]["parent_session_id"] == SESSION_ID

    # Lifecycle worker_exit healed: the stale report_missing failure must have
    # been replaced by the successful exit of the resumed worker.
    def _lifecycle_healed() -> bool:
        try:
            state = json.loads(resume_env["state_path"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        stage = state["stages"][0]
        exit_record = stage.get("worker_exit") or {}
        return bool(exit_record.get("artifact_ok"))

    assert _wait_for(_lifecycle_healed), "lifecycle worker_exit was not healed"

    # observe/await truth: the control-plane projection of the SAME run id must
    # now be terminal-successful.
    def _projection_ok() -> bool:
        run = control_plane.lookup_run(RUN_ID)
        if not run:
            return False
        return bool(run.get("artifact_ok")) and str(run.get("state") or "") in {
            "completed",
            "report_validated",
            "closed",
        }

    assert _wait_for(_projection_ok), control_plane.lookup_run(RUN_ID)


def test_resume_run_rejects_missing_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "failed",
            "agent": "codex",
            "skill": "review",
            "root": str(tmp_path),
            "exit_code": 1,
        },
    )
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        workflow, "append_event", lambda **kwargs: events.append(kwargs)
    )

    payload = workflow.resume_run("revi-x", tmp_path)

    assert payload["accepted"] is False
    assert payload["reason"] == "no_agent_session"
    assert events and events[0]["kind"] == "audit:resume"


def test_resume_run_rejects_live_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {"run_id": run_id, "state": "running", "agent": "codex"},
    )
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        workflow, "append_event", lambda **kwargs: events.append(kwargs)
    )

    payload = workflow.resume_run("revi-live", tmp_path)

    assert payload["accepted"] is False
    assert payload["reason"] == "run_not_terminal"


def test_resume_run_fork_headless_codex_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    run_dir = home / "control_plane" / "runtime_runs" / "revi-f"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "revi-f",
                "agent": "codex",
                "agent_session_id": SESSION_ID,
                "status": "failed",
                "exit_code": 1,
                "root": str(tmp_path),
                "report": str(tmp_path / "r.md"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "failed",
            "agent": "codex",
            "skill": "review",
            "root": str(tmp_path),
            "exit_code": 1,
            "session_id": SESSION_ID,
        },
    )
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        workflow, "append_event", lambda **kwargs: events.append(kwargs)
    )

    payload = workflow.resume_run("revi-f", tmp_path, fork_session=True)

    assert payload["accepted"] is False
    assert payload["reason"] == "resume_unsupported"
    assert "fork" in str(payload.get("error", ""))

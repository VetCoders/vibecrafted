from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from vibecrafted_core import control_plane


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / "vibecrafted-core"
SCRIPT_DIR = CORE_ROOT / "vibecrafted_core" / "runtime" / "scripts"
SESSION_PLACEHOLDERS = {"", "pending", "none", "null", "unknown"}


def _child_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_CORE_PYTHONPATH"] = str(CORE_ROOT)
    env["PYTHONPATH"] = (
        str(CORE_ROOT)
        if not env.get("PYTHONPATH")
        else str(CORE_ROOT) + os.pathsep + env["PYTHONPATH"]
    )
    return env


def _snapshot_path(home: Path, run_id: str) -> Path:
    return home / "control_plane" / "runs" / f"{run_id}.json"


def _read_projection(home: Path, run_id: str) -> dict[str, Any] | None:
    control_plane.sync_state()
    path = _snapshot_path(home, run_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _wait_for_active_projection(
    home: Path,
    run_id: str,
    label: str,
    *,
    timeout: float = 1.5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last = _read_projection(home, run_id)
        if last:
            state = str(last.get("state", ""))
            session_id = str(last.get("session_id", ""))
            if state == "active" and session_id.lower() not in SESSION_PLACEHOLDERS:
                return last
        time.sleep(0.05)

    if last is None:
        raise AssertionError(
            f"{label} state drift: expected runs/{run_id}.json to reach "
            "state=active with non-empty session_id; no projection was written"
        )

    raise AssertionError(
        f"{label} state drift: expected runs/{run_id}.json to reach "
        "state=active with non-empty session_id; "
        f"last projection state={last.get('state')!r}, "
        f"liveness={last.get('liveness')!r}, "
        f"session_id={last.get('session_id')!r}, "
        f"operator_state={last.get('operator_state')!r}, "
        f"path={_snapshot_path(home, run_id)}"
    )


def _wait_process(proc: subprocess.Popen[str], *, timeout: float = 5.0) -> None:
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)


def _write_async_worker(tmp_path: Path, *, sleep_seconds: float = 2.0) -> Path:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "\n".join(
            [
                "import time",
                "print('dispatcher-active', flush=True)",
                f"time.sleep({sleep_seconds!r})",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return worker


def _append_lifecycle_event(home: Path, payload: dict[str, Any]) -> None:
    events = home / "control_plane" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": "2026-06-29T00:00:00+00:00",
        "run_id": payload["run_id"],
        "kind": f"lifecycle:{payload['state']}",
        "message": f"test {payload['state']}",
        "payload": payload,
    }
    with events.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def test_python_dispatcher_projection_reaches_active_with_session_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Async dispatcher is the control case: live events advance the projection."""

    home = tmp_path / "home"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "parity-async"
    worker = _write_async_worker(tmp_path)
    transcript = tmp_path / "dispatcher.transcript.log"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vibecrafted_core.dispatcher",
            "run",
            "--run-id",
            run_id,
            "--root",
            str(tmp_path),
            "--transcript",
            str(transcript),
            "--no-require-report",
            "--require-transcript-output",
            "--quiet",
            "--",
            sys.executable,
            str(worker),
        ],
        cwd=tmp_path,
        env=_child_env(home),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        projection = _wait_for_active_projection(home, run_id, "python-dispatcher path")
    finally:
        _wait_process(proc)

    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, (
        "dispatcher control path should finish cleanly; "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )
    assert projection["state"] == "active"
    assert projection["session_id"].lower() not in SESSION_PLACEHOLDERS


def test_shell_meta_projection_reaches_active_with_session_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Legacy shell path must match async liveness.

    This drives the shell-owned `spawn_write_meta` writer directly instead of
    launching a terminal or LLM. The RED bug is that the worker can be alive
    while `control_plane/runs/<id>.json` remains launching/pid_pending with no
    session identity because the shell path emits no live lifecycle events.
    """

    home = tmp_path / "home"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "parity-shell"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8")
    report = tmp_path / "reports" / f"{run_id}.md"
    transcript = tmp_path / "shell.transcript.log"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    meta = (
        home
        / "artifacts"
        / "VetCoders"
        / "vibecrafted"
        / "2026_0629"
        / "reports"
        / f"{run_id}.meta.json"
    )

    with transcript.open("w", encoding="utf-8") as transcript_fh:
        worker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import time; print('shell worker active', flush=True); time.sleep(2.0)",
            ],
            stdout=transcript_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )
        shell = "\n".join(
            [
                f"source {shlex.quote(str(SCRIPT_DIR / 'common.sh'))}",
                f"export SPAWN_RUN_ID={shlex.quote(run_id)}",
                "export SPAWN_PROMPT_ID=prompt-red",
                "export SPAWN_LOOP_NR=0",
                "export SPAWN_SKILL_CODE=impl",
                "spawn_write_meta "
                f"{shlex.quote(str(meta))} "
                "launching codex implement "
                f"{shlex.quote(str(tmp_path))} "
                f"{shlex.quote(str(prompt))} "
                f"{shlex.quote(str(report))} "
                f"{shlex.quote(str(transcript))} "
                f"{shlex.quote(str(tmp_path / 'legacy-launcher.sh'))} "
                "codex-cli-default",
            ]
        )
        try:
            subprocess.run(
                ["bash", "-lc", shell],
                cwd=REPO_ROOT,
                env=_child_env(home),
                check=True,
                capture_output=True,
                text=True,
            )
            _wait_for_active_projection(home, run_id, "shell/legacy path")
        finally:
            _wait_process(worker)


def test_active_projection_without_report_is_not_blocked_mid_delivery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_id = "active-report-pending"
    home = tmp_path / "home"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    transcript = tmp_path / "active.log"
    transcript.write_text("still working\n", encoding="utf-8")
    report = tmp_path / "active-report.md"

    _append_lifecycle_event(
        home,
        {
            "run_id": run_id,
            "state": "active",
            "agent": "codex",
            "skill": "implement",
            "mode": "terminal",
            "root": str(tmp_path),
            "report": str(report),
            "transcript": str(transcript),
            "session_id": "session-live",
            "identity_required": True,
            "liveness": "pid_alive",
        },
    )

    projection = _read_projection(home, run_id)
    assert projection is not None
    assert projection["state"] == "active"
    assert projection["operator_state"] == "running", (
        "active run drift: a healthy ACTIVE projection must not be blocked "
        "or report_missing before the run has reached a terminal state"
    )
    assert projection["artifact_gate"] == "pending"
    assert "report_missing" not in projection["artifact_errors"]


def test_report_validated_projection_clears_recovery_required(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_id = "validated-clears-recovery"
    home = tmp_path / "home"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    report = tmp_path / "validated.md"
    report.write_text("# Report\n\nok\n", encoding="utf-8")

    _append_lifecycle_event(
        home,
        {
            "run_id": run_id,
            "state": "report_validated",
            "agent": "codex",
            "skill": "implement",
            "mode": "terminal",
            "root": str(tmp_path),
            "report": str(report),
            "session_id": "session-done",
            "identity_required": True,
            "liveness": "terminal",
            "recovery_required": True,
        },
    )

    projection = _read_projection(home, run_id)
    assert projection is not None
    assert projection["state"] == "report_validated"
    assert projection["operator_state"] == "completed"
    assert projection["exit_code"] == 0, (
        "report_validated drift: validated terminal reports should project a "
        "successful exit_code instead of leaving exit_code=null"
    )
    assert projection.get("recovery_required") is not True
    assert projection["lifecycle"]["recovery_required"] is False, (
        "report_validated drift: validated terminal reports must clear stale "
        "recovery_required instead of projecting a recovery lane"
    )

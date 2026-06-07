from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AWAIT_SH = REPO_ROOT / "runtime" / "scripts" / "await.sh"
OBSERVE_SH = REPO_ROOT / "runtime" / "scripts" / "observe.sh"


def _write_meta(
    reports_dir: Path,
    *,
    run_id: str,
    status: str,
    exit_code: int | None,
    liveness: str,
    launcher_pid: int | None,
    transcript_text: str = "",
) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    meta = reports_dir / f"{run_id}_codex.meta.json"
    report = reports_dir / f"{run_id}_codex.md"
    transcript = reports_dir / f"{run_id}_codex.transcript.log"
    launcher = reports_dir.parent / "tmp" / f"vc-spawn-cmd-{run_id}.sh"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("---\nstatus: pending\n---\n", encoding="utf-8")
    transcript.write_text(transcript_text, encoding="utf-8")
    launcher.write_text("#!/usr/bin/env bash\nprintf recovered\\n\n", encoding="utf-8")
    launcher.chmod(0o755)
    payload = {
        "updated_at": "2026-05-19T01:00:00+00:00",
        "status": status,
        "agent": "codex",
        "mode": "implement",
        "model": "test-model",
        "input": str(reports_dir / "prompt.md"),
        "report": str(report),
        "transcript": str(transcript),
        "launcher": str(launcher),
        "run_id": run_id,
        "exit_code": exit_code,
        "launcher_pid": launcher_pid,
        "liveness": liveness,
    }
    meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "meta": meta,
        "report": report,
        "transcript": transcript,
        "launcher": launcher,
    }


def _run(
    script: Path, store_root: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_AWAIT_STORE_DIR"] = str(store_root)
    env["VIBECRAFTED_AWAIT_REPORTS_DIR"] = str(store_root / "reports")
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_await_exits_zero_for_completed_meta(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_meta(
        store_root / "reports",
        run_id="just-030101-00001",
        status="completed",
        exit_code=0,
        liveness="terminal",
        launcher_pid=None,
        transcript_text="done\n",
    )

    result = _run(AWAIT_SH, store_root, "--run-id", "just-030101-00001")

    assert result.returncode == 0, result.stderr
    assert "heartbeat run_id=just-030101-00001" in result.stdout
    assert f"report={paths['report']}" in result.stdout
    assert f"transcript={paths['transcript']}" in result.stdout
    assert "tracks:  1" in result.stdout


def test_await_exits_nonzero_for_failed_meta(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    _write_meta(
        store_root / "reports",
        run_id="just-030101-00002",
        status="failed",
        exit_code=1,
        liveness="terminal",
        launcher_pid=None,
        transcript_text="failed\n",
    )

    result = _run(AWAIT_SH, store_root, "--run-id", "just-030101-00002")

    assert result.returncode == 1
    assert "heartbeat run_id=just-030101-00002" in result.stdout


def test_await_heartbeat_for_running_pid_alive_meta(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    _write_meta(
        store_root / "reports",
        run_id="just-030101-00003",
        status="running",
        exit_code=None,
        liveness="pid_alive",
        launcher_pid=os.getpid(),
        transcript_text="worker started\n",
    )

    result = _run(
        AWAIT_SH,
        store_root,
        "--run-id",
        "just-030101-00003",
        "--interval",
        "1",
        "--timeout",
        "1",
    )

    assert result.returncode == 124
    assert "heartbeat run_id=just-030101-00003" in result.stdout
    assert "status=running" in result.stdout
    assert "liveness=pid_alive" in result.stdout


def test_await_detects_false_launched_pid_pending_meta(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_meta(
        store_root / "reports",
        run_id="just-030101-00004",
        status="launching",
        exit_code=None,
        liveness="pid_pending",
        launcher_pid=None,
    )
    stale_mtime = time.time() - 120
    os.utime(paths["meta"], (stale_mtime, stale_mtime))

    result = _run(
        AWAIT_SH,
        store_root,
        "--run-id",
        "just-030101-00004",
        "--startup-grace",
        "0",
    )

    assert result.returncode == 2
    assert "heartbeat run_id=just-030101-00004" in result.stdout
    assert "Detected false-launched run" in result.stderr
    assert f"Recovery: bash {paths['launcher']}" in result.stderr


def test_observe_resolves_run_id(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_meta(
        store_root / "reports",
        run_id="just-030101-00005",
        status="completed",
        exit_code=0,
        liveness="terminal",
        launcher_pid=None,
        transcript_text="observable\n",
    )

    result = _run(OBSERVE_SH, store_root, "codex", "--run-id", "just-030101-00005")

    assert result.returncode == 0, result.stderr
    assert "Run ID:     just-030101-00005" in result.stdout
    assert "Liveness:   terminal" in result.stdout
    assert f"Transcript: {paths['transcript']}" in result.stdout
    assert "--- report tail ---" in result.stdout

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


def _write_renamed_artifact_set(store_root: Path) -> dict[str, Path]:
    reports_dir = store_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    run_id = "inte-204103-26970"
    old_base = reports_dir / "20260609_204104_20260609_2041_perform_claude"
    old_report = old_base.with_suffix(".md")
    old_transcript = reports_dir / f"{old_base.name}.transcript.log"
    old_meta = reports_dir / f"{old_base.name}.meta.json"
    canonical_base = reports_dir / "2026-06-09_Loctree_aicx_c7ff-report"
    canonical_report = canonical_base.with_suffix(".md")
    canonical_transcript = reports_dir / f"{canonical_base.name}.transcript.log"
    canonical_meta = reports_dir / f"{canonical_base.name}.meta.json"

    old_report.write_text(
        f"---\nrun_id: {run_id}\nstatus: completed\n---\nold report\n",
        encoding="utf-8",
    )
    old_transcript.write_text(
        f"---\nrun_id: {run_id}\nstatus: transcript\n---\nold transcript\n",
        encoding="utf-8",
    )
    canonical_report.write_text("canonical report\n", encoding="utf-8")
    canonical_transcript.write_text("canonical transcript\n", encoding="utf-8")
    canonical_meta.write_text(
        json.dumps(
            {
                "updated_at": "2026-06-09T21:03:04+00:00",
                "completed_at": "2026-06-09T21:03:04+00:00",
                "status": "completed",
                "agent": "claude",
                "mode": "intents",
                "model": "claude-fable-5",
                "input": "prompt.md",
                "report": str(canonical_report),
                "transcript": str(canonical_transcript),
                "launcher": "launcher.sh",
                "run_id": run_id,
                "exit_code": 0,
                "launcher_pid": None,
                "liveness": "terminal",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert not old_meta.exists()
    return {
        "old_meta": old_meta,
        "old_report": old_report,
        "canonical_meta": canonical_meta,
        "canonical_report": canonical_report,
    }


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


def test_await_describe_keeps_spawn_identity_before_finalization(
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "store"
    launcher = store_root / "tmp" / "launcher.sh"
    announced_meta = store_root / "reports" / "plan.meta.json"
    report = store_root / "reports" / "plan.md"
    transcript = store_root / "reports" / "plan.transcript.log"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"meta='{announced_meta}'",
                f"report='{report}'",
                f"transcript='{transcript}'",
                "export SPAWN_RUN_ID='plan-260726-130833-74630'",
                "export SPAWN_AGENT='codex'",
                'meta="$(spawn_finalize_artifacts "$meta" "$report" "$transcript")"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _run(AWAIT_SH, store_root, "--describe", str(launcher))

    assert result.returncode == 0, result.stderr
    assert f"meta       {announced_meta}" in result.stdout
    assert "run_id     plan-260726-130833-74630" in result.stdout
    assert "agent      codex" in result.stdout
    assert "$(spawn_finalize_artifacts" not in result.stdout


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


def test_observe_filters_transient_rmcp_transport_noise(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_meta(
        store_root / "reports",
        run_id="just-030101-00006",
        status="running",
        exit_code=None,
        liveness="pid_alive",
        launcher_pid=os.getpid(),
        transcript_text=(
            "\x1b[33m[16:37:02] session: 019eb3e5-7d6a-7cd0-bc93-363824971556\x1b[0m\n"
            "2026-06-10T23:37:03.409403Z ERROR rmcp::transport::worker: "
            'worker quit with fatal: Unexpected content type: Some("text/plain; '
            "body: upstream connect error or disconnect/reset before headers. "
            'transport failure reason: delayed connect error: Connection refused")\n'
            "actual worker progress\n"
        ),
    )
    paths["report"].write_text("", encoding="utf-8")

    result = _run(OBSERVE_SH, store_root, "codex", "--run-id", "just-030101-00006")

    assert result.returncode == 0, result.stderr
    assert "--- transcript tail ---" in result.stdout
    assert "actual worker progress" in result.stdout
    assert "rmcp::transport::worker" not in result.stdout
    assert "session: 019eb3e5-7d6a-7cd0-bc93-363824971556" not in result.stdout


def test_await_resolves_renamed_legacy_meta_path(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_renamed_artifact_set(store_root)

    result = _run(AWAIT_SH, store_root, str(paths["old_meta"]))

    assert result.returncode == 0, result.stderr
    assert "heartbeat run_id=inte-204103-26970 status=completed" in result.stdout
    assert str(paths["canonical_meta"]) in result.stdout
    assert str(paths["canonical_report"]) in result.stdout


def test_observe_resolves_renamed_legacy_meta_path(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    paths = _write_renamed_artifact_set(store_root)

    result = _run(OBSERVE_SH, store_root, str(paths["old_meta"]))

    assert result.returncode == 0, result.stderr
    assert "Run ID:     inte-204103-26970" in result.stdout
    assert f"Report:     {paths['canonical_report']}" in result.stdout
    assert "FileNotFoundError" not in result.stderr

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "runtime" / "scripts" / "common.sh"
AWAIT_SH = REPO_ROOT / "runtime" / "scripts" / "await.sh"


def _bash(script: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["bash", "-c", script],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        raise


def _finalized_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    # Announced paths live in a canonical store layout (org/repo/YYYY_MMDD/
    # reports) so spawn_finalize_artifacts takes the artifact-contract rename
    # path — the exact path measured to betray watchers.
    reports = tmp_path / "vetcoders" / "vibecrafted" / "2026_0609" / "reports"
    reports.mkdir(parents=True)
    report = reports / "20260609_2200_some-plan_codex.md"
    transcript = reports / "20260609_2200_some-plan_codex.transcript.log"
    meta = reports / "20260609_2200_some-plan_codex.meta.json"

    report.write_text("# Report\n\nDone.\n", encoding="utf-8")
    transcript.write_text("session: cafe-1234-test\nwork done\n", encoding="utf-8")
    _bash(
        f'''
        set -euo pipefail
        export VIBECRAFTED_HOME="{tmp_path / ".vibecrafted"}"
        source "{COMMON_SH}"
        export SPAWN_RUN_ID=trth-test-001
        spawn_write_meta "{meta}" launching codex implement / plan.md "{report}" "{transcript}" l.sh
        spawn_finish_meta "{meta}" completed 0
        spawn_finalize_artifacts "{meta}" "{report}" "{transcript}"
        '''
    )
    return report, transcript, meta


def test_announced_paths_survive_artifact_rename(tmp_path: Path) -> None:
    # VC-vbcr-stabilize-032: the path announced at spawn must be the path the
    # report actually lands under. After the session-stem rename, the
    # announced names must keep resolving (compat symlinks, one truth).
    report, transcript, meta = _finalized_run(tmp_path)

    assert report.exists(), "announced report path is dead after finalize"
    assert report.read_text(encoding="utf-8").strip(), "announced report is empty"
    assert transcript.exists(), "announced transcript path is dead after finalize"
    assert meta.exists(), "announced meta path is dead after finalize"

    payload = json.loads(meta.read_text(encoding="utf-8"))
    final_report = Path(payload["report"])
    assert final_report.is_file()
    assert final_report.name.endswith("-report.md")
    assert report.resolve() == final_report.resolve()


def test_await_closes_on_announced_report_path(tmp_path: Path) -> None:
    # Plan verifier: an await keyed on the announced path must terminate on
    # its own instead of waiting forever for a renamed-away meta.
    report, _transcript, _meta = _finalized_run(tmp_path)

    result = subprocess.run(
        ["bash", str(AWAIT_SH), str(report), "--interval", "1", "--timeout", "20"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"await did not close cleanly: rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

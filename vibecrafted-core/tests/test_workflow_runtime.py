from __future__ import annotations

import os
from pathlib import Path

from vibecrafted_core import workflow_runtime


def _fake_agent(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\"\n"
        "printf 'fake worker ok\\n'\n"
        'printf "%s\\n" "---" "status: completed" "---" "report for $0" > "$VIBECRAFTED_REPORT_PATH"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _runtime_env(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex", "gemini"):
        _fake_agent(bin_dir, name)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    monkeypatch.setenv("VIBECRAFTED_RUN_ID", run_id)
    monkeypatch.setenv("VIBECRAFTED_REPORT_PATH", str(home / "parent.md"))
    monkeypatch.setenv("VIBECRAFTED_TRANSCRIPT_PATH", str(home / "parent.log"))
    monkeypatch.setenv("VIBECRAFTED_META_PATH", str(home / "parent.meta.json"))
    return home


def test_research_runtime_supervises_three_tracks(monkeypatch, tmp_path: Path) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "rsch-test")

    rc = workflow_runtime.main(
        ["research", "--root", str(tmp_path), "--prompt", "map it"]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "vc-research supervised run" in report
    assert "research-claude" in report
    assert "research-codex" in report
    assert "research-gemini" in report
    assert (home / "rsch-test-children" / "research-claude.md").is_file()
    assert (home / "rsch-test-children" / "research-codex.md").is_file()
    assert (home / "rsch-test-children" / "research-gemini.md").is_file()


def test_marbles_runtime_supervises_loops(monkeypatch, tmp_path: Path) -> None:
    home = _runtime_env(monkeypatch, tmp_path, "marb-test")

    rc = workflow_runtime.main(
        [
            "marbles",
            "--agent",
            "codex",
            "--root",
            str(tmp_path),
            "--prompt",
            "converge",
            "--count",
            "2",
            "--depth",
            "4",
        ]
    )

    assert rc == 0
    report = (home / "parent.md").read_text(encoding="utf-8")
    assert "vc-marbles supervised run" in report
    assert "marbles-L1" in report
    assert "marbles-L2" in report
    assert (home / "marb-test-children" / "marbles-L1.md").is_file()
    assert (home / "marb-test-children" / "marbles-L2.md").is_file()
    l2_transcript = (
        home / "marb-test-children" / "marbles-L2.transcript.log"
    ).read_text(encoding="utf-8")
    assert "intentionally blind to prior marbles runs" in l2_transcript
    assert "Previous loop report" not in l2_transcript
    assert "marbles-L1.md" not in l2_transcript

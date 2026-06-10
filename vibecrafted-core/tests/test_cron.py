from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vibecrafted_core import cron


def write_state(path: Path, *, updated_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "active: true",
                "iteration: 3",
                'session_id: "sess-loop"',
                f'updated_at: "{updated_at.isoformat().replace("+00:00", "Z")}"',
                "---",
                "",
                "keep moving",
            ]
        ),
        encoding="utf-8",
    )


def test_tick_runs_then_command_after_idle_window(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = root / ".vibecrafted" / "operator-loop.local.md"
    journal = tmp_path / "journal.jsonl"
    write_state(state, updated_at=datetime.now(timezone.utc) - timedelta(minutes=15))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "home"))

    rc = cron.main(
        [
            "tick",
            "--root",
            str(root),
            "--state-file",
            str(state),
            "--journal",
            str(journal),
            "--no-context",
            "--after-idle-minutes",
            "10",
            "--then-cmd",
            "python3 -c \"open('ran.txt','w').write('ok')\"",
        ]
    )

    assert rc == 0
    assert (root / "ran.txt").read_text(encoding="utf-8") == "ok"
    payload = json.loads(capsys.readouterr().out)
    assert payload["then"]["status"] == "ran"
    assert (
        json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])["active"]
        is True
    )


def test_tick_refuses_hard_stop_then_command(
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = root / ".vibecrafted" / "operator-loop.local.md"
    write_state(state, updated_at=datetime.now(timezone.utc) - timedelta(minutes=15))

    rc = cron.main(
        [
            "tick",
            "--root",
            str(root),
            "--state-file",
            str(state),
            "--journal",
            str(tmp_path / "journal.jsonl"),
            "--no-context",
            "--then-cmd",
            "git push origin main",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["then"]["status"] == "refused"
    assert "git push" in payload["then"]["reason"]


def test_cron_line_prints_real_vibecrafted_command(
    tmp_path: Path,
    capsys,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    rc = cron.main(
        [
            "line",
            "--root",
            str(root),
            "--every-minutes",
            "10",
            "--no-context",
            "--then-cmd",
            "vibecrafted loop next",
        ]
    )

    assert rc == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("*/10 * * * *")
    assert "vibecrafted cron tick" in line
    assert "--then-cmd 'vibecrafted loop next'" in line

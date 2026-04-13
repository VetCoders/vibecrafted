from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARBLES_CTL = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "marbles_ctl.sh"


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_marbles_delete_archives_run_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    session_dir = crafted_home / "marbles" / "marb-424242"
    state_file = session_dir / "state.json"

    home.mkdir()
    _write_state(
        state_file,
        {
            "run_id": "marb-424242",
            "status": "initialized",
            "agent": "codex",
            "root": "/tmp/worktree",
        },
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)

    subprocess.run(
        ["bash", str(MARBLES_CTL), "delete", "marb-424242"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    archived_dir = crafted_home / "marbles" / "deleted" / "marb-424242"
    archived_state = json.loads(
        (archived_dir / "state.json").read_text(encoding="utf-8")
    )

    assert not session_dir.exists()
    assert archived_dir.is_dir()
    assert archived_state["status"] == "deleted"
    assert archived_state["previous_status"] == "initialized"
    assert archived_state["archived_from"] == str(session_dir)
    assert "archived_at" in archived_state
    assert "deleted_at" in archived_state


def test_marbles_delete_refuses_live_session(tmp_path: Path) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    session_dir = crafted_home / "marbles" / "marb-live"
    state_file = session_dir / "state.json"

    home.mkdir()
    _write_state(
        state_file,
        {
            "run_id": "marb-live",
            "status": "running",
            "watcher_pid": os.getpid(),
            "agent": "codex",
            "root": "/tmp/worktree",
        },
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)

    result = subprocess.run(
        ["bash", str(MARBLES_CTL), "delete", "marb-live"],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    archived_dir = crafted_home / "marbles" / "deleted" / "marb-live"

    assert result.returncode != 0
    assert session_dir.is_dir()
    assert not archived_dir.exists()
    assert "appears live; stop it first" in result.stderr

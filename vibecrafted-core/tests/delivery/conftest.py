from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Return a real one-commit Git repository for delivery integration tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Delivery Tests"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "delivery@example.invalid"],
        check=True,
    )
    witness = repo / "witness.txt"
    witness.write_text("delivery witness\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "witness.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "initial witness"],
        check=True,
    )
    return repo


@pytest.fixture
def two_producers(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Return distinct executable producers for subject/oracle separation tests."""
    producers: list[dict[str, object]] = []
    for producer_id, output in (("subject.test", "subject"), ("oracle.test", "oracle")):
        script = tmp_path / f"{producer_id}.sh"
        script.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | 0o111)
        producers.append(
            {
                "producer_id": producer_id,
                "public_surface": str(script),
                "argv": [str(script)],
                "cwd": str(tmp_path),
                "expected_exit": 0,
                "output": str(tmp_path / f"{producer_id}.out"),
            }
        )
    assert os.access(str(producers[0]["public_surface"]), os.X_OK)
    assert os.access(str(producers[1]["public_surface"]), os.X_OK)
    return producers[0], producers[1]

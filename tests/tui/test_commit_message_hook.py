from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts/hooks/commit-msg"


def run_hook(tmp_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(textwrap.dedent(message).lstrip(), encoding="utf-8")
    return subprocess.run(
        ["bash", str(HOOK), str(msg_file)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_commit_msg_hook_accepts_agent_runtime_standard(tmp_path: Path) -> None:
    result = run_hook(
        tmp_path,
        """
        [codex/interactive] chore: Polish Makefile help output formatting

        Refactors the help target to use structured printf output.

        Authored-By: codex <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-06-05T12:52:47-06:00
        runtime: iterm2
        """,
    )

    assert result.returncode == 0, result.stderr


def test_commit_msg_hook_requires_runtime_trailers(tmp_path: Path) -> None:
    result = run_hook(
        tmp_path,
        """
        [codex/interactive] chore: Polish Makefile help output formatting

        Refactors the help target to use structured printf output.

        Authored-By: codex <agents@vetcoders.io>
        runtime: iterm2
        """,
    )

    assert result.returncode != 0
    assert "session_id:" in result.stderr
    assert "time:" in result.stderr


def test_commit_msg_hook_rejects_vendor_footers(tmp_path: Path) -> None:
    result = run_hook(
        tmp_path,
        """
        [codex/interactive] chore: Polish Makefile help output formatting

        Refactors the help target to use structured printf output.

        Authored-By: codex <agents@vetcoders.io>
        Co-Authored-By: Claude <noreply@anthropic.com>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-06-05T12:52:47-06:00
        runtime: iterm2
        """,
    )

    assert result.returncode != 0
    assert "vendor footers" in result.stderr


def test_commit_msg_hook_rejects_legacy_timestamp_trailer(tmp_path: Path) -> None:
    result = run_hook(
        tmp_path,
        """
        [codex/interactive] chore: Polish Makefile help output formatting

        Refactors the help target to use structured printf output.

        Authored-By: codex <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        timestamp: 2026_0604_1408_MDT
        runtime: iterm2
        """,
    )

    assert result.returncode != 0
    assert "timestamp: is legacy" in result.stderr
    assert "time:" in result.stderr


def test_commit_msg_hook_requires_explanatory_body(tmp_path: Path) -> None:
    result = run_hook(
        tmp_path,
        """
        [codex/interactive] chore: Polish Makefile help output formatting

        Authored-By: codex <agents@vetcoders.io>
        session_id: 019e93be-379d-7303-9ad4-ffae468db99f
        time: 2026-06-05T12:52:47-06:00
        runtime: iterm2
        """,
    )

    assert result.returncode != 0
    assert "body" in result.stderr

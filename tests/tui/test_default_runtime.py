from __future__ import annotations

import os
from pathlib import Path

from vibecrafted_core import cli

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fake_vc_frame(bin_dir: Path, sessions: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "vc-frame"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "list-sessions" ]; then\n'
        f"cat <<'EOF'\n{sessions}\nEOF\n"
        "fi\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _force_non_tty(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False, raising=False)


def _clear_session_env(monkeypatch) -> None:
    for key in (
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME_SESSION_NAME",
        "ZELLIJ_SESSION_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_live_operator_session_exists_matches_repo_bound_live_session(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    fake_bin = tmp_path / "bin"
    _fake_vc_frame(
        fake_bin, "myrepo [Created 1h ago] (current)\nother [Created 2h ago]"
    )
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    assert cli._live_operator_session_exists(str(repo)) is True


def test_live_operator_session_exists_ignores_exited_and_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    fake_bin = tmp_path / "bin"
    # The repo-bound session is listed but EXITED; a live session exists but is
    # named differently. Neither must count as a host for a visible tab.
    _fake_vc_frame(fake_bin, "myrepo [Created 1h ago] (EXITED)\nother [Created 2h ago]")
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    assert cli._live_operator_session_exists(str(repo)) is False


def test_live_operator_session_exists_false_without_vc_frame(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))  # no vc-frame on PATH
    assert cli._live_operator_session_exists(str(repo)) is False


def test_default_runtime_prefers_terminal_for_nontty_with_live_session(
    monkeypatch,
) -> None:
    _clear_session_env(monkeypatch)
    _force_non_tty(monkeypatch)
    monkeypatch.setattr(cli, "_live_operator_session_exists", lambda root: True)
    # The mission: a CLI/headless/nested dispatch lands as a visible tab when a
    # live repo-bound operator session exists — not an invisible headless orphan.
    assert cli._default_runtime("", "/some/repo") == "terminal"


def test_default_runtime_headless_for_nontty_without_live_session(monkeypatch) -> None:
    _clear_session_env(monkeypatch)
    _force_non_tty(monkeypatch)
    monkeypatch.setattr(cli, "_live_operator_session_exists", lambda root: False)
    # Headless remains the correct fallback when no live session can host a tab.
    assert cli._default_runtime("", "/some/repo") == "headless"


def test_default_runtime_passes_through_explicit_runtime(monkeypatch) -> None:
    _clear_session_env(monkeypatch)
    _force_non_tty(monkeypatch)
    # Explicit runtime wins even with a live session — internal `--runtime headless`
    # dispatches (wrappers, supervisor) must stay headless.
    monkeypatch.setattr(cli, "_live_operator_session_exists", lambda root: True)
    assert cli._default_runtime("headless", "/some/repo") == "headless"


def test_default_runtime_terminal_when_inside_vc_frame_env(monkeypatch) -> None:
    _clear_session_env(monkeypatch)
    _force_non_tty(monkeypatch)
    monkeypatch.setenv("VC_FRAME_SESSION_NAME", "pensieve")
    # In-frame path: an inherited env session resolves to terminal without
    # consulting repo-bound discovery — the in-pane oracle stays unbroken.
    monkeypatch.setattr(
        cli,
        "_live_operator_session_exists",
        lambda root: (_ for _ in ()).throw(AssertionError("discovery must be skipped")),
    )
    assert cli._default_runtime("", "/some/repo") == "terminal"

"""Regression: vc-frame Ctrl+Q must close a pane, never quit the whole session.

The zellij->vc-frame rebrand once left Ctrl+Q bound to `Quit` in the loaded
config, so a single shortcut tore down the operator's entire frame (every pane,
every dispatched run visible in it). The contract:

- `Ctrl+Q`  -> CloseFocus (close the focused pane; zellij ends the session
              gracefully only when the LAST pane closes).
- `Ctrl+O` then `q` -> Quit (the explicit, immediate full-session quit).

This guards the canonical config so the binding can never silently regress.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CONFIG = REPO_ROOT / "config" / "vc-frame" / "config.kdl"


def test_canonical_config_exists() -> None:
    assert CANONICAL_CONFIG.is_file(), f"missing {CANONICAL_CONFIG}"


def test_ctrl_q_closes_pane_never_quits_session() -> None:
    text = CANONICAL_CONFIG.read_text(encoding="utf-8")
    assert 'bind "Ctrl q" { CloseFocus' in text, (
        "Ctrl+Q must be bound to CloseFocus (close one pane), not the whole session"
    )
    assert 'bind "Ctrl q" { Quit' not in text, (
        "Ctrl+Q must never be bound to Quit — that kills the entire vc-frame session"
    )


def test_session_mode_keeps_explicit_hard_quit() -> None:
    text = CANONICAL_CONFIG.read_text(encoding="utf-8")
    # Immediate full quit stays available via Ctrl+O (session mode) then q.
    assert 'bind "q" { Quit' in text, (
        "session mode must keep `q -> Quit` so Ctrl+O then q remains the hard quit"
    )


def test_no_zellij_named_config_dir_in_repo() -> None:
    # The rebrand is complete: the canonical config lives under config/vc-frame/,
    # never config/zellij/ (a stale zellij dir was the root cause of the load miss).
    assert not (REPO_ROOT / "config" / "zellij").exists(), (
        "config/zellij must not exist — vc-frame config is config/vc-frame/"
    )

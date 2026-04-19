"""Regression tests for vetcoders_installer branding / summary rendering.

Covers the user-visible output paths in
``scripts/installer/vetcoders_installer/__init__.py``:

- ``_print_title`` — headline from manifest title + version
- ``_print_reason_block`` — per-phase reason block
- ``_print_summary`` — end-of-run recap incl. branding.name /
  unicode_wordmark / installer_cmd / next_steps / docs_url
- ``_print_cleanup_notice`` — persist=true vs uv-tool uninstall guidance

All tests exercise the plain (non-Rich) console so assertions can inspect
raw stdout; _PlainConsole.print strips Rich markup tokens, so we check the
stripped result.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PKG_DIR = REPO_ROOT / "scripts" / "installer"
if str(INSTALLER_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_PKG_DIR))

import vetcoders_installer as installer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_manifest(
    tmp_path: Path,
    *,
    title: str = "⚒ Vibecrafted.",
    version: str = "1.2.3",
    branding: dict | None = None,
    persist: bool = False,
) -> installer.Manifest:
    return installer.Manifest(
        title=title,
        version=version,
        log_pattern=None,
        persist=persist,
        phases=[],
        path=tmp_path / "install.toml",
        branding=dict(branding or {}),
        intro_screens=[],
        textual_screens=[],
        diagnostics={},
    )


def _plain_console_capture(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> installer._PlainConsole:
    """Force the plain-console fallback so stdout carries raw, markup-free text."""
    monkeypatch.setattr(installer, "HAS_RICH", False)
    return installer._PlainConsole()


# ---------------------------------------------------------------------------
# _print_title — happy + edges
# ---------------------------------------------------------------------------


def test_print_title_happy_path_includes_title_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, title="My Installer", version="4.5.6")

    installer._print_title(console, manifest)
    out = capsys.readouterr().out

    assert "My Installer v4.5.6" in out


def test_print_title_edge_blank_version_omits_v_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, title="No Version Installer", version="")

    installer._print_title(console, manifest)
    out = capsys.readouterr().out

    # No version → no "v…" suffix, just the raw title.
    assert "No Version Installer" in out
    assert "No Version Installer v" not in out


# ---------------------------------------------------------------------------
# _print_reason_block — phase reason rendering
# ---------------------------------------------------------------------------


def test_print_reason_block_renders_label_and_reason_lines(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    console = _plain_console_capture(monkeypatch, capsys)
    phase = installer.Phase(
        key="diag",
        label="Diagnostics",
        reason="first line\nsecond line",
        cmd=["echo", "ok"],
        cwd=Path("/tmp"),
    )

    installer._print_reason_block(console, phase)
    out = capsys.readouterr().out

    assert "Diagnostics" in out
    assert "first line" in out
    assert "second line" in out


def test_print_reason_block_empty_reason_still_renders_label(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Edge: a phase with an empty reason should still print the label."""
    console = _plain_console_capture(monkeypatch, capsys)
    phase = installer.Phase(
        key="noop",
        label="Silent Phase",
        reason="",
        cmd=["true"],
        cwd=Path("/tmp"),
    )

    installer._print_reason_block(console, phase)
    out = capsys.readouterr().out

    assert "Silent Phase" in out


# ---------------------------------------------------------------------------
# _print_summary — branding + verdict + next steps
# ---------------------------------------------------------------------------


def test_print_summary_happy_path_uses_branded_wordmark_and_next_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """All phases ok → branded '... is ready' line + next_steps list + docs_url."""
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(
        tmp_path,
        branding={
            "name": "BrandedThing",
            "unicode_wordmark": "⚒ BrandedThing",
            "next_steps": [
                {"cmd": "brandedthing tour", "desc": "see the map"},
                {"cmd": "brandedthing doctor", "desc": "audit"},
            ],
            "installer_cmd": "make brandedthing",
            "docs_url": "https://example.test/docs",
        },
    )
    results = [
        ("Diagnostics", "ok", 0),
        ("Installation", "ok", 0),
    ]

    installer._print_summary(console, manifest, results, log_path=None)
    out = capsys.readouterr().out

    assert "⚒ BrandedThing is ready" in out
    assert "brandedthing tour" in out
    assert "see the map" in out
    assert "brandedthing doctor" in out
    assert "https://example.test/docs" in out


def test_print_summary_edge_failure_shows_recovery_block_with_installer_cmd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A failing phase → Recovery block with branded installer_cmd hint."""
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(
        tmp_path,
        branding={
            "name": "RecoverBrand",
            "installer_cmd": "make recoverbrand",
        },
    )
    results = [
        ("Diagnostics", "ok", 0),
        ("Installation", "failed (exit 3)", 3),
    ]

    installer._print_summary(
        console, manifest, results, log_path=Path("/var/log/run.log")
    )
    out = capsys.readouterr().out

    assert "Install stopped with errors" in out
    assert "Recovery" in out
    assert "make recoverbrand" in out
    # Log path must be surfaced in the failure footer.
    assert "/var/log/run.log" in out


def test_print_summary_edge_empty_results_produces_no_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Edge: zero results (no phases ran) → _print_summary is a silent no-op."""
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, branding={})

    installer._print_summary(console, manifest, results=[], log_path=None)
    out = capsys.readouterr().out

    # Empty results short-circuits before any output. No banner, no rule.
    assert out == ""


def test_print_summary_pure_cancel_without_branding_uses_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Edge: user cancelled + empty branding → default installer_cmd + docs_url."""
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, branding={})
    results = [("Diagnostics", "cancelled", 0)]

    installer._print_summary(console, manifest, results, log_path=None)
    out = capsys.readouterr().out

    assert "cancelled" in out.lower()
    # Defaults from the code when branding is empty.
    assert "make vibecrafted" in out
    assert "https://vibecrafted.io" in out


# ---------------------------------------------------------------------------
# _print_cleanup_notice — persist vs remove guidance
# ---------------------------------------------------------------------------


def test_print_cleanup_notice_persist_manifest_stays_silent_about_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, persist=True)

    installer._print_cleanup_notice(console, manifest, cleanup_flag=False)
    out = capsys.readouterr().out

    assert "stays installed" in out
    assert installer.TOOL_NAME not in out  # no uninstall command printed


def test_print_cleanup_notice_non_persist_prints_uv_uninstall_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    console = _plain_console_capture(monkeypatch, capsys)
    manifest = _build_manifest(tmp_path, persist=False)

    installer._print_cleanup_notice(console, manifest, cleanup_flag=False)
    out = capsys.readouterr().out

    assert installer.TOOL_NAME in out
    assert "uv tool uninstall" in out

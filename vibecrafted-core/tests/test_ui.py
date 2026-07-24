"""Contract tests for the shared CLI output system (vibecrafted_core.ui)."""

from __future__ import annotations

import io

import pytest
from vibecrafted_core import ui


@pytest.fixture(autouse=True)
def _no_color_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)


def test_glyph_is_the_prefix_no_bracket_tags(capsys: pytest.CaptureFixture) -> None:
    ui.ok("staged vibecrafted 3.1.0")
    ui.warn("loctree missing — optional")
    captured = capsys.readouterr()
    assert captured.out.startswith("✓ staged vibecrafted 3.1.0")
    assert "! loctree missing" in captured.out
    assert "[" not in captured.out.split("\n")[0]


def test_err_shape_goes_to_stderr_with_fix_and_log(
    capsys: pytest.CaptureFixture,
) -> None:
    ui.err(
        "could not refresh staged tools",
        fix="rerun `vibecrafted update`",
        log="~/.vibecrafted/install.log",
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "✗ could not refresh staged tools",
        "  → fix: rerun `vibecrafted update`",
        "  log: ~/.vibecrafted/install.log",
    ]


def test_no_color_strips_ansi(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    ui.ok("done")
    ui.stage("scanning repo")
    captured = capsys.readouterr()
    assert "\033[" not in captured.out


def test_bounded_collapses_long_lists() -> None:
    items = [f"skill-{i}" for i in range(17)]
    collapsed = ui.bounded(items)
    assert len(collapsed) == 6
    assert collapsed[-1] == "… and 12 more (--full)"
    assert ui.bounded(["a", "b"]) == ["a", "b"]


def test_spinner_non_tty_prints_single_stage_line() -> None:
    stream = io.StringIO()
    with ui.Spinner("scanning repo", stream=stream) as spinner:
        spinner_message = spinner.message
    assert spinner_message == "scanning repo"
    assert stream.getvalue() == "▸ scanning repo\n"

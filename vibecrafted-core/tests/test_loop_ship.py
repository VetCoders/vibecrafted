from __future__ import annotations

from pathlib import Path

from vibecrafted_core import loop, ship


def test_loop_start_next_complete_round_trip(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state_file = tmp_path / "operator-loop.local.md"
    monkeypatch.chdir(tmp_path)

    assert (
        loop.main(
            [
                "start",
                "--state-file",
                str(state_file),
                "--prompt",
                "keep going",
                "--completion-promise",
                "DONE",
                "--max-iterations",
                "2",
            ]
        )
        == 0
    )
    assert state_file.is_file()
    assert "active: true" in state_file.read_text(encoding="utf-8")

    assert loop.main(["next", "--state-file", str(state_file)]) == 0
    out = capsys.readouterr().out
    assert "CONTINUE: operator loop iteration 2" in out
    assert "keep going" in out

    assert loop.main(["next", "--state-file", str(state_file)]) == 0
    assert "STOP: max iterations reached (2)" in capsys.readouterr().out


def test_ship_loop_only_creates_vc_ship_contract(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    input_file = tmp_path / "plan.md"
    state_file = tmp_path / "state.md"
    input_file.write_text("dispatch this", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECRAFTED_LOOP_STATE_FILE", str(state_file))

    assert (
        ship.main(
            [
                "codex",
                "--checkpoint",
                "workflow",
                "--file",
                str(input_file),
                "--loop-only",
            ]
        )
        == 0
    )

    assert "Operator loop activated" in capsys.readouterr().out
    content = state_file.read_text(encoding="utf-8")
    assert "VC-SHIP interactive supervisor loop." in content
    assert "checkpoint: workflow" in content
    assert "dispatch this" in content

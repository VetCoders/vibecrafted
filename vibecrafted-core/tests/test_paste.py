from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from vibecrafted_core import paste
from vibecrafted_core.workflow import normalize_launch_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_prompt_names_clipboard_task_contract() -> None:
    assert paste.BOOTSTRAP_PASTE_PROMPT
    assert "BOOTSTRAP — CLIPBOARD RUN" in paste.BOOTSTRAP_PASTE_PROMPT
    assert "pbpaste" in paste.BOOTSTRAP_PASTE_PROMPT
    assert "schowka jest JEDYNYM" in paste.BOOTSTRAP_PASTE_PROMPT


def test_payload_defers_clipboard_resolution_to_agent() -> None:
    payload = paste.build_paste_payload("claude")

    assert payload["prompt"] == paste.BOOTSTRAP_PASTE_PROMPT
    assert payload["skill"] == "workflow"
    assert payload["mode"] == "paste"
    assert payload["file"] == ""


def test_paste_source_does_not_call_clipboard_tools() -> None:
    source = Path(paste.__file__).read_text(encoding="utf-8")

    forbidden_calls = (
        "subprocess",
        "os.system",
        "Popen",
        "run(",
        "check_output",
    )
    for call in forbidden_calls:
        assert call not in source


def test_payload_normalizes_to_workflow(tmp_path: Path) -> None:
    spec = normalize_launch_spec(paste.build_paste_payload("claude"), tmp_path)

    assert spec.skill == "workflow"
    assert spec.agent == "claude"
    assert spec.prompt == paste.BOOTSTRAP_PASTE_PROMPT
    assert spec.mode == "paste"


def test_print_prompt_does_not_launch(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def fail_launch(*_args, **_kwargs):
        raise AssertionError("print-prompt must not launch")

    monkeypatch.setattr(paste, "launch_workflow", fail_launch)

    assert paste.paste_main(["claude", "--print-prompt"]) == 0

    assert capsys.readouterr().out.startswith("BOOTSTRAP — CLIPBOARD RUN")


def test_dry_run_normalizes_and_does_not_launch(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def fail_launch(*_args, **_kwargs):
        raise AssertionError("dry-run must not launch")

    monkeypatch.setattr(paste, "launch_workflow", fail_launch)

    assert paste.paste_main(["claude", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert '"skill": "workflow"' in out
    assert '"agent": "claude"' in out
    assert '"mode": "paste"' in out


def test_cli_paste_print_prompt_uses_python_path(capsys) -> None:
    from vibecrafted_core import cli

    assert cli.main(["paste", "claude", "--print-prompt"]) == 0

    assert capsys.readouterr().out.startswith("BOOTSTRAP — CLIPBOARD RUN")


def test_unsupported_agent_returns_clear_error(capsys) -> None:
    assert paste.paste_main(["pizza"]) == 2

    assert "Unsupported agent: pizza" in capsys.readouterr().err


def test_shim_exists_is_executable_and_points_to_paste_main() -> None:
    shim = REPO_ROOT / "bin" / "vc-paste"

    assert shim.exists()
    assert os.access(shim, os.X_OK)
    assert shim.stat().st_mode & stat.S_IXUSR
    source = shim.read_text(encoding="utf-8")
    assert "from vibecrafted_core.paste import paste_main" in source
    assert "raise SystemExit(paste_main())" in source


def test_installer_registers_vc_paste() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import vetcoders_install as installer

    assert "vc-paste" in installer.LAUNCHER_WRAPPERS
    assert "vc-paste" in installer.PYTHON_ENTRYPOINT_LAUNCHERS


def test_pyproject_registers_vc_paste_console_script() -> None:
    pyproject = (REPO_ROOT / "vibecrafted-core" / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert 'vc-paste = "vibecrafted_core.paste:paste_main"' in pyproject


def test_skill_override_flows_through_payload() -> None:
    assert paste.build_paste_payload("codex", skill="review")["skill"] == "review"


def test_vc_paste_shim_prints_prompt() -> None:
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "vc-paste"), "claude", "--print-prompt"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.startswith("BOOTSTRAP — CLIPBOARD RUN")

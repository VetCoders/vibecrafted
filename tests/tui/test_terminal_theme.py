from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
THEME_COMMAND = REPO_ROOT / "bin/vc-theme"


def _run_theme(
    action: str,
    *,
    config_home: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(THEME_COMMAND), action],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "VIBECRAFTED_RUNTIME_ROOT": str(REPO_ROOT),
            "XDG_CONFIG_HOME": str(config_home),
            **(extra_env or {}),
        },
    )


def test_theme_toggle_owns_only_vibecrafted_xdg_state(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg"
    private_alacritty = config_home / "alacritty" / "alacritty.toml"
    private_alacritty.parent.mkdir(parents=True)
    private_alacritty.write_text("operator-owned\n", encoding="utf-8")

    current = _run_theme("current", config_home=config_home)
    assert current.returncode == 0
    assert current.stdout == "dark\n"

    light = _run_theme("toggle", config_home=config_home)
    assert light.returncode == 0
    assert light.stdout == "light\n"
    active = config_home / "vibecrafted" / "terminal-theme.toml"
    assert active.read_text(encoding="utf-8") == (
        REPO_ROOT / "config/vc-terminal/themes/light.toml"
    ).read_text(encoding="utf-8")

    dark = _run_theme("toggle", config_home=config_home)
    assert dark.returncode == 0
    assert dark.stdout == "dark\n"
    assert active.read_text(encoding="utf-8") == (
        REPO_ROOT / "config/vc-terminal/themes/dark.toml"
    ).read_text(encoding="utf-8")
    assert private_alacritty.read_text(encoding="utf-8") == "operator-owned\n"


def test_theme_command_rejects_unknown_action(tmp_path: Path) -> None:
    result = _run_theme("sepia", config_home=tmp_path / "xdg")
    assert result.returncode == 2
    assert "usage: vc-theme" in result.stderr


def test_theme_toggle_switches_the_active_vc_frame_session_too(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    action_log = tmp_path / "vc-frame-actions.log"
    fake_bin.mkdir()
    fake_vc_frame = fake_bin / "vc-frame"
    fake_vc_frame.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$VC_FRAME_ACTION_LOG"\n',
        encoding="utf-8",
    )
    fake_vc_frame.chmod(0o755)

    result = _run_theme(
        "light",
        config_home=config_home,
        extra_env={
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ZELLIJ_SESSION_NAME": "workspace-9082c14d",
            "VC_FRAME_ACTION_LOG": str(action_log),
        },
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "light\n"
    assert action_log.read_text(encoding="utf-8") == (
        "--session workspace-9082c14d action set-light-theme\n"
    )

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = (
    REPO_ROOT
    / "vibecrafted-core"
    / "vibecrafted_core"
    / "runtime"
    / "shell"
    / "vetcoders.sh"
)


def _write_fake_binary(bin_dir: Path, name: str) -> None:
    script = bin_dir / name
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)


def test_ensure_vc_frame_session_uses_frontier_config_not_user_vc_frame(
    tmp_path: Path,
) -> None:
    """The vc-frame launcher must be isolated from stock ~/.config/vc-frame."""
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    capture = tmp_path / "vc-frame-env.log"
    frontier_vc_frame = xdg_config_home / "vetcoders" / "frontier" / "vc-frame"
    user_vc_frame = xdg_config_home / "vc-frame"
    layout_file = frontier_vc_frame / "layouts" / "operator.kdl"

    home.mkdir()
    fake_bin.mkdir()
    frontier_vc_frame.mkdir(parents=True)
    (frontier_vc_frame / "config.kdl").write_text("// frontier\n", encoding="utf-8")
    layout_file.parent.mkdir()
    layout_file.write_text("layout {}\n", encoding="utf-8")
    user_vc_frame.mkdir(parents=True)
    (user_vc_frame / "config.kdl").write_text(
        "// stale user vc_frame\n", encoding="utf-8"
    )

    vc_frame = fake_bin / "vc-frame"
    vc_frame.write_text(
        '#!/usr/bin/env bash\nif [[ "${1:-}" == "ls" ]]; then exit 0; fi\nprintf "VC_FRAME_CONFIG_DIR=%s\\n" "${VC_FRAME_CONFIG_DIR:-}" >> "$CAPTURE_FILE"\nprintf "args=%s\\n" "$*" >> "$CAPTURE_FILE"\nexit 0\n',
        encoding="utf-8",
    )
    vc_frame.chmod(0o755)

    env = os.environ.copy()
    env["CAPTURE_FILE"] = str(capture)
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'_vetcoders_ensure_vc_frame_session "operator-test" "{layout_file}"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    payload = capture.read_text(encoding="utf-8")
    assert f"VC_FRAME_CONFIG_DIR={frontier_vc_frame}" in payload
    assert str(user_vc_frame) not in payload


def test_sourcing_helper_respects_existing_user_config(
    tmp_path: Path,
) -> None:
    """When the user already has config env vars set, vetcoders.sh must NOT
    override them. Frontier configs are suggestions, not mandates."""
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "vc-frame")

    user_starship = str(tmp_path / "user-starship.toml")
    user_atuin = str(tmp_path / "user-atuin.toml")
    # The user's pinned VC_FRAME_CONFIG_DIR must resolve to a real config.kdl;
    # vetcoders.sh only self-heals a stale/dangling pin, never a live one.
    user_vc_frame_dir = tmp_path / "user-vc-frame"
    user_vc_frame_dir.mkdir()
    (user_vc_frame_dir / "config.kdl").write_text("// user\n", encoding="utf-8")
    user_vc_frame = str(user_vc_frame_dir)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["STARSHIP_CONFIG"] = user_starship
    env["ATUIN_CONFIG"] = user_atuin
    env["VC_FRAME_CONFIG_DIR"] = user_vc_frame

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "VC_FRAME_CONFIG_DIR=%s\\n" "$VC_FRAME_CONFIG_DIR"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    # User's configs must be preserved — not overwritten by frontier
    assert f"STARSHIP_CONFIG={user_starship}" in result.stdout
    assert f"ATUIN_CONFIG={user_atuin}" in result.stdout
    assert f"VC_FRAME_CONFIG_DIR={user_vc_frame}" in result.stdout


def test_sourcing_helper_sets_frontier_when_no_user_config(
    tmp_path: Path,
) -> None:
    """When user has no config env vars, vetcoders.sh provides frontier defaults."""
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    vc_frame_config.parent.mkdir(parents=True)
    vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "vc-frame")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    # No STARSHIP_CONFIG, ATUIN_CONFIG, VC_FRAME_CONFIG_DIR set
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ATUIN_CONFIG", None)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'printf "STARSHIP_CONFIG=%s\\n" "$STARSHIP_CONFIG"; '
                'printf "ATUIN_CONFIG=%s\\n" "$ATUIN_CONFIG"; '
                'printf "VC_FRAME_CONFIG_DIR=%s\\n" "$VC_FRAME_CONFIG_DIR"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    # Frontier defaults should be set
    assert "STARSHIP_CONFIG=" in result.stdout
    assert f"VC_FRAME_CONFIG_DIR={vc_frame_config.parent}" in result.stdout


def test_sourcing_helper_pins_vc_frame_despite_default_user_vc_frame_config(
    tmp_path: Path,
) -> None:
    """vc-frame uses frontier config even when stock vc_frame has user config."""
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    fake_bin = tmp_path / "bin"
    frontier_vc_frame_config = (
        xdg_config_home / "vetcoders" / "frontier" / "vc-frame" / "config.kdl"
    )

    home.mkdir()
    fake_bin.mkdir()
    frontier_vc_frame_config.parent.mkdir(parents=True)
    frontier_vc_frame_config.write_text("layout {}\n", encoding="utf-8")
    (xdg_config_home / "atuin").mkdir(parents=True)
    (xdg_config_home / "vc-frame").mkdir(parents=True)
    (xdg_config_home / "starship.toml").write_text("# user\n", encoding="utf-8")
    (xdg_config_home / "atuin" / "config.toml").write_text("# user\n", encoding="utf-8")
    (xdg_config_home / "vc-frame" / "config.kdl").write_text(
        "// user\n", encoding="utf-8"
    )
    _write_fake_binary(fake_bin, "starship")
    _write_fake_binary(fake_bin, "atuin")
    _write_fake_binary(fake_bin, "vc-frame")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("STARSHIP_CONFIG", None)
    env.pop("ATUIN_CONFIG", None)
    env.pop("VC_FRAME_CONFIG_DIR", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'printf "STARSHIP_CONFIG=%s\\n" "${STARSHIP_CONFIG:-}"; '
                'printf "ATUIN_CONFIG=%s\\n" "${ATUIN_CONFIG:-}"; '
                'printf "VC_FRAME_CONFIG_DIR=%s\\n" "${VC_FRAME_CONFIG_DIR:-}"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "STARSHIP_CONFIG=\n" in result.stdout
    assert "ATUIN_CONFIG=\n" in result.stdout
    assert f"VC_FRAME_CONFIG_DIR={frontier_vc_frame_config.parent}" in result.stdout

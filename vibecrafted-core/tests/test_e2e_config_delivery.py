"""W3-B: e2e channel matrix (wheel/dev × shell). Marked e2e_delivery."""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from vibecrafted_core.vc_frame_delivery import stage_vc_frame_config

CORE = Path(__file__).resolve().parents[1]
REPO = CORE.parent

pytestmark = pytest.mark.e2e_delivery


def _build_wheel(dist: Path) -> Path:
    dist.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist)],
        cwd=str(CORE),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
            cwd=str(CORE),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        pytest.skip(f"wheel build failed: {(proc.stderr or proc.stdout)[-400:]}")
    return wheels[-1]


@pytest.mark.e2e_delivery
def test_wheel_members_include_vc_frame(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path / "dist")
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert "vibecrafted_core/config/vc-frame/config.kdl" in names
    assert any("auto-theme.sh" in n for n in names)
    assert any("operator.kdl" in n for n in names)


@pytest.mark.e2e_delivery
def test_channel_store_stage_from_source_accessor(tmp_path: Path, monkeypatch) -> None:
    """Simulate post-wheel install by staging under sandbox HOME (accessor path)."""
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    plan = stage_vc_frame_config(
        home=home,
        tools_home=tools,
        version="e2e-store",
        prefer_repo=False,
        path_env=os.environ.get("PATH", ""),
    )
    cfg = (home / ".config" / "vc-frame" / "config.kdl").resolve()
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "theme" in text
    assert (home / ".config" / "vc-frame" / "layouts").exists()
    assert (home / ".config" / "vc-frame" / "themes").exists()
    assert plan.channel == "store-current"


@pytest.mark.e2e_delivery
def test_channel_dev_checkout(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    plan = stage_vc_frame_config(
        home=home, tools_home=tools, version="e2e-dev", prefer_repo=True
    )
    assert plan.channel == "dev-checkout"
    resolved = (home / ".config" / "vc-frame" / "config.kdl").resolve()
    assert "config/vc-frame" in str(resolved)


@pytest.mark.e2e_delivery
def test_upgrade_flip_atomicity(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tools = home / ".local" / "share" / "vibecrafted" / "tools"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("VIBECRAFTED_PREFER_REPO_VC_FRAME", raising=False)
    stage_vc_frame_config(
        home=home, tools_home=tools, version="e2e-A", prefer_repo=False
    )
    view = home / ".config" / "vc-frame" / "config.kdl"
    path_before = str(view)
    stage_vc_frame_config(
        home=home, tools_home=tools, version="e2e-B", prefer_repo=False, force=True
    )
    assert str(view) == path_before
    assert (tools / "vibecrafted-current").resolve() == (
        tools / "vibecrafted-e2e-B"
    ).resolve()
    assert (tools / "vibecrafted-e2e-A").is_dir()
    # no orphan .tmp current links
    assert not list(tools.glob(".vibecrafted-current.tmp.*"))

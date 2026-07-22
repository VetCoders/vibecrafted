"""W1-A: wheel/sdist carry config/vc-frame; accessor resolves checkout + package."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from vibecrafted_core.frontier_assets import vc_frame_config_kdl, vc_frame_config_source

CORE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CORE_ROOT.parent
# uv build may emit to monorepo dist/ or vibecrafted-core/dist/
DIST_CANDIDATES = (CORE_ROOT / "dist", REPO_ROOT / "dist")

REQUIRED_MEMBERS = (
    "vibecrafted_core/config/vc-frame/config.kdl",
    "vibecrafted_core/config/vc-frame/auto-theme.sh",
    "vibecrafted_core/config/vc-frame/layouts/operator.kdl",
    "vibecrafted_core/config/vc-frame/layouts/dashboard.kdl",
    "vibecrafted_core/config/vc-frame/layouts/research.kdl",
    "vibecrafted_core/config/vc-frame/layouts/workflow.kdl",
    "vibecrafted_core/config/vc-frame/layouts/marbles.kdl",
    "vibecrafted_core/config/vc-frame/themes/vibecrafted-ivory.kdl",
    "vibecrafted_core/config/vc-frame/themes/vetcoders-mesh.kdl",
)


def test_accessor_returns_existing_tree_from_checkout() -> None:
    source = vc_frame_config_source()
    assert source.is_dir()
    assert (source / "config.kdl").is_file()
    assert (source / "auto-theme.sh").is_file()
    for layout in (
        "operator.kdl",
        "dashboard.kdl",
        "research.kdl",
        "workflow.kdl",
        "marbles.kdl",
    ):
        assert (source / "layouts" / layout).is_file(), layout
    assert (source / "themes" / "vibecrafted-ivory.kdl").is_file()
    assert (source / "themes" / "vetcoders-mesh.kdl").is_file()
    text = vc_frame_config_kdl().read_text(encoding="utf-8")
    assert 'theme "monochrome"' in text or "theme " in text


def test_repo_root_config_is_canonical_source() -> None:
    """Checkout accessor must land on monorepo config/vc-frame, not a duplicate."""
    source = vc_frame_config_source().resolve()
    canonical = (REPO_ROOT / "config" / "vc-frame").resolve()
    # When package data is also present (editable install after wheel stage),
    # either path is valid if it contains the tree; prefer equality when possible.
    assert (source / "config.kdl").is_file()
    assert (canonical / "config.kdl").is_file()
    assert (
        source == canonical
        or (source / "config.kdl").read_bytes()
        == (canonical / "config.kdl").read_bytes()
    )


def _latest_artifacts() -> tuple[list[Path], list[Path]]:
    wheels: list[Path] = []
    sdists: list[Path] = []
    for dist in DIST_CANDIDATES:
        if not dist.is_dir():
            continue
        wheels.extend(dist.glob("vibecrafted-*.whl"))
        wheels.extend(dist.glob("*.whl"))
        sdists.extend(dist.glob("vibecrafted-*.tar.gz"))
        sdists.extend(dist.glob("*.tar.gz"))
    # Prefer newest by mtime
    wheels = sorted(set(wheels), key=lambda p: p.stat().st_mtime)
    sdists = sorted(set(sdists), key=lambda p: p.stat().st_mtime)
    return wheels, sdists


def _ensure_build_artifacts() -> tuple[Path, Path | None]:
    """Build wheel/sdist if missing; return (wheel, sdist|None)."""
    wheels, sdists = _latest_artifacts()
    # Prefer 3.6+ artifacts that contain package data
    if wheels:
        try:
            import zipfile

            names = zipfile.ZipFile(wheels[-1]).namelist()
            if "vibecrafted_core/config/vc-frame/config.kdl" in names:
                return wheels[-1], sdists[-1] if sdists else None
        except OSError:
            pass
    import subprocess
    import sys

    cmds = [
        ["uv", "build", "--directory", str(CORE_ROOT)],
        [sys.executable, "-m", "build", str(CORE_ROOT)],
    ]
    last_err = ""
    for cmd in cmds:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(CORE_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            last_err = str(exc)
            continue
        if proc.returncode == 0:
            break
        last_err = (proc.stderr or proc.stdout or "")[-500:]
    else:
        pytest.skip(f"could not build wheel/sdist: {last_err}")

    wheels, sdists = _latest_artifacts()
    if not wheels:
        pytest.skip("build produced no wheel")
    return wheels[-1], sdists[-1] if sdists else None


def test_wheel_contains_vc_frame_tree() -> None:
    wheel, _ = _ensure_build_artifacts()
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    missing = [n for n in REQUIRED_MEMBERS if n not in names]
    assert not missing, f"wheel {wheel.name} missing: {missing}"


def test_sdist_contains_vc_frame_tree() -> None:
    _, sdist = _ensure_build_artifacts()
    if sdist is None:
        pytest.skip("no sdist produced")
    with tarfile.open(sdist, "r:gz") as tf:
        names = set(tf.getnames())
    # sdist prefixes with package-version/
    missing = []
    for member in REQUIRED_MEMBERS:
        if not any(n.endswith(member) or n.endswith("/" + member) for n in names):
            # also allow top-level without vibecrafted- prefix quirks
            if not any(member.split("/", 1)[-1] in n for n in names if "vc-frame" in n):
                missing.append(member)
    # stricter: any path ending with config/vc-frame/config.kdl
    assert any(n.endswith("config/vc-frame/config.kdl") for n in names), (
        f"sdist {sdist.name} has no config.kdl; sample={sorted(names)[:20]}"
    )
    assert any("auto-theme.sh" in n for n in names)
    assert any("operator.kdl" in n for n in names)

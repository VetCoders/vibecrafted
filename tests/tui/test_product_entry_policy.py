"""Product entry choke — execute shipped shell/wrapper, not greps or reimpls.

Surfaces under test:
  - scripts/vc-frame-product-entry.sh  (bare frame refuse / pin)
  - runtime/shell vc-start path          (_vetcoders_product_entry_prepare via probe)
"""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "vc-frame-product-entry.sh"
HELPER = REPO / "runtime" / "shell" / "vetcoders.sh"
DASHBOARD = REPO / "runtime" / "shell" / "lib" / "dashboard.sh"
DISPATCH = REPO / "runtime" / "shell" / "lib" / "dispatch.sh"
SCRATCH = Path(
    "/var/folders/k2/gcr84s3x0z7dgzfspkq1klt80000gn/T/grok-goal-2158121b574a/implementer"
)


def _ensure_scratch() -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return SCRATCH


def _write_fake_bin(bin_dir: Path, name: str, body: str) -> Path:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_wrapper_exists_executable() -> None:
    assert WRAPPER.is_file()
    assert WRAPPER.stat().st_mode & stat.S_IXUSR
    text = WRAPPER.read_text(encoding="utf-8")
    assert "pin_product_config" in text
    assert "is_product_session_name" in text


def test_product_entry_prepare_exists_in_shipped_dashboard() -> None:
    """Shell prepare is the real choke (vc-start never enters deck cmd_start)."""
    text = DASHBOARD.read_text(encoding="utf-8")
    assert "_vetcoders_product_entry_prepare()" in text
    dispatch = DISPATCH.read_text(encoding="utf-8")
    assert "_vetcoders_product_entry_prepare" in dispatch
    assert "VIBECRAFTED_PRODUCT_ENTRY_PROBE" in dispatch


def test_wrapper_refuses_product_attach_without_config(tmp_path: Path) -> None:
    """Execute shipped wrapper: product attach with no frontier/view config → exit 2."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()

    real = _write_fake_bin(
        bin_dir,
        "vc-frame.real",
        "#!/usr/bin/env bash\necho REAL_RAN args=$*\nexit 0\n",
    )
    wrapper = bin_dir / "vc-frame"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper.chmod(0o755)

    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_VC_FRAME_BIN": str(real),
        "USER": "test",
    }
    # No VC_FRAME_* leakage
    for key in list(os.environ):
        if key.startswith("VC_FRAME"):
            continue
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        **env,
    }

    proc = subprocess.run(
        [str(wrapper), "attach", "vibecrafted"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "Refusing bare attach to product session" in proc.stderr
    assert "Run: vc-start" in proc.stderr
    assert "REAL_RAN" not in proc.stdout


def test_wrapper_refuses_dash_s_product_session_without_config(tmp_path: Path) -> None:
    """-s / --session product names also refuse without product config."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()
    real = _write_fake_bin(
        bin_dir,
        "vc-frame.real",
        "#!/usr/bin/env bash\necho REAL_RAN\nexit 0\n",
    )
    wrapper = bin_dir / "vc-frame"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper.chmod(0o755)

    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_VC_FRAME_BIN": str(real),
        "USER": "test",
    }
    proc = subprocess.run(
        [str(wrapper), "-s", "operator", "list-sessions"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "Refusing bare attach to product session" in proc.stderr
    assert "REAL_RAN" not in proc.stdout


def test_wrapper_pins_and_execs_when_frontier_config_present(tmp_path: Path) -> None:
    """With frontier config present, wrapper pins VC_FRAME_CONFIG_DIR and execs real bin."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()
    frontier = xdg / "vetcoders" / "frontier" / "vc-frame"
    frontier.mkdir(parents=True)
    (frontier / "config.kdl").write_text("// product\n", encoding="utf-8")

    real = _write_fake_bin(
        bin_dir,
        "vc-frame.real",
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            printf 'VC_FRAME_CONFIG_DIR=%s\\n' "${VC_FRAME_CONFIG_DIR:-}"
            printf 'args=%s\\n' "$*"
            exit 0
            """
        ),
    )
    wrapper = bin_dir / "vc-frame"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper.chmod(0o755)

    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_VC_FRAME_BIN": str(real),
        "USER": "test",
    }
    proc = subprocess.run(
        [str(wrapper), "attach", "vibecrafted"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert f"VC_FRAME_CONFIG_DIR={frontier}" in proc.stdout
    assert "args=attach vibecrafted" in proc.stdout


def test_wrapper_allows_non_product_session_without_config(tmp_path: Path) -> None:
    """Non-product sessions may run bare without product config (polyversai etc.)."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()
    real = _write_fake_bin(
        bin_dir,
        "vc-frame.real",
        "#!/usr/bin/env bash\necho REAL_RAN args=$*\nexit 0\n",
    )
    wrapper = bin_dir / "vc-frame"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper.chmod(0o755)
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_VC_FRAME_BIN": str(real),
        "USER": "test",
    }
    proc = subprocess.run(
        [str(wrapper), "attach", "polyversai"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "REAL_RAN args=attach polyversai" in proc.stdout


def test_vc_start_probe_pins_product_config(tmp_path: Path) -> None:
    """Exercise real shell vc-start path with PROBE=1 (no TUI attach)."""
    assert HELPER.is_file(), f"missing helper facade {HELPER}"

    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()
    frontier = xdg / "vetcoders" / "frontier" / "vc-frame"
    layout = frontier / "layouts" / "operator.kdl"
    frontier.mkdir(parents=True)
    layout.parent.mkdir(parents=True)
    (frontier / "config.kdl").write_text("// product frontier\n", encoding="utf-8")
    layout.write_text("layout {\n}\n", encoding="utf-8")
    # starship.toml makes frontier_root resolve for sidecar path
    (xdg / "vetcoders" / "frontier" / "starship.toml").write_text(
        "#\n", encoding="utf-8"
    )

    _write_fake_bin(
        bin_dir,
        "vc-frame",
        "#!/usr/bin/env bash\necho should-not-run-in-probe\nexit 99\n",
    )
    _write_fake_bin(bin_dir, "python3", "#!/usr/bin/env bash\nexit 1\n")
    # vibecrafted server status is best-effort — fake that returns non-zero is fine
    _write_fake_bin(
        bin_dir,
        "vibecrafted",
        "#!/usr/bin/env bash\nexit 1\n",
    )

    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_ROOT": str(REPO),
        "VIBECRAFTED_PRODUCT_ENTRY_PROBE": "1",
        "USER": "test",
    }
    env.pop("VC_FRAME_CONFIG_DIR", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    env.pop("VC_FRAME", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    proc = subprocess.run(
        ["bash", "-lc", f'source "{HELPER}"; vc-start'],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        check=False,
    )
    out = proc.stdout + proc.stderr
    scratch = _ensure_scratch()
    (scratch / "vc-start-entry.log").write_text(
        f"returncode={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}\n",
        encoding="utf-8",
    )

    assert proc.returncode == 0, out
    assert "VIBECRAFTED_PRODUCT_ENTRY=1" in proc.stdout
    assert f"VC_FRAME_CONFIG_DIR={frontier}" in proc.stdout
    assert "VC_FRAME_CONFIG_KDL=present" in proc.stdout
    assert "OPERATOR_LAYOUT_PRESENT=1" in proc.stdout
    assert "should-not-run-in-probe" not in out


def test_vc_start_probe_twice_is_stable(tmp_path: Path) -> None:
    """Verification plan: re-run twice for consistent success."""
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    xdg.mkdir()
    bin_dir.mkdir()
    frontier = xdg / "vetcoders" / "frontier" / "vc-frame"
    frontier.mkdir(parents=True)
    (frontier / "layouts").mkdir()
    (frontier / "config.kdl").write_text("// product\n", encoding="utf-8")
    (frontier / "layouts" / "operator.kdl").write_text("layout {}\n", encoding="utf-8")
    (xdg / "vetcoders" / "frontier" / "starship.toml").write_text(
        "#\n", encoding="utf-8"
    )
    _write_fake_bin(bin_dir, "vc-frame", "#!/usr/bin/env bash\nexit 0\n")
    _write_fake_bin(bin_dir, "python3", "#!/usr/bin/env bash\nexit 1\n")
    _write_fake_bin(bin_dir, "vibecrafted", "#!/usr/bin/env bash\nexit 1\n")

    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("VC_FRAME")},
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "VIBECRAFTED_ROOT": str(REPO),
        "VIBECRAFTED_PRODUCT_ENTRY_PROBE": "1",
        "USER": "test",
    }
    env.pop("VC_FRAME_CONFIG_DIR", None)

    outs: list[str] = []
    for _ in range(2):
        proc = subprocess.run(
            ["bash", "-lc", f'source "{HELPER}"; vc-start'],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        outs.append(proc.stdout)
    assert outs[0] == outs[1]
    assert f"VC_FRAME_CONFIG_DIR={frontier}" in outs[0]

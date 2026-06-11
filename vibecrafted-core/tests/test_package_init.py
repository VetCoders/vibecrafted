from __future__ import annotations

import subprocess
import sys


def test_package_import_does_not_preload_spawn_module() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, vibecrafted_core; "
                "raise SystemExit('vibecrafted_core.spawn' in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_spawn_module_runs_without_runpy_preload_warning() -> None:
    result = subprocess.run(
        [sys.executable, "-W", "error", "-m", "vibecrafted_core.spawn", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "found in sys.modules" not in result.stderr

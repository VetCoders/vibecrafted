"""Deck must locate a built scaffold-doctor binary without VIBECRAFTED_ROOT.

Regression for: deck only searched ``${VIBECRAFTED_ROOT}/…`` so
``./scripts/vibecrafted scaffold-doctor`` failed with "binary not found"
even when ``vibecrafted-server/target/debug/scaffold-doctor`` existed.

Follow-up to ``afecda98`` (validator). Path resolution lives in both deck
copies (``scripts/vibecrafted`` and ``vibecrafted_core/deck/vibecrafted``).
Installed PATH (``uv tool`` / staged ``vibecrafted-current``) is a separate
delivery surface — green source does not update the operator's shim until
``make install-python-tools`` (or equivalent force-reinstall) is run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1].parent
SCRIPTS_DECK = REPO_ROOT / "scripts" / "vibecrafted"
PACKAGE_DECK = (
    REPO_ROOT / "vibecrafted-core" / "vibecrafted_core" / "deck" / "vibecrafted"
)
EXPECTED_DEBUG_BIN = (
    REPO_ROOT / "vibecrafted-server" / "target" / "debug" / "scaffold-doctor"
)
CONTROL_CORE_MANIFEST = REPO_ROOT / "vibecrafted-server" / "control-core" / "Cargo.toml"


def _ensure_binary() -> Path:
    if EXPECTED_DEBUG_BIN.is_file() and os.access(EXPECTED_DEBUG_BIN, os.X_OK):
        return EXPECTED_DEBUG_BIN
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo not available to build scaffold-doctor")
    if not CONTROL_CORE_MANIFEST.is_file():
        pytest.skip("control-core Cargo.toml missing — not a full monorepo checkout")
    built = subprocess.run(
        [
            cargo,
            "build",
            "-q",
            "--manifest-path",
            str(CONTROL_CORE_MANIFEST),
            "--bin",
            "scaffold-doctor",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert built.returncode == 0, (
        f"cargo build scaffold-doctor failed:\n{built.stderr}\n{built.stdout}"
    )
    assert EXPECTED_DEBUG_BIN.is_file(), (
        f"expected binary at {EXPECTED_DEBUG_BIN} after cargo build"
    )
    return EXPECTED_DEBUG_BIN


def _run_deck(deck: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("VIBECRAFTED_ROOT", None)
    return subprocess.run(
        [str(deck), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "deck",
    [
        pytest.param(SCRIPTS_DECK, id="scripts/vibecrafted"),
        pytest.param(PACKAGE_DECK, id="deck/vibecrafted"),
    ],
)
def test_deck_locates_built_scaffold_doctor_without_vibecrafted_root(
    deck: Path, tmp_path: Path
) -> None:
    assert deck.is_file(), f"missing deck script: {deck}"
    binary = _ensure_binary()
    assert os.access(binary, os.X_OK)

    # A non-plan directory forces the binary to run. Success criterion is that
    # we do NOT get the old "binary not found" path-resolution failure.
    not_a_plan = tmp_path / "empty-not-a-plan"
    not_a_plan.mkdir()
    result = _run_deck(deck, "scaffold-doctor", "--plan", str(not_a_plan))
    combined = f"{result.stdout}\n{result.stderr}"

    assert "binary not found" not in combined.lower(), (
        "deck failed to locate the built scaffold-doctor binary even though "
        f"{binary} exists.\nexit={result.returncode}\noutput:\n{combined}"
    )
    assert result.returncode == 2, (
        "expected exit 2 (not a plan / refuse cleanly), got "
        f"{result.returncode}\n{combined}"
    )
    assert "manifest.json" in combined.lower() or "not a plan" in combined.lower(), (
        f"expected a clean non-plan refusal, got:\n{combined}"
    )


def test_deck_scaffold_doctor_help_does_not_require_binary() -> None:
    assert SCRIPTS_DECK.is_file()
    result = _run_deck(SCRIPTS_DECK, "scaffold-doctor", "--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout or "Usage:" in result.stderr

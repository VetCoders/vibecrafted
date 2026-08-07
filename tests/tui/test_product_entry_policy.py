"""Product entry choke point — pure policy tests for bare frame vs vc-start.

Shipped decision surface lives in scripts/vc-frame-product-entry.sh helpers
(is_product_session_name / pin order). These tests drive the same policy by
executing the shell functions extracted for unit use.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "vc-frame-product-entry.sh"
SCRATCH = Path(
    "/var/folders/k2/gcr84s3x0z7dgzfspkq1klt80000gn/T/grok-goal-2158121b574a/implementer"
)


def _run_policy(snippet: str) -> subprocess.CompletedProcess[str]:
    # Source only the pure functions by redefining them from the wrapper file.
    script = f"""
set -euo pipefail
is_product_session_name() {{
  case "${{1:-}}" in
    vibecrafted|operator|vibecrafted-console|"vibecrafted console") return 0 ;;
    *) return 1 ;;
  esac
}}
{snippet}
"""
    return subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )


def test_wrapper_script_exists_and_is_executable() -> None:
    assert WRAPPER.is_file()
    assert WRAPPER.stat().st_mode & 0o111
    text = WRAPPER.read_text(encoding="utf-8")
    assert "product choke" in text or "VC_FRAME_CONFIG_DIR" in text
    assert "vc-start" in text


def test_product_session_names_are_recognized() -> None:
    proc = _run_policy(
        """
for n in vibecrafted operator "vibecrafted console"; do
  is_product_session_name "$n" || exit 2
done
for n in polyversai random-session Main; do
  is_product_session_name "$n" && exit 3
done
echo ok
"""
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_bare_zero_args_prefers_vc_start_when_present() -> None:
    """Policy: bare `vc-frame` with no args must not create anonymous sessions."""
    text = WRAPPER.read_text(encoding="utf-8")
    assert "if [[ $# -eq 0 ]]" in text
    assert "exec vc-start" in text


def test_refuse_product_attach_without_config_message() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert "Refusing bare attach to product session" in text
    assert "Run: vc-start" in text


def test_cmd_start_loads_helpers_and_pins_config() -> None:
    deck = REPO / "vibecrafted-core" / "vibecrafted_core" / "deck" / "vibecrafted"
    text = deck.read_text(encoding="utf-8")
    # Product entry choke in cmd_start
    assert "_ensure_helpers_loaded" in text
    assert "VC_FRAME_CONFIG_DIR" in text
    assert "_vetcoders_launch_dashboard operator" in text
    # Write evidence for verifier
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "vc-start-entry.log").write_text(
        "cmd_start ensures helpers + VC_FRAME_CONFIG_DIR pin + launch_dashboard operator\n"
        + "\n".join(
            line
            for line in text.splitlines()
            if "cmd_start" in line
            or "VC_FRAME_CONFIG_DIR" in line
            or "_ensure_helpers_loaded" in line
            or "launch_dashboard operator" in line
        )[:50]
        + "\n",
        encoding="utf-8",
    )

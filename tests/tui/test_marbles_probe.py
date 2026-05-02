from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CORE = REPO_ROOT / "runtime" / "helpers" / "vetcoders-runtime-core.sh"


def test_marbles_emit_probe_detaches_and_keeps_foreground_quiet(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    osascript = fake_bin / "osascript"
    osascript.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "sleep 2",
                'printf "called\\n" >> "$PROBE_CAPTURE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    osascript.chmod(0o755)

    capture = tmp_path / "probe-called.txt"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["PROBE_CAPTURE"] = str(capture)
    env["VIBECRAFTED_MARBLES_PROBE_TTL"] = "10"

    proc = subprocess.run(
        [
            "bash",
            "-lc",
            f'''
            set -euo pipefail
            source "{RUNTIME_CORE}"
            _vetcoders_marbles_emit_probe "{tmp_path}" "marb-123456" "launched"
            ''',
        ],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=1,
    )

    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""

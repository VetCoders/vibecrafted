from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_generic_skill_entry_routes_polarize_count_to_loop_runtime(
    tmp_path: Path,
) -> None:
    capture_file = tmp_path / "polarize-loop-args.txt"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"source {REPO_ROOT / 'runtime' / 'shell' / 'vetcoders.sh'}",
            "_vetcoders_marbles() {",
            '  printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            "}",
            "_vetcoders_skill_entry claude polarize --count 6 --prompt 'choose one truth'",
        ]
    )
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        ["bash", "-lc", script],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload[0] == "claude"
    assert "--count" in payload
    assert payload[payload.index("--count") + 1] == "6"
    assert "--file" in payload
    seed_file = Path(payload[payload.index("--file") + 1])
    prompt = seed_file.read_text(encoding="utf-8")
    assert "Perform the vc-polarize skill on this repository." in prompt
    assert "choose one truth" in prompt

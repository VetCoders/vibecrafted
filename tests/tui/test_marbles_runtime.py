from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _write_fake_marbles_spawn(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _write_replaying_zellij(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import subprocess",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'Path(os.environ["ZELLIJ_CAPTURE_FILE"]).write_text("\\n".join(args) + "\\n", encoding="utf-8")',
                "if args:",
                "    subprocess.run(['/bin/zsh', '-lc', args[-1]], check=True, env=os.environ.copy())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def _run_marbles_prompt(tmp_path: Path, *, inside_zellij: bool) -> list[str]:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "marbles-args.txt"
    zellij_capture_file = tmp_path / "zellij-args.txt"
    spawn_script = (
        crafted_home / "skills" / "vc-agents" / "scripts" / "marbles_spawn.sh"
    )

    home.mkdir()
    fake_bin.mkdir()
    spawn_script.parent.mkdir(parents=True)
    _write_fake_marbles_spawn(spawn_script)
    _write_replaying_zellij(fake_bin / "zellij")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["ZELLIJ_CAPTURE_FILE"] = str(zellij_capture_file)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    operator_session = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])

    if inside_zellij:
        env["ZELLIJ"] = "operator"
        env["ZELLIJ_PANE_ID"] = "terminal_7"
        env["ZELLIJ_SESSION_NAME"] = operator_session
    else:
        env["VIBECRAFTED_OPERATOR_SESSION"] = operator_session

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'claude-marbles --count 1 --prompt "weź i vc-justdo wszystko co marbles znajdzie"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    return capture_file.read_text(encoding="utf-8").splitlines()


def test_vc_marbles_preserves_prompt_as_single_argument_inside_zellij(
    tmp_path: Path,
) -> None:
    payload = _run_marbles_prompt(tmp_path, inside_zellij=True)

    assert "--agent" in payload
    assert "claude" in payload
    assert "--count" in payload
    assert "1" in payload
    assert "--prompt" in payload
    assert "weź i vc-justdo wszystko co marbles znajdzie" in payload


def test_vc_marbles_preserves_prompt_as_single_argument_in_operator_session(
    tmp_path: Path,
) -> None:
    payload = _run_marbles_prompt(tmp_path, inside_zellij=False)

    assert "--agent" in payload
    assert "claude" in payload
    assert "--count" in payload
    assert "1" in payload
    assert "--prompt" in payload
    assert "weź i vc-justdo wszystko co marbles znajdzie" in payload

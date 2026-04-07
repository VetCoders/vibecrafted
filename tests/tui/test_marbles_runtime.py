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


def test_vetcoders_shell_quote_join_stays_utf8_clean_for_multiline_prompt(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["PROMPT_PAYLOAD"] = (
        "Siemka! weź i zażółć gęślą jaźń.\n"
        "_Run inside zellij - if there is any open window attach to it._\n"
        "Don't drop UTF-8 on the floor."
    )

    quoted = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; _vetcoders_shell_quote_join "$PROMPT_PAYLOAD"',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
    ).stdout.decode("utf-8")

    roundtrip_script = tmp_path / "roundtrip.sh"
    roundtrip_script.write_text(
        f"#!/usr/bin/env bash\nprintf %s {quoted}\n",
        encoding="utf-8",
    )
    roundtrip_script.chmod(0o755)

    roundtrip = subprocess.run(
        ["bash", str(roundtrip_script)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
    ).stdout.decode("utf-8")

    assert roundtrip == env["PROMPT_PAYLOAD"]


def test_parse_contract_treats_everything_after_prompt_as_prompt_block() -> None:
    env = os.environ.copy()
    env["PROMPT_HEAD"] = "Portable musi działać."

    payload = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                '_vetcoders_parse_contract --count 8 --prompt "$PROMPT_HEAD" '
                "--runtime headless --depth 99; "
                'printf "COUNT=%s\\n" "$_vetcoders_contract_count"; '
                'printf "RUNTIME=%s\\n" "$_vetcoders_contract_runtime"; '
                'printf "DEPTH=%s\\n" "$_vetcoders_contract_depth"; '
                'printf "PROMPT=%s\\n" "$_vetcoders_contract_prompt"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    ).stdout

    lines = dict(line.split("=", 1) for line in payload.strip().splitlines())
    assert lines["COUNT"] == "8"
    assert lines["RUNTIME"] == ""
    assert lines["DEPTH"] == ""
    assert lines["PROMPT"] == "Portable musi działać. --runtime headless --depth 99"

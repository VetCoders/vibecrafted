from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _write_fake_atuin(bin_dir: Path, capture_file: Path) -> Path:
    script = bin_dir / "atuin"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'capture = Path(os.environ["CAPTURE_FILE"])',
                'home = os.environ["HOME"]',
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("CALL " + " ".join(args) + "\\n")',
                'if args[:1] == ["search"]:',
                "    cwd = None",
                "    interactive = False",
                "    cmd_only = False",
                "    i = 0",
                "    while i < len(args):",
                "        arg = args[i]",
                '        if arg in ("-c", "--cwd") and i + 1 < len(args):',
                "            cwd = args[i + 1]",
                "            i += 1",
                '        elif arg in ("-i", "--interactive", "--shell-up-key-binding"):',
                "            interactive = True",
                '        elif arg == "--cmd-only":',
                "            cmd_only = True",
                "        i += 1",
                "    if interactive and cwd == home:",
                '        print("home-interactive-hit", end="")',
                "    elif interactive:",
                '        print("repo-interactive-hit", end="")',
                "    elif cmd_only and cwd == home:",
                '        print("home-suggestion", end="")',
                "    elif cmd_only:",
                '        print("", end="")',
                "    elif cwd == home:",
                '        print("home-search-hit", end="")',
                "    else:",
                '        print("", end="")',
                "    sys.exit(0)",
                'if args[:1] == ["uuid"]:',
                '    print("uuid-1", end="")',
                "    sys.exit(0)",
                "sys.exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_atuin_interactive_search_falls_back_to_home_scope(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "project"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "atuin.log"

    home.mkdir()
    project.mkdir()
    fake_bin.mkdir()
    fake_atuin = _write_fake_atuin(fake_bin, capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ATUIN_BIN"] = str(fake_atuin)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'ATUIN_QUERY="deploy" atuin search --shell-up-key-binding -i'
            ),
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == "home-interactive-hit"
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == [
        "CALL search --cmd-only --limit 1",
        "CALL search --cwd " + str(home) + " --shell-up-key-binding -i",
    ]


def test_atuin_noninteractive_search_respects_explicit_scope(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "project"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "atuin.log"
    scoped_dir = tmp_path / "elsewhere"

    home.mkdir()
    project.mkdir()
    fake_bin.mkdir()
    scoped_dir.mkdir()
    fake_atuin = _write_fake_atuin(fake_bin, capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ATUIN_BIN"] = str(fake_atuin)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; atuin search --cmd-only --cwd "{scoped_dir}"',
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == [f"CALL search --cmd-only --cwd {scoped_dir}"]


def test_atuin_noninteractive_search_falls_back_to_home_scope(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "project"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "atuin.log"

    home.mkdir()
    project.mkdir()
    fake_bin.mkdir()
    fake_atuin = _write_fake_atuin(fake_bin, capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ATUIN_BIN"] = str(fake_atuin)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; atuin search --cmd-only',
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == "home-suggestion"
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == [
        "CALL search --cmd-only",
        "CALL search --cwd " + str(home) + " --cmd-only",
    ]

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "vibecrafted"


def _write_fake_agent(bin_dir: Path, name: str, capture_file: Path) -> None:
    script = bin_dir / name
    script.write_text(
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
    script.chmod(0o755)


def _write_fake_command(bin_dir: Path, name: str, capture_file: Path) -> None:
    script = bin_dir / name
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "%s\\n" "$@"',
                '  printf "ZELLIJ_CONFIG_DIR=%s\\n" "${ZELLIJ_CONFIG_DIR:-}"',
                '} > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_stateful_zellij(
    bin_dir: Path, capture_file: Path, session_state_file: Path
) -> None:
    default_session = _expected_operator_session()
    script = bin_dir / "zellij"
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
                'state_file = Path(os.environ["SESSION_STATE_FILE"])',
                'state = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else "missing"',
                f'session = os.environ.get("FAKE_ZELLIJ_SESSION", "{default_session}")',
                'if "--session" in args:',
                '    idx = args.index("--session")',
                "    if idx + 1 < len(args):",
                "        session = args[idx + 1]",
                'elif args[:1] == ["attach"] and len(args) > 1:',
                "    session = args[-1]",
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("ZELLIJ " + " ".join(args) + "\\n")',
                'if args[:1] == ["ls"]:',
                '    if state == "live":',
                '        print(f"{session} [Created 1m ago]")',
                '    elif state == "dead":',
                '        print(f"{session} [Created 1m ago] (EXITED - attach to resurrect)")',
                "    sys.exit(0)",
                'if args[:1] == ["attach"]:',
                '    if "--force-run-commands" in args:',
                '        state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if args[:1] == ["delete-session"]:',
                '    state_file.write_text("missing", encoding="utf-8")',
                "    sys.exit(0)",
                'if "--new-session-with-layout" in args:',
                '    state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if "action" in args and ("new-pane" in args or "new-tab" in args):',
                "    sys.exit(0)",
                "sys.exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_fake_osascript(
    bin_dir: Path, capture_file: Path, session_state_file: Path
) -> None:
    script = bin_dir / "osascript"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "payload = sys.stdin.read()",
                'capture = Path(os.environ["CAPTURE_FILE"])',
                'state_file = Path(os.environ["SESSION_STATE_FILE"])',
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("OSA " + payload.replace("\\n", "\\\\n") + "\\n")',
                'if "new-session-with-layout" in payload or "attach --force-run-commands" in payload:',
                '    state_file.write_text("live", encoding="utf-8")',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _spawned_command_script(capture_payload: str) -> Path:
    match = re.search(r"ZELLIJ .* action new-tab .* -- (\S+)", capture_payload)
    assert match, capture_payload
    return Path(match.group(1))


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def test_init_claude_uses_interactive_tab_without_print_mode(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)
    _write_fake_agent(fake_bin, "claude", tmp_path / "unused-claude.txt")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    # Sanitize real zellij env to prevent leaks from the host session.
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "init", "claude"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    # When zellij operator session exists, spawn routes directly through zellij
    # without opening a new terminal via osascript.
    assert f"ZELLIJ --session {_expected_operator_session()} action new-tab" in payload

    command_script = _spawned_command_script(payload)
    script_body = command_script.read_text(encoding="utf-8")
    assert "claude --verbose --dangerously-skip-permissions " in script_body
    assert "/vc-init" in script_body
    assert " -p " not in script_body


def test_init_codex_uses_interactive_tab_without_exec_mode(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)
    _write_fake_agent(fake_bin, "codex", tmp_path / "unused-codex.txt")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    # Sanitize real zellij env to prevent leaks from the host session.
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "init", "codex"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    # When zellij operator session exists, spawn routes directly through zellij
    # without opening a new terminal via osascript.
    assert f"ZELLIJ --session {_expected_operator_session()} action new-tab" in payload

    command_script = _spawned_command_script(payload)
    script_body = command_script.read_text(encoding="utf-8")
    assert "codex --dangerously-bypass-approvals-and-sandbox " in script_body
    assert "/vc-init" in script_body
    assert "codex exec" not in script_body


def test_vc_help_wrapper_symlink_renders_main_help(tmp_path: Path) -> None:
    wrapper = tmp_path / "vc-help"
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        ["bash", str(wrapper)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in result.stdout
    assert "Front door:" in result.stdout
    assert "vibecrafted dashboard" in result.stdout
    assert "Start here:" in result.stdout
    assert 'vibecrafted hydrate codex --prompt "Package the product"' in result.stdout
    assert "Dashboard is optional" in result.stdout


def test_repo_launcher_is_directly_executable() -> None:
    expected_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    result = subprocess.run(
        [str(LAUNCHER), "help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in result.stdout
    assert expected_version in result.stdout
    assert "vibecrafted dashboard" in result.stdout
    assert 'vibecrafted hydrate codex --prompt "Package the product"' in result.stdout
    assert "START_HERE.md" in result.stdout


def test_skill_subcommand_help_is_human_readable_without_agent() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "justdo", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "justdo" in result.stdout
    assert "Autonomous end-to-end implementation" in result.stdout
    assert "vibecrafted justdo <claude|codex|gemini> [flags]" in result.stdout
    assert "vibecrafted implement <agent> [flags]" in result.stdout


def test_skill_wrapper_help_is_human_readable_without_agent(tmp_path: Path) -> None:
    wrapper = tmp_path / "vc-followup"
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        [str(wrapper), "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "followup" in result.stdout
    assert "Post-implementation audit" in result.stdout
    assert "vc-followup <claude|codex|gemini> [flags]" in result.stdout


def test_agent_subcommand_help_lists_modes() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "codex", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "Plan-based helper modes for codex." in result.stdout
    assert "implement <plan.md>" in result.stdout
    assert "observe   --last" in result.stdout


def test_dashboard_subcommand_launches_repo_owned_zellij_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ_CONFIG_DIR", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "dashboard"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert f"{_expected_operator_session()}-dashboard" in payload
    assert "--new-session-with-layout" in payload
    assert (
        str(REPO_ROOT / "config" / "zellij" / "layouts" / "vc-dashboard.kdl") in payload
    )
    assert f"ZELLIJ_CONFIG_DIR={REPO_ROOT / 'config' / 'zellij'}" in payload


def test_start_subcommand_launches_operator_entrypoint_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ_CONFIG_DIR", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "start"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert _expected_operator_session() in payload
    assert "--new-session-with-layout" in payload
    assert (
        str(REPO_ROOT / "config" / "zellij" / "layouts" / "vibecrafted.kdl") in payload
    )
    assert f"ZELLIJ_CONFIG_DIR={REPO_ROOT / 'config' / 'zellij'}" in payload


def test_resume_subcommand_forwards_session_and_prompt_to_agent(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "codex-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_agent(fake_bin, "codex", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "resume",
            "codex",
            "--session",
            "resume-session-123",
            "--prompt",
            "Continue the fix",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["resume", "resume-session-123", "Continue the fix"]


def test_resume_wrapper_symlink_forwards_session_and_prompt_to_agent(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "codex-args.txt"
    wrapper = tmp_path / "vc-resume"

    home.mkdir()
    fake_bin.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_fake_agent(fake_bin, "codex", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        [
            "bash",
            str(wrapper),
            "codex",
            "--session",
            "resume-session-456",
            "--prompt",
            "Continue from wrapper",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["resume", "resume-session-456", "Continue from wrapper"]

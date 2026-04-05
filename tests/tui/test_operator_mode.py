from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _write_capture_command(bin_dir: Path, name: str, capture_file: Path) -> None:
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


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def test_vc_start_launches_operator_entrypoint_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env.pop("ZELLIJ_CONFIG_DIR", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-start'],
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


def test_marbles_from_operator_mode_spawns_launcher_below_and_loops_right(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["ZELLIJ"] = "operator"
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env["ZELLIJ_SESSION_NAME"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])

    subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; codex-marbles --prompt "Check runtime" --count 2',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--direction" in payload
    assert "down" in payload
    next(line for line in payload if "marbles_spawn.sh" in line)


def test_vc_start_resume_resurrects_dead_session(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    session_state_file.write_text("dead", encoding="utf-8")
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-start resume'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    assert (
        f"ZELLIJ attach --force-run-commands {_expected_operator_session()}" in payload
    )


def test_vc_dashboard_recreates_dead_run_id_session_without_layout_suffix(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    session_state_file.write_text("dead", encoding="utf-8")
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-dashboard vc-marbles'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    expected_session = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    assert f"attach --force-run-commands {expected_session}" in payload
    assert f"{expected_session}-marbles" not in payload


def test_skill_bootstraps_operator_session_before_spawning(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)
    _write_capture_command(fake_bin, "codex", tmp_path / "unused-codex.txt")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; codex-followup --prompt "Check runtime"',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    assert "OSA " in payload
    assert "new-session-with-layout" in payload
    assert re.search(rf"{re.escape(REPO_ROOT.name.lower())}-fwup-\d{{6}}", payload)


def test_skill_bootstraps_fresh_operator_session_when_existing_one_is_dead(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    session_state_file.write_text("dead", encoding="utf-8")
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["VIBECRAFTED_RUN_ID"] = "fwup-014520"
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "_vetcoders_prepare_operator_runtime terminal; "
                'printf "%s\\n" "$VIBECRAFTED_OPERATOR_SESSION"'
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    expected_session = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    assert result.returncode == 0
    assert result.stdout.strip().endswith(expected_session)
    payload = capture_file.read_text(encoding="utf-8")
    assert "attach --force-run-commands" in payload and expected_session in payload
    assert "OSA " in payload
    # Session name appears in the osascript zellij command (possibly escaped)
    assert expected_session in payload

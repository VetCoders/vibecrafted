from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"


def _write_capture_command(bin_dir: Path, name: str, capture_file: Path) -> None:
    script_names = [name]
    if name == "vc-frame":
        script_names.insert(0, "vc-frame")
    for script_name in script_names:
        script = bin_dir / script_name
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


def _write_stateful_vc_frame(
    bin_dir: Path, capture_file: Path, session_state_file: Path
) -> None:
    default_session = _expected_operator_session()
    script = bin_dir / "vc-frame"
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
                f'session = os.environ.get("FAKE_VC_FRAME_SESSION", "{default_session}")',
                'if "--session" in args:',
                '    idx = args.index("--session")',
                "    if idx + 1 < len(args):",
                "        session = args[idx + 1]",
                'elif args[:1] == ["attach"] and len(args) > 1:',
                "    session = args[-1]",
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("VC_FRAME " + " ".join(args) + "\\n")',
                'if args[:1] == ["ls"]:',
                '    if state == "live":',
                '        print(f"{session} [Created 1m ago]")',
                '    elif state == "dead":',
                '        print(f"{session} [Created 1m ago] (EXITED - attach to resurrect)")',
                "    sys.exit(0)",
                # list-sessions feeds spawn_session_is_live (awk drops EXITED), so it
                # only needs to report a LIVE session. Emitting an EXITED line here
                # regresses the dead-session recreate tests, which rely on the
                # ls-based recovery path; keep list-sessions live-only.
                'if args[:1] == ["list-sessions"]:',
                '    if state == "live":',
                '        print(f"{session} [Created 1m ago]")',
                "    sys.exit(0)",
                'if args[:1] == ["attach"]:',
                '    if "--force-run-commands" in args:',
                '        state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if args[:1] == ["kill-session"]:',
                '    state_file.write_text("missing", encoding="utf-8")',
                "    sys.exit(0)",
                'if args[:1] == ["delete-session"]:',
                '    state_file.write_text("missing", encoding="utf-8")',
                "    sys.exit(0)",
                'if "--new-session-with-layout" in args:',
                '    state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if "action" in args and ("new-pane" in args or "new-tab" in args):',
                '    if state != "live":',
                '        print("There is no active session!", file=sys.stderr)',
                "        sys.exit(1)",
                "    sys.exit(0)",
                "sys.exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    vc_frame = bin_dir / "vc-frame"
    vc_frame.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    vc_frame.chmod(0o755)


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


def _org_repo() -> str:
    remote = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    match = re.search(r"[:/]([^/]+)/([^/.]+)(?:\.git)?$", remote)
    assert match
    return f"{match.group(1)}/{match.group(2)}"


def test_vc_start_launches_operator_entrypoint_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_command(fake_bin, "vc-frame", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME_CONFIG_DIR", None)
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)

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
        str(REPO_ROOT / "config" / "vc-frame" / "layouts" / "operator.kdl") in payload
    )


def test_operator_console_first_screen_is_actionable() -> None:
    payload = (
        REPO_ROOT
        / "runtime"
        / "vc-operator"
        / "mission-control"
        / "operator-console.sh"
    ).read_text(encoding="utf-8")

    expected_fragments = [
        "Vibecrafted Operator",
        "vc-start",
        "vibecrafted workflow codex --prompt",
        "vibecrafted implement codex --file",
        "vibecrafted research --prompt",
        "vibecrafted codex observe --run-id",
        "vibecrafted codex await --run-id",
        "~/.vibecrafted/artifacts",
        "close terminal: detach",
        "Ctrl+q: quit intentionally",
    ]

    for fragment in expected_fragments:
        assert fragment in payload


def test_helper_exports_vc_skill_wrappers() -> None:
    expected_wrappers = [
        "vc-agents",
        "vc-audit",
        "vc-decorate",
        "vc-delegate",
        "vc-dou",
        "vc-followup",
        "vc-hydrate",
        "vc-init",
        "vc-intents",
        "vc-justdo",
        "vc-marbles",
        "vc-ownership",
        "vc-partner",
        "vc-prune",
        "vc-release",
        "vc-review",
        "vc-scaffold",
        "vc-workflow",
    ]
    command = f'source "{HELPER_SCRIPT}"; ' + " ".join(
        f"command -v {wrapper} >/dev/null || {{ echo missing:{wrapper} >&2; exit 1; }};"
        for wrapper in expected_wrappers
    )

    result = subprocess.run(
        ["bash", "-lc", command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_vc_init_finds_bundled_vc_frame_and_creates_missing_operator_session(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    bundled_bin = runtime_home / "bin"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    bundled_bin.mkdir(parents=True)
    fake_bin.mkdir()
    _write_stateful_vc_frame(bundled_bin, capture_file, session_state_file)
    (fake_bin / "osascript").write_text(
        "#!/usr/bin/env bash\nexit 1\n", encoding="utf-8"
    )
    (fake_bin / "osascript").chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session()
    # This test exercises the real session-create path; allow it without a TTY.
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    # Scrub any operator-session context leaked from a running operator shell so
    # the runtime computes a fresh session instead of latching onto the ambient one.
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("VIBECRAFTED_OPERATOR_MODE", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; vc-init claude --prompt "Check runtime"',
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8")
    expected_session = _expected_operator_session()
    assert f"--session {expected_session} --new-session-with-layout" in payload
    assert f"--session {expected_session} action new-tab" in payload
    assert "There is no active session!" not in result.stderr


def test_vc_init_missing_vc_frame_message_has_fresh_install_path_hint(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"

    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; vc-init claude --prompt "Check runtime"',
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "vc-frame is required for the Vibecrafted operator runtime." in result.stderr
    assert (
        f"Expected vc-frame on PATH or bundled at: {home}/.local/share/vibecrafted/bin/vc-frame"
        in result.stderr
    )


def test_marbles_from_operator_mode_spawns_launcher_in_fresh_tab_and_loops_right(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_capture_command(fake_bin, "vc-frame", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VC_FRAME"] = "operator"
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env["VIBECRAFTED_MARBLES_RUN_ID"] = "marb-014520"
    env["VC_FRAME_SESSION_NAME"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
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
    assert "new-tab" in payload
    assert "--name" in payload
    assert "marbles" in payload
    assert "vibecrafted-marb-014520" in payload


def test_marbles_inside_vc_frame_uses_bundled_vc_frame_priority(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    runtime_home = home / ".local" / "share" / "vibecrafted"
    bundled_bin = runtime_home / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"

    home.mkdir()
    bundled_bin.mkdir(parents=True)
    _write_capture_command(bundled_bin, "vc-frame", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["PATH"] = os.defpath
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VC_FRAME"] = "operator"
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env["VIBECRAFTED_MARBLES_RUN_ID"] = "marb-014520"
    env["VC_FRAME_SESSION_NAME"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])

    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            (
                f'source "{HELPER_SCRIPT}"; '
                'codex-marbles --prompt "Check runtime" --count 2 && '
                'printf "PATH=%s\\n" "$PATH"'
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    payload = capture_file.read_text(encoding="utf-8")
    assert "new-tab" in payload
    assert result.stdout.endswith(f"PATH={os.defpath}\n")


def test_marbles_manual_spawn_emits_probe_without_l1_transcript_tail(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "vc_frame-args.txt"
    run_id = "marb-424242"
    transcript = tmp_path / "l1.transcript.log"
    reports_dir = (
        home
        / ".vibecrafted"
        / "artifacts"
        / _org_repo()
        / datetime.now().strftime("%Y_%m%d")
        / "marbles"
        / "reports"
    )
    meta = reports_dir / "fixture.meta.json"

    home.mkdir()
    fake_bin.mkdir()
    reports_dir.mkdir(parents=True)
    _write_capture_command(fake_bin, "vc-frame", capture_file)
    (fake_bin / "osascript").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    (fake_bin / "osascript").chmod(0o755)

    transcript.write_text(
        "\n".join(f"line {idx}" for idx in range(1, 21)) + "\n",
        encoding="utf-8",
    )
    meta.write_text(
        json.dumps(
            {
                "run_id": f"{run_id}-001",
                "transcript": str(transcript),
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VC_FRAME"] = "operator"
    env["VIBECRAFTED_RUN_ID"] = "marb-014521"
    env["VC_FRAME_SESSION_NAME"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    env["VIBECRAFTED_MARBLES_RUN_ID"] = run_id
    env["VIBECRAFTED_MARBLES_PROBE_TTL"] = "10"
    env["VIBECRAFTED_PREFER_REPO_SPAWN"] = "1"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; codex-marbles --prompt "Check runtime" --count 2',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "--- marbles L1 transcript tail" not in result.stdout
    assert "line 6" not in result.stdout
    assert "line 20" not in result.stdout
    assert result.stderr == ""


def test_spawn_script_prefers_repo_runtime_over_installed_copy(tmp_path: Path) -> None:
    home = tmp_path / "home"
    installed = home / ".vibecrafted" / "skills" / "vc-agents" / "scripts"

    installed.mkdir(parents=True)
    (installed / "marbles_spawn.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_PREFER_REPO_SPAWN"] = "1"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                "_vetcoders_spawn_script claude marbles_spawn.sh"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == str(
        REPO_ROOT / "runtime" / "scripts" / "marbles_spawn.sh"
    )


def test_vc_start_resume_resurrects_dead_session(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    session_state_file.write_text("dead", encoding="utf-8")
    _write_stateful_vc_frame(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session()
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)

    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-start resume'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    payload = capture_file.read_text(encoding="utf-8")
    # Dead sessions are recovery evidence: preserve them and launch a fresh
    # frame session with the layout file.
    expected = _expected_operator_session()
    created = re.search(r"creating '([^']+)'", result.stderr)
    assert created is not None
    recovery_session = created.group(1)
    assert f"Session '{expected}' is dead; preserving it" in result.stderr
    assert recovery_session != expected
    assert f"kill-session {expected}" not in payload
    assert f"--session {recovery_session}" in payload
    assert "--new-session-with-layout" in payload


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
    _write_stateful_vc_frame(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    # Scrub any operator-session context leaked from a running operator shell so
    # the dashboard resolves the run-id session rather than the ambient one.
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("VIBECRAFTED_OPERATOR_MODE", None)

    result = subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-dashboard vc-marbles'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    payload = capture_file.read_text(encoding="utf-8")
    expected_session = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    # Dead sessions are preserved; a fresh recovery session gets the layout.
    created = re.search(r"creating '([^']+)'", result.stderr)
    assert created is not None
    recovery_session = created.group(1)
    assert f"Session '{expected_session}' is dead; preserving it" in result.stderr
    assert recovery_session != expected_session
    assert f"kill-session {expected_session}" not in payload
    assert f"--session {recovery_session}" in payload
    assert "--new-session-with-layout" in payload
    assert f"{expected_session}-marbles" not in payload


def test_skill_bootstraps_operator_session_before_spawning(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = home / ".local" / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir(parents=True)
    _write_stateful_vc_frame(fake_bin, capture_file, session_state_file)
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
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session()
    # This test exercises the real session-bootstrap path; allow it without a TTY.
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    # Scrub any operator-session context leaked from a running operator shell so
    # the runtime bootstraps a session instead of latching onto the ambient one.
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("VIBECRAFTED_OPERATOR_MODE", None)

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
    assert "OSA " not in payload
    assert "VC_FRAME ls" in payload
    assert f"--session {_expected_operator_session()}" in payload
    assert "--new-session-with-layout" in payload
    assert "vc-spawn-cmd" in payload
    assert re.search(r"\bfwup-\d{6}-\d+\b", payload)


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
    _write_stateful_vc_frame(fake_bin, capture_file, session_state_file)
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
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])
    # This test exercises the real dead-session recreate path; allow it without a TTY.
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)
    # Scrub any operator-session context leaked from a running operator shell so
    # the runtime recreates the dead run-id session instead of reusing the ambient one.
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("VIBECRAFTED_OPERATOR_MODE", None)

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
    created = re.search(r"creating '([^']+)'", result.stderr)
    assert created is not None
    recovery_session = created.group(1)
    assert result.stdout.strip() == recovery_session
    payload = capture_file.read_text(encoding="utf-8")
    assert f"Session '{expected_session}' is dead; preserving it" in result.stderr
    assert f"kill-session {expected_session}" not in payload
    assert (
        str(REPO_ROOT / "config" / "vc-frame" / "layouts" / "operator.kdl") in payload
    )
    assert "--new-session-with-layout" in payload and recovery_session in payload
    assert "OSA " not in payload


def test_dashboard_alt_layout_reuses_live_repo_session_instead_of_layout_session(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    session_state_file.write_text("live", encoding="utf-8")
    _write_stateful_vc_frame(fake_bin, capture_file, session_state_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["FAKE_VC_FRAME_SESSION"] = _expected_operator_session()
    env["VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME"] = "1"
    env.pop("VC_FRAME", None)
    env.pop("VC_FRAME_PANE_ID", None)
    env.pop("VC_FRAME_SESSION_NAME", None)

    subprocess.run(
        ["bash", "-lc", f'source "{HELPER_SCRIPT}"; vc-dashboard vc-marbles'],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    expected_session = _expected_operator_session()
    assert f"--session {expected_session} action new-tab --layout" in payload
    assert f"attach {expected_session}" in payload
    assert "--new-session-with-layout" not in payload
    assert f"{expected_session}-marbles" not in payload

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from scripts import vetcoders_install

REPO_ROOT = Path(__file__).resolve().parents[2]
SHELL_SH = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"


def _write_fake_command(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_resume_terminal_runtime_routes_codex_resume_into_vc_frame(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    vc_frame_capture = tmp_path / "vc_frame.txt"
    codex_capture = tmp_path / "codex.txt"
    fake_bin.mkdir()
    home.mkdir()

    _write_fake_command(
        fake_bin / "vc-frame",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "%s\\n" "--CALL--"',
                '  printf "%s\\n" "$@"',
                '} >> "$VC_FRAME_CAPTURE"',
            ]
        )
        + "\n",
    )
    _write_fake_command(
        fake_bin / "codex",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CODEX_CAPTURE"',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    for key in (
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_RUN_LOCK",
        "VIBECRAFTED_SKILL_CODE",
        "VIBECRAFTED_SKILL_NAME",
        "VIBECRAFTED_LOOP_NR",
        "VC_FRAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_SESSION_NAME",
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_OPERATOR_SESSION"] = "operator-session"
    env["VC_FRAME_CAPTURE"] = str(vc_frame_capture)
    env["CODEX_CAPTURE"] = str(codex_capture)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume codex --runtime terminal "
                "--session sess-123 --prompt 'carry on'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    # Explicit VIBECRAFTED_OPERATOR_SESSION wins over the repo-derived name
    # (W1-06: honour explicit operator session in vc-frame targeting).
    assert "Resume launched in operator session: operator-session" in result.stdout
    assert not codex_capture.exists()
    vc_frame_lines = vc_frame_capture.read_text(encoding="utf-8").splitlines()
    calls: list[list[str]] = []
    current: list[str] = []
    for line in vc_frame_lines:
        if line == "--CALL--":
            if current:
                calls.append(current)
            current = []
        else:
            current.append(line)
    if current:
        calls.append(current)
    new_tab_call = next(call for call in calls if call[2:4] == ["action", "new-tab"])
    assert new_tab_call[:5] == [
        "--session",
        "operator-session",
        "action",
        "new-tab",
        "--name",
    ]
    assert "resume-codex" in new_tab_call
    command_script = Path(new_tab_call[-1])
    command_body = command_script.read_text(encoding="utf-8")
    assert "codex resume sess-123" in command_body
    assert "carry on" in command_body


def test_resume_headless_routes_codex_through_exec(tmp_path: Path) -> None:
    """With no operator session / tty (piped, or async-supervisor baton-pass),
    resume must run the NON-INTERACTIVE invocation `codex exec resume`, not the
    interactive `codex resume` (which would hang under eval). This is the path the
    operator hit when they had to drop to raw `codex exec ... resume`."""
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    codex_capture = tmp_path / "codex.txt"
    fake_bin.mkdir()
    home.mkdir()

    _write_fake_command(
        fake_bin / "codex",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CODEX_CAPTURE"',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    for key in (
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_RUN_LOCK",
        "VIBECRAFTED_SKILL_CODE",
        "VIBECRAFTED_SKILL_NAME",
        "VIBECRAFTED_LOOP_NR",
        "VC_FRAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_SESSION_NAME",
        "VIBECRAFTED_OPERATOR_SESSION",
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["CODEX_CAPTURE"] = str(codex_capture)

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume codex --runtime terminal "
                "--session sess-123 --prompt 'carry on'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert codex_capture.exists(), "headless resume must invoke codex directly"
    args = codex_capture.read_text(encoding="utf-8")
    assert "exec" in args, (
        "headless resume must use `codex exec`, not interactive `codex resume`"
    )
    assert "resume" in args
    assert "sess-123" in args
    assert "carry on" in args


def test_fork_session_terminal_routes_codex_through_native_fork_with_file(
    tmp_path: Path,
) -> None:
    """A visible Codex fork must create a new lineage branch and seed its
    first turn from --file. It must never degrade to a normal resume."""
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    vc_frame_capture = tmp_path / "vc_frame.txt"
    prompt_file = tmp_path / "handoff.md"
    fake_bin.mkdir()
    home.mkdir()
    prompt_file.write_text("Build the crew dashboard from our shared history.\n")

    _write_fake_command(
        fake_bin / "vc-frame",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "%s\\n" "--CALL--"',
                '  printf "%s\\n" "$@"',
                '} >> "$VC_FRAME_CAPTURE"',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    for key in (
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_RUN_LOCK",
        "VIBECRAFTED_SKILL_CODE",
        "VIBECRAFTED_SKILL_NAME",
        "VIBECRAFTED_LOOP_NR",
        "VC_FRAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_SESSION_NAME",
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VIBECRAFTED_OPERATOR_SESSION"] = "operator-session"
    env["VC_FRAME_CAPTURE"] = str(vc_frame_capture)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume codex --runtime terminal --fork-session "
                f"--session parent-session-123 --file '{prompt_file}'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "Fork launched in operator session: operator-session" in result.stdout
    lines = vc_frame_capture.read_text(encoding="utf-8").splitlines()
    calls: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line == "--CALL--":
            if current:
                calls.append(current)
            current = []
        else:
            current.append(line)
    if current:
        calls.append(current)
    new_tab_call = next(call for call in calls if call[2:4] == ["action", "new-tab"])
    assert "fork-codex" in new_tab_call
    command_body = Path(new_tab_call[-1]).read_text(encoding="utf-8")
    assert (
        "codex --dangerously-bypass-approvals-and-sandbox fork parent-session-123"
        in command_body
    )
    assert "Build the crew dashboard from our shared history." in command_body
    assert "codex resume" not in command_body


def test_fork_session_headless_codex_fails_closed(tmp_path: Path) -> None:
    """Codex exposes fork only through the interactive TUI. A headless runner
    must refuse instead of silently resuming the parent session."""
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    codex_capture = tmp_path / "codex.txt"
    fake_bin.mkdir()
    home.mkdir()
    _write_fake_command(
        fake_bin / "codex",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\n" "$@" > "$CODEX_CAPTURE"\n',
    )

    env = os.environ.copy()
    for key in (
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_SESSION_NAME",
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CODEX_CAPTURE"] = str(codex_capture)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume codex --fork-session --session parent-session-123 "
                "--prompt 'start the branch'"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Codex --fork-session requires a visible terminal runtime" in result.stderr
    assert not codex_capture.exists()


def test_fork_session_headless_claude_uses_native_flag(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    claude_capture = tmp_path / "claude.txt"
    fake_bin.mkdir()
    home.mkdir()
    _write_fake_command(
        fake_bin / "claude",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\n" "$@" > "$CLAUDE_CAPTURE"\n',
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CLAUDE_CAPTURE"] = str(claude_capture)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume claude --fork-session --session parent-session-456 "
                "--prompt 'start the branch'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert claude_capture.read_text(encoding="utf-8").splitlines() == [
        "--print",
        "--dangerously-skip-permissions",
        "--fork-session",
        "--resume",
        "parent-session-456",
        "start the branch",
    ]


def test_fork_session_headless_grok_uses_native_flag(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    grok_capture = tmp_path / "grok.txt"
    fake_bin.mkdir()
    home.mkdir()
    _write_fake_command(
        fake_bin / "grok",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\n" "$@" > "$GROK_CAPTURE"\n',
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["GROK_CAPTURE"] = str(grok_capture)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume grok --fork-session --session parent-session-654 "
                "--prompt 'start the branch'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    args = grok_capture.read_text(encoding="utf-8").splitlines()
    assert args[:3] == ["--resume", "parent-session-654", "--fork-session"]
    assert "--single" in args
    assert "start the branch" in args


def test_fork_session_rejects_agent_without_native_fork(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume agy --fork-session --session parent-session-789"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "agy does not support --fork-session" in result.stderr


def test_resume_headless_agy_uses_conversation_contract(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    agy_capture = tmp_path / "agy.txt"
    fake_bin.mkdir()
    home.mkdir()
    _write_fake_command(
        fake_bin / "agy",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf "%s\\n" "$@" > "$AGY_CAPTURE"\n',
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["AGY_CAPTURE"] = str(agy_capture)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-resume agy --session 334a67b1-56ae-448a-9a88-0668ff48262c "
                "--prompt 'continue the runtime research'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert agy_capture.read_text(encoding="utf-8").splitlines() == [
        "--dangerously-skip-permissions",
        "--conversation",
        "334a67b1-56ae-448a-9a88-0668ff48262c",
        "--print",
        "continue the runtime research",
    ]


def test_fork_session_is_rejected_outside_resume(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{SHELL_SH}"; '
                "vc-implement codex --fork-session --prompt 'must not dispatch'"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--fork-session is only supported by vibecrafted resume" in result.stderr


def test_copy_managed_launcher_replaces_broken_framework_symlink(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src-vibecrafted"
    dst = tmp_path / "bin" / "vibecrafted"
    missing_target = tmp_path / ".vibecrafted" / "bin" / "vibecrafted"
    src.write_text("#!/usr/bin/env bash\nprintf 'ok\\n'\n", encoding="utf-8")
    src.chmod(0o755)
    dst.parent.mkdir()
    dst.symlink_to(missing_target)

    assert dst.is_symlink()
    assert not dst.exists()

    assert vetcoders_install._copy_managed_launcher(src, dst) is True

    assert dst.is_file()
    assert not dst.is_symlink()
    assert dst.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")


def test_spawn_launch_headless_detaches_into_new_session(tmp_path: Path) -> None:
    """A headless launcher must run in its OWN session (setsid), not the spawner's
    process group — otherwise a GUI app's Process teardown (the Pensieve dispatch)
    kills the 'detached' run ~2s after spawn, before it writes a transcript."""
    launcher = tmp_path / "launcher.sh"
    sid_file = tmp_path / "child_sid.txt"
    _write_fake_command(
        launcher,
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f'python3 -c \'import os; open("{sid_file}","w").write(str(os.getsid(0)))\'',
                "sleep 2",
            ]
        )
        + "\n",
    )

    launcher_sh = (
        REPO_ROOT
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "runtime"
        / "scripts"
        / "lib"
        / "launcher.sh"
    )
    # Spawn from a parent shell that exits immediately, then compare sessions.
    parent_sid = subprocess.run(
        [
            "bash",
            "-c",
            (
                "spawn_die(){ echo die >&2; exit 1; }; "
                f'eval "$(sed -n "/^spawn_launch_headless()/,/^}}/p" "{launcher_sh}")"; '
                f'spawn_launch_headless "{launcher}" >/dev/null; '
                "python3 -c 'import os; print(os.getsid(0))'"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    deadline = time.monotonic() + 5
    while not sid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert sid_file.exists(), "headless child never ran (died at spawn)"
    child_sid = sid_file.read_text(encoding="utf-8").strip()
    assert child_sid and child_sid != parent_sid, (
        f"headless child must be its own session leader (child={child_sid}, parent={parent_sid})"
    )

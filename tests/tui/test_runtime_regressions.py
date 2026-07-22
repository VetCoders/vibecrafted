from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from scripts import vetcoders_install

REPO_ROOT = Path(__file__).resolve().parents[2]
SHELL_SH = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"


def _write_fake_command(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _probe_codex_resume_contract(
    tmp_path: Path,
    args: list[str],
    *,
    operator_available: bool = True,
) -> tuple[subprocess.CompletedProcess[str], str, bool]:
    home = tmp_path / "home"
    context_file = tmp_path / "aicx-context.md"
    command_capture = tmp_path / "command.txt"
    aicx_capture = tmp_path / "aicx-called.txt"
    home.mkdir(parents=True)
    context_file.write_text("AICX OVERLAY BODY\n", encoding="utf-8")

    env = os.environ.copy()
    for key in (
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME",
        "VC_FRAME_PANE_ID",
        "VC_FRAME_SESSION_NAME",
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["TEST_AICX_CONTEXT"] = str(context_file)
    env["TEST_AICX_CAPTURE"] = str(aicx_capture)
    env["TEST_COMMAND_CAPTURE"] = str(command_capture)
    env["TEST_OPERATOR_AVAILABLE"] = "1" if operator_available else ""
    if operator_available:
        # Headless requests only enter the visible-host branch when an operator
        # surface is already known; interactive Codex may also prepare one.
        env["VIBECRAFTED_OPERATOR_SESSION"] = "operator-session"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    f'source "{SHELL_SH}"',
                    "codex() {",
                    "  {",
                    "    printf 'codex'",
                    "    printf ' %s' \"$@\"",
                    "    printf '\\n'",
                    '  } > "$TEST_COMMAND_CAPTURE"',
                    "}",
                    "_vetcoders_aicx_resume_fallback() {",
                    "  printf 'called\\n' > \"$TEST_AICX_CAPTURE\"",
                    "  printf 'SESSION_ID=historical-codex-session\\n'",
                    "  printf 'CONTEXT_FILE=%s\\n' \"$TEST_AICX_CONTEXT\"",
                    "  printf 'MODE=native_resume\\n'",
                    "}",
                    "_vetcoders_prepare_operator_runtime() {",
                    '  if [[ -n "$TEST_OPERATOR_AVAILABLE" ]]; then',
                    "    export VIBECRAFTED_OPERATOR_SESSION=operator-session",
                    "  else",
                    "    unset VIBECRAFTED_OPERATOR_SESSION",
                    "  fi",
                    "}",
                    "_vetcoders_spawn_into_operator_session() {",
                    '  printf \'%s\\n\' "$2" > "$TEST_COMMAND_CAPTURE"',
                    "}",
                    "vc-resume codex --runtime terminal " + shlex.join(args),
                ]
            ),
        ],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    command = (
        command_capture.read_text(encoding="utf-8").strip()
        if command_capture.exists()
        else ""
    )
    return result, command, aicx_capture.exists()


def test_bare_codex_resume_uses_aicx_pack_in_fresh_interactive_session(
    tmp_path: Path,
) -> None:
    result, command, aicx_called = _probe_codex_resume_contract(tmp_path, [])

    assert result.returncode == 0, result.stderr
    assert aicx_called
    assert command.startswith("codex ")
    assert "AICX OVERLAY BODY" in command
    assert "codex exec" not in command
    assert "codex resume" not in command
    assert "historical-codex-session" not in command


def test_codex_session_only_is_exact_interactive_resume(tmp_path: Path) -> None:
    result, command, aicx_called = _probe_codex_resume_contract(
        tmp_path, ["--session", "sess-123"]
    )

    assert result.returncode == 0, result.stderr
    assert not aicx_called
    assert command == "codex resume sess-123"


def test_codex_explicit_prompt_and_file_are_fresh_noninteractive_runs(
    tmp_path: Path,
) -> None:
    prompt_result, prompt_command, prompt_aicx = _probe_codex_resume_contract(
        tmp_path / "prompt", ["--prompt", "carry on"]
    )
    input_file = tmp_path / "file" / "input.md"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("FILE INPUT\n", encoding="utf-8")
    file_result, file_command, file_aicx = _probe_codex_resume_contract(
        tmp_path / "file", ["--file", str(input_file)]
    )

    assert prompt_result.returncode == 0, prompt_result.stderr
    assert file_result.returncode == 0, file_result.stderr
    assert not prompt_aicx and not file_aicx
    assert prompt_command.startswith(
        "codex exec --dangerously-bypass-approvals-and-sandbox "
    )
    assert "carry on" in prompt_command
    assert file_command.startswith(
        "codex exec --dangerously-bypass-approvals-and-sandbox "
    )
    assert "FILE INPUT" in file_command


def test_codex_session_with_explicit_file_is_noninteractive_continuation(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "input.md"
    input_file.write_text("SESSION FILE INPUT\n", encoding="utf-8")

    result, command, aicx_called = _probe_codex_resume_contract(
        tmp_path / "probe",
        ["--session", "sess-file-123", "--file", str(input_file)],
    )

    assert result.returncode == 0, result.stderr
    assert not aicx_called
    assert command.startswith("codex exec --dangerously-bypass-approvals-and-sandbox ")
    assert "resume sess-file-123" in command
    assert "SESSION FILE INPUT" in command


def test_codex_positional_resume_compatibility_preserves_mode_contract(
    tmp_path: Path,
) -> None:
    session_id = "019ec264-0b50-7bb2-9336-0aae5c841209"
    session_result, session_command, _ = _probe_codex_resume_contract(
        tmp_path / "session", [session_id]
    )
    continuation_result, continuation_command, _ = _probe_codex_resume_contract(
        tmp_path / "continuation", [session_id, "carry", "on"]
    )
    prompt_result, prompt_command, prompt_aicx = _probe_codex_resume_contract(
        tmp_path / "prompt", ["carry", "on"]
    )

    assert session_result.returncode == 0, session_result.stderr
    assert session_command == f"codex resume {session_id}"
    assert continuation_result.returncode == 0, continuation_result.stderr
    assert "codex exec" in continuation_command
    assert f"resume {session_id}" in continuation_command
    assert "carry on" in continuation_command
    assert prompt_result.returncode == 0, prompt_result.stderr
    assert "codex exec" in prompt_command
    assert " resume " not in prompt_command
    assert not prompt_aicx


def test_interactive_codex_resume_fails_without_operator_surface(
    tmp_path: Path,
) -> None:
    result, command, aicx_called = _probe_codex_resume_contract(
        tmp_path, ["--session", "sess-123"], operator_available=False
    )

    assert result.returncode != 0
    assert not command
    assert not aicx_called
    assert "requires a vc-frame operator session" in result.stderr
    assert "refusing to downgrade to codex exec" in result.stderr


def test_public_and_packaged_resume_help_describe_codex_mode_contract() -> None:
    launchers = (
        REPO_ROOT / "scripts" / "vibecrafted",
        REPO_ROOT / "vibecrafted-core" / "vibecrafted_core" / "deck" / "vibecrafted",
    )

    for launcher in launchers:
        result = subprocess.run(
            ["bash", str(launcher), "resume", "--help"],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert "Codex always starts a NEW interactive session" in result.stdout
        assert "Explicit --prompt/--file starts a non-interactive Codex run" in (
            result.stdout
        )
        assert "native-resumes it with the pack as prompt" not in result.stdout


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
    # Explicit --prompt means "continue the job": the visible tab must host the
    # NON-INTERACTIVE `codex exec ... resume`, never the interactive picker
    # (operator contract 2026-07-21). Bare resume without input keeps the TUI.
    assert "codex exec" in command_body
    assert "resume sess-123" in command_body
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

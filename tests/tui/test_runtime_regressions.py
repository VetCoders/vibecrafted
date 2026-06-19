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
                f'source <(sed -n "/^spawn_launch_headless()/,/^}}/p" "{launcher_sh}"); '
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

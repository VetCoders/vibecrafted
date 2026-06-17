from __future__ import annotations

import os
import subprocess
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

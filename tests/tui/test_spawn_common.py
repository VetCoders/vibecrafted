from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "skills" / "vc-agents" / "scripts" / "common.sh"


def _bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def test_runtime_prompt_guards_report_path_from_bare_slash(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    runtime_file = tmp_path / "runtime.md"
    report_path = tmp_path / "report.md"
    source_file.write_text("# Prompt\n", encoding="utf-8")

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_PROMPT_ID="prompt-123"
        spawn_build_runtime_prompt "{source_file}" "{runtime_file}" "{report_path}" claude
        '''
    )

    payload = runtime_file.read_text(encoding="utf-8")
    assert f"Report path: {report_path}" in payload
    assert f"\n{report_path}\n" not in payload


def test_generated_launcher_runs_from_spawn_root(tmp_path: Path) -> None:
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{root_dir}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_LOOP_NR="2"
        export SPAWN_SKILL_CODE="marb"
        cmd='pwd > "{report}"'
        spawn_write_meta "{meta}" "launching" "claude" "marbles" "{root_dir}" "{launcher}" "{report}" "{transcript}" "{launcher}"
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
        chmod +x "{launcher}"
        bash "{launcher}"
        '''
    )

    assert report.read_text(encoding="utf-8").strip() == str(root_dir)


def test_spawn_in_zellij_pane_honors_requested_direction(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture_file = tmp_path / "zellij-args.txt"
    zellij = fake_bin / "zellij"
    zellij.write_text(
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
    zellij.chmod(0o755)

    _bash(
        f'''
        set -euo pipefail
        export PATH="{fake_bin}:$PATH"
        export CAPTURE_FILE="{capture_file}"
        export ZELLIJ=1
        export ZELLIJ_PANE_ID=terminal_1
        export VIBECRAFTED_RUN_ID="{run_id}"
        export ZELLIJ_SESSION_NAME="{operator_session}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION=down
        source "{COMMON_SH}"
        spawn_in_zellij_pane "{launcher}" "workflow"
        '''
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--name" in payload
    assert "workflow" in payload
    assert "--direction" in payload
    assert "down" in payload


def test_generated_launcher_preserves_operator_session_contract(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    meta = tmp_path / "meta.json"
    report = tmp_path / "report.txt"
    transcript = tmp_path / "trace.log"

    _bash(
        f'''
        set -euo pipefail
        source "{COMMON_SH}"
        export SPAWN_ROOT="{tmp_path}"
        export SPAWN_AGENT="claude"
        export SPAWN_PROMPT_ID="prompt-123"
        export SPAWN_RUN_ID="run-123"
        export SPAWN_LOOP_NR="2"
        export SPAWN_SKILL_CODE="marb"
        export VIBECRAFTED_RUN_ID="{run_id}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION="right"
        cmd='printf "%s\\n%s\\n" "$VIBECRAFTED_OPERATOR_SESSION" "$VIBECRAFTED_ZELLIJ_SPAWN_DIRECTION" > "{report}"'
        spawn_write_meta "{meta}" "launching" "claude" "marbles" "{tmp_path}" "{launcher}" "{report}" "{transcript}" "{launcher}"
        spawn_generate_launcher "{launcher}" "{meta}" "{report}" "{transcript}" "{COMMON_SH}" "$cmd"
        chmod +x "{launcher}"
        bash "{launcher}"
        '''
    )

    payload = report.read_text(encoding="utf-8").splitlines()
    assert payload == [operator_session, "right"]


def test_spawn_prepare_paths_generates_real_run_context_when_missing(
    tmp_path: Path,
) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("# Prompt\n", encoding="utf-8")

    result = _bash(
        f'''
        set -euo pipefail
        export HOME="{tmp_path / "home"}"
        export VIBECRAFTED_ROOT="{REPO_ROOT}"
            mkdir -p "$VIBECRAFTED_ROOT/"
        source "{COMMON_SH}"
        unset VIBECRAFTED_RUN_ID
        unset VIBECRAFTED_RUN_LOCK
        unset VIBECRAFTED_SKILL_CODE
        export VIBECRAFTED_LOOP_NR="0"
        spawn_prepare_paths claude "{prompt_file}" "{tmp_path}" "followup"
        printf 'RUN_ID=%s\\n' "$SPAWN_RUN_ID"
        printf 'SKILL_CODE=%s\\n' "$SPAWN_SKILL_CODE"
        printf 'RUN_LOCK=%s\\n' "$SPAWN_RUN_LOCK"
        '''
    )

    payload = dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
    )
    assert re.fullmatch(r"fwup-\d{6}", payload["RUN_ID"])
    assert payload["SKILL_CODE"] == "fwup"
    lock_path = Path(payload["RUN_LOCK"])
    expected_lock = (
        tmp_path
        / "home"
        / ".vibecrafted"
        / "locks"
        / tmp_path.name
        / f"{payload['RUN_ID']}.lock"
    )
    assert lock_path == expected_lock
    assert "skill=followup" in lock_path.read_text(encoding="utf-8")
    assert result.stderr == ""


def test_spawn_in_operator_session_targets_named_session(tmp_path: Path) -> None:
    run_id = "marb-014520"
    operator_session = _expected_operator_session(run_id)
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture_file = tmp_path / "zellij-args.txt"
    zellij = fake_bin / "zellij"
    zellij.write_text(
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
    zellij.chmod(0o755)

    _bash(
        f'''
        set -euo pipefail
        export PATH="{fake_bin}:$PATH"
        export CAPTURE_FILE="{capture_file}"
        export VIBECRAFTED_RUN_ID="{run_id}"
        export VIBECRAFTED_OPERATOR_SESSION="{operator_session}"
        export SPAWN_ROOT="{tmp_path}"
        source "{COMMON_SH}"
        spawn_in_operator_session "{launcher}" "workflow"
        '''
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert operator_session in payload
    assert "action" in payload
    assert "new-pane" in payload
    assert "--name" in payload
    assert "workflow" in payload

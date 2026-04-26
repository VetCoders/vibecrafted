from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"
RUNTIME_HELPER = REPO_ROOT / "runtime" / "helpers" / "vetcoders-runtime-core.sh"


def _run_vetcoders_helper(
    helper_script: Path,
    command: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", "-lc", f'source "{helper_script}"; {command}'],
        cwd=str(REPO_ROOT),
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def _install_runtime_probe_helper(helper_root: Path, marker: str) -> None:
    helper_target = helper_root / "runtime" / "helpers" / "vetcoders-runtime-core.sh"
    helper_target.parent.mkdir(parents=True, exist_ok=True)
    helper_target.write_text(
        textwrap.dedent(
            f'''
            # shellcheck shell=bash
            source "{RUNTIME_HELPER}"
            _vetcoders_spawn_home() {{
              printf "{marker}\\n"
            }}
            '''
        ),
        encoding="utf-8",
    )


def test_vetcoders_shim_prefers_runtime_helper_from_repo_root(tmp_path: Path) -> None:
    marker = "runtime-helper-from-repo-root"
    helper_root = tmp_path / "probe-runtime"
    _install_runtime_probe_helper(helper_root, marker)

    result = _run_vetcoders_helper(
        HELPER_SCRIPT,
        'printf "%s\\n" "$(_vetcoders_spawn_home codex)"',
        {"VIBECRAFTED_ROOT": str(helper_root)},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == marker
    assert result.stderr == ""


def test_vetcoders_shim_prefers_staged_tools_runtime_helper(tmp_path: Path) -> None:
    marker = "runtime-helper-from-staged-tools"
    staged_home = tmp_path / "vibecrafted-home" / ".vibecrafted"
    staged_root = staged_home / "tools" / "vibecrafted-current"
    _install_runtime_probe_helper(staged_root, marker)

    installed_script = (
        tmp_path / "installed-tree" / "skills" / "vc-agents" / "shell" / "vetcoders.sh"
    )
    installed_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HELPER_SCRIPT, installed_script)

    result = _run_vetcoders_helper(
        installed_script,
        'printf "%s\\n" "$(_vetcoders_spawn_home codex)"',
        {"VIBECRAFTED_HOME": str(staged_home), "VIBECRAFTED_ROOT": ""},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == marker
    assert result.stderr == ""


def test_vetcoders_spawn_script_path_stays_command_compatible() -> None:
    env = os.environ.copy()
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    result = _run_vetcoders_helper(
        HELPER_SCRIPT,
        'printf "%s\\n" "$(_vetcoders_spawn_script codex codex_spawn.sh)"',
        env=env,
    )

    assert result.returncode == 0
    spawn_script = Path(result.stdout.strip())
    assert spawn_script.name == "codex_spawn.sh"
    assert spawn_script.is_file()


def test_vetcoders_keeps_launcher_entrypoints_available() -> None:
    result = _run_vetcoders_helper(
        HELPER_SCRIPT,
        "command -v vc-implement && command -v vc-research && command -v codex-implement",
        {"VIBECRAFTED_ROOT": str(REPO_ROOT)},
    )

    assert result.returncode == 0
    assert "vc-implement" in result.stdout
    assert "vc-research" in result.stdout
    assert "codex-implement" in result.stdout
    assert "command not found" not in result.stderr


def test_runtime_core_preserves_origin_org_repo_resolution(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", str(repo)], check=True, capture_output=True, text=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "https://github.com/VetCoders/vibecrafted.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = _run_vetcoders_helper(
        HELPER_SCRIPT,
        f'_vetcoders_org_repo "{repo}"',
        {"VIBECRAFTED_ROOT": str(REPO_ROOT)},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "VetCoders/vibecrafted"


def test_research_summary_does_not_execute_await_command(tmp_path: Path) -> None:
    run_dir = tmp_path / "research" / "rsch-test"
    run_dir.mkdir(parents=True)
    prompt_file = run_dir / "plans" / "plan.md"
    prompt_file.parent.mkdir()
    prompt_file.write_text("research plan\n", encoding="utf-8")

    result = _run_vetcoders_helper(
        HELPER_SCRIPT,
        (
            f'_vetcoders_write_research_summary "{run_dir}" "rsch-test" '
            f'"{tmp_path}" "{prompt_file}" claude.sh codex.sh gemini.sh'
        ),
        {"VIBECRAFTED_ROOT": str(REPO_ROOT)},
    )

    assert result.returncode == 0
    summary_file = run_dir / "summary.md"
    assert result.stdout.strip() == str(summary_file)
    assert "Await: vc-research-await --run-id rsch-test" in summary_file.read_text(
        encoding="utf-8"
    )
    assert "No matching launchers or metadata found yet" not in result.stderr

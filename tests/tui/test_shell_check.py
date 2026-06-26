from pathlib import Path

from scripts import check_shell


def test_tracked_shell_files_cover_repo_level_shell_surfaces() -> None:
    tracked = {
        path.relative_to(check_shell.REPO_ROOT).as_posix()
        for path in check_shell.tracked_shell_files()
    }

    assert "install.sh" in tracked
    assert "scripts/hooks/commit-msg" in tracked
    assert "scripts/hooks/pre-commit" in tracked
    assert "scripts/hooks/pre-push" in tracked
    assert "scripts/vibecrafted" in tracked
    assert "tests/portable/run.sh" in tracked
    assert "tools/hooks/load-project-context.sh" in tracked


def test_shell_for_path_uses_suffix_and_shebang(tmp_path: Path) -> None:
    zsh_file = tmp_path / "session"
    zsh_file.write_text("#!/usr/bin/env zsh\nprint ok\n", encoding="utf-8")
    bash_file = tmp_path / "bootstrap"
    bash_file.write_text("#!/usr/bin/env bash\nprintf 'hi\\n'\n", encoding="utf-8")
    suffix_only_bash = tmp_path / "bootstrap.sh"
    suffix_only_bash.write_text("printf 'hi\\n'\n", encoding="utf-8")

    assert check_shell.shell_for_path(zsh_file) == "zsh"
    assert check_shell.shell_for_path(bash_file) == "bash"
    assert check_shell.shell_for_path(suffix_only_bash) == "bash"


def test_build_shellcheck_command_keeps_repo_exclude_list(tmp_path: Path) -> None:
    sample = tmp_path / "sample.sh"
    sample.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    command = check_shell.build_shellcheck_command([sample])

    assert command[:3] == [
        "shellcheck",
        "-e",
        ",".join(check_shell.SHELLCHECK_EXCLUDES),
    ]
    assert command[-1] == str(sample)

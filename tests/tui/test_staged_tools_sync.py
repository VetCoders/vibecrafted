from __future__ import annotations

import io
import os
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import vetcoders_install as installer

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _write_complete_source(root: Path, *, helper: str, launcher: str) -> None:
    installer.stage_distribution_payload(REPO_ROOT, root, mirror=True)
    (root / "runtime" / "shell" / "vetcoders.sh").write_text(helper, encoding="utf-8")
    _write_executable(root / "scripts" / "vibecrafted", launcher)


def _write_valid_runtime_generation(root: Path) -> None:
    (root / "skills").mkdir(parents=True)
    (root / "runtime").mkdir()
    (root / "VERSION").write_text("9.9.8+gold\n", encoding="utf-8")
    _write_executable(
        root / "scripts" / "vibecrafted",
        "#!/usr/bin/env bash\nprintf 'old launcher\\n'\n",
    )


class _TtyBuffer:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True

    @property
    def text(self) -> str:
        return "".join(self.parts)


def test_compact_status_updates_one_tty_row() -> None:
    out = _TtyBuffer()

    installer._compact_line(out, "✓", "Skills", "27 installed")
    installer._compact_line(out, "✓", "Store", "~/.vibecrafted/skills")
    installer._clear_compact_status(out)

    assert "\n" not in out.text
    assert out.text.count("\r\033[K") == 3
    assert "Skills" in out.text
    assert "Store" in out.text
    assert out.text.endswith("\r\033[K")


def test_compact_status_appends_lines_for_non_tty_logs() -> None:
    out = io.StringIO()

    installer._compact_line(out, "✓", "Skills", "27 installed")
    installer._compact_line(out, "✓", "Store", "~/.vibecrafted/skills")
    installer._clear_compact_status(out)

    assert out.getvalue().splitlines() == [
        "  ✓ Skills        27 installed",
        "  ✓ Store         ~/.vibecrafted/skills",
    ]


def test_compact_checkpoint_prints_title_and_bounded_details_without_reason() -> None:
    """CLI_PRODUCT_SPEC §4: installers don't explain their own typography —
    the REASON narration line is retired from compact checkpoints."""
    out = io.StringIO()

    installer._compact_checkpoint(
        out,
        2,
        "Diagnostics and Plan",
        ("Skills   27 -> ~/.vibecrafted/skills", "Shell    enabled"),
    )

    assert out.getvalue().splitlines() == [
        "",
        "  [2/4] Diagnostics and Plan",
        "      Skills   27 -> ~/.vibecrafted/skills",
        "      Shell    enabled",
    ]


def test_refresh_current_tools_mirrors_shadowing_files(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    crafted_home = tmp_path / "home" / ".vibecrafted"
    runtime_tools = tmp_path / "home" / ".local" / "share" / "vibecrafted" / "tools"
    old_target = runtime_tools / "vibecrafted-main"
    current_link = runtime_tools / "vibecrafted-current"

    _write_complete_source(
        source,
        helper='printf "fresh helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n',
    )
    (old_target / "runtime" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "runtime" / "shell" / "vetcoders.sh").write_text(
        'printf "stale helper\\n"\n', encoding="utf-8"
    )
    (old_target / "scripts" / "vibecrafted").write_text(
        'printf "stale launcher\\n"\n', encoding="utf-8"
    )
    (old_target / "obsolete.txt").write_text("delete me\n", encoding="utf-8")
    stale_cache = old_target / "vibecrafted-core" / "vibecrafted_core" / "__pycache__"
    stale_cache.mkdir(parents=True)
    (stale_cache / "dispatcher.cpython-314.pyc").write_bytes(b"stale")
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(old_target)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))

    refreshed = installer.refresh_current_tools(
        source, crafted_home, dry_run=False, mirror=True
    )

    assert refreshed == current_link
    assert current_link.is_symlink()
    new_target = current_link.resolve()
    assert new_target != old_target
    assert (new_target / "runtime" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh helper\\n"\n'
    assert (new_target / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n'
    assert not (new_target / "obsolete.txt").exists()
    assert not (
        new_target / "vibecrafted-core" / "vibecrafted_core" / "__pycache__"
    ).exists()
    # Rollback truth remains immutable until the tool/service handoff is sealed.
    assert (old_target / "obsolete.txt").read_text(encoding="utf-8") == "delete me\n"
    assert (old_target / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == 'printf "stale launcher\\n"\n'


def _runtime_pointer_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    old_target = tmp_path / "tools" / "vibecrafted-generation-old"
    current = tmp_path / "tools" / "vibecrafted-current"
    _write_complete_source(
        source,
        helper='printf "new helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "new launcher\\n"\n',
    )
    _write_valid_runtime_generation(old_target)
    (old_target / "proof.txt").write_text("old runtime\n", encoding="utf-8")
    current.symlink_to(old_target.name)
    return source, old_target, current


@pytest.mark.parametrize("failure_point", ["stage", "stamp", "rename", "publish"])
def test_runtime_generation_failure_keeps_old_pointer_live(
    tmp_path: Path, monkeypatch, failure_point: str
) -> None:
    source, old_target, current = _runtime_pointer_fixture(tmp_path)

    if failure_point == "stage":
        monkeypatch.setattr(
            installer,
            "stage_distribution_payload",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("stage failed")),
        )
    elif failure_point == "stamp":
        monkeypatch.setattr(
            installer,
            "stamp_install_version",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("stamp failed")),
        )
    elif failure_point == "rename":
        original_rename = Path.rename

        def fail_generation_rename(path: Path, target: Path) -> Path:
            if path.name.startswith(".vibecrafted-current.staging-"):
                raise OSError("generation publish failed")
            return original_rename(path, target)

        monkeypatch.setattr(Path, "rename", fail_generation_rename)
    else:
        monkeypatch.setattr(
            installer,
            "_atomic_symlink",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("pointer publish failed")
            ),
        )

    with pytest.raises(OSError):
        installer.sync_control_plane_tree(
            source,
            current,
            mirror=True,
            install_version="9.9.9+gtest",
        )

    assert current.is_symlink()
    assert current.resolve() == old_target.resolve()
    assert (current / "proof.txt").read_text(encoding="utf-8") == "old runtime\n"
    assert not list(current.parent.glob(".vibecrafted-current.staging-*"))
    assert not list(current.parent.glob("vibecrafted-generation-9.9.9+gtest-*"))


def test_runtime_generation_pointer_swap_never_removes_current(
    tmp_path: Path, monkeypatch
) -> None:
    source, old_target, current = _runtime_pointer_fixture(tmp_path)
    original_replace = installer.os.replace
    observations: list[tuple[bool, bool]] = []

    def observed_replace(source_path, destination_path) -> None:
        destination = Path(destination_path)
        if destination == current:
            before = current.is_symlink() and current.resolve() == old_target.resolve()
            original_replace(source_path, destination_path)
            observations.append((before, current.is_symlink() and current.exists()))
            return
        original_replace(source_path, destination_path)

    monkeypatch.setattr(installer.os, "replace", observed_replace)

    generation = installer.sync_control_plane_tree(
        source,
        current,
        mirror=True,
        install_version="9.9.9+gtest",
    )

    assert observations == [(True, True)]
    assert current.resolve() == generation.resolve()
    assert current.resolve() != old_target.resolve()
    assert (current / "scripts" / "vibecrafted").is_file()


def test_runtime_generation_handoff_rolls_back_and_completes(
    tmp_path: Path, monkeypatch
) -> None:
    source, old_target, current = _runtime_pointer_fixture(tmp_path)
    home = tmp_path / "home"
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime_tools.parent.mkdir(parents=True)
    current.parent.rename(runtime_tools)
    current = runtime_tools / "vibecrafted-current"
    old_target = runtime_tools / old_target.name
    monkeypatch.setenv("HOME", str(home))

    installer.sync_control_plane_tree(
        source,
        current,
        mirror=True,
        install_version="9.9.9+gtest",
    )
    new_target = current.resolve()

    assert installer.rollback_current_tools(home) is True
    assert current.resolve() == old_target.resolve()
    assert installer.rollback_current_tools(home) is False

    installer.sync_control_plane_tree(
        source,
        current,
        mirror=True,
        install_version="9.9.9+gtest2",
    )
    assert current.resolve() != new_target
    assert installer.complete_current_tools_handoff(home) is True
    receipt = installer._read_tools_handoff(home)
    assert receipt is not None
    assert receipt["state"] == "complete"
    completed_target = current.resolve()
    assert installer.rollback_current_tools(home) is False
    assert current.resolve() == completed_target


def test_completed_handoff_is_not_rolled_back_after_next_stage_failure(
    tmp_path: Path, monkeypatch
) -> None:
    source, _, current = _runtime_pointer_fixture(tmp_path)
    home = tmp_path / "home"
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime_tools.parent.mkdir(parents=True)
    current.parent.rename(runtime_tools)
    current = runtime_tools / "vibecrafted-current"
    monkeypatch.setenv("HOME", str(home))

    installer.sync_control_plane_tree(
        source,
        current,
        mirror=True,
        install_version="9.9.9+gcomplete",
    )
    completed_target = current.resolve()
    assert installer.complete_current_tools_handoff(home) is True
    monkeypatch.setattr(
        installer,
        "stage_distribution_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("stage failed")),
    )

    with pytest.raises(OSError, match="stage failed"):
        installer.sync_control_plane_tree(
            source,
            current,
            mirror=True,
            install_version="9.9.9+gnext",
        )

    assert installer.rollback_current_tools(home) is False
    assert current.resolve() == completed_target


def test_portable_runtime_pointer_discards_stale_generation_handoff(
    tmp_path: Path, monkeypatch
) -> None:
    source, _, current = _runtime_pointer_fixture(tmp_path)
    home = tmp_path / "home"
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    runtime_tools.parent.mkdir(parents=True)
    current.parent.rename(runtime_tools)
    current = runtime_tools / "vibecrafted-current"
    monkeypatch.setenv("HOME", str(home))

    installer.sync_control_plane_tree(
        source,
        current,
        mirror=True,
        install_version="9.9.9+gstale",
    )
    assert installer.complete_current_tools_handoff(home) is True
    installer._atomic_symlink(source, current)
    assert installer._tools_handoff_file(home).is_file()

    refreshed = installer.refresh_current_tools(source, home, mirror=True)

    assert refreshed == current
    assert current.resolve() == source.resolve()
    assert not installer._tools_handoff_file(home).exists()
    assert installer.complete_current_tools_handoff(home) is False
    assert installer.rollback_current_tools(home) is False


def test_runtime_generation_refuses_legacy_real_directory_without_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    current = tmp_path / "tools" / "vibecrafted-current"
    _write_complete_source(
        source,
        helper='printf "new helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "new launcher\\n"\n',
    )
    current.mkdir(parents=True)
    (current / "proof.txt").write_text("legacy runtime\n", encoding="utf-8")

    with pytest.raises(OSError, match="must be a symlink pointer"):
        installer.sync_control_plane_tree(
            source,
            current,
            mirror=True,
            install_version="9.9.9+gtest",
        )

    assert (current / "proof.txt").read_text(encoding="utf-8") == "legacy runtime\n"


@pytest.mark.parametrize("failed_uv_install", [1, 2, 3, 0])
def test_make_install_tools_failure_rolls_runtime_pointer_back(
    tmp_path: Path, failed_uv_install: int
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "xdg-data"
    tools = data_home / "vibecrafted" / "tools"
    old_target = tools / "vibecrafted-generation-old"
    current = tools / "vibecrafted-current"
    _write_valid_runtime_generation(old_target)
    (old_target / "proof.txt").write_text("old runtime\n", encoding="utf-8")
    current.symlink_to(old_target.name)

    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(data_home),
            "VIBECRAFTED_TOOLS_HOME": str(tools),
        }
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
        monkeypatch.setenv("VIBECRAFTED_TOOLS_HOME", str(tools))
        installer.sync_control_plane_tree(
            REPO_ROOT,
            current,
            mirror=True,
            install_version="9.9.9+gtest",
        )
    assert current.resolve() != old_target.resolve()

    fake_bin = tmp_path / "fake-bin"
    state_file = tmp_path / "uv-install-count"
    fake_tool_dir = tmp_path / "uv-tools"
    fake_uv = fake_bin / "uv"
    _write_executable(
        fake_uv,
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'if [[ "${1:-} ${2:-}" == "tool install" ]]; then\n'
        f'  count="$(cat "{state_file}" 2>/dev/null || printf 0)"\n'
        '  count="$((count + 1))"\n'
        f'  printf "%s\\n" "$count" > "{state_file}"\n'
        f'  if [[ "{failed_uv_install}" -gt 0 && "$count" -eq "{failed_uv_install}" ]]; then exit 42; fi\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "${1:-} ${2:-}" == "tool dir" ]]; then\n'
        f'  printf "%s\\n" "{fake_tool_dir}"\n'
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
    )
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    result = subprocess.run(
        ["make", "--no-print-directory", "install-tools"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "restored previous runtime generation" in result.stdout
    assert "persistent service remains stopped and recoverable" in result.stderr
    assert current.resolve() == old_target.resolve()
    assert (current / "proof.txt").read_text(encoding="utf-8") == "old runtime\n"


def test_compact_install_refreshes_current_tools_from_local_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "checkout"
    crafted_home = home / ".vibecrafted"
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    old_target = runtime_tools / "vibecrafted-main"
    current_link = runtime_tools / "vibecrafted-current"

    _write_complete_source(
        source,
        helper='printf "fresh installed helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n',
    )
    (old_target / "runtime" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "runtime" / "shell" / "vetcoders.sh").write_text(
        'printf "stale staged helper\\n"\n', encoding="utf-8"
    )
    (old_target / "scripts" / "vibecrafted").write_text(
        'printf "stale staged launcher\\n"\n', encoding="utf-8"
    )
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(old_target)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(
        installer,
        "detect_system_deps",
        lambda: {"python3": "/usr/bin/python3", "git": "/usr/bin/git", "rsync": None},
    )
    monkeypatch.setattr(
        installer,
        "detect_agent_runtimes",
        lambda: {"claude": None, "codex": None, "gemini": None},
    )
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(installer, "run_doctor", lambda _store, _state: [])
    monkeypatch.setattr(
        installer,
        "write_start_here_guide",
        lambda _store, _state, _findings: crafted_home / "START_HERE.md",
    )

    def fail_runtime_venv(*_args, **_kwargs):
        raise AssertionError("compact install must not prepare runtime venv")

    def fail_runtime_entrypoints(*_args, **_kwargs):
        raise AssertionError("compact install must not publish runtime venv launchers")

    monkeypatch.setattr(installer, "_ensure_runtime_venv", fail_runtime_venv)
    monkeypatch.setattr(
        installer, "_install_python_entrypoint_launchers", fail_runtime_entrypoints
    )
    exit_code = installer._cmd_install_compact(
        Namespace(dry_run=False, mirror=True, with_shell=False),
        source,
    )

    assert exit_code == 0
    assert (current_link / "runtime" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh installed helper\\n"\n'
    assert (current_link / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n'


def _build_symlinked_skill_store(tmp_path: Path) -> tuple[Path, Path]:
    """Wire vibecrafted-current -> vibecrafted-main so the skill store and the
    install source resolve to the same inode (portable-CI staging shape)."""
    main = tmp_path / "vibecrafted-main"
    skills = main / "skills"
    skills.mkdir(parents=True)
    for filename in installer.SKILL_ROOT_RULE_FILES:
        (skills / filename).write_text(f"{filename}\n", encoding="utf-8")
    for localized in installer.LOCALIZED_SKILL_RULE_DIRS:
        (skills / localized).mkdir(parents=True, exist_ok=True)
        for filename in installer.SKILL_ROOT_RULE_FILES:
            (skills / localized / filename).write_text(
                f"{localized}/{filename}\n", encoding="utf-8"
            )
    current = tmp_path / "vibecrafted-current"
    current.symlink_to(main)
    # source_skills_root(...).resolve() is what the installer passes as the
    # source; the store comes from the unresolved current-link path -> same
    # inode via two different string paths.
    source = (current / "skills").resolve()
    store = current / "skills"
    return source, store


def test_sync_skill_root_rules_skips_same_inode_store(tmp_path: Path) -> None:
    """Regression: a symlinked store (vibecrafted-current -> vibecrafted-main)
    made copy2 raise shutil.SameFileError during the portable "skills and
    launchers" phase. The sync must treat the self-copy as a no-op."""
    source, store = _build_symlinked_skill_store(tmp_path)

    copied = installer.sync_skill_root_rules(source, store, dry_run=False)

    # All rule files are still reported as synced (they already exist in place).
    expected = {p for _src, p in installer.iter_skill_root_rule_files(source)}
    assert set(copied) == expected
    for filename in installer.SKILL_ROOT_RULE_FILES:
        assert (store / filename).read_text(encoding="utf-8") == f"{filename}\n"


def test_rsync_skill_skips_same_inode_dir(tmp_path: Path, monkeypatch) -> None:
    """Regression: the shutil fallback copied a skill dir onto itself (and under
    --mirror rmtree'd the source) when the store symlinked back to the source."""
    source, store = _build_symlinked_skill_store(tmp_path)
    # A skill living inside the skills dir: source/vc-demo (real) and
    # store/vc-demo (via the current-link symlink) are the same inode.
    src_skill = source / "vc-demo"
    src_skill.mkdir()
    (src_skill / "SKILL.md").write_text("demo\n", encoding="utf-8")
    dst_skill = store / "vc-demo"

    # Force the pure-Python fallback path (no rsync) with mirror=True — the most
    # destructive shape (rmtree of dst == the source) — and assert the source
    # survives untouched.
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    installer.rsync_skill(src_skill, dst_skill, dry_run=False, mirror=True)

    assert (src_skill / "SKILL.md").read_text(encoding="utf-8") == "demo\n"

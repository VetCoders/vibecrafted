from pathlib import Path

from scripts import vetcoders_install as installer


def test_canonical_store_is_the_package_owned_generation_path(
    tmp_path: Path, monkeypatch
) -> None:
    crafted_home = tmp_path / "state"
    tools_home = tmp_path / "tools"
    generation = tools_home / "vibecrafted-generation-test"
    package_skills = generation / "vibecrafted-core" / "vibecrafted_core" / "skills"
    package_skills.mkdir(parents=True)
    tools_home.mkdir(parents=True, exist_ok=True)
    (tools_home / "vibecrafted-current").symlink_to(generation)
    monkeypatch.setattr(installer, "vibecrafted_home", lambda: crafted_home)
    monkeypatch.setattr(installer, "vibecrafted_tools_home", lambda: tools_home)

    store = installer._canonical_store_path(crafted_home)

    assert store == (
        tools_home
        / "vibecrafted-current"
        / "vibecrafted-core"
        / "vibecrafted_core"
        / "skills"
    )
    assert store.resolve() == package_skills


def test_install_state_lives_outside_the_immutable_generation(
    tmp_path: Path, monkeypatch
) -> None:
    crafted_home = tmp_path / "state"
    store = tmp_path / "generation/vibecrafted-core/vibecrafted_core/skills"
    store.mkdir(parents=True)
    monkeypatch.setattr(installer, "vibecrafted_home", lambda: crafted_home)

    state_file = installer._install_state_file(store)
    installer.InstallState(framework_version="3.7.1").save(state_file.parent)

    assert state_file == crafted_home / installer.STATE_FILE
    assert not (store / installer.STATE_FILE).exists()
    assert installer._load_install_state(store).framework_version == "3.7.1"


def test_default_skill_view_has_one_cross_agent_owner() -> None:
    assert installer.SYMLINK_TARGETS == ["agents"]


def test_standard_views_cover_runtimes_that_read_their_own_dirs() -> None:
    # Claude Code and Codex CLIs never look at ~/.agents/skills; dropping their
    # views from the default install blanks the /vc-* deck (regression: 3.6.0).
    assert installer.STANDARD_VIEW_RUNTIMES == ["agents", "claude", "codex"]


def test_prune_shadowed_skill_views_removes_managed_runtime_links(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    store = tmp_path / "store"
    skill = store / "vc-scaffold"
    skill.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    canonical = home / ".agents" / "skills" / "vc-scaffold"
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(skill)

    codex = home / ".codex" / "skills" / "vc-scaffold"
    codex.parent.mkdir(parents=True)
    codex.symlink_to(skill)
    claude = home / ".claude" / "skills" / "vc-scaffold"
    claude.parent.mkdir(parents=True)
    claude.symlink_to("/missing/vibecrafted/tools/current/skills/vc-scaffold")

    removed = installer.prune_shadowed_skill_views(store, ["vc-scaffold"], ["agents"])

    assert removed == [claude, codex]
    assert canonical.is_symlink()
    assert not claude.is_symlink()
    assert not codex.is_symlink()


def test_prune_shadowed_skill_views_preserves_explicit_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    store = tmp_path / "store"
    skill = store / "vc-scaffold"
    skill.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    canonical = home / ".agents" / "skills" / "vc-scaffold"
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(skill)
    codex = home / ".codex" / "skills" / "vc-scaffold"
    codex.parent.mkdir(parents=True)
    codex.symlink_to(skill)

    removed = installer.prune_shadowed_skill_views(
        store, ["vc-scaffold"], ["agents", "codex"]
    )

    assert removed == []
    assert codex.is_symlink()

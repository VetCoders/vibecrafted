from pathlib import Path

from scripts import vetcoders_install as installer


def test_default_skill_view_has_one_cross_agent_owner() -> None:
    assert installer.SYMLINK_TARGETS == ["agents"]


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

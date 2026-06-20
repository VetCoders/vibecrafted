from __future__ import annotations

from pathlib import Path

from scripts import vetcoders_install as installer


def _make_snapshot(root: Path, name: str, *, blob_bytes: int = 0) -> Path:
    snap = root / name
    snap.mkdir(parents=True)
    (snap / "VERSION").write_text("1.0.0-test\n", encoding="utf-8")
    if blob_bytes:
        (snap / "blob.bin").write_text("x" * blob_bytes, encoding="utf-8")
    return snap


def _point_current(root: Path, target: Path) -> None:
    link = root / "vibecrafted-current"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def test_quarantine_moves_orphan_into_recoverable_dir(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    orphan = _make_snapshot(tools, "vibecrafted-oldref", blob_bytes=2048)
    _point_current(tools, active)

    moved = installer.quarantine_orphaned_snapshots(tools)

    assert len(moved) == 1
    src, _dst, size = moved[0]
    assert src == orphan
    assert not orphan.exists()  # moved out of the live tools dir
    quarantine = tools / installer.ORPHAN_QUARANTINE_DIRNAME
    assert (quarantine / "vibecrafted-oldref").is_dir()  # recoverable
    assert active.exists()  # active snapshot untouched
    assert size >= 2048


def test_quarantine_dry_run_changes_nothing(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    orphan = _make_snapshot(tools, "vibecrafted-oldref")
    _point_current(tools, active)

    moved = installer.quarantine_orphaned_snapshots(tools, dry_run=True)

    assert len(moved) == 1  # reported...
    assert orphan.exists()  # ...but not actually moved
    assert not (tools / installer.ORPHAN_QUARANTINE_DIRNAME).exists()


def test_purge_removes_quarantine_after_prune(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _make_snapshot(tools, "vibecrafted-oldref", blob_bytes=1024)
    _point_current(tools, active)
    installer.quarantine_orphaned_snapshots(tools)
    quarantine = tools / installer.ORPHAN_QUARANTINE_DIRNAME
    assert quarantine.is_dir()

    purged = installer.purge_orphan_quarantine(tools)

    assert len(purged) == 1
    assert not quarantine.exists()  # disk reclaimed
    assert active.exists()  # active still safe


def test_purge_dry_run_keeps_quarantine(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _make_snapshot(tools, "vibecrafted-oldref")
    _point_current(tools, active)
    installer.quarantine_orphaned_snapshots(tools)
    quarantine = tools / installer.ORPHAN_QUARANTINE_DIRNAME

    purged = installer.purge_orphan_quarantine(tools, dry_run=True)

    assert len(purged) == 1  # reported...
    assert quarantine.is_dir()  # ...but kept on disk


def test_full_lifecycle_collect_prune_purge(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _make_snapshot(tools, "vibecrafted-oldref", blob_bytes=512)
    _point_current(tools, active)

    assert len(installer.collect_orphaned_snapshots(tools)) == 1
    assert len(installer.quarantine_orphaned_snapshots(tools)) == 1
    # Orphan is gone from the live dir, so a re-scan finds nothing.
    assert installer.collect_orphaned_snapshots(tools) == []
    assert len(installer.purge_orphan_quarantine(tools)) == 1
    assert not (tools / installer.ORPHAN_QUARANTINE_DIRNAME).exists()
    assert active.exists()


def test_purge_without_quarantine_is_noop(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    _make_snapshot(tools, "vibecrafted-local")
    assert installer.purge_orphan_quarantine(tools) == []

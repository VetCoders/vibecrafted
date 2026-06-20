from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import vetcoders_install as installer


def _make_snapshot(root: Path, name: str, *, blob_bytes: int = 0) -> Path:
    """Create a fake vibecrafted-<ref> snapshot tree under ``root``."""
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


# ── helpers ─────────────────────────────────────────────────────────────────


def test_human_size_renders_compact_units() -> None:
    assert installer._human_size(0) == "0B"
    assert installer._human_size(512) == "512B"
    assert installer._human_size(1536) == "1.5KB"
    assert installer._human_size(5 * 1024 * 1024) == "5.0MB"


def test_dir_size_sums_tree_without_following_symlinks(tmp_path: Path) -> None:
    snap = _make_snapshot(tmp_path, "vibecrafted-x", blob_bytes=2048)
    # A symlink inside the tree must not be followed/counted as content.
    (snap / "link").symlink_to(snap / "blob.bin")

    size = installer._dir_size(snap)

    # VERSION (~11 bytes) + blob (2048) — symlink target not double-counted.
    assert size >= 2048
    assert size < 2048 + 200


# ── collect_orphaned_snapshots ──────────────────────────────────────────────


def test_finds_depointed_snapshot_and_excludes_active(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local", blob_bytes=100)
    _make_snapshot(tools, "vibecrafted-oldref", blob_bytes=4096)
    _point_current(tools, active)

    orphans = installer.collect_orphaned_snapshots(tools)

    names = [path.name for path, _size in orphans]
    assert names == ["vibecrafted-oldref"]
    assert orphans[0][1] >= 4096  # size reported


def test_clean_when_only_active_present(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _point_current(tools, active)

    assert installer.collect_orphaned_snapshots(tools) == []


def test_current_symlink_and_symlinked_entries_are_skipped(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _point_current(tools, active)
    # A stray symlink named like a snapshot must not be reported (only real dirs).
    (tools / "vibecrafted-aliased").symlink_to(active)

    orphans = installer.collect_orphaned_snapshots(tools)

    assert orphans == []


def test_scans_legacy_root_for_abandoned_snapshots(tmp_path: Path) -> None:
    tools = tmp_path / "xdg" / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _point_current(tools, active)

    legacy = tmp_path / "legacy" / "tools"
    _make_snapshot(legacy, "vibecrafted-main", blob_bytes=8192)  # no current here

    orphans = installer.collect_orphaned_snapshots(tools, legacy)

    names = sorted(path.name for path, _size in orphans)
    assert names == ["vibecrafted-main"]


def test_identical_active_and_legacy_root_is_not_double_counted(
    tmp_path: Path,
) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local")
    _make_snapshot(tools, "vibecrafted-oldref")
    _point_current(tools, active)

    orphans = installer.collect_orphaned_snapshots(tools, tools)

    assert [path.name for path, _size in orphans] == ["vibecrafted-oldref"]


def test_missing_roots_are_tolerated(tmp_path: Path) -> None:
    assert installer.collect_orphaned_snapshots(tmp_path / "nope") == []


# ── run_doctor integration ──────────────────────────────────────────────────


def test_run_doctor_reports_snapshot_orphans(monkeypatch, tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    active = _make_snapshot(tools, "vibecrafted-local", blob_bytes=100)
    _make_snapshot(tools, "vibecrafted-oldref", blob_bytes=4096)
    _point_current(tools, active)

    monkeypatch.setattr(installer, "vibecrafted_tools_home", lambda: tools)
    monkeypatch.setattr(installer, "vibecrafted_home", lambda: tmp_path / "legacy-home")

    # Section 0c runs before the store-existence early-return, so a missing store
    # is fine: the snapshot-orphan findings are already appended.
    state = SimpleNamespace(framework_version="test", skills=[])
    findings = installer.run_doctor(tmp_path / "no-such-store", state)

    snapshot_findings = [
        f for f in findings if f.component.startswith("snapshot-orphan:")
    ]
    assert len(snapshot_findings) == 1
    finding = snapshot_findings[0]
    assert finding.level == "warn"
    assert "vibecrafted-oldref" in finding.component
    assert "gc --prune" in finding.message

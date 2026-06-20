from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vibecrafted_core import gc


def _fake_installer(**overrides):
    base = dict(
        vibecrafted_tools_home=lambda: Path("/tools"),
        vibecrafted_home=lambda: Path("/home"),
        _human_size=lambda n: f"{n}B",
        collect_orphaned_snapshots=lambda t, legacy: [
            (Path("/tools/vibecrafted-old"), 100)
        ],
        quarantine_orphaned_snapshots=lambda t, legacy, dry_run=False: [
            (
                Path("/tools/vibecrafted-old"),
                Path("/tools/.orphan-snapshots/vibecrafted-old"),
                100,
            )
        ],
        purge_orphan_quarantine=lambda t, legacy, dry_run=False: [
            (Path("/tools/.orphan-snapshots"), 100)
        ],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_gc_collect_shapes_summary(monkeypatch) -> None:
    monkeypatch.setattr(gc, "_installer_module", lambda: _fake_installer())

    summary = gc.gc_collect()

    assert summary["mode"] == "collect"
    assert summary["dry_run"] is False
    assert summary["count"] == 1
    assert summary["total_bytes"] == 100
    assert summary["total_human"] == "100B"
    assert summary["items"][0]["path"] == "/tools/vibecrafted-old"
    assert summary["items"][0]["size_human"] == "100B"
    # collect is read-only: it does not report a quarantine destination
    assert "quarantine" not in summary["items"][0]


def test_gc_prune_reports_quarantine_destination(monkeypatch) -> None:
    monkeypatch.setattr(gc, "_installer_module", lambda: _fake_installer())

    summary = gc.gc_prune(dry_run=True)

    assert summary["mode"] == "prune"
    assert summary["dry_run"] is True
    assert summary["items"][0]["quarantine"].endswith(
        ".orphan-snapshots/vibecrafted-old"
    )


def test_gc_purge_shapes_summary(monkeypatch) -> None:
    monkeypatch.setattr(gc, "_installer_module", lambda: _fake_installer())

    summary = gc.gc_purge()

    assert summary["mode"] == "purge"
    assert summary["count"] == 1
    assert summary["total_bytes"] == 100


def test_gc_collect_empty_is_clean(monkeypatch) -> None:
    monkeypatch.setattr(
        gc,
        "_installer_module",
        lambda: _fake_installer(collect_orphaned_snapshots=lambda t, legacy: []),
    )

    summary = gc.gc_collect()

    assert summary["count"] == 0
    assert summary["total_bytes"] == 0
    assert summary["items"] == []

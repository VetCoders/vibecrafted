"""Unit tests for Delivery/Runtime Receipt (no live PATH dependency)."""

from __future__ import annotations

import json
from pathlib import Path

from vibecrafted_core import runtime_receipt as rr


def test_schema_version_stable() -> None:
    assert rr.SCHEMA_VERSION == "vibecrafted.delivery_receipt.v1"


def test_parse_installed_provenance_cargo_style() -> None:
    p = rr.parse_installed_provenance("vc-frame 0.46.0+g5c99f72d.dirty")
    assert p["installed_sha"] == "5c99f72d"
    assert p["installed_dirty"] is True


def test_parse_installed_provenance_clean() -> None:
    p = rr.parse_installed_provenance("aicx 0.12.0+g770149ec")
    assert p["installed_sha"] == "770149ec"
    assert p["installed_dirty"] is False


def test_parse_installed_provenance_refuses_without_sha() -> None:
    p = rr.parse_installed_provenance("vibecrafted 3.6.0")
    assert isinstance(p["installed_sha"], dict)
    assert p["installed_sha"]["value"] == "unknown"


def test_parse_dirty_false_is_not_dirty_build() -> None:
    """loct banner includes ``dirty=false`` — must not trip DIRTY_BUILD."""
    line = (
        "loct 0.14.1+g8188cf0d schema=loctree.bundle.v1 "
        "bundle_id=0.14.1+g8188cf0d commit=8188cf0d dirty=false"
    )
    p = rr.parse_installed_provenance(line)
    assert p["installed_sha"] == "8188cf0d"
    assert p["installed_dirty"] is False


def test_parse_path_hint_for_bare_semver() -> None:
    p = rr.parse_installed_provenance(
        "vibecrafted 3.6.0",
        path_hint="/home/x/.local/share/vibecrafted/tools/"
        "vibecrafted-3.6.0+g560310a9/bin/vibecrafted",
    )
    assert p["installed_sha"] == "560310a9"


def test_checkout_head_sha_loose_ref(tmp_path: Path) -> None:
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    sha = "7fa51c66aabbccddeeff00112233445566778899"
    (git / "HEAD").write_text("ref: refs/heads/develop\n", encoding="utf-8")
    (git / "refs" / "heads" / "develop").write_text(sha + "\n", encoding="utf-8")
    assert rr.checkout_head_sha(tmp_path) == sha
    assert rr.checkout_branch(tmp_path) == "develop"


def test_checkout_head_sha_packed_refs(tmp_path: Path) -> None:
    git = tmp_path / ".git"
    git.mkdir()
    sha = "8188cf0d00112233445566778899aabbccddeeff"
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{sha} refs/heads/main\n",
        encoding="utf-8",
    )
    assert rr.checkout_head_sha(tmp_path) == sha


def test_checkout_head_sha_missing_is_none(tmp_path: Path) -> None:
    assert rr.checkout_head_sha(tmp_path) is None


def test_classify_source_ahead() -> None:
    classes = rr.classify_drift(
        on_path=True,
        checkout_sha="7fa51c66deadbeef",
        installed_sha="5c99f72dcafe",
        installed_dirty=False,
        ahead=0,
        index_stale=False,
        source_known=True,
    )
    assert rr.DRIFT_SOURCE_AHEAD in classes
    assert rr.primary_drift(classes) == rr.DRIFT_SOURCE_AHEAD


def test_classify_not_on_path_primary() -> None:
    classes = rr.classify_drift(
        on_path=False,
        checkout_sha="abc",
        installed_sha=None,
        installed_dirty=None,
        ahead=3,
        index_stale=False,
        source_known=True,
    )
    assert rr.primary_drift(classes) == rr.DRIFT_NOT_ON_PATH
    assert rr.DRIFT_UNPUSHED in classes


def test_classify_dirty_build() -> None:
    classes = rr.classify_drift(
        on_path=True,
        checkout_sha="5c99f72d",
        installed_sha="5c99f72d",
        installed_dirty=True,
        ahead=0,
        index_stale=False,
        source_known=True,
    )
    assert rr.primary_drift(classes) == rr.DRIFT_DIRTY_BUILD


def test_classify_clean() -> None:
    classes = rr.classify_drift(
        on_path=True,
        checkout_sha="abc12345",
        installed_sha="abc12345",
        installed_dirty=False,
        ahead=0,
        index_stale=False,
        source_known=True,
    )
    assert classes == [rr.DRIFT_CLEAN]


def test_never_uses_cwd_for_source(tmp_path: Path, monkeypatch) -> None:
    """Cwd is a decoy repo — receipt must not adopt it as a tool source."""
    decoy = tmp_path / "decoy"
    (decoy / ".git" / "refs" / "heads").mkdir(parents=True)
    (decoy / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (decoy / ".git" / "refs" / "heads" / "main").write_text(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", encoding="utf-8"
    )
    (decoy / "Cargo.toml").write_text(
        '[package]\nname = "something-else"\n', encoding="utf-8"
    )
    monkeypatch.chdir(decoy)
    # Clear env that could legitimately point at sources
    for key in (
        "VC_FRAME_SOURCE",
        "VC_FRAME_ROOT",
        "VIBECRAFTED_SOURCE",
        "VIBECRAFTED_ROOT",
        "LOCTREE_SOURCE",
        "AICX_SOURCE",
        "VIBECRAFTED_FLEET_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)

    # Force no binary and only impossible candidates
    monkeypatch.setattr(rr, "which_binary", lambda _name: None)
    monkeypatch.setattr(rr, "_default_candidate_roots", lambda _name: [])
    monkeypatch.setattr(rr, "_vibecrafted_package_repo", lambda: None)

    specs = [
        rr.ToolSpec(
            name="vc-frame",
            binaries=("vc-frame",),
            env_roots=("VC_FRAME_SOURCE",),
            markers=(("Cargo.toml", r'name\s*=\s*"vc-frame"'),),
            candidate_roots=(),
        )
    ]
    receipt = rr.build_receipt(specs)
    tool = receipt["tools"][0]
    path = tool["source"]["path"]
    assert isinstance(path, dict)
    assert path["value"] == "unknown"
    assert (
        "cwd" not in json.dumps(tool).lower() or "never uses" in receipt["cwd_policy"]
    )


def test_vibecrafted_receipt_uses_checkout_free_runtime_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    revision = "0123456789abcdef0123456789abcdef01234567"
    generation = tmp_path / "vibecrafted-generation-3.7.0+g01234567"
    deck = generation / "vibecrafted-core" / "vibecrafted_core" / "deck" / "vibecrafted"
    deck.parent.mkdir(parents=True)
    deck.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    deck.chmod(0o755)
    (generation / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "schema": "vibecrafted.runtime-generation.v1",
                "owner_repo": "Vetcoders/vibecrafted",
                "source_revision": revision,
                "entrypoint": "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        rr, "which_binary", lambda name: str(deck) if name == "vibecrafted" else None
    )
    monkeypatch.setattr(rr, "run_version", lambda _path: "vibecrafted 3.7.0+g01234567")
    monkeypatch.setattr(rr, "_vibecrafted_tools_path_hints", list)

    [tool] = rr.build_receipt(
        [
            rr.ToolSpec(
                name="vibecrafted",
                binaries=("vibecrafted",),
                env_roots=("VIBECRAFTED_SOURCE",),
                markers=(("VERSION", r".+"),),
                candidate_roots=(),
            )
        ]
    )["tools"]

    assert tool["source"]["resolution"] == "installed_runtime_manifest"
    assert tool["source"]["owner_repo"] == "Vetcoders/vibecrafted"
    assert tool["source"]["checkout_sha"] == revision
    assert tool["installed"]["dirty_build"] is False
    assert rr.DRIFT_DIRTY_BUILD not in tool["drift"]


def test_render_contains_drift_tokens() -> None:
    receipt = {
        "schema": rr.SCHEMA_VERSION,
        "cwd_policy": "never uses process cwd",
        "tools": [
            {
                "name": "vc-frame",
                "primary_drift": rr.DRIFT_SOURCE_AHEAD,
                "drift": [rr.DRIFT_SOURCE_AHEAD, rr.DRIFT_UNPUSHED],
                "chain": {
                    "owner_repo": "Vetcoders/vc-frame",
                    "branch": "develop",
                    "checkout_sha": "7fa51c66",
                    "dirty": False,
                    "installed_sha": "5c99f72d",
                    "ahead": 3,
                    "behind": 0,
                    "index_generation": {"value": "unknown", "reason": "n/a"},
                },
                "source": {
                    "path": "/tmp/vc-frame",
                    "resolution": "env:VC_FRAME_SOURCE",
                    "dirty_detail": {
                        "source_dirty_count": 0,
                        "generated_dirty_count": 0,
                    },
                },
                "installed": {
                    "path": "/usr/bin/vc-frame",
                    "sha": "5c99f72d",
                    "dirty_build": True,
                    "version_line": "vc-frame 0.46.0+g5c99f72d.dirty",
                },
                "remote": {"upstream": "origin/develop", "ahead": 3, "behind": 0},
                "index": None,
                "related": [],
            }
        ],
        "summary": {"tool_count": 1, "by_primary_drift": {rr.DRIFT_SOURCE_AHEAD: 1}},
    }
    text = rr.render_receipt_text(receipt)
    assert "SOURCE_AHEAD_OF_INSTALLED" in text
    assert "UNPUSHED" in text
    assert "7fa51c66" in text


def test_is_generated_path() -> None:
    assert rr._is_generated_path("target/release/foo")
    assert rr._is_generated_path(".loctree/context-atlas/x")
    assert not rr._is_generated_path("src/main.rs")

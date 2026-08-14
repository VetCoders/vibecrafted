from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PAGE = "https://github.com/vetcoders/vibecrafted/releases/latest"


def test_public_install_surfaces_point_at_the_single_dmg() -> None:
    surfaces = (
        "README.md",
        "docs/QUICK_START.md",
        "docs/public/getting-started/install.md",
    )
    for relative in surfaces:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert RELEASE_PAGE in text, f"{relative} must point to the unified release"
        assert "Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg" in text
        assert "vc-frame/releases/latest/download/install.sh" not in text


def test_tag_workflow_is_a_read_only_source_gate() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert 'test "$(git cat-file -t "$GITHUB_REF_NAME")" = "tag"' in workflow
    assert 'test "$(git rev-parse "$GITHUB_REF_NAME")" = "$GITHUB_SHA"' in workflow
    assert (
        'test "$(git rev-list -n 1 "$GITHUB_REF_NAME")" = "$(git rev-parse HEAD)"'
        in workflow
    )
    assert "run: make unified-product-contract-gate" in workflow
    assert "run: make test-core" in workflow
    assert "run: make semgrep" in workflow
    assert "contents: write" not in workflow
    assert "gh release create" not in workflow
    assert "gh release upload" not in workflow
    assert "install.sh" not in workflow
    assert "vibecrafted-framework.plugin" not in workflow


def test_macos_publisher_cold_verifies_exact_uploaded_bytes() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    publisher = (REPO_ROOT / "scripts/publish-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )

    assert "publish-release:" in makefile
    assert "scripts/publish-vibecrafted-release.sh" in makefile
    assert 'DMG_NAME="$(uv run python3' in publisher
    assert 'DMG="$DIST/$DMG_NAME"' in publisher
    assert 'DMG_CHECKSUM="$DMG.sha256"' in publisher
    assert 'test "$(uname -s)" = "Darwin"' in publisher
    assert "verify-vibecrafted-walkaround verify-release" in publisher
    assert "verify-vibecrafted-walkaround walkaround" in publisher
    assert 'gh release download "$TAG"' in publisher
    assert 'cmp "$DMG" "$DOWNLOAD_DIR/$DMG_NAME"' in publisher
    assert 'shasum -a 256 -c "$DMG_NAME.sha256"' in publisher
    assert "xcrun stapler validate" in publisher
    assert "spctl --assess --type open" in publisher
    assert "code-scanning/alerts?state=open&ref=refs/heads/main" in publisher
    assert "per_page=1" in publisher
    assert "gh api --paginate" not in publisher
    assert "--slurp --jq" not in publisher
    assert 'gh release edit "$TAG"' in publisher

    expected_assets = publisher.split('EXPECTED_ASSETS="', 1)[1].split('"', 1)[0]
    assert expected_assets.splitlines() == [
        "$DMG_NAME",
        "$DMG_NAME.sha256",
        "release-output.json",
        "release-output.json.sig",
    ]


def test_builder_emits_the_canonical_versioned_dmg_and_checksum() -> None:
    builder = (REPO_ROOT / "scripts/build-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )
    assert 'RELEASE_DATE="${VIBECRAFTED_RELEASE_DATE:-$(date -u +%Y%m%d)}"' in builder
    assert (
        'DMG_NAME="Vibecrafted_${VERSION}-${RELEASE_DATE}-${ROOT_SHA:0:8}.dmg"'
        in builder
    )
    assert 'RUNTIME_VERSION="${VERSION}+g${ROOT_SHA:0:8}"' in builder
    assert 'printf \'%s\\n\' "$RUNTIME_VERSION" > "$runtime/VERSION"' in builder
    assert 'DMG_CHECKSUM="$DMG.sha256"' in builder
    assert 'LEGACY_DMG="$DIST_DIR/Vibecrafted.dmg"' in builder
    assert 'rm -f "$DMG_CHECKSUM" "$LEGACY_DMG"' in builder
    assert '/usr/bin/shasum -a 256 "$DMG_NAME"' in builder
    assert "-type d -name __pycache__" in builder
    assert "-name '*.pyc'" in builder
    assert "-name '.DS_Store'" in builder
    assert "build-server-release" in builder
    assert 'install -m 0755 "$server_source" "$runtime/bin/vc-server"' in builder
    assert '"$runtime/server/site/"' in builder
    assert "vc-server-supervisor:vibecrafted_core.server_supervisor" in builder
    assert '"$runtime/runtime"' not in builder


def test_release_bundle_binds_the_vibecrafted_app_icon() -> None:
    project = (REPO_ROOT / "vibecrafted-app/shell-agent/app/project.yml").read_text(
        encoding="utf-8"
    )
    info_plist = (
        REPO_ROOT / "vibecrafted-app/shell-agent/app/Vibecrafted/Info.plist"
    ).read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "scripts/unified_product_manifest.py").read_text(
        encoding="utf-8"
    )
    builder = (REPO_ROOT / "scripts/build-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )
    icon_builder = (REPO_ROOT / "scripts/build-vibecrafted-icon.sh").read_text(
        encoding="utf-8"
    )
    icon = REPO_ROOT / "vibecrafted-app/shell-agent/app/Vibecrafted/Vibecrafted.icns"

    assert "INFOPLIST_FILE: Vibecrafted/Info.plist" in project
    assert "<key>CFBundleIconFile</key>" in info_plist
    assert "<string>Vibecrafted.icns</string>" in info_plist
    assert 'plist["CFBundleIconFile"] = contract.PRODUCT_ICON_FILE' in manifest
    assert icon.is_file()
    assert icon.stat().st_size > 100_000
    assert "$TERMINAL_REPO/assets/icon/vc-terminal-icon.png" in builder
    assert "$TERMINAL_REPO/assets/icon/terminal.png" in builder
    assert '"$ICON_SOURCE" "$resources/Vibecrafted.icns" "$ICON_REFERENCE"' in builder
    assert "! -name 'Vibecrafted.icns'" in builder
    assert "iconutil -c icns" in icon_builder
    assert 'cmp -s "$ICONSET/icon_128x128.png" "$REFERENCE"' in icon_builder


def test_mission_control_failure_board_exposes_absolute_failure_time() -> None:
    view = (
        REPO_ROOT
        / "vibecrafted-app/shell-agent/app/Vibecrafted/Views/MissionControlViewController.swift"
    ).read_text(encoding="utf-8")
    ffi = (REPO_ROOT / "vibecrafted-app/shell-agent/ffi/src/lib.rs").read_text(
        encoding="utf-8"
    )
    mission = (
        REPO_ROOT / "vibecrafted-app/tui-agent/src/mission_control.rs"
    ).read_text(encoding="utf-8")

    assert '("Date", "DATE", 145)' in view
    assert 'case "DATE": return dateTime(item.occurredAt)' in view
    assert "private static let iso8601DateFormatter" in view
    assert "private static let failureDateFormatter" in view
    assert "ISO8601DateFormatter().date" not in view
    assert "pub occurred_at: Option<String>" in ffi
    assert "occurred_at: Some(record.completed_at.to_rfc3339())" in mission


def test_signed_bundle_runtime_cannot_write_python_bytecode() -> None:
    builder = (REPO_ROOT / "scripts/build-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )
    app_delegate = (
        REPO_ROOT / "vibecrafted-app/shell-agent/app/Vibecrafted/AppDelegate.swift"
    ).read_text(encoding="utf-8")
    vc_start = (REPO_ROOT / "vibecrafted-app/tui-agent/src/bin/vc_start.rs").read_text(
        encoding="utf-8"
    )

    assert "export PYTHONDONTWRITEBYTECODE=1" in builder
    assert 'environment["PYTHONDONTWRITEBYTECODE"] = "1"' in app_delegate
    assert '.env("PYTHONDONTWRITEBYTECODE", "1")' in vc_start
    assert '"$runtime/bin/python3" -c' in builder
    assert "bundled Python mutated the signed application payload" in builder


def test_publisher_writes_the_mandatory_release_report() -> None:
    publisher = (REPO_ROOT / "scripts/publish-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )
    for heading in (
        "## 1. Security gate",
        "## 2. Exposed surface inventory",
        "## 3. Deployment mode decision",
        "## 4. Post-release install smoke",
        "## Sign-off",
    ):
        assert heading in publisher
    assert ".vibecrafted/artifacts" in publisher
    assert "100.82.232.70:3025" in publisher


def test_vc_release_skill_locks_four_mandatory_report_sections() -> None:
    skill = (
        REPO_ROOT / "vibecrafted-core/vibecrafted_core/skills/vc-release/SKILL.md"
    ).read_text(encoding="utf-8")
    template = (
        REPO_ROOT
        / "vibecrafted-core/vibecrafted_core/skills/vc-release/references/release-report-template.md"
    )

    assert "## Release Report Contract" in skill
    for required in (
        "**Security gate**",
        "**Exposed surface inventory**",
        "**Deployment mode decision**",
        "**Post-release install smoke**",
    ):
        assert required in skill
    assert "make semgrep" in skill
    assert "references/release-report-template.md" in skill

    template_text = template.read_text(encoding="utf-8")
    for heading in (
        "## 1. Security gate",
        "## 2. Exposed surface inventory",
        "## 3. Deployment mode decision",
        "## 4. Post-release install smoke",
        "## Sign-off",
    ):
        assert heading in template_text

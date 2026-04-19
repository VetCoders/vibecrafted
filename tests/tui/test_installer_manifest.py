"""Regression tests for vetcoders_installer manifest loading and interpolation.

Covers the manifest parsing + placeholder interpolation path in
``scripts/installer/vetcoders_installer/__init__.py`` — specifically
``Manifest.load`` (TOML → dataclass) and ``_interpolate_mock`` (placeholder
substitution used when rendering intro/mockup screens).

These paths had no matching tests before P2-04.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PKG_DIR = REPO_ROOT / "scripts" / "installer"
if str(INSTALLER_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_PKG_DIR))

import vetcoders_installer as installer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "install.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _minimal_phase_block(label: str = "Diagnostics") -> str:
    # Every Manifest.load call requires at least one [[phase]] with a cmd.
    return (
        f'[[phase]]\nlabel = "{label}"\nreason = "check things"\ncmd = ["echo", "hi"]\n'
    )


# ---------------------------------------------------------------------------
# Manifest.load — happy path + edges
# ---------------------------------------------------------------------------


def test_manifest_load_parses_title_version_and_phases(tmp_path: Path) -> None:
    """Happy path: full manifest with title, version, one phase, branding, intro."""
    body = (
        'title = "Vibecrafted test"\n'
        'version = "9.9.9"\n'
        'log = "~/.cache/foo/{ts}.log"\n'
        "persist = true\n\n"
        "[[phase]]\n"
        'key = "diag"\n'
        'label = "Diagnostics"\n'
        'reason = "line one\\nline two"\n'
        'cmd = ["echo", "ok"]\n'
        "optional = true\n\n"
        "[[phase]]\n"
        'label = "Installation"\n'
        'reason = "install things"\n'
        'cmd = ["bash", "scripts/install.sh"]\n\n'
        "[branding]\n"
        'name = "Vibecrafted."\n'
        'header = "⚒ header ⚒"\n\n'
        "[intro]\n"
        'screens = ["0.md", "1.md"]\n'
    )
    manifest = installer.Manifest.load(_write_manifest(tmp_path, body))

    assert manifest.title == "Vibecrafted test"
    assert manifest.version == "9.9.9"
    assert manifest.log_pattern == "~/.cache/foo/{ts}.log"
    assert manifest.persist is True
    assert len(manifest.phases) == 2

    diag = manifest.phases[0]
    assert diag.key == "diag"
    assert diag.label == "Diagnostics"
    assert diag.reason_lines == ["line one", "line two"]
    assert diag.cmd == ["echo", "ok"]
    assert diag.optional is True
    # Default cwd resolves to the manifest's parent (repo root at test time).
    assert diag.cwd == tmp_path.resolve()

    install_phase = manifest.phases[1]
    # Auto key derivation: "Installation" → "installation"
    assert install_phase.key == "installation"
    assert install_phase.optional is False

    assert manifest.branding == {"name": "Vibecrafted.", "header": "⚒ header ⚒"}
    assert manifest.intro_screens == ["0.md", "1.md"]


def test_manifest_load_resolves_version_from_version_file(tmp_path: Path) -> None:
    """Edge: when `version` is absent but `version_file` points at a VERSION file."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n", encoding="utf-8")
    body = 'title = "v"\nversion_file = "VERSION"\n' + _minimal_phase_block()
    manifest = installer.Manifest.load(_write_manifest(tmp_path, body))
    assert manifest.version == "1.2.3"


def test_manifest_load_rejects_phase_without_cmd(tmp_path: Path) -> None:
    """Edge: a [[phase]] without a list-typed cmd must raise ValueError."""
    body = 'title = "t"\n[[phase]]\nlabel = "Broken"\nreason = "no cmd"\n'
    with pytest.raises(ValueError, match="has no 'cmd'"):
        installer.Manifest.load(_write_manifest(tmp_path, body))


def test_manifest_load_defaults_when_sections_missing(tmp_path: Path) -> None:
    """Edge: branding / intro / diagnostics sections are optional."""
    body = 'title = "t"\n' + _minimal_phase_block()
    manifest = installer.Manifest.load(_write_manifest(tmp_path, body))
    assert manifest.branding == {}
    assert manifest.intro_screens == []
    assert manifest.textual_screens == []
    assert manifest.diagnostics == {}
    # Missing version → empty string (not "dev").
    assert manifest.version == ""
    # Missing log → None.
    assert manifest.log_pattern is None


# ---------------------------------------------------------------------------
# _interpolate_mock — placeholder substitution
# ---------------------------------------------------------------------------


def _build_manifest(
    tmp_path: Path,
    *,
    version: str = "",
    branding: dict[str, str] | None = None,
    diagnostics: dict | None = None,
) -> installer.Manifest:
    return installer.Manifest(
        title="T",
        version=version,
        log_pattern=None,
        persist=False,
        phases=[],
        path=tmp_path / "install.toml",
        branding=dict(branding or {}),
        intro_screens=[],
        textual_screens=[],
        diagnostics=dict(diagnostics or {}),
    )


def test_interpolate_mock_replaces_version_and_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: {version}, $HOME, $VIBECRAFTED_ROOT are substituted."""
    monkeypatch.setenv("VIBECRAFTED_ROOT", "/tmp/vc-test-root")
    monkeypatch.setattr(
        installer.Path, "home", classmethod(lambda cls: Path("/tmp/home-xyz"))
    )
    manifest = _build_manifest(tmp_path, version="7.8.9")

    text = "hello v{version} root=$VIBECRAFTED_ROOT home=$HOME 𝚟0.0.1 end"
    out = installer._interpolate_mock(text, manifest)

    assert "v7.8.9" in out
    assert "root=/tmp/vc-test-root" in out
    assert "home=/tmp/home-xyz" in out
    # The monospace-unicode version regex should be rewritten to the real version.
    assert "𝚟7.8.9" in out


def test_interpolate_mock_applies_branding_overrides(tmp_path: Path) -> None:
    """Happy path: branding.name / header / unicode_wordmark / footer rewrite targets."""
    manifest = _build_manifest(
        tmp_path,
        version="1.0.0",
        branding={
            "name": "ToolkitBrand.",
            "header": "⚒ BRANDED ⚒",
            "unicode_wordmark": "⚒ ToolkitBrand.",
            "footer_tagline": "ship it",
        },
    )
    template = (
        "⚒ V A P O R C R A F T ⚒\nWelcome to Vibecrafted\n⚒ Vibecrafted.\nFRAMEWORK"
    )
    out = installer._interpolate_mock(template, manifest)

    assert "⚒ BRANDED ⚒" in out
    assert "Welcome to ToolkitBrand" in out
    assert "⚒ ToolkitBrand." in out
    assert "ship it" in out
    # Default strings must be gone.
    assert "⚒ V A P O R C R A F T ⚒" not in out
    assert "FRAMEWORK" not in out


def test_interpolate_mock_defaults_version_when_blank(tmp_path: Path) -> None:
    """Edge: empty manifest.version → '{version}' becomes 'dev'."""
    manifest = _build_manifest(tmp_path, version="")
    out = installer._interpolate_mock("release={version}", manifest)
    assert out == "release=dev"


def test_interpolate_mock_is_noop_without_branding(tmp_path: Path) -> None:
    """Edge: empty branding section must not alter non-placeholder text."""
    manifest = _build_manifest(tmp_path, version="2.0.0", branding={})
    template = "plain text with Vibecrafted word and ⚒ V A P O R C R A F T ⚒"
    out = installer._interpolate_mock(template, manifest)
    # Without a branding.name, the bare "Vibecrafted" token survives untouched.
    assert "Vibecrafted" in out
    assert "⚒ V A P O R C R A F T ⚒" in out


def test_interpolate_mock_handles_missing_branding_keys(tmp_path: Path) -> None:
    """Edge: partial branding (only `name`) must not crash or mis-substitute."""
    manifest = _build_manifest(
        tmp_path, version="3.0.0", branding={"name": "OnlyName."}
    )
    out = installer._interpolate_mock("Vibecrafted + FRAMEWORK", manifest)
    # `name` rewrite is active (bare "Vibecrafted" → "OnlyName").
    assert "OnlyName + FRAMEWORK" == out

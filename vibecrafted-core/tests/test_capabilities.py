from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from vibecrafted_core import capabilities


def _runner_factory(results: dict[str, capabilities.ProbeResult]):
    def run(cmd: Sequence[str]) -> capabilities.ProbeResult:
        # Key on the probe flag (last argument): --version / --help.
        flag = cmd[-1]
        return results[flag]

    return run


def test_probe_tool_reports_product_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: Path("/definitely/missing/bin"),
    )
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(capabilities, "_ghost_bin_roots", lambda: ())

    cap = capabilities.probe_tool("loct", runner=lambda cmd: pytest.fail("no exec"))

    assert cap.present is False
    assert cap.runnable is False
    assert cap.status == "product_missing"
    assert cap.provenance == "missing"


def test_probe_tool_discovers_canonical_binary_without_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canonical_bin = tmp_path / "bin"
    canonical_bin.mkdir()
    binary = canonical_bin / "loct"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(capabilities, "vibecrafted_launcher_bin", lambda: canonical_bin)

    def run(cmd: Sequence[str]) -> capabilities.ProbeResult:
        assert cmd[0] == str(binary)
        if cmd[-1] == "--version":
            return capabilities.ProbeResult(ok=True, returncode=0, stdout="loct 0.12.0")
        return capabilities.ProbeResult(
            ok=True,
            returncode=0,
            stdout="Commands:\n  context\n  slice\n",
        )

    cap = capabilities.probe_tool("loct", runner=run)

    assert cap.present is True
    assert cap.runnable is True
    assert cap.provenance == "canonical"
    assert cap.status == "ok"
    assert cap.version == "loct 0.12.0"
    assert cap.capabilities == ["context", "slice"]


def test_probe_tool_reports_product_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: "/Users/you/.local/bin/loct",
    )
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: __import__("pathlib").Path("/Users/you/.local/bin"),
    )
    runner = _runner_factory(
        {"--version": capabilities.ProbeResult(ok=False, returncode=127, stderr="boom")}
    )

    cap = capabilities.probe_tool("loct", runner=runner)

    assert cap.present is True
    assert cap.runnable is False
    assert cap.status == "product_broken"
    assert "failed to execute" in cap.detail


def test_probe_tool_ok_with_capability_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: "/Users/you/.local/bin/loct",
    )
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: __import__("pathlib").Path("/Users/you/.local/bin"),
    )
    help_text = (
        "Loctree operator CLI\n\n"
        "Usage: loct <command>\n\n"
        "Commands:\n"
        "  context   Atlas + pill + memory continuity\n"
        "  slice     Extract context with dependencies\n"
        "  impact    Blast radius\n"
        "  help      Print help\n\n"
        "Options:\n"
        "  -h, --help\n"
    )
    runner = _runner_factory(
        {
            "--version": capabilities.ProbeResult(
                ok=True, returncode=0, stdout="loct 0.11.2"
            ),
            "--help": capabilities.ProbeResult(ok=True, returncode=0, stdout=help_text),
        }
    )

    cap = capabilities.probe_tool("loct", runner=runner)

    assert cap.status == "ok"
    assert cap.runnable is True
    assert cap.provenance == "canonical"
    assert cap.version == "loct 0.11.2"
    assert cap.capabilities == ["context", "slice", "impact"]


def test_probe_tool_flags_noncanonical_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capabilities.shutil,
        "which",
        lambda name: "/Users/you/.cargo/bin/loct",
    )
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: __import__("pathlib").Path("/Users/you/.local/bin"),
    )
    runner = _runner_factory(
        {
            "--version": capabilities.ProbeResult(
                ok=True, returncode=0, stdout="loct 0.11.2"
            ),
            "--help": capabilities.ProbeResult(ok=True, returncode=0, stdout=""),
        }
    )

    cap = capabilities.probe_tool("loct", runner=runner)

    assert cap.runnable is True
    assert cap.provenance == "noncanonical"
    assert cap.status == "noncanonical"


def test_probe_tool_reports_ghost_root_even_when_path_is_minimal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ghost_home = tmp_path / "home"
    ghost_bin = ghost_home / ".cargo" / "bin"
    ghost_bin.mkdir(parents=True)
    binary = ghost_bin / "loct"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: tmp_path / "missing-local-bin",
    )
    monkeypatch.setattr(capabilities.Path, "home", lambda: ghost_home)
    runner = _runner_factory(
        {
            "--version": capabilities.ProbeResult(
                ok=True, returncode=0, stdout="loct 0.12.0"
            ),
            "--help": capabilities.ProbeResult(ok=True, returncode=0, stdout=""),
        }
    )

    cap = capabilities.probe_tool("loct", runner=runner)

    assert cap.executable == str(binary)
    assert cap.runnable is True
    assert cap.provenance == "noncanonical"
    assert cap.status == "noncanonical"


def test_foundation_capabilities_emits_versioned_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        capabilities,
        "vibecrafted_launcher_bin",
        lambda: Path("/definitely/missing/bin"),
    )
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(capabilities, "_ghost_bin_roots", lambda: ())

    payload = capabilities.foundation_capabilities(tools=("loct", "aicx"))

    assert payload["schema"] == "vibecrafted.capabilities.v1"
    assert payload["summary"]["product_missing"] == 2
    assert payload["healthy"] is True  # missing != broken
    assert [t["tool"] for t in payload["tools"]] == ["loct", "aicx"]

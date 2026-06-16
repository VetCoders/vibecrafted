from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from vibecrafted_core import doctor


def test_installer_module_loads_source_file_without_mutating_sys_path(
    monkeypatch, tmp_path: Path
) -> None:
    repo = tmp_path / "vibecrafted"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    installer = scripts / "vetcoders_install.py"
    installer.write_text("VALUE = 'loaded'\n", encoding="utf-8")

    monkeypatch.setattr(doctor, "_INSTALLER_MODULE", None)
    monkeypatch.setattr(doctor, "_repo_root_from_source", lambda: repo)
    before = list(sys.path)

    module = doctor._installer_module()

    assert module.VALUE == "loaded"
    assert sys.path == before


def test_repo_root_from_source_detects_live_checkout() -> None:
    repo_root = doctor._repo_root_from_source()

    assert repo_root is not None
    assert (repo_root / "scripts" / "vetcoders_install.py").is_file()


def test_launcher_shim_finding_flags_bash_deck(tmp_path: Path) -> None:
    deck = tmp_path / "vibecrafted"
    deck.write_text(
        "#!/usr/bin/env bash\n# \U0001d7656 command deck\nset -euo pipefail\n",
        encoding="utf-8",
    )

    findings = doctor._launcher_shim_findings(which=lambda _name: str(deck))

    assert findings, "expected a launcher finding"
    finding = findings[0]
    assert finding.level == "fail"
    assert finding.component == "launcher"
    assert "deck" in finding.message.lower()


def test_launcher_shim_finding_ok_for_uv_shim(tmp_path: Path) -> None:
    shim = tmp_path / "vibecrafted"
    shim.write_text(
        "#!/path/uv/python3\nfrom vibecrafted_core.cli import main\n",
        encoding="utf-8",
    )

    findings = doctor._launcher_shim_findings(which=lambda _name: str(shim))

    assert findings
    finding = findings[0]
    assert finding.level == "ok"
    assert finding.component == "launcher"


def test_launcher_shim_finding_warns_when_absent() -> None:
    findings = doctor._launcher_shim_findings(which=lambda _name: None)

    assert findings
    assert findings[0].level == "warn"
    assert findings[0].component == "launcher"


def test_doctor_summary_counts_findings() -> None:
    payload = doctor.doctor_summary(
        [
            SimpleNamespace(level="ok", component="a", message="fine"),
            SimpleNamespace(level="warn", component="b", message="careful"),
            SimpleNamespace(level="fail", component="c", message="broken"),
        ]
    )

    assert payload["ok"] == 1
    assert payload["warnings"] == 1
    assert payload["failures"] == 1
    assert payload["healthy"] is False

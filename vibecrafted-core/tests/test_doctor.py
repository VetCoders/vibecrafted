from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from xml.parsers.expat import ExpatError

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


def test_server_supervision_finding_proves_current_managed_pair() -> None:
    status = SimpleNamespace(
        installed=True,
        loaded=True,
        supervisor_live=True,
        supervisor_verified=True,
        supervisor_service_managed=True,
        build_current=True,
        pair_healthy=True,
        supervisor_pid=4242,
    )

    findings = doctor._server_supervision_findings(
        platform="darwin",
        which=lambda _name: "/usr/local/bin/vibecrafted",
        config_factory=lambda **kwargs: kwargs,
        status_reader=lambda _config: status,
    )

    assert findings == [
        doctor._Finding(
            "ok",
            "server-supervisor",
            "verified LaunchAgent-managed supervisor and healthy server/guardian "
            "pair (pid=4242, current build)",
        )
    ]


def test_server_supervision_finding_fails_closed_for_stale_pair() -> None:
    status = SimpleNamespace(
        installed=True,
        loaded=False,
        supervisor_live=False,
        supervisor_verified=False,
        supervisor_service_managed=False,
        build_current=False,
        pair_healthy=False,
        supervisor_pid=None,
    )

    findings = doctor._server_supervision_findings(
        platform="darwin",
        which=lambda _name: "/usr/local/bin/vibecrafted",
        config_factory=lambda **kwargs: kwargs,
        status_reader=lambda _config: status,
    )

    assert findings[0].level == "fail"
    assert findings[0].component == "server-supervisor"
    assert "loaded" in findings[0].message
    assert "supervisor_pid" in findings[0].message
    assert "pair_healthy" in findings[0].message


def test_server_supervision_finding_fails_when_probe_raises() -> None:
    def broken_status(_config) -> None:
        raise RuntimeError("stale pidfile")

    findings = doctor._server_supervision_findings(
        platform="darwin",
        which=lambda _name: "/usr/local/bin/vibecrafted",
        config_factory=lambda **kwargs: kwargs,
        status_reader=broken_status,
    )

    assert findings[0].level == "fail"
    assert findings[0].component == "server-supervisor"
    assert "stale pidfile" in findings[0].message


def test_server_supervision_finding_fails_when_plist_is_truncated() -> None:
    def truncated_plist(_config) -> None:
        raise ExpatError("unclosed token")

    findings = doctor._server_supervision_findings(
        platform="darwin",
        which=lambda _name: "/usr/local/bin/vibecrafted",
        config_factory=lambda **kwargs: kwargs,
        status_reader=truncated_plist,
    )

    assert findings[0].level == "fail"
    assert findings[0].component == "server-supervisor"
    assert "unclosed token" in findings[0].message


def test_server_supervision_finding_is_not_applicable_off_macos() -> None:
    findings = doctor._server_supervision_findings(
        platform="linux",
        which=lambda _name: None,
    )

    assert findings[0].level == "ok"
    assert findings[0].component == "server-supervisor"
    assert "not applicable" in findings[0].message


def test_doctor_run_includes_server_supervision_finding(monkeypatch) -> None:
    expected = doctor._Finding("fail", "server-supervisor", "not supervised")

    def missing_installer() -> None:
        raise ModuleNotFoundError

    monkeypatch.setattr(doctor, "_installer_module", missing_installer)
    monkeypatch.setattr(doctor, "_packaged_asset_findings", list)
    monkeypatch.setattr(doctor, "_launcher_shim_findings", list)
    monkeypatch.setattr(doctor, "_server_supervision_findings", lambda: [expected])
    monkeypatch.setattr(doctor, "_vc_frame_delivery_findings", list)
    monkeypatch.setattr(doctor, "_vc_frame_truth_drift_findings", list)

    assert doctor.doctor_run() == [expected]


def _seed_truth(root: Path, content: str = "layout ok\n") -> None:
    (root / "layouts").mkdir(parents=True)
    (root / "config.kdl").write_text(content, encoding="utf-8")
    (root / "layouts" / "operator.kdl").write_text(content, encoding="utf-8")


def _truth_sandbox(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    """Tools home with one published generation behind vibecrafted-current."""
    from vibecrafted_core import frontier_assets

    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    def no_checkout() -> Path:
        raise FileNotFoundError

    monkeypatch.setattr(frontier_assets, "vc_frame_config_source", no_checkout)
    tools = tmp_path / "tools"
    generation = tools / "vibecrafted-generation-test"
    _seed_truth(generation / "config" / "vc-frame")
    _seed_truth(generation / "runtime" / "generated" / "vc-frame")
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "vibecrafted-current").symlink_to(generation)
    home = tmp_path / "home"
    home.mkdir()
    return tools, generation, home


def test_truth_drift_ok_when_generation_agrees(tmp_path: Path, monkeypatch) -> None:
    tools, _, home = _truth_sandbox(tmp_path, monkeypatch)

    findings = doctor._vc_frame_truth_drift_findings(home=home, tools_home=tools)

    assert [finding.level for finding in findings] == ["ok", "ok"]
    assert all(finding.component == "vc-frame:truth" for finding in findings)


def test_truth_drift_fails_when_generation_disagrees_with_itself(
    tmp_path: Path, monkeypatch
) -> None:
    tools, generation, home = _truth_sandbox(tmp_path, monkeypatch)
    drifted = generation / "runtime" / "generated" / "vc-frame" / "config.kdl"
    drifted.write_text("layout drifted\n", encoding="utf-8")

    findings = doctor._vc_frame_truth_drift_findings(home=home, tools_home=tools)

    split = [finding for finding in findings if finding.level == "fail"]
    assert len(split) == 1
    assert "disagrees with itself" in split[0].message
    assert "config.kdl" in split[0].message


def test_truth_drift_warns_when_dev_checkout_runs_ahead(
    tmp_path: Path, monkeypatch
) -> None:
    from vibecrafted_core import frontier_assets

    tools, _, home = _truth_sandbox(tmp_path, monkeypatch)
    checkout = tmp_path / "repo" / "config" / "vc-frame"
    _seed_truth(checkout, content="layout ahead\n")
    monkeypatch.setattr(frontier_assets, "vc_frame_config_source", lambda: checkout)

    findings = doctor._vc_frame_truth_drift_findings(home=home, tools_home=tools)

    ahead = [finding for finding in findings if finding.level == "warn"]
    assert len(ahead) == 1
    assert "dev checkout differs from published store" in ahead[0].message


def test_truth_drift_fails_on_projection_into_parked_generation(
    tmp_path: Path, monkeypatch
) -> None:
    tools, _, home = _truth_sandbox(tmp_path, monkeypatch)
    parked = tools / "vibecrafted-generation-parked"
    _seed_truth(parked / "runtime" / "generated" / "vc-frame")
    view = home / ".config" / "vc-frame"
    view.mkdir(parents=True)
    (view / "config.kdl").symlink_to(
        parked / "runtime" / "generated" / "vc-frame" / "config.kdl"
    )

    findings = doctor._vc_frame_truth_drift_findings(home=home, tools_home=tools)

    stale = [finding for finding in findings if finding.level == "fail"]
    assert len(stale) == 1
    assert "parked generation" in stale[0].message


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

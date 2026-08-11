from __future__ import annotations

import copy
import hashlib
import json
import os
import plistlib
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from vibecrafted_core import product_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = REPO_ROOT / "scripts/verify-vibecrafted-product.sh"
SCHEMA_PATH = (
    REPO_ROOT
    / "vibecrafted-core/vibecrafted_core/schemas/unified_product.schema.v1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _entry(
    root: Path,
    relative: str,
    *,
    kind: str,
    dylibs: list[str] | None = None,
) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": _sha256(path),
        "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        "kind": kind,
        "size": path.stat().st_size,
        "dylibs": dylibs or [],
    }


def _module_fixture(root: Path, module: str = "vc-terminal") -> dict[str, Any]:
    entrypoint_name = "terminal" if module == "vc-terminal" else "frame"
    executable = f"bin/{module}"
    _write_executable(root / executable)
    manifest = {
        "schema": contract.MODULE_SCHEMA,
        "module": module,
        "version": "1.0.0",
        "git_sha": "1" * 40,
        "dirty": False,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "files": [_entry(root, executable, kind="executable")],
        "entrypoints": {entrypoint_name: executable},
    }
    _write_json(root / "module-manifest.json", manifest)
    return manifest


def _app_fixture(app: Path) -> dict[str, Any]:
    for relative in (
        "Contents/MacOS/Vibecrafted",
        "Contents/Helpers/vc-terminal",
        "Contents/Helpers/vc-frame",
    ):
        _write_executable(app / relative)
    plist = app / "Contents/Info.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    with plist.open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleIdentifier": contract.PRODUCT_BUNDLE_ID,
                "CFBundleExecutable": contract.PRODUCT_EXECUTABLE,
            },
            handle,
        )
    manifest = {
        "schema": contract.PRODUCT_SCHEMA,
        "product": contract.PRODUCT_NAME,
        "bundle_id": contract.PRODUCT_BUNDLE_ID,
        "bundle_executable": contract.PRODUCT_EXECUTABLE,
        "version": "1.0.0",
        "git_sha": "2" * 40,
        "dirty": False,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "modules": [
            {
                "module": "vc-terminal",
                "manifest_sha256": "3" * 64,
                "git_sha": "4" * 40,
            },
            {
                "module": "vc-frame",
                "manifest_sha256": "5" * 64,
                "git_sha": "6" * 40,
            },
        ],
        "files": [
            _entry(app, "Contents/Info.plist", kind="config"),
            _entry(app, "Contents/MacOS/Vibecrafted", kind="executable"),
            _entry(app, "Contents/Helpers/vc-terminal", kind="executable"),
            _entry(app, "Contents/Helpers/vc-frame", kind="executable"),
        ],
        "entrypoints": {
            "app": "Contents/MacOS/Vibecrafted",
            "terminal": "Contents/Helpers/vc-terminal",
            "frame": "Contents/Helpers/vc-frame",
        },
    }
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)
    return manifest


def _identity(version: str, digest: str, revision: str) -> dict[str, str]:
    return {
        "version": version,
        "sha256": digest,
        "source_revision": revision,
    }


def _transaction_fixture(path: Path) -> dict[str, Any]:
    previous = {
        "app": _identity("0.9.0", "1" * 64, "2" * 40),
        "runtime": _identity("0.9.0", "3" * 64, "4" * 40),
    }
    new = {
        "app": _identity("1.0.0", "5" * 64, "6" * 40),
        "runtime": _identity("1.0.0", "7" * 64, "8" * 40),
    }
    payload = {
        "schema": contract.TRANSACTION_SCHEMA,
        "transaction_id": "tx-test",
        "previous": previous,
        "new": new,
        "active": copy.deepcopy(new),
        "outcome": "activated",
    }
    _write_json(path, payload)
    return payload


def _walkaround_fixture(path: Path) -> dict[str, Any]:
    dmg = path.parent / "Vibecrafted.dmg"
    dmg.write_bytes(b"synthetic-dmg\n")
    payload = {
        "schema": contract.WALKAROUND_SCHEMA,
        "dmg_path": str(dmg),
        "dmg_sha256": _sha256(dmg),
        "dmg_size": dmg.stat().st_size,
        "product_manifest_sha256": "9" * 64,
        "source_revisions": {
            "vibecrafted": "a" * 40,
            "vc-terminal": "b" * 40,
            "vc-frame": "c" * 40,
        },
        "checks": {name: True for name in contract._WALKAROUND_CHECKS},
    }
    _write_json(path, payload)
    return payload


def _assert_error(code: int, call: Callable[[], Any]) -> None:
    with pytest.raises(contract.ProductContractError) as exc_info:
        call()
    assert exc_info.value.code == code


def test_versioned_json_schema_matches_runtime_contract_ids() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$id"] == "io.vetcoders.vibecrafted.contracts.v1"
    assert schema["$defs"]["moduleManifest"]["properties"]["schema"]["const"] == (
        contract.MODULE_SCHEMA
    )
    assert schema["$defs"]["productManifest"]["properties"]["schema"]["const"] == (
        contract.PRODUCT_SCHEMA
    )
    assert (
        schema["$defs"]["transactionReceipt"]["properties"]["schema"]["const"]
        == contract.TRANSACTION_SCHEMA
    )
    assert (
        schema["$defs"]["walkaroundReceipt"]["properties"]["schema"]["const"]
        == contract.WALKAROUND_SCHEMA
    )


def test_versioned_json_schema_accepts_every_valid_contract_fixture(
    tmp_path: Path,
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    fixtures = [
        _module_fixture(tmp_path / "terminal", "vc-terminal"),
        _module_fixture(tmp_path / "frame", "vc-frame"),
        _app_fixture(tmp_path / "Vibecrafted.app"),
        _transaction_fixture(tmp_path / "transaction.json"),
        _walkaround_fixture(tmp_path / "walkaround.json"),
    ]

    for fixture in fixtures:
        validator.validate(fixture)


@pytest.mark.parametrize("module", ["vc-terminal", "vc-frame"])
def test_valid_module_binds_provenance_inventory_and_entrypoint(
    tmp_path: Path, module: str
) -> None:
    root = tmp_path / module
    expected = _module_fixture(root, module)

    assert contract.verify_module(root) == expected


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_entrypoint", contract.E_MISSING),
        ("absolute_path", contract.E_PATH),
        ("wrong_hash", contract.E_HASH),
        ("host_bound_path", contract.E_PATH),
        ("wrong_mode", contract.E_MODE),
        ("wrong_size", contract.E_SIZE),
        ("extra_file", contract.E_INVENTORY),
        ("external_dylib", contract.E_DEPENDENCY),
        ("wrong_arch", contract.E_PLATFORM),
        ("old_macos", contract.E_PLATFORM),
    ],
)
def test_module_negative_controls_fail_closed_with_stable_codes(
    tmp_path: Path, mutation: str, expected_code: int
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root)
    if mutation == "missing_entrypoint":
        manifest["entrypoints"] = {}
    elif mutation == "absolute_path":
        manifest["files"][0]["path"] = "/tmp/vc-terminal"
    elif mutation == "wrong_hash":
        manifest["files"][0]["sha256"] = "f" * 64
    elif mutation == "host_bound_path":
        _write_executable(
            root / "bin/vc-terminal",
            "#!/bin/sh\nexec /Volumes/vc-workspace/bin/vc-terminal\n",
        )
        manifest["files"][0] = _entry(
            root,
            "bin/vc-terminal",
            kind="executable",
        )
    elif mutation == "wrong_mode":
        manifest["files"][0]["mode"] = "0644"
    elif mutation == "wrong_size":
        manifest["files"][0]["size"] += 1
    elif mutation == "extra_file":
        (root / "undeclared.txt").write_text("extra\n", encoding="utf-8")
    elif mutation == "external_dylib":
        manifest["files"][0]["dylibs"] = ["/opt/homebrew/lib/libescape.dylib"]
    elif mutation == "wrong_arch":
        manifest["architecture"] = "x86_64"
    elif mutation == "old_macos":
        manifest["minimum_macos"] = "13.0"
    _write_json(root / "module-manifest.json", manifest)

    _assert_error(expected_code, lambda: contract.verify_module(root))


def test_valid_app_has_one_bundle_identity_and_three_bound_entrypoints(
    tmp_path: Path,
) -> None:
    app = tmp_path / "Vibecrafted.app"
    expected = _app_fixture(app)

    assert contract.verify_app(app) == expected


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("wrong_bundle_id", contract.E_BUNDLE),
        ("wrong_executable", contract.E_BUNDLE),
        ("missing_module", contract.E_SCHEMA),
        ("undeclared_file", contract.E_INVENTORY),
        ("nested_app", contract.E_BUNDLE),
    ],
)
def test_app_negative_controls_reject_competing_or_unbound_product_shape(
    tmp_path: Path, mutation: str, expected_code: int
) -> None:
    app = tmp_path / "Vibecrafted.app"
    manifest = _app_fixture(app)
    if mutation == "wrong_bundle_id":
        manifest["bundle_id"] = "space.div0.vibecrafted"
    elif mutation == "wrong_executable":
        manifest["bundle_executable"] = "vibecrafted-launch"
    elif mutation == "missing_module":
        manifest["modules"] = manifest["modules"][:1]
    elif mutation == "undeclared_file":
        (app / "Contents/Resources/ambient-path.txt").write_text(
            "/Applications/Vibecrafted.app\n", encoding="utf-8"
        )
    elif mutation == "nested_app":
        nested = app / "Contents/Resources/Second.app/Contents"
        nested.mkdir(parents=True)
        (nested / ".keep").write_text("nested app\n", encoding="utf-8")
        manifest["files"].append(
            _entry(
                app,
                "Contents/Resources/Second.app/Contents/.keep",
                kind="resource",
            )
        )
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)

    _assert_error(expected_code, lambda: contract.verify_app(app))


def test_transaction_receipt_binds_app_and_runtime_as_one_active_pair(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "transaction.json"
    expected = _transaction_fixture(receipt)

    assert contract.verify_transaction(receipt) == expected

    split = copy.deepcopy(expected)
    split["active"]["runtime"] = copy.deepcopy(split["previous"]["runtime"])
    _write_json(receipt, split)
    _assert_error(
        contract.E_TRANSACTION,
        lambda: contract.verify_transaction(receipt),
    )

    rolled_back = copy.deepcopy(expected)
    rolled_back["outcome"] = "rolled_back"
    rolled_back["active"] = copy.deepcopy(rolled_back["previous"])
    _write_json(receipt, rolled_back)
    assert contract.verify_transaction(receipt) == rolled_back


def test_walkaround_receipt_requires_exact_artifact_and_every_proof(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "walkaround.json"
    expected = _walkaround_fixture(receipt)

    assert contract.verify_walkaround(receipt) == expected

    failed = copy.deepcopy(expected)
    failed["checks"]["gatekeeper"] = False
    _write_json(receipt, failed)
    _assert_error(contract.E_PROOF, lambda: contract.verify_walkaround(receipt))

    _write_json(receipt, expected)
    Path(expected["dmg_path"]).write_bytes(b"tampered\n")
    _assert_error(contract.E_SIZE, lambda: contract.verify_walkaround(receipt))


def test_cli_returns_distinct_nonzero_codes_for_hash_and_dylib_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root)
    assert contract.main(["module", str(root)]) == 0

    manifest["files"][0]["sha256"] = "f" * 64
    _write_json(root / "module-manifest.json", manifest)
    assert contract.main(["module", str(root)]) == contract.E_HASH
    assert "VCPC024" in capsys.readouterr().err

    manifest = _module_fixture(root)
    manifest["files"][0]["dylibs"] = ["/usr/local/lib/libescape.dylib"]
    _write_json(root / "module-manifest.json", manifest)
    assert contract.main(["module", str(root)]) == contract.E_DEPENDENCY
    assert "VCPC027" in capsys.readouterr().err


def test_shell_front_door_self_test_exercises_real_verifier() -> None:
    env = {
        "HOME": os.environ["HOME"],
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [str(VERIFY_SCRIPT), "--self-test"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "self-test: PASS valid=4 negative=2 error_codes=24,27" in result.stdout

from __future__ import annotations

import copy
import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys
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


def _clang() -> str:
    if sys.platform != "darwin":
        pytest.skip("unified app contract requires macOS Mach-O tooling")
    xcrun = shutil.which("xcrun")
    if xcrun is None:
        pytest.skip("xcrun is unavailable")
    return xcrun


def _compile_macho(
    path: Path,
    *,
    source: str = "int main(void) { return 0; }\n",
    architecture: str = "arm64",
    minimum_macos: str = "14.0",
    extra_args: tuple[str, ...] = (),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            _clang(),
            "--sdk",
            "macosx",
            "clang",
            "-arch",
            architecture,
            f"-mmacosx-version-min={minimum_macos}",
            *extra_args,
            "-x",
            "c",
            "-",
            "-o",
            str(path),
        ],
        input=source,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="session")
def macho_executable(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("unified-contract-macho") / "fixture"
    _compile_macho(path)
    return path


def _macho_dependencies(path: Path) -> list[str]:
    result = subprocess.run(
        ["otool", "-L", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        line.strip().split(" (", 1)[0]
        for line in result.stdout.splitlines()[1:]
        if line.strip()
    ]


def _entry(
    root: Path,
    relative: str,
    *,
    kind: str,
    dylibs: list[str] | None = None,
) -> dict[str, Any]:
    path = root / relative
    if dylibs is None and kind in {"executable", "dylib"}:
        dylibs = _macho_dependencies(path)
    return {
        "path": relative,
        "sha256": _sha256(path),
        "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        "kind": kind,
        "size": path.stat().st_size,
        "dylibs": dylibs or [],
    }


def _module_fixture(
    root: Path, macho_executable: Path, module: str = "vc-terminal"
) -> dict[str, Any]:
    entrypoint_name = "terminal" if module == "vc-terminal" else "frame"
    executable = f"bin/{module}"
    (root / executable).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(macho_executable, root / executable)
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


def _app_fixture(app: Path, macho_executable: Path) -> dict[str, Any]:
    for relative in (
        "Contents/MacOS/Vibecrafted",
        "Contents/Helpers/vc-terminal",
        "Contents/Helpers/vc-frame",
    ):
        (app / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(macho_executable, app / relative)
    plist = app / "Contents/Info.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    with plist.open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleIdentifier": contract.PRODUCT_BUNDLE_ID,
                "CFBundleExecutable": contract.PRODUCT_EXECUTABLE,
                "CFBundleShortVersionString": "1.0.0",
                "CFBundleVersion": "1",
            },
            handle,
        )
    terminal_product_entry = _entry(
        app, "Contents/Helpers/vc-terminal", kind="executable"
    )
    frame_product_entry = _entry(app, "Contents/Helpers/vc-frame", kind="executable")

    def add_module_receipt(
        *,
        module: str,
        git_sha: str,
        entrypoint_name: str,
        product_entry: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        module_path = f"bin/{module}"
        module_entry = copy.deepcopy(product_entry)
        module_entry["path"] = module_path
        receipt = {
            "schema": contract.MODULE_SCHEMA,
            "module": module,
            "version": "1.0.0",
            "git_sha": git_sha,
            "dirty": False,
            "architecture": "arm64",
            "minimum_macos": "14.0",
            "files": [module_entry],
            "entrypoints": {entrypoint_name: module_path},
        }
        relative = f"Contents/Resources/module-receipts/{module}/module-manifest.json"
        _write_json(app / relative, receipt)
        return relative, receipt

    terminal_receipt_path, _ = add_module_receipt(
        module="vc-terminal",
        git_sha="4" * 40,
        entrypoint_name="terminal",
        product_entry=terminal_product_entry,
    )
    frame_receipt_path, _ = add_module_receipt(
        module="vc-frame",
        git_sha="6" * 40,
        entrypoint_name="frame",
        product_entry=frame_product_entry,
    )
    manifest = {
        "schema": contract.PRODUCT_SCHEMA,
        "product": contract.PRODUCT_NAME,
        "bundle_id": contract.PRODUCT_BUNDLE_ID,
        "bundle_executable": contract.PRODUCT_EXECUTABLE,
        "version": "1.0.0",
        "build": "1",
        "git_sha": "2" * 40,
        "dirty": False,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "modules": [
            {
                "module": "vc-terminal",
                "manifest_path": terminal_receipt_path,
                "manifest_sha256": _sha256(app / terminal_receipt_path),
                "git_sha": "4" * 40,
                "files": [
                    {
                        "module_path": "bin/vc-terminal",
                        "product_path": "Contents/Helpers/vc-terminal",
                    }
                ],
            },
            {
                "module": "vc-frame",
                "manifest_path": frame_receipt_path,
                "manifest_sha256": _sha256(app / frame_receipt_path),
                "git_sha": "6" * 40,
                "files": [
                    {
                        "module_path": "bin/vc-frame",
                        "product_path": "Contents/Helpers/vc-frame",
                    }
                ],
            },
        ],
        "files": [
            _entry(app, "Contents/Info.plist", kind="config"),
            _entry(app, "Contents/MacOS/Vibecrafted", kind="executable"),
            terminal_product_entry,
            frame_product_entry,
            _entry(app, terminal_receipt_path, kind="config"),
            _entry(app, frame_receipt_path, kind="config"),
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


def _walkaround_fixture(path: Path, macho_executable: Path) -> dict[str, Any]:
    dmg = path.parent / "Vibecrafted.dmg"
    dmg.write_bytes(b"synthetic-dmg\n")
    mount = path.parent / "mounted"
    app = mount / "Vibecrafted.app"
    _app_fixture(app, macho_executable)
    live_commands = contract._expected_live_commands(app, dmg)
    proofs: dict[str, Any] = {}
    for name in sorted(contract._WALKAROUND_CHECKS):
        stdout = path.parent / f"proofs/{name}.stdout"
        stderr = path.parent / f"proofs/{name}.stderr"
        stdout.parent.mkdir(parents=True, exist_ok=True)
        stdout.write_text(f"{name}: passed\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        proofs[name] = {
            "command": live_commands.get(name, [f"verify-{name}", str(app)]),
            "exit_code": 0,
            "stdout": {
                "path": stdout.relative_to(path.parent).as_posix(),
                "sha256": _sha256(stdout),
                "size": stdout.stat().st_size,
            },
            "stderr": {
                "path": stderr.relative_to(path.parent).as_posix(),
                "sha256": _sha256(stderr),
                "size": stderr.stat().st_size,
            },
        }
    payload = {
        "schema": contract.WALKAROUND_SCHEMA,
        "dmg_path": str(dmg),
        "dmg_sha256": _sha256(dmg),
        "dmg_size": dmg.stat().st_size,
        "mount_path": str(mount),
        "app_path": str(app),
        "product_manifest_sha256": _sha256(
            app / "Contents/Resources/product-manifest.json"
        ),
        "source_revisions": {
            "vibecrafted": "2" * 40,
            "vc-terminal": "4" * 40,
            "vc-frame": "6" * 40,
        },
        "proofs": proofs,
    }
    _write_json(path, payload)
    return payload


def _patch_walkaround_runtime(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    *,
    live_calls: list[tuple[Path, Path]] | None = None,
) -> None:
    dmg = Path(payload["dmg_path"])
    mount = Path(payload["mount_path"])
    monkeypatch.setattr(
        contract,
        "_attached_image_mounts",
        lambda: {(dmg.resolve(), mount.resolve())},
    )

    def record(app: Path, artifact: Path) -> None:
        if live_calls is not None:
            live_calls.append((app, artifact))

    monkeypatch.setattr(contract, "_run_live_release_checks", record)


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
    tmp_path: Path, macho_executable: Path
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    fixtures = [
        _module_fixture(tmp_path / "terminal", macho_executable, "vc-terminal"),
        _module_fixture(tmp_path / "frame", macho_executable, "vc-frame"),
        _app_fixture(tmp_path / "Vibecrafted.app", macho_executable),
        _transaction_fixture(tmp_path / "transaction.json"),
        _walkaround_fixture(tmp_path / "walkaround.json", macho_executable),
    ]

    for fixture in fixtures:
        validator.validate(fixture)


@pytest.mark.parametrize("module", ["vc-terminal", "vc-frame"])
def test_valid_module_binds_provenance_inventory_and_entrypoint(
    tmp_path: Path, macho_executable: Path, module: str
) -> None:
    root = tmp_path / module
    expected = _module_fixture(root, macho_executable, module)

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
    tmp_path: Path,
    macho_executable: Path,
    mutation: str,
    expected_code: int,
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root, macho_executable)
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


@pytest.mark.parametrize(
    ("actual_architecture", "actual_minimum"),
    [("x86_64", "13.0"), ("arm64", "13.0")],
)
def test_module_measures_macho_platform_instead_of_trusting_manifest(
    tmp_path: Path,
    macho_executable: Path,
    actual_architecture: str,
    actual_minimum: str,
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root, macho_executable)
    _compile_macho(
        root / "bin/vc-terminal",
        architecture=actual_architecture,
        minimum_macos=actual_minimum,
    )
    manifest["files"][0] = _entry(root, "bin/vc-terminal", kind="executable")
    _write_json(root / "module-manifest.json", manifest)

    _assert_error(contract.E_PLATFORM, lambda: contract.verify_module(root))


def test_module_rejects_ambient_lc_rpath_even_when_basename_is_bundled(
    tmp_path: Path,
) -> None:
    root = tmp_path / "module"
    dylib = root / "lib/libfixture.dylib"
    _compile_macho(
        dylib,
        source="int fixture(void) { return 0; }\n",
        extra_args=(
            "-dynamiclib",
            "-Wl,-install_name,@rpath/libfixture.dylib",
        ),
    )
    executable = root / "bin/vc-terminal"
    _compile_macho(
        executable,
        source="extern int fixture(void); int main(void) { return fixture(); }\n",
        extra_args=(
            f"-L{dylib.parent}",
            "-lfixture",
            "-Wl,-rpath,/tmp",
        ),
    )
    manifest = {
        "schema": contract.MODULE_SCHEMA,
        "module": "vc-terminal",
        "version": "1.0.0",
        "git_sha": "1" * 40,
        "dirty": False,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "files": [
            _entry(root, "bin/vc-terminal", kind="executable"),
            _entry(root, "lib/libfixture.dylib", kind="dylib"),
        ],
        "entrypoints": {"terminal": "bin/vc-terminal"},
    }
    _write_json(root / "module-manifest.json", manifest)

    _assert_error(contract.E_DEPENDENCY, lambda: contract.verify_module(root))


def test_module_resolves_loader_relative_rpath_to_exact_declared_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "module"
    dylib = root / "lib/libfixture.dylib"
    _compile_macho(
        dylib,
        source="int fixture(void) { return 0; }\n",
        extra_args=(
            "-dynamiclib",
            "-Wl,-install_name,@rpath/libfixture.dylib",
        ),
    )
    executable = root / "bin/vc-terminal"
    _compile_macho(
        executable,
        source="extern int fixture(void); int main(void) { return fixture(); }\n",
        extra_args=(
            f"-L{dylib.parent}",
            "-lfixture",
            "-Wl,-rpath,@loader_path/../lib",
        ),
    )
    manifest = {
        "schema": contract.MODULE_SCHEMA,
        "module": "vc-terminal",
        "version": "1.0.0",
        "git_sha": "1" * 40,
        "dirty": False,
        "architecture": "arm64",
        "minimum_macos": "14.0",
        "files": [
            _entry(root, "bin/vc-terminal", kind="executable"),
            _entry(root, "lib/libfixture.dylib", kind="dylib"),
        ],
        "entrypoints": {"terminal": "bin/vc-terminal"},
    }
    _write_json(root / "module-manifest.json", manifest)

    assert contract.verify_module(root) == manifest


def test_release_policy_can_require_clean_module_receipts(
    tmp_path: Path, macho_executable: Path
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root, macho_executable)
    manifest["dirty"] = True
    _write_json(root / "module-manifest.json", manifest)

    assert contract.verify_module(root) == manifest
    _assert_error(
        contract.E_PROOF,
        lambda: contract.verify_module(root, require_clean=True),
    )
    assert contract.main(["module", str(root), "--require-clean"]) == contract.E_PROOF


def test_valid_app_has_one_bundle_identity_and_three_bound_entrypoints(
    tmp_path: Path, macho_executable: Path
) -> None:
    app = tmp_path / "Vibecrafted.app"
    expected = _app_fixture(app, macho_executable)

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
    tmp_path: Path,
    macho_executable: Path,
    mutation: str,
    expected_code: int,
) -> None:
    app = tmp_path / "Vibecrafted.app"
    manifest = _app_fixture(app, macho_executable)
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


def test_app_binds_embedded_module_receipt_bytes_and_copied_inventory(
    tmp_path: Path, macho_executable: Path
) -> None:
    app = tmp_path / "Vibecrafted.app"
    manifest = _app_fixture(app, macho_executable)
    binding = manifest["modules"][0]
    receipt_path = app / binding["manifest_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["git_sha"] = "e" * 40
    _write_json(receipt_path, receipt)
    binding["manifest_sha256"] = _sha256(receipt_path)
    receipt_entry = next(
        item for item in manifest["files"] if item["path"] == binding["manifest_path"]
    )
    receipt_entry.update(_entry(app, binding["manifest_path"], kind="config"))
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)

    _assert_error(contract.E_PROOF, lambda: contract.verify_app(app))


def test_app_binds_manifest_version_to_dictionary_info_plist(
    tmp_path: Path, macho_executable: Path
) -> None:
    app = tmp_path / "Vibecrafted.app"
    manifest = _app_fixture(app, macho_executable)
    manifest["version"] = "9.9.9"
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)
    _assert_error(contract.E_BUNDLE, lambda: contract.verify_app(app))

    plist_path = app / "Contents/Info.plist"
    with plist_path.open("wb") as handle:
        plistlib.dump(["not", "a", "dictionary"], handle)
    plist_entry = next(
        item for item in manifest["files"] if item["path"] == "Contents/Info.plist"
    )
    plist_entry.update(_entry(app, "Contents/Info.plist", kind="config"))
    manifest["version"] = "1.0.0"
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)
    _assert_error(contract.E_BUNDLE, lambda: contract.verify_app(app))


def test_app_allows_install_location_copy_in_declared_resource(
    tmp_path: Path, macho_executable: Path
) -> None:
    app = tmp_path / "Vibecrafted.app"
    manifest = _app_fixture(app, macho_executable)
    resource = app / "Contents/Resources/install-help.txt"
    resource.write_text("Drag to /Applications/Vibecrafted.app\n", encoding="utf-8")
    manifest["files"].append(
        _entry(app, "Contents/Resources/install-help.txt", kind="resource")
    )
    _write_json(app / "Contents/Resources/product-manifest.json", manifest)

    assert contract.verify_app(app) == manifest


def test_schema_and_runtime_reject_the_same_module_and_binding_shapes(
    tmp_path: Path, macho_executable: Path
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    module_root = tmp_path / "module"
    module = _module_fixture(module_root, macho_executable)
    module["entrypoints"] = {"frame": "bin/vc-terminal"}
    _write_json(module_root / "module-manifest.json", module)
    assert list(validator.iter_errors(module))
    _assert_error(contract.E_MISSING, lambda: contract.verify_module(module_root))

    app = tmp_path / "Vibecrafted.app"
    product = _app_fixture(app, macho_executable)
    product["modules"][1] = copy.deepcopy(product["modules"][0])
    _write_json(app / "Contents/Resources/product-manifest.json", product)
    assert list(validator.iter_errors(product))
    _assert_error(contract.E_SCHEMA, lambda: contract.verify_app(app))


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
    macho_executable: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "walkaround.json"
    expected = _walkaround_fixture(receipt, macho_executable)
    live_calls: list[tuple[Path, Path]] = []
    _patch_walkaround_runtime(monkeypatch, expected, live_calls=live_calls)

    assert contract.verify_walkaround(receipt) == expected
    assert live_calls == [(Path(expected["app_path"]), Path(expected["dmg_path"]))]

    failed = copy.deepcopy(expected)
    failed["proofs"]["gatekeeper"]["exit_code"] = 1
    _write_json(receipt, failed)
    _assert_error(contract.E_PROOF, lambda: contract.verify_walkaround(receipt))

    wrong_command = copy.deepcopy(expected)
    wrong_command["proofs"]["codesign"]["command"] = ["true"]
    _write_json(receipt, wrong_command)
    _assert_error(contract.E_PROOF, lambda: contract.verify_walkaround(receipt))

    unbound_product = copy.deepcopy(expected)
    unbound_product["product_manifest_sha256"] = "9" * 64
    _write_json(receipt, unbound_product)
    _assert_error(contract.E_HASH, lambda: contract.verify_walkaround(receipt))

    tampered_proof = copy.deepcopy(expected)
    stdout_path = (
        receipt.parent / tampered_proof["proofs"]["start_here"]["stdout"]["path"]
    )
    stdout_path.write_text("fabricated\n", encoding="utf-8")
    _write_json(receipt, tampered_proof)
    _assert_error(contract.E_SIZE, lambda: contract.verify_walkaround(receipt))

    _write_json(receipt, expected)
    Path(expected["dmg_path"]).write_bytes(b"tampered\n")
    _assert_error(contract.E_SIZE, lambda: contract.verify_walkaround(receipt))


def test_walkaround_proof_artifacts_cannot_escape_through_symlinked_parent(
    tmp_path: Path,
    macho_executable: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "walkaround.json"
    payload = _walkaround_fixture(receipt, macho_executable)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    escaped = outside / "codesign.stdout"
    escaped.write_text("fabricated evidence\n", encoding="utf-8")
    proof_parent = tmp_path / "proof-link"
    proof_parent.symlink_to(outside, target_is_directory=True)
    payload["proofs"]["codesign"]["stdout"] = {
        "path": "proof-link/codesign.stdout",
        "sha256": _sha256(escaped),
        "size": escaped.stat().st_size,
    }
    _write_json(receipt, payload)
    _patch_walkaround_runtime(monkeypatch, payload)

    _assert_error(contract.E_DEPENDENCY, lambda: contract.verify_walkaround(receipt))


def test_cli_returns_distinct_nonzero_codes_for_hash_and_dylib_failures(
    tmp_path: Path,
    macho_executable: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "module"
    manifest = _module_fixture(root, macho_executable)
    assert contract.main(["module", str(root)]) == 0

    manifest["files"][0]["sha256"] = "f" * 64
    _write_json(root / "module-manifest.json", manifest)
    assert contract.main(["module", str(root)]) == contract.E_HASH
    assert "VCPC024" in capsys.readouterr().err

    manifest = _module_fixture(root, macho_executable)
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

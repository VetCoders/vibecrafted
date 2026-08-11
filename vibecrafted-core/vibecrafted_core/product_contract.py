"""Fail-closed contracts for the unified Vibecrafted macOS product.

The module payloads, assembled app, activation transaction, and release
walk-around each have a versioned manifest.  This verifier intentionally takes
only paths supplied by the caller: it never searches sibling checkouts, PATH,
or ``/Applications`` for product inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

MODULE_SCHEMA = "io.vetcoders.vibecrafted.module.v1"
PRODUCT_SCHEMA = "io.vetcoders.vibecrafted.product.v1"
TRANSACTION_SCHEMA = "io.vetcoders.vibecrafted.transaction.v1"
WALKAROUND_SCHEMA = "io.vetcoders.vibecrafted.walkaround.v1"

PRODUCT_NAME = "Vibecrafted"
PRODUCT_BUNDLE_ID = "io.vetcoders.vibecrafted"
PRODUCT_EXECUTABLE = "Vibecrafted"
SUPPORTED_MODULES = frozenset({"vc-terminal", "vc-frame"})
SUPPORTED_ARCHITECTURES = frozenset({"arm64"})
MINIMUM_MACOS = (14, 0)

E_JSON = 20
E_SCHEMA = 21
E_MISSING = 22
E_PATH = 23
E_HASH = 24
E_INVENTORY = 25
E_BUNDLE = 26
E_DEPENDENCY = 27
E_TRANSACTION = 28
E_PLATFORM = 29
E_MODE = 30
E_SIZE = 31
E_ENTRYPOINT = 32
E_PROOF = 33

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_MODE_RE = re.compile(r"0[0-7]{3}")
_MACOS_RE = re.compile(r"([0-9]+)\.([0-9]+)")
_HOST_BOUND_PATH_RE = re.compile(
    rb"(?:^|[\s\"'=:(])(?P<path>/(?:Volumes|Users|Applications|opt/homebrew|usr/local)/[^\s\"'\x00]{0,512})"
)
_FILE_KINDS = frozenset({"executable", "dylib", "resource", "config"})
_APP_ENTRYPOINTS = frozenset({"app", "terminal", "frame"})
_WALKAROUND_CHECKS = frozenset(
    {
        "one_app",
        "codesign",
        "app_notarization",
        "dmg_notarization",
        "gatekeeper",
        "sanitized_launch",
        "mission_control",
        "bundled_console",
        "start_here",
        "update",
        "rollback",
        "reattach",
        "one_outer_writer",
    }
)


class ProductContractError(ValueError):
    """A stable, machine-classifiable unified-product contract violation."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: int, message: str) -> NoReturn:
    raise ProductContractError(code, message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        _fail(E_MISSING, f"missing manifest or receipt: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(E_JSON, f"invalid JSON at {path}: {exc}")
    if not isinstance(payload, dict):
        _fail(E_SCHEMA, f"top-level JSON must be an object: {path}")
    return payload


def _expect_keys(
    payload: Mapping[str, Any],
    *,
    required: set[str] | frozenset[str],
    context: str,
) -> None:
    missing = sorted(set(required) - set(payload))
    extra = sorted(set(payload) - set(required))
    if missing:
        _fail(E_MISSING, f"{context} missing keys: {', '.join(missing)}")
    if extra:
        _fail(E_SCHEMA, f"{context} has unknown keys: {', '.join(extra)}")


def _expect_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(E_SCHEMA, f"{field} must be a non-empty string")
    return value


def _expect_sha256(value: Any, *, field: str) -> str:
    text = _expect_string(value, field=field)
    if not _SHA256_RE.fullmatch(text):
        _fail(E_SCHEMA, f"{field} must be a lowercase SHA-256")
    return text


def _expect_git_sha(value: Any, *, field: str) -> str:
    text = _expect_string(value, field=field)
    if not _GIT_SHA_RE.fullmatch(text):
        _fail(E_SCHEMA, f"{field} must be a full lowercase Git SHA")
    return text


def _relative_path(value: Any, *, field: str) -> Path:
    text = _expect_string(value, field=field)
    pure = PurePosixPath(text)
    if (
        pure.is_absolute()
        or pure in {PurePosixPath("."), PurePosixPath("..")}
        or ".." in pure.parts
        or "\\" in text
        or pure.as_posix() != text
    ):
        _fail(E_PATH, f"{field} must be a normalized relative POSIX path: {text}")
    return Path(*pure.parts)


def _minimum_macos(value: Any, *, field: str) -> str:
    text = _expect_string(value, field=field)
    match = _MACOS_RE.fullmatch(text)
    if not match:
        _fail(E_PLATFORM, f"{field} must be major.minor")
    version = (int(match.group(1)), int(match.group(2)))
    if version < MINIMUM_MACOS:
        _fail(E_PLATFORM, f"{field} must be macOS 14.0 or newer")
    return text


def _validate_platform(payload: Mapping[str, Any], *, context: str) -> None:
    architecture = _expect_string(
        payload.get("architecture"), field=f"{context}.architecture"
    )
    if architecture not in SUPPORTED_ARCHITECTURES:
        _fail(E_PLATFORM, f"{context} unsupported architecture: {architecture!r}")
    _minimum_macos(payload.get("minimum_macos"), field=f"{context}.minimum_macos")


def _is_excluded(relative: Path, exclusions: Sequence[Path]) -> bool:
    return any(relative == item or item in relative.parents for item in exclusions)


def _payload_files(root: Path, *, exclusions: Sequence[Path]) -> set[str]:
    files: set[str] = set()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _is_excluded(relative, exclusions):
            continue
        if path.is_symlink():
            _fail(E_PATH, f"payload symlinks are forbidden: {relative.as_posix()}")
        if path.is_file():
            files.add(relative.as_posix())
    return files


def _dependency_is_closed(dependency: str, declared_paths: set[str]) -> bool:
    if dependency.startswith(("/usr/lib/", "/System/Library/")):
        return True
    prefixes = ("@executable_path/", "@loader_path/", "@rpath/")
    if dependency.startswith(prefixes):
        target_name = PurePosixPath(dependency).name
        return any(PurePosixPath(path).name == target_name for path in declared_paths)
    return False


def _observed_macho_dependencies(path: Path, *, kind: str) -> list[str] | None:
    file_tool = shutil.which("file")
    if file_tool is None:
        _fail(E_DEPENDENCY, "file(1) is required to inspect executable payloads")
    probe = subprocess.run(
        [file_tool, "-b", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        _fail(E_DEPENDENCY, f"file(1) could not inspect {path}")
    if "Mach-O" not in probe.stdout:
        if kind == "dylib":
            _fail(E_DEPENDENCY, f"declared dylib is not Mach-O: {path}")
        return None
    otool = shutil.which("otool")
    if otool is None:
        _fail(E_DEPENDENCY, "otool is required to inspect Mach-O dependencies")
    result = subprocess.run(
        [otool, "-L", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(E_DEPENDENCY, f"otool could not inspect {path}")
    dependencies: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        stripped = line.strip()
        if stripped:
            dependencies.append(stripped.split(" (", 1)[0])
    return dependencies


def _reject_host_bound_paths(path: Path, *, relative: str) -> None:
    """Reject payload bytes that silently bind a module to the build host."""
    try:
        content = path.read_bytes()
    except OSError:
        return
    match = _HOST_BOUND_PATH_RE.search(content)
    if match:
        host_path = match.group("path").decode("utf-8", errors="replace")
        _fail(
            E_PATH,
            f"host-bound absolute path in {relative}: {host_path}",
        )


def _validate_files(
    root: Path,
    raw_files: Any,
    *,
    manifest_relative: Path,
    exclusions: Sequence[Path] = (),
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(raw_files, list) or not raw_files:
        _fail(E_SCHEMA, "files must be a non-empty array")
    entries: dict[str, Mapping[str, Any]] = {}
    required = {"path", "sha256", "mode", "kind", "size", "dylibs"}
    for index, raw in enumerate(raw_files):
        context = f"files[{index}]"
        if not isinstance(raw, dict):
            _fail(E_SCHEMA, f"{context} must be an object")
        _expect_keys(raw, required=required, context=context)
        relative = _relative_path(raw["path"], field=f"{context}.path")
        relative_text = relative.as_posix()
        if relative_text in entries:
            _fail(E_INVENTORY, f"duplicate manifest path: {relative_text}")
        expected_hash = _expect_sha256(raw["sha256"], field=f"{context}.sha256")
        mode = _expect_string(raw["mode"], field=f"{context}.mode")
        if not _MODE_RE.fullmatch(mode):
            _fail(E_SCHEMA, f"{context}.mode must be a four-digit octal string")
        kind = _expect_string(raw["kind"], field=f"{context}.kind")
        if kind not in _FILE_KINDS:
            _fail(E_SCHEMA, f"{context}.kind is unsupported: {kind!r}")
        size = raw["size"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _fail(E_SCHEMA, f"{context}.size must be a non-negative integer")
        dylibs = raw["dylibs"]
        if not isinstance(dylibs, list) or not all(
            isinstance(item, str) and item for item in dylibs
        ):
            _fail(E_SCHEMA, f"{context}.dylibs must be an array of strings")
        if len(dylibs) != len(set(dylibs)):
            _fail(E_SCHEMA, f"{context}.dylibs must not contain duplicates")
        entries[relative_text] = raw

        candidate = root / relative
        if not candidate.is_file() or candidate.is_symlink():
            _fail(E_MISSING, f"manifest-bound file is missing: {relative_text}")
        _reject_host_bound_paths(candidate, relative=relative_text)
        actual_mode = f"{stat.S_IMODE(candidate.stat().st_mode):04o}"
        if actual_mode != mode:
            _fail(
                E_MODE,
                f"mode mismatch for {relative_text}: expected {mode}, got {actual_mode}",
            )
        actual_size = candidate.stat().st_size
        if actual_size != size:
            _fail(
                E_SIZE,
                f"size mismatch for {relative_text}: expected {size}, got {actual_size}",
            )
        actual_hash = _sha256(candidate)
        if actual_hash != expected_hash:
            _fail(E_HASH, f"SHA-256 mismatch for {relative_text}")

    declared_paths = set(entries)
    for relative_text, raw in entries.items():
        declared_dylibs = list(raw["dylibs"])
        for dependency in declared_dylibs:
            if not _dependency_is_closed(dependency, declared_paths):
                _fail(
                    E_DEPENDENCY,
                    f"external dylib for {relative_text}: {dependency}",
                )
        kind = str(raw["kind"])
        if kind not in {"executable", "dylib"}:
            if declared_dylibs:
                _fail(E_DEPENDENCY, f"non-code file declares dylibs: {relative_text}")
            continue
        observed = _observed_macho_dependencies(root / relative_text, kind=kind)
        if observed is not None and sorted(observed) != sorted(declared_dylibs):
            _fail(
                E_DEPENDENCY,
                f"declared dylibs do not match otool for {relative_text}",
            )

    actual_paths = _payload_files(
        root,
        exclusions=(manifest_relative, *exclusions),
    )
    missing = sorted(declared_paths - actual_paths)
    extra = sorted(actual_paths - declared_paths)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extra:
            details.append(f"undeclared={','.join(extra)}")
        _fail(E_INVENTORY, "payload inventory mismatch: " + " ".join(details))
    return entries


def _validate_entrypoints(
    root: Path,
    raw_entrypoints: Any,
    files: Mapping[str, Mapping[str, Any]],
    *,
    required_names: frozenset[str],
) -> dict[str, str]:
    if not isinstance(raw_entrypoints, dict):
        _fail(E_SCHEMA, "entrypoints must be an object")
    _expect_keys(
        raw_entrypoints,
        required=required_names,
        context="entrypoints",
    )
    entrypoints: dict[str, str] = {}
    for name in sorted(required_names):
        relative = _relative_path(raw_entrypoints[name], field=f"entrypoints.{name}")
        relative_text = relative.as_posix()
        entry = files.get(relative_text)
        if entry is None:
            _fail(E_ENTRYPOINT, f"entrypoint is not manifest-bound: {relative_text}")
        if entry["kind"] != "executable":
            _fail(E_ENTRYPOINT, f"entrypoint is not executable-kind: {relative_text}")
        if not os.access(root / relative, os.X_OK):
            _fail(E_ENTRYPOINT, f"entrypoint lacks executable mode: {relative_text}")
        entrypoints[name] = relative_text
    return entrypoints


def verify_module(root: str | Path) -> dict[str, Any]:
    """Verify one explicit unsigned vc-terminal or vc-frame module directory."""
    module_root = Path(root)
    if not module_root.is_dir() or module_root.is_symlink():
        _fail(E_MISSING, f"module root is not a directory: {module_root}")
    manifest_relative = Path("module-manifest.json")
    payload = _load_json(module_root / manifest_relative)
    required = {
        "schema",
        "module",
        "version",
        "git_sha",
        "dirty",
        "architecture",
        "minimum_macos",
        "files",
        "entrypoints",
    }
    _expect_keys(payload, required=required, context="module manifest")
    if payload["schema"] != MODULE_SCHEMA:
        _fail(E_SCHEMA, f"module schema must be {MODULE_SCHEMA}")
    module_name = _expect_string(payload["module"], field="module")
    if module_name not in SUPPORTED_MODULES:
        _fail(E_SCHEMA, f"unsupported module: {module_name!r}")
    _expect_string(payload["version"], field="version")
    _expect_git_sha(payload["git_sha"], field="git_sha")
    if not isinstance(payload["dirty"], bool):
        _fail(E_SCHEMA, "dirty must be boolean")
    _validate_platform(payload, context="module")
    files = _validate_files(
        module_root,
        payload["files"],
        manifest_relative=manifest_relative,
    )
    required_entrypoints = frozenset(
        {"terminal"} if module_name == "vc-terminal" else {"frame"}
    )
    _validate_entrypoints(
        module_root,
        payload["entrypoints"],
        files,
        required_names=required_entrypoints,
    )
    return payload


def _validate_product_modules(raw_modules: Any) -> None:
    if not isinstance(raw_modules, list) or len(raw_modules) != 2:
        _fail(E_SCHEMA, "product modules must contain terminal and frame receipts")
    names: set[str] = set()
    required = {"module", "manifest_sha256", "git_sha"}
    for index, item in enumerate(raw_modules):
        if not isinstance(item, dict):
            _fail(E_SCHEMA, f"modules[{index}] must be an object")
        _expect_keys(item, required=required, context=f"modules[{index}]")
        name = _expect_string(item["module"], field=f"modules[{index}].module")
        if name not in SUPPORTED_MODULES or name in names:
            _fail(E_SCHEMA, f"invalid or duplicate product module: {name!r}")
        names.add(name)
        _expect_sha256(item["manifest_sha256"], field="manifest_sha256")
        _expect_git_sha(item["git_sha"], field="git_sha")
    if names != SUPPORTED_MODULES:
        _fail(E_SCHEMA, "product must bind vc-terminal and vc-frame")


def verify_app(app_path: str | Path) -> dict[str, Any]:
    """Verify one explicit assembled Vibecrafted.app and its product manifest."""
    app = Path(app_path)
    if not app.is_dir() or app.is_symlink() or app.suffix != ".app":
        _fail(E_MISSING, f"app path is not an explicit .app directory: {app}")
    manifest_relative = Path("Contents/Resources/product-manifest.json")
    payload = _load_json(app / manifest_relative)
    required = {
        "schema",
        "product",
        "bundle_id",
        "bundle_executable",
        "version",
        "git_sha",
        "dirty",
        "architecture",
        "minimum_macos",
        "modules",
        "files",
        "entrypoints",
    }
    _expect_keys(payload, required=required, context="product manifest")
    if payload["schema"] != PRODUCT_SCHEMA:
        _fail(E_SCHEMA, f"product schema must be {PRODUCT_SCHEMA}")
    if payload["product"] != PRODUCT_NAME:
        _fail(E_BUNDLE, f"product must be {PRODUCT_NAME}")
    if payload["bundle_id"] != PRODUCT_BUNDLE_ID:
        _fail(E_BUNDLE, f"bundle_id must be {PRODUCT_BUNDLE_ID}")
    if payload["bundle_executable"] != PRODUCT_EXECUTABLE:
        _fail(E_BUNDLE, f"bundle_executable must be {PRODUCT_EXECUTABLE}")
    _expect_string(payload["version"], field="version")
    _expect_git_sha(payload["git_sha"], field="git_sha")
    if not isinstance(payload["dirty"], bool):
        _fail(E_SCHEMA, "dirty must be boolean")
    _validate_platform(payload, context="product")
    _validate_product_modules(payload["modules"])
    files = _validate_files(
        app,
        payload["files"],
        manifest_relative=manifest_relative,
        exclusions=(Path("Contents/_CodeSignature"), Path("Contents/CodeResources")),
    )
    entrypoints = _validate_entrypoints(
        app,
        payload["entrypoints"],
        files,
        required_names=_APP_ENTRYPOINTS,
    )
    if entrypoints["app"] != f"Contents/MacOS/{PRODUCT_EXECUTABLE}":
        _fail(E_ENTRYPOINT, "app entrypoint must be Contents/MacOS/Vibecrafted")

    plist_path = app / "Contents/Info.plist"
    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        _fail(E_BUNDLE, f"invalid Info.plist: {exc}")
    if plist.get("CFBundleIdentifier") != PRODUCT_BUNDLE_ID:
        _fail(E_BUNDLE, f"Info.plist bundle id must be {PRODUCT_BUNDLE_ID}")
    if plist.get("CFBundleExecutable") != PRODUCT_EXECUTABLE:
        _fail(E_BUNDLE, f"Info.plist executable must be {PRODUCT_EXECUTABLE}")
    nested_apps = sorted(
        path.relative_to(app).as_posix() for path in app.rglob("*.app") if path.is_dir()
    )
    if nested_apps:
        _fail(E_BUNDLE, f"nested customer app bundles are forbidden: {nested_apps}")
    return payload


def _validate_identity(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, f"{field} must be an object")
    required = {"version", "sha256", "source_revision"}
    _expect_keys(value, required=required, context=field)
    return {
        "version": _expect_string(value["version"], field=f"{field}.version"),
        "sha256": _expect_sha256(value["sha256"], field=f"{field}.sha256"),
        "source_revision": _expect_git_sha(
            value["source_revision"], field=f"{field}.source_revision"
        ),
    }


def _validate_release_pair(value: Any, *, field: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, f"{field} must be an object")
    _expect_keys(value, required={"app", "runtime"}, context=field)
    return {
        "app": _validate_identity(value["app"], field=f"{field}.app"),
        "runtime": _validate_identity(value["runtime"], field=f"{field}.runtime"),
    }


def verify_transaction(receipt_path: str | Path) -> dict[str, Any]:
    """Verify that one activation receipt describes an atomic app/runtime pair."""
    path = Path(receipt_path)
    payload = _load_json(path)
    required = {"schema", "transaction_id", "previous", "new", "active", "outcome"}
    _expect_keys(payload, required=required, context="transaction receipt")
    if payload["schema"] != TRANSACTION_SCHEMA:
        _fail(E_SCHEMA, f"transaction schema must be {TRANSACTION_SCHEMA}")
    _expect_string(payload["transaction_id"], field="transaction_id")
    previous = _validate_release_pair(payload["previous"], field="previous")
    new = _validate_release_pair(payload["new"], field="new")
    active = _validate_release_pair(payload["active"], field="active")
    if previous == new:
        _fail(E_TRANSACTION, "transaction previous and new releases are identical")
    outcome = payload["outcome"]
    if outcome == "activated":
        expected = new
    elif outcome == "rolled_back":
        expected = previous
    else:
        _fail(E_TRANSACTION, f"unsupported transaction outcome: {outcome!r}")
    if active != expected:
        _fail(E_TRANSACTION, f"split activation: {outcome} pair is not active")
    return payload


def verify_walkaround(receipt_path: str | Path) -> dict[str, Any]:
    """Verify the release walk-around receipt bound to one exact DMG and app."""
    path = Path(receipt_path)
    payload = _load_json(path)
    required = {
        "schema",
        "dmg_path",
        "dmg_sha256",
        "dmg_size",
        "product_manifest_sha256",
        "source_revisions",
        "checks",
    }
    _expect_keys(payload, required=required, context="walk-around receipt")
    if payload["schema"] != WALKAROUND_SCHEMA:
        _fail(E_SCHEMA, f"walk-around schema must be {WALKAROUND_SCHEMA}")
    dmg_path = Path(_expect_string(payload["dmg_path"], field="dmg_path"))
    if not dmg_path.is_absolute():
        _fail(E_PATH, "walk-around dmg_path must be absolute")
    expected_hash = _expect_sha256(payload["dmg_sha256"], field="dmg_sha256")
    size = payload["dmg_size"]
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        _fail(E_SCHEMA, "dmg_size must be a positive integer")
    _expect_sha256(payload["product_manifest_sha256"], field="product_manifest_sha256")
    revisions = payload["source_revisions"]
    if not isinstance(revisions, dict):
        _fail(E_SCHEMA, "source_revisions must be an object")
    _expect_keys(
        revisions,
        required={"vibecrafted", "vc-terminal", "vc-frame"},
        context="source_revisions",
    )
    for name, revision in revisions.items():
        _expect_git_sha(revision, field=f"source_revisions.{name}")
    checks = payload["checks"]
    if not isinstance(checks, dict):
        _fail(E_SCHEMA, "checks must be an object")
    _expect_keys(checks, required=_WALKAROUND_CHECKS, context="checks")
    failed = sorted(name for name, value in checks.items() if value is not True)
    if failed:
        _fail(E_PROOF, f"walk-around checks are not proven: {', '.join(failed)}")
    if not dmg_path.is_file():
        _fail(E_MISSING, f"walk-around DMG is missing: {dmg_path}")
    if dmg_path.stat().st_size != size:
        _fail(E_SIZE, "walk-around DMG size does not match the artifact")
    if _sha256(dmg_path) != expected_hash:
        _fail(E_HASH, "walk-around DMG hash does not match the artifact")
    return payload


def _fixture_entry(
    root: Path,
    relative: str,
    *,
    kind: str,
    dylibs: Sequence[str] = (),
) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": _sha256(path),
        "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        "kind": kind,
        "size": path.stat().st_size,
        "dylibs": list(dylibs),
    }


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _self_test() -> int:
    expected_failures: list[int] = []
    with tempfile.TemporaryDirectory(prefix="vibecrafted-product-contract-") as tmp:
        root = Path(tmp)
        module = root / "vc-terminal-module"
        executable = module / "bin/vc-terminal"
        _write_executable(executable, "#!/bin/sh\nexit 0\n")
        module_manifest: dict[str, Any] = {
            "schema": MODULE_SCHEMA,
            "module": "vc-terminal",
            "version": "1.0.0",
            "git_sha": "1" * 40,
            "dirty": False,
            "architecture": "arm64",
            "minimum_macos": "14.0",
            "files": [_fixture_entry(module, "bin/vc-terminal", kind="executable")],
            "entrypoints": {"terminal": "bin/vc-terminal"},
        }
        manifest_path = module / "module-manifest.json"
        _write_json(manifest_path, module_manifest)
        verify_module(module)

        module_manifest["files"][0]["sha256"] = "f" * 64
        _write_json(manifest_path, module_manifest)
        try:
            verify_module(module)
        except ProductContractError as exc:
            expected_failures.append(exc.code)
        module_manifest["files"] = [
            _fixture_entry(
                module,
                "bin/vc-terminal",
                kind="executable",
                dylibs=("/opt/homebrew/lib/libescape.dylib",),
            )
        ]
        _write_json(manifest_path, module_manifest)
        try:
            verify_module(module)
        except ProductContractError as exc:
            expected_failures.append(exc.code)

        app = root / "Vibecrafted.app"
        app_executable = app / "Contents/MacOS/Vibecrafted"
        terminal = app / "Contents/Helpers/vc-terminal"
        frame = app / "Contents/Helpers/vc-frame"
        for target in (app_executable, terminal, frame):
            _write_executable(target, "#!/bin/sh\nexit 0\n")
        plist_path = app / "Contents/Info.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with plist_path.open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleIdentifier": PRODUCT_BUNDLE_ID,
                    "CFBundleExecutable": PRODUCT_EXECUTABLE,
                },
                handle,
            )
        product_manifest: dict[str, Any] = {
            "schema": PRODUCT_SCHEMA,
            "product": PRODUCT_NAME,
            "bundle_id": PRODUCT_BUNDLE_ID,
            "bundle_executable": PRODUCT_EXECUTABLE,
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
                _fixture_entry(app, "Contents/Info.plist", kind="config"),
                _fixture_entry(app, "Contents/MacOS/Vibecrafted", kind="executable"),
                _fixture_entry(app, "Contents/Helpers/vc-terminal", kind="executable"),
                _fixture_entry(app, "Contents/Helpers/vc-frame", kind="executable"),
            ],
            "entrypoints": {
                "app": "Contents/MacOS/Vibecrafted",
                "terminal": "Contents/Helpers/vc-terminal",
                "frame": "Contents/Helpers/vc-frame",
            },
        }
        _write_json(app / "Contents/Resources/product-manifest.json", product_manifest)
        verify_app(app)

        def identity(version: str, digest: str, revision: str) -> dict[str, str]:
            return {
                "version": version,
                "sha256": digest,
                "source_revision": revision,
            }

        previous = {
            "app": identity("0.9.0", "7" * 64, "8" * 40),
            "runtime": identity("0.9.0", "9" * 64, "a" * 40),
        }
        new = {
            "app": identity("1.0.0", "b" * 64, "c" * 40),
            "runtime": identity("1.0.0", "d" * 64, "e" * 40),
        }
        transaction = root / "transaction.json"
        _write_json(
            transaction,
            {
                "schema": TRANSACTION_SCHEMA,
                "transaction_id": "self-test",
                "previous": previous,
                "new": new,
                "active": new,
                "outcome": "activated",
            },
        )
        verify_transaction(transaction)

        dmg = root / "synthetic.dmg"
        dmg.write_bytes(b"synthetic-dmg\n")
        walkaround = root / "walkaround.json"
        _write_json(
            walkaround,
            {
                "schema": WALKAROUND_SCHEMA,
                "dmg_path": str(dmg),
                "dmg_sha256": _sha256(dmg),
                "dmg_size": dmg.stat().st_size,
                "product_manifest_sha256": "1" * 64,
                "source_revisions": {
                    "vibecrafted": "2" * 40,
                    "vc-terminal": "3" * 40,
                    "vc-frame": "4" * 40,
                },
                "checks": {name: True for name in _WALKAROUND_CHECKS},
            },
        )
        verify_walkaround(walkaround)

    if expected_failures != [E_HASH, E_DEPENDENCY]:
        _fail(
            E_PROOF,
            f"self-test negative controls returned {expected_failures}, expected "
            f"{[E_HASH, E_DEPENDENCY]}",
        )
    print(f"self-test: PASS valid=4 negative=2 error_codes={E_HASH},{E_DEPENDENCY}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    module = commands.add_parser("module", help="verify an unsigned module")
    module.add_argument("path", type=Path)
    app = commands.add_parser("app", help="verify an assembled app bundle")
    app.add_argument("path", type=Path)
    transaction = commands.add_parser(
        "transaction", help="verify an app/runtime activation receipt"
    )
    transaction.add_argument("path", type=Path)
    walkaround = commands.add_parser(
        "walkaround", help="verify a mounted-DMG walk-around receipt"
    )
    walkaround.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint with stable non-zero exit statuses per failure class."""
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments == ["--self-test"]:
        try:
            return _self_test()
        except ProductContractError as exc:
            print(f"VCPC{exc.code:03d}: {exc}", file=sys.stderr)
            return exc.code
    args = _parser().parse_args(arguments)
    try:
        if args.command == "module":
            verify_module(args.path)
        elif args.command == "app":
            verify_app(args.path)
        elif args.command == "transaction":
            verify_transaction(args.path)
        elif args.command == "walkaround":
            verify_walkaround(args.path)
        else:  # pragma: no cover - argparse owns the command set.
            _fail(E_SCHEMA, f"unsupported command: {args.command}")
    except ProductContractError as exc:
        print(f"VCPC{exc.code:03d}: {exc}", file=sys.stderr)
        return exc.code
    print(f"verified {args.command}: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

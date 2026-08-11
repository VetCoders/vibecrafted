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
import struct
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, ValidationError, validators

from .delivery.model import (
    ContractError,
    DeliveryProofContract,
    DeliverySeal,
    ProofResult,
    ProofState,
)
from .delivery.seal import reconstruct_seal

MODULE_SCHEMA = "io.vetcoders.vibecrafted.module.v1"
ASSEMBLY_SCHEMA = "io.vetcoders.vibecrafted.module-assembly.v1"
PRODUCT_SCHEMA = "io.vetcoders.vibecrafted.product.v1"
TRANSACTION_SCHEMA = "io.vetcoders.vibecrafted.transaction.v1"
WALKAROUND_SCHEMA = "io.vetcoders.vibecrafted.walkaround.v1"
LAUNCH_SCHEMA = "io.vetcoders.vibecrafted.launch.v1"
RELEASE_OUTPUT_SCHEMA = "io.vetcoders.vibecrafted.release-output.v1"
RELEASE_POLICY_SCHEMA = "io.vetcoders.vibecrafted.release-policy.v1"
TRUST_PROBE_SCHEMA = "io.vetcoders.vibecrafted.trust-probe.v1"
TRUST_PROBE_DOMAIN = "io.vetcoders.vibecrafted.release-trust-probe.v1"

PRODUCT_NAME = "Vibecrafted"
PRODUCT_BUNDLE_ID = "io.vetcoders.vibecrafted"
PRODUCT_EXECUTABLE = "Vibecrafted"
SUPPORTED_MODULES = frozenset({"vc-terminal", "vc-frame"})
SUPPORTED_ARCHITECTURES = frozenset({"arm64"})
MINIMUM_MACOS = (14, 0)
WALKAROUND_SCOPE = "unified-vibecrafted-app-walkaround-v1"
WALKAROUND_SEAL_ISSUER = "vc-ship"
WALKAROUND_RUNNER_ID = "io.vetcoders.vibecrafted.walkaround-runner.v1"
WALKAROUND_RUNNER_EXECUTABLE = "verify-vibecrafted-walkaround"
OUTER_BUNDLE_CODE_IDENTITY = "outer-bundle-codesign-v1"
MACHO_CODE_IDENTITY = "macho-code-v1"
TRUSTED_RUNNER_PUBLIC_KEY_NAME = "vibecrafted-signing-v1.pub"
RELEASE_POLICY_NAME = "release-policy.v1.json"
RELEASE_KEY_SPKI_SHA256 = (
    "521ed59d3c446c540afe1557c2dbc39c9c190775f99896b2b65206c32814b25b"
)

_MACHO_CODE_DOMAIN = b"io.vetcoders.vibecrafted.macho-code-v1\0"
_MACHO_MAX_BYTES = 512 * 1024 * 1024
_MACHO_MAX_COMMANDS = 4096
_MACHO_MAX_COMMAND_BYTES = 16 * 1024 * 1024
_MH_MAGIC_64 = 0xFEEDFACF
_CPU_TYPE_ARM64 = 0x0100000C
_MH_EXECUTE = 2
_LC_SEGMENT_64 = 0x19
_LC_CODE_SIGNATURE = 0x1D

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
_BUILD_HOST_PATH_RE = re.compile(
    rb"(?:^|[\s\"'=:(])(?P<path>/(?:Volumes|Users|opt/homebrew|usr/local)/[^\s\"'\x00]{0,512})"
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
_STATE_TRANSITION_CHECKS = frozenset({"update", "rollback", "reattach"})
_LAUNCH_INHERITED_ENV = (
    "HOME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "COLORTERM",
    "TMPDIR",
    "SHELL",
)
_LAUNCH_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_LAUNCH_TERMINAL = "Contents/Helpers/vc-terminal"
_LAUNCH_FRAME = "Contents/Helpers/vc-frame"
_LAUNCH_CONFIG = "Contents/Resources/terminal/vibecrafted.toml"
_LAUNCH_SHELL = "Contents/Resources/runtime/bin/vc-start"


@dataclass(frozen=True)
class _MachOInfo:
    relative: str
    dependencies: tuple[str, ...]
    rpaths: tuple[str, ...]
    architectures: frozenset[str]
    minimum_macos: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _ValidatedFiles:
    entries: dict[str, Mapping[str, Any]]
    machos: dict[str, _MachOInfo]


@dataclass(frozen=True)
class _ModuleManifest:
    module: str
    version: str
    git_sha: str
    dirty: bool
    architecture: str
    minimum_macos: str
    files: dict[str, Mapping[str, Any]]
    entrypoints: dict[str, str]


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


def _canonical_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _validate_unique_keys(
    _validator: Any,
    keys: Any,
    instance: Any,
    _schema: Any,
) -> Sequence[ValidationError]:
    errors: list[ValidationError] = []
    if not isinstance(keys, list) or not isinstance(instance, list):
        return errors
    for key in keys:
        if not isinstance(key, str):
            continue
        seen: dict[Any, int] = {}
        for index, item in enumerate(instance):
            if not isinstance(item, dict) or key not in item:
                continue
            value = item[key]
            if value in seen:
                errors.append(
                    ValidationError(
                        f"duplicate {key} at indexes {seen[value]} and {index}"
                    )
                )
            else:
                seen[value] = index
    return errors


def _validate_canonical_relative_path(
    _validator: Any,
    enabled: Any,
    instance: Any,
    _schema: Any,
) -> Sequence[ValidationError]:
    if enabled is not True or not isinstance(instance, str):
        return ()
    pure = PurePosixPath(instance)
    if (
        pure.is_absolute()
        or pure in {PurePosixPath("."), PurePosixPath("..")}
        or ".." in pure.parts
        or "\\" in instance
        or pure.as_posix() != instance
    ):
        return (ValidationError("path is not canonical relative POSIX spelling"),)
    return ()


UnifiedProductValidator = validators.extend(
    Draft202012Validator,
    {
        "x-vibecrafted-uniqueKeys": _validate_unique_keys,
        "x-vibecrafted-canonicalRelativePath": _validate_canonical_relative_path,
    },
)


def validate_schema_document(payload: Mapping[str, Any]) -> None:
    """Validate one public product-contract document with supported semantics."""
    schema_path = Path(__file__).parent / "schemas/unified_product.schema.v1.json"
    schema = _load_json(schema_path)
    errors = sorted(
        UnifiedProductValidator(schema).iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        _fail(E_SCHEMA, f"schema validation failed at {location}: {error.message}")


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


def _validate_platform(payload: Mapping[str, Any], *, context: str) -> tuple[str, str]:
    architecture = _expect_string(
        payload.get("architecture"), field=f"{context}.architecture"
    )
    if architecture not in SUPPORTED_ARCHITECTURES:
        _fail(E_PLATFORM, f"{context} unsupported architecture: {architecture!r}")
    minimum_macos = _minimum_macos(
        payload.get("minimum_macos"), field=f"{context}.minimum_macos"
    )
    return architecture, minimum_macos


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


def _required_tool(name: str, *, failure_code: int) -> str:
    executable = shutil.which(name)
    if executable is None:
        _fail(failure_code, f"{name} is required for product verification")
    return executable


def _run_tool(command: Sequence[str], *, failure_code: int, context: str) -> str:
    result = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
        _fail(failure_code, f"{context}: {detail}")
    return result.stdout


def _verify_assembler_signed_macho(path: Path, *, relative: str) -> None:
    """Require a post-link code signature, not the linker-generated ad-hoc placeholder."""
    codesign = _required_tool("codesign", failure_code=E_PROOF)
    _run_tool(
        [codesign, "--verify", "--strict", "--verbose=2", str(path)],
        failure_code=E_PROOF,
        context=f"signed transformation has an invalid code signature: {relative}",
    )
    result = subprocess.run(
        [codesign, "--display", "--verbose=4", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    metadata = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        _fail(E_PROOF, f"signed transformation has no valid code signature: {relative}")
    if "linker-signed" in metadata:
        _fail(
            E_PROOF,
            f"signed transformation retained only a linker signature: {relative}",
        )


def _codesign_identifier(path: Path) -> str:
    codesign = _required_tool("codesign", failure_code=E_PROOF)
    result = subprocess.run(
        [codesign, "--display", "--verbose=4", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, f"bundle has no readable code signature: {path}")
    metadata = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"^Identifier=(.+)$", metadata, flags=re.MULTILINE)
    if match is None:
        _fail(E_PROOF, f"bundle signature has no Identifier: {path}")
    return match.group(1).strip()


def _macho_code_sha256(path: Path) -> str:
    """Hash the immutable code image while excluding only signature bookkeeping."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        _fail(E_MISSING, f"outer Mach-O is unavailable: {exc}")
    if size > _MACHO_MAX_BYTES:
        _fail(E_SIZE, "outer Mach-O exceeds the 512 MiB identity limit")
    try:
        data = path.read_bytes()
    except OSError as exc:
        _fail(E_MISSING, f"outer Mach-O cannot be read: {exc}")
    if len(data) < 32:
        _fail(E_PROOF, "outer Mach-O header is truncated")
    try:
        magic, cpu_type, _, file_type, ncmds, sizeofcmds, _, _ = struct.unpack_from(
            "<IiiIIIII", data, 0
        )
    except struct.error as exc:  # pragma: no cover - guarded by the size check.
        _fail(E_PROOF, f"outer Mach-O header is malformed: {exc}")
    if magic != _MH_MAGIC_64 or cpu_type != _CPU_TYPE_ARM64 or file_type != _MH_EXECUTE:
        _fail(
            E_PLATFORM,
            "outer code identity requires thin little-endian arm64 MH_EXECUTE",
        )
    if ncmds > _MACHO_MAX_COMMANDS or sizeofcmds > _MACHO_MAX_COMMAND_BYTES:
        _fail(E_SIZE, "outer Mach-O load-command limits exceeded")
    commands_end = 32 + sizeofcmds
    if commands_end > len(data):
        _fail(E_PROOF, "outer Mach-O load commands are out of bounds")

    segments: list[tuple[str, int, int, int, int, int, int]] = []
    code_signatures: list[tuple[int, int, int]] = []
    offset = 32
    for index in range(ncmds):
        if offset % 8 or offset + 8 > commands_end:
            _fail(E_PROOF, "outer Mach-O has an unaligned or truncated load command")
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        if cmdsize < 8 or cmdsize % 8 or offset + cmdsize > commands_end:
            _fail(E_PROOF, "outer Mach-O has a malformed load command")
        if cmd == _LC_SEGMENT_64:
            if cmdsize < 72:
                _fail(E_PROOF, "outer Mach-O has a truncated LC_SEGMENT_64")
            raw_name = data[offset + 8 : offset + 24].split(b"\0", 1)[0]
            try:
                name = raw_name.decode("ascii")
            except UnicodeDecodeError:
                _fail(E_PROOF, "outer Mach-O has a non-ASCII segment name")
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from(
                "<QQQQ", data, offset + 24
            )
            nsects = struct.unpack_from("<I", data, offset + 64)[0]
            if cmdsize != 72 + nsects * 80:
                _fail(E_PROOF, f"outer Mach-O segment {name!r} has malformed sections")
            segments.append((name, offset, vmaddr, vmsize, fileoff, filesize, nsects))
        elif cmd == _LC_CODE_SIGNATURE:
            if cmdsize != 16:
                _fail(E_PROOF, "outer Mach-O has a malformed LC_CODE_SIGNATURE")
            dataoff, datasize = struct.unpack_from("<II", data, offset + 8)
            code_signatures.append((offset, dataoff, datasize))
            if index != ncmds - 1:
                _fail(E_PROOF, "outer Mach-O LC_CODE_SIGNATURE is not terminal")
        offset += cmdsize
    if offset != commands_end:
        _fail(E_PROOF, "outer Mach-O load-command size does not match its header")

    names = [segment[0] for segment in segments]
    if len(names) != len(set(names)):
        _fail(E_PROOF, "outer Mach-O contains duplicate segments")
    linkedit = [segment for segment in segments if segment[0] == "__LINKEDIT"]
    if len(linkedit) != 1 or not segments or segments[-1][0] != "__LINKEDIT":
        _fail(E_PROOF, "outer Mach-O requires one final __LINKEDIT segment")
    if len(code_signatures) != 1:
        _fail(E_PROOF, "outer Mach-O requires one LC_CODE_SIGNATURE")

    file_ranges: list[tuple[int, int, str]] = []
    vm_ranges: list[tuple[int, int, str]] = []
    for name, _, vmaddr, vmsize, fileoff, filesize, _ in segments:
        if fileoff + filesize > len(data):
            _fail(E_PROOF, f"outer Mach-O segment {name!r} is out of file bounds")
        if filesize:
            file_ranges.append((fileoff, fileoff + filesize, name))
        if vmsize:
            vm_ranges.append((vmaddr, vmaddr + vmsize, name))
    for ranges, label in ((file_ranges, "file"), (vm_ranges, "virtual-memory")):
        ordered = sorted(ranges)
        for previous, current in pairwise(ordered):
            if current[0] < previous[1]:
                _fail(E_PROOF, f"outer Mach-O has overlapping {label} segments")

    _, linkedit_command, _, _, linkedit_fileoff, linkedit_filesize, nsects = linkedit[0]
    if nsects != 0:
        _fail(E_PROOF, "outer Mach-O __LINKEDIT must not contain sections")
    for name, _, _, _, fileoff, filesize, _ in segments:
        if name == "__LINKEDIT":
            continue
        if fileoff + filesize > linkedit_fileoff or (
            filesize == 0 and fileoff >= linkedit_fileoff
        ):
            _fail(
                E_PROOF,
                f"outer Mach-O segment {name!r} reaches into __LINKEDIT",
            )
    signature_command, dataoff, datasize = code_signatures[0]
    if dataoff % 16 or datasize == 0:
        _fail(E_PROOF, "outer Mach-O code signature is missing or unaligned")
    if dataoff < commands_end:
        _fail(E_PROOF, "outer Mach-O code signature overlaps the load-command table")
    expected_end = dataoff + datasize
    if (
        expected_end != len(data)
        or linkedit_fileoff + linkedit_filesize != len(data)
        or dataoff < linkedit_fileoff
    ):
        _fail(E_PROOF, "outer Mach-O code signature or __LINKEDIT is non-terminal")

    canonical = bytearray(data[:dataoff])
    canonical[linkedit_command + 32 : linkedit_command + 40] = b"\0" * 8
    canonical[linkedit_command + 48 : linkedit_command + 56] = b"\0" * 8
    canonical[signature_command + 8 : signature_command + 16] = b"\0" * 8
    return hashlib.sha256(_MACHO_CODE_DOMAIN + canonical).hexdigest()


def _trusted_runner_public_key() -> Path:
    """Resolve the package-owned public trust root, never receipt or caller input."""
    return Path(__file__).with_name("trust") / TRUSTED_RUNNER_PUBLIC_KEY_NAME


def _release_policy() -> Mapping[str, Any]:
    policy = _load_json(Path(__file__).with_name("trust") / RELEASE_POLICY_NAME)
    required = {
        "schema",
        "algorithm",
        "public_key",
        "public_key_spki_sha256",
        "bundle_id",
        "team_id",
        "designated_requirement",
        "hardened_runtime",
        "entitlements",
    }
    _expect_keys(policy, required=required, context="release policy")
    expected = {
        "schema": RELEASE_POLICY_SCHEMA,
        "algorithm": "rsa-pkcs1v15-sha256",
        "public_key": TRUSTED_RUNNER_PUBLIC_KEY_NAME,
        "public_key_spki_sha256": RELEASE_KEY_SPKI_SHA256,
        "bundle_id": PRODUCT_BUNDLE_ID,
        "team_id": "MW223P3NPX",
        "designated_requirement": (
            'identifier "io.vetcoders.vibecrafted" and anchor apple generic and '
            "certificate 1[field.1.2.840.113635.100.6.2.6] exists and "
            "certificate leaf[field.1.2.840.113635.100.6.1.13] exists and "
            'certificate leaf[subject.OU] = "MW223P3NPX"'
        ),
        "hardened_runtime": True,
        "entitlements": {},
    }
    if policy != expected:
        _fail(E_PROOF, "packaged release policy does not match the v1 trust contract")
    return policy


def _public_key_spki_sha256(public_key: Path) -> str:
    openssl = _release_openssl()
    result = subprocess.run(
        [openssl, "pkey", "-pubin", "-in", str(public_key), "-outform", "DER"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, "packaged release public key is unreadable")
    return hashlib.sha256(result.stdout).hexdigest()


def _verify_release_signature(payload: Path, signature: Path) -> None:
    policy = _release_policy()
    public_key = _trusted_runner_public_key()
    if not public_key.is_file() or public_key.is_symlink():
        _fail(E_MISSING, "packaged release public key is missing")
    if _public_key_spki_sha256(public_key) != policy["public_key_spki_sha256"]:
        _fail(E_PROOF, "packaged release public key fingerprint is not policy-pinned")
    if not payload.is_file() or payload.is_symlink():
        _fail(E_MISSING, "signed release payload is missing")
    if not signature.is_file() or signature.is_symlink():
        _fail(E_MISSING, "detached release signature is missing")
    openssl = _release_openssl()
    result = subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature),
            str(payload),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, "detached release signature is invalid")


def _release_openssl() -> str:
    openssl = Path("/usr/bin/openssl")
    if not openssl.is_file() or openssl.is_symlink() or not os.access(openssl, os.X_OK):
        _fail(E_PROOF, "fixed system OpenSSL verifier is unavailable")
    return str(openssl)


def verify_trust_probe(
    challenge_path: str | Path, signature_path: str | Path
) -> dict[str, Any]:
    """Verify a narrowly scoped challenge through the installed production trust root."""
    challenge = Path(challenge_path)
    _verify_release_signature(challenge, Path(signature_path))
    payload = _load_json(challenge)
    _expect_keys(payload, required={"schema", "domain", "nonce"}, context="trust probe")
    if (
        payload["schema"] != TRUST_PROBE_SCHEMA
        or payload["domain"] != TRUST_PROBE_DOMAIN
    ):
        _fail(E_PROOF, "trust probe is outside the release trust domain")
    _expect_string(payload["nonce"], field="trust probe nonce")
    return payload


def _version_tuple(value: str) -> tuple[int, int]:
    match = _MACOS_RE.fullmatch(value)
    if match is None:
        _fail(E_PLATFORM, f"invalid measured macOS version: {value!r}")
    return int(match.group(1)), int(match.group(2))


def _observed_macho(path: Path, *, relative: str, kind: str) -> _MachOInfo | None:
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

    lipo = _required_tool("lipo", failure_code=E_PLATFORM)
    architecture_output = _run_tool(
        [lipo, "-archs", str(path)],
        failure_code=E_PLATFORM,
        context=f"lipo could not inspect {relative}",
    )
    architectures = frozenset(architecture_output.split())
    if not architectures:
        _fail(E_PLATFORM, f"no Mach-O architecture slices found for {relative}")

    otool = _required_tool("otool", failure_code=E_DEPENDENCY)
    dependency_output = _run_tool(
        [otool, "-L", str(path)],
        failure_code=E_DEPENDENCY,
        context=f"otool -L could not inspect {relative}",
    )
    dependencies: list[str] = []
    for line in dependency_output.splitlines()[1:]:
        stripped = line.strip()
        if stripped:
            dependencies.append(stripped.split(" (", 1)[0])

    load_output = _run_tool(
        [otool, "-l", str(path)],
        failure_code=E_DEPENDENCY,
        context=f"otool -l could not inspect {relative}",
    )
    command = ""
    rpaths: list[str] = []
    minimum_versions: list[tuple[int, int]] = []
    for line in load_output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cmd "):
            command = stripped.split(maxsplit=1)[1]
            continue
        if command == "LC_RPATH" and stripped.startswith("path "):
            match = re.match(r"path (.+?) \(offset [0-9]+\)$", stripped)
            if match is None:
                _fail(E_DEPENDENCY, f"unparseable LC_RPATH for {relative}: {stripped}")
            rpaths.append(match.group(1))
        elif (
            command == "LC_BUILD_VERSION"
            and stripped.startswith("minos ")
            or command == "LC_VERSION_MIN_MACOSX"
            and stripped.startswith("version ")
        ):
            minimum_versions.append(_version_tuple(stripped.split()[1]))

    absolute_rpaths = sorted(rpath for rpath in rpaths if rpath.startswith("/"))
    if absolute_rpaths:
        _fail(
            E_DEPENDENCY,
            f"absolute LC_RPATH is forbidden for {relative}: {absolute_rpaths[0]}",
        )
    if not minimum_versions:
        _fail(E_PLATFORM, f"Mach-O has no macOS deployment target: {relative}")
    return _MachOInfo(
        relative=relative,
        dependencies=tuple(dependencies),
        rpaths=tuple(rpaths),
        architectures=architectures,
        minimum_macos=tuple(minimum_versions),
    )


def _inside_payload(root: Path, candidate: Path, *, context: str) -> str:
    try:
        root_resolved = root.resolve()
        candidate_resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        _fail(E_PATH, f"{context} cannot be resolved inside payload: {exc}")
    try:
        relative = candidate_resolved.relative_to(root_resolved)
    except ValueError:
        _fail(E_DEPENDENCY, f"{context} escapes payload: {candidate}")
    return relative.as_posix()


def _expanded_dyld_base(
    value: str,
    *,
    loader: Path,
    executable: Path,
    context: str,
) -> Path:
    if value == "@loader_path":
        return loader.parent
    if value.startswith("@loader_path/"):
        return loader.parent / value.removeprefix("@loader_path/")
    if value == "@executable_path":
        return executable.parent
    if value.startswith("@executable_path/"):
        return executable.parent / value.removeprefix("@executable_path/")
    if value.startswith("/"):
        _fail(E_DEPENDENCY, f"absolute LC_RPATH is forbidden for {context}: {value}")
    _fail(E_DEPENDENCY, f"unsupported LC_RPATH for {context}: {value}")


def _resolve_dependency(
    dependency: str,
    *,
    root: Path,
    loader: Path,
    executable: Path,
    rpaths: Sequence[str],
    declared_paths: set[str],
) -> str | None:
    if dependency.startswith(("/usr/lib/", "/System/Library/")):
        return None
    if dependency.startswith("@loader_path/"):
        candidate = loader.parent / dependency.removeprefix("@loader_path/")
        relative = _inside_payload(root, candidate, context=dependency)
    elif dependency.startswith("@executable_path/"):
        candidate = executable.parent / dependency.removeprefix("@executable_path/")
        relative = _inside_payload(root, candidate, context=dependency)
    elif dependency.startswith("@rpath/"):
        suffix = dependency.removeprefix("@rpath/")
        relative = ""
        for rpath in rpaths:
            base = _expanded_dyld_base(
                rpath,
                loader=loader,
                executable=executable,
                context=loader.relative_to(root).as_posix(),
            )
            candidate = base / suffix
            candidate_relative = _inside_payload(root, candidate, context=dependency)
            if candidate_relative in declared_paths and candidate.is_file():
                relative = candidate_relative
                break
        if not relative:
            _fail(
                E_DEPENDENCY,
                f"unresolved @rpath dependency for {loader.relative_to(root)}: {dependency}",
            )
    else:
        _fail(
            E_DEPENDENCY, f"external dylib for {loader.relative_to(root)}: {dependency}"
        )
    if relative not in declared_paths:
        _fail(
            E_DEPENDENCY,
            f"dependency is not manifest-bound for {loader.relative_to(root)}: {dependency}",
        )
    return relative


def _verify_macho_platform(
    machos: Mapping[str, _MachOInfo],
    *,
    architecture: str,
    minimum_macos: str,
) -> None:
    if not machos:
        _fail(E_PLATFORM, "payload contains no measurable Mach-O code")
    expected_architectures = frozenset({architecture})
    for relative, info in machos.items():
        if info.architectures != expected_architectures:
            observed = ",".join(sorted(info.architectures))
            _fail(
                E_PLATFORM,
                f"Mach-O architecture mismatch for {relative}: {observed} != {architecture}",
            )
    observed_floor = max(
        version for info in machos.values() for version in info.minimum_macos
    )
    expected_floor = _version_tuple(minimum_macos)
    if observed_floor != expected_floor:
        _fail(
            E_PLATFORM,
            "Mach-O minimum macOS mismatch: "
            f"{observed_floor[0]}.{observed_floor[1]} != {minimum_macos}",
        )


def _verify_macho_closure(
    root: Path,
    files: Mapping[str, Mapping[str, Any]],
    machos: Mapping[str, _MachOInfo],
    *,
    entrypoints: Mapping[str, str],
) -> None:
    declared_paths = set(files)
    visited: set[tuple[str, str, tuple[str, ...]]] = set()
    reached: set[str] = set()

    def visit(
        relative: str,
        *,
        executable_relative: str,
        inherited_rpaths: tuple[str, ...],
    ) -> None:
        info = machos[relative]
        effective_rpaths = tuple(dict.fromkeys((*info.rpaths, *inherited_rpaths)))
        key = (relative, executable_relative, effective_rpaths)
        if key in visited:
            return
        visited.add(key)
        reached.add(relative)
        loader = root / relative
        executable = root / executable_relative
        for dependency in info.dependencies:
            target = _resolve_dependency(
                dependency,
                root=root,
                loader=loader,
                executable=executable,
                rpaths=effective_rpaths,
                declared_paths=declared_paths,
            )
            if target is None:
                continue
            if target not in machos:
                _fail(E_DEPENDENCY, f"Mach-O dependency is not code: {target}")
            visit(
                target,
                executable_relative=executable_relative,
                inherited_rpaths=effective_rpaths,
            )

    executable_roots = sorted(
        relative for relative, entry in files.items() if entry["kind"] == "executable"
    )
    if not executable_roots:
        _fail(E_PLATFORM, "payload contains no declared executable roots")
    for relative in entrypoints.values():
        if relative not in executable_roots:
            _fail(E_ENTRYPOINT, f"entrypoint is not a declared executable: {relative}")
    for relative in executable_roots:
        if relative not in machos:
            _fail(E_PLATFORM, f"declared executable is not Mach-O code: {relative}")
        visit(relative, executable_relative=relative, inherited_rpaths=())

    unreachable = sorted(
        relative
        for relative, entry in files.items()
        if entry["kind"] == "dylib" and relative not in reached
    )
    if unreachable:
        _fail(E_DEPENDENCY, f"unreachable declared dylibs: {', '.join(unreachable)}")


def _reject_host_bound_paths(path: Path, *, relative: str, kind: str) -> None:
    """Reject payload bytes that silently bind a module to the build host."""
    if kind == "resource":
        return
    try:
        content = path.read_bytes()
    except OSError:
        return
    match = _BUILD_HOST_PATH_RE.search(content)
    if match:
        host_path = match.group("path").decode("utf-8", errors="replace")
        _fail(
            E_PATH,
            f"host-bound absolute path in {relative}: {host_path}",
        )


def _validate_file_entry_shape(
    raw: Any, *, index: int
) -> tuple[str, str, str, str, int, list[str]]:
    context = f"files[{index}]"
    if not isinstance(raw, dict):
        _fail(E_SCHEMA, f"{context} must be an object")
    required = {"path", "sha256", "mode", "kind", "size", "dylibs"}
    _expect_keys(raw, required=required, context=context)
    relative = _relative_path(raw["path"], field=f"{context}.path")
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
    return relative.as_posix(), expected_hash, mode, kind, size, dylibs


def _validate_files(
    root: Path,
    raw_files: Any,
    *,
    manifest_relative: Path,
    architecture: str,
    minimum_macos: str,
    exclusions: Sequence[Path] = (),
) -> _ValidatedFiles:
    if not isinstance(raw_files, list) or not raw_files:
        _fail(E_SCHEMA, "files must be a non-empty array")
    entries: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(raw_files):
        relative_text, expected_hash, mode, kind, size, _ = _validate_file_entry_shape(
            raw, index=index
        )
        relative = Path(*PurePosixPath(relative_text).parts)
        if relative_text in entries:
            _fail(E_INVENTORY, f"duplicate manifest path: {relative_text}")
        entries[relative_text] = raw

        candidate = root / relative
        if not candidate.is_file() or candidate.is_symlink():
            _fail(E_MISSING, f"manifest-bound file is missing: {relative_text}")
        _reject_host_bound_paths(candidate, relative=relative_text, kind=kind)
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

    machos: dict[str, _MachOInfo] = {}
    for relative_text, raw in entries.items():
        declared_dylibs = list(raw["dylibs"])
        kind = str(raw["kind"])
        if kind not in {"executable", "dylib"}:
            if declared_dylibs:
                _fail(E_DEPENDENCY, f"non-code file declares dylibs: {relative_text}")
            continue
        observed = _observed_macho(
            root / relative_text,
            relative=relative_text,
            kind=kind,
        )
        if observed is None:
            continue
        machos[relative_text] = observed
        if sorted(observed.dependencies) != sorted(declared_dylibs):
            _fail(
                E_DEPENDENCY,
                f"declared dylibs do not match otool for {relative_text}",
            )

    _verify_macho_platform(
        machos,
        architecture=architecture,
        minimum_macos=minimum_macos,
    )

    declared_paths = set(entries)
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
    return _ValidatedFiles(entries=entries, machos=machos)


def _validate_outer_bundle_code(
    app: Path,
    raw: Any,
    *,
    architecture: str,
    minimum_macos: str,
    plist_path: Path,
) -> tuple[str, Mapping[str, Any], _MachOInfo]:
    context = "outer_bundle_code"
    if not isinstance(raw, dict):
        _fail(E_SCHEMA, f"{context} must be an object")
    required = {
        "identity",
        "path",
        "mode",
        "kind",
        "architecture",
        "minimum_macos",
        "dylibs",
        "code_identity",
        "code_sha256",
        "info_plist_sha256",
        "codesign_identifier",
    }
    _expect_keys(raw, required=required, context=context)
    if raw["identity"] != OUTER_BUNDLE_CODE_IDENTITY:
        _fail(E_SCHEMA, f"{context}.identity must be {OUTER_BUNDLE_CODE_IDENTITY}")
    relative = _relative_path(raw["path"], field=f"{context}.path").as_posix()
    expected_relative = f"Contents/MacOS/{PRODUCT_EXECUTABLE}"
    if relative != expected_relative or raw["kind"] != "executable":
        _fail(E_ENTRYPOINT, f"{context} must describe {expected_relative}")
    mode = _expect_string(raw["mode"], field=f"{context}.mode")
    if not _MODE_RE.fullmatch(mode):
        _fail(E_SCHEMA, f"{context}.mode must be a four-digit octal string")
    if raw["architecture"] != architecture or raw["minimum_macos"] != minimum_macos:
        _fail(E_PLATFORM, f"{context} platform does not match product")
    dylibs = raw["dylibs"]
    if not isinstance(dylibs, list) or not all(
        isinstance(item, str) and item for item in dylibs
    ):
        _fail(E_SCHEMA, f"{context}.dylibs must be an array of strings")
    executable = app / relative
    if not executable.is_file() or executable.is_symlink():
        _fail(E_MISSING, f"outer bundle executable is missing: {relative}")
    actual_mode = f"{stat.S_IMODE(executable.stat().st_mode):04o}"
    if actual_mode != mode:
        _fail(E_MODE, f"outer bundle executable mode mismatch: {relative}")
    observed = _observed_macho(executable, relative=relative, kind="executable")
    if observed is None:
        _fail(E_PLATFORM, "outer bundle executable is not Mach-O code")
    if sorted(observed.dependencies) != sorted(dylibs):
        _fail(E_DEPENDENCY, "outer bundle dylibs do not match measured load commands")
    if raw["code_identity"] != MACHO_CODE_IDENTITY:
        _fail(E_SCHEMA, f"{context}.code_identity must be {MACHO_CODE_IDENTITY}")
    _verify_macho_platform(
        {relative: observed},
        architecture=architecture,
        minimum_macos=minimum_macos,
    )
    expected_code_hash = _expect_sha256(
        raw["code_sha256"], field=f"{context}.code_sha256"
    )
    if _macho_code_sha256(executable) != expected_code_hash:
        _fail(E_HASH, "outer bundle Mach-O code identity does not match manifest")
    if _expect_sha256(
        raw["info_plist_sha256"], field=f"{context}.info_plist_sha256"
    ) != _sha256(plist_path):
        _fail(E_HASH, "outer bundle identity does not bind Info.plist")
    identifier = _expect_string(
        raw["codesign_identifier"], field=f"{context}.codesign_identifier"
    )
    if identifier != PRODUCT_BUNDLE_ID:
        _fail(E_BUNDLE, "outer bundle codesign Identifier is not canonical")
    return relative, raw, observed


def _verify_outer_bundle_signature(app: Path, *, expected_identifier: str) -> None:
    codesign = _required_tool("codesign", failure_code=E_PROOF)
    _run_tool(
        [codesign, "--verify", "--deep", "--strict", "--verbose=2", str(app)],
        failure_code=E_PROOF,
        context="outer bundle strict code signature is invalid",
    )
    if _codesign_identifier(app) != expected_identifier:
        _fail(E_PROOF, "outer bundle signature Identifier does not match manifest")


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


def _canonical_launch_contract() -> dict[str, Any]:
    return {
        "schema": LAUNCH_SCHEMA,
        "program": _LAUNCH_TERMINAL,
        "argv": [
            "--config-file",
            _LAUNCH_CONFIG,
            "-e",
            _LAUNCH_SHELL,
            "operator",
        ],
        "config_path": _LAUNCH_CONFIG,
        "shell": {"program": _LAUNCH_SHELL, "argv": ["operator"]},
        "environment": {
            "resolver_inputs": ["VIBECRAFTED_RUNTIME_HOME", "XDG_DATA_HOME"],
            "inherit_exact": list(_LAUNCH_INHERITED_ENV),
            "inject_literal": {"PATH": _LAUNCH_SYSTEM_PATH},
            "inject_bundle_paths": {
                "VIBECRAFTED_APP_ROOT": ".",
                "VIBECRAFTED_VC_FRAME_BIN": _LAUNCH_FRAME,
            },
            "resolve_writable": {
                "VIBECRAFTED_RUNTIME_HOME": {
                    "source_order": [
                        "env:VIBECRAFTED_RUNTIME_HOME",
                        "env:XDG_DATA_HOME+rel:vibecrafted",
                        "env:HOME+rel:.local/share/vibecrafted",
                    ],
                    "must_be_absolute": True,
                    "must_be_writable_or_creatable": True,
                    "must_not_descend_from": "$APP_BUNDLE",
                    "publish_to_env": "VIBECRAFTED_RUNTIME_HOME",
                }
            },
        },
    }


def _validate_launch_contract(
    raw: Any,
    *,
    files: Mapping[str, Mapping[str, Any]],
    entrypoints: Mapping[str, str],
) -> Mapping[str, Any]:
    if not isinstance(raw, dict):
        _fail(E_SCHEMA, "launch_contract must be an object")
    _expect_keys(
        raw,
        required={"schema", "program", "argv", "config_path", "shell", "environment"},
        context="launch_contract",
    )
    if raw["schema"] != LAUNCH_SCHEMA:
        _fail(E_SCHEMA, f"launch_contract.schema must be {LAUNCH_SCHEMA}")
    shell = raw["shell"]
    if not isinstance(shell, dict):
        _fail(E_SCHEMA, "launch_contract.shell must be an object")
    _expect_keys(shell, required={"program", "argv"}, context="launch_contract.shell")
    canonical = _canonical_launch_contract()
    if (
        raw["program"] != _LAUNCH_TERMINAL
        or raw["config_path"] != _LAUNCH_CONFIG
        or raw["argv"] != canonical["argv"]
        or shell != {"program": _LAUNCH_SHELL, "argv": ["operator"]}
    ):
        _fail(
            E_ENTRYPOINT,
            "launch_contract does not encode the canonical Start here entry",
        )
    environment = raw["environment"]
    if not isinstance(environment, dict):
        _fail(E_SCHEMA, "launch_contract.environment must be an object")
    _expect_keys(
        environment,
        required={
            "resolver_inputs",
            "inherit_exact",
            "inject_literal",
            "inject_bundle_paths",
            "resolve_writable",
        },
        context="launch_contract.environment",
    )
    expected_environment = canonical["environment"]
    if environment != expected_environment:
        _fail(E_SCHEMA, "launch_contract.environment is not the closed v1 environment")
    required_files = {
        _LAUNCH_TERMINAL: "executable",
        _LAUNCH_FRAME: "executable",
        _LAUNCH_CONFIG: "config",
        _LAUNCH_SHELL: "executable",
    }
    for relative, kind in required_files.items():
        entry = files.get(relative)
        if entry is None or entry.get("kind") != kind:
            _fail(
                E_ENTRYPOINT,
                f"launch_contract path is not exact inventory {kind}: {relative}",
            )
    if (
        entrypoints["terminal"] != _LAUNCH_TERMINAL
        or entrypoints["frame"] != _LAUNCH_FRAME
    ):
        _fail(E_ENTRYPOINT, "launch_contract disagrees with product entrypoints")
    return raw


def build_launch_environment(
    app_path: str | Path,
    *,
    host_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Verify the product and build its closed child environment."""
    app = Path(app_path).resolve(strict=True)
    payload = verify_app(app)
    host = dict(os.environ if host_environment is None else host_environment)
    explicit = host.get("VIBECRAFTED_RUNTIME_HOME")
    xdg = host.get("XDG_DATA_HOME")
    home = host.get("HOME")
    if explicit:
        runtime_home = Path(explicit)
    elif xdg:
        runtime_home = Path(xdg) / "vibecrafted"
    elif home:
        runtime_home = Path(home) / ".local/share/vibecrafted"
    else:
        _fail(E_PATH, "launch environment cannot resolve VIBECRAFTED_RUNTIME_HOME")
    if not runtime_home.is_absolute():
        _fail(E_PATH, "VIBECRAFTED_RUNTIME_HOME must resolve to an absolute path")
    runtime_home = runtime_home.resolve(strict=False)
    if runtime_home == app or app in runtime_home.parents:
        _fail(E_PATH, "VIBECRAFTED_RUNTIME_HOME must not descend from the app bundle")
    writable_parent = runtime_home
    while not writable_parent.exists() and writable_parent != writable_parent.parent:
        writable_parent = writable_parent.parent
    if not writable_parent.is_dir() or not os.access(writable_parent, os.W_OK):
        _fail(E_PATH, "VIBECRAFTED_RUNTIME_HOME is not writable or creatable")
    child = {name: host[name] for name in _LAUNCH_INHERITED_ENV if host.get(name)}
    child.update(
        {
            "PATH": _LAUNCH_SYSTEM_PATH,
            "VIBECRAFTED_RUNTIME_HOME": str(runtime_home),
            "VIBECRAFTED_APP_ROOT": str(app),
            "VIBECRAFTED_VC_FRAME_BIN": str(app / _LAUNCH_FRAME),
        }
    )
    # Accessing the field after verification keeps this builder bound to the manifest.
    _validate_launch_contract(
        payload["launch_contract"],
        files={item["path"]: item for item in payload["files"]},
        entrypoints=payload["entrypoints"],
    )
    return child


def _validate_module_manifest(
    payload: Mapping[str, Any], *, context: str
) -> _ModuleManifest:
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
    _expect_keys(payload, required=required, context=context)
    if payload["schema"] != MODULE_SCHEMA:
        _fail(E_SCHEMA, f"module schema must be {MODULE_SCHEMA}")
    module_name = _expect_string(payload["module"], field="module")
    if module_name not in SUPPORTED_MODULES:
        _fail(E_SCHEMA, f"unsupported module: {module_name!r}")
    version = _expect_string(payload["version"], field="version")
    git_sha = _expect_git_sha(payload["git_sha"], field="git_sha")
    if not isinstance(payload["dirty"], bool):
        _fail(E_SCHEMA, "dirty must be boolean")
    architecture, minimum_macos = _validate_platform(payload, context="module")
    raw_files = payload["files"]
    if not isinstance(raw_files, list) or not raw_files:
        _fail(E_SCHEMA, "files must be a non-empty array")
    files: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(raw_files):
        relative, *_ = _validate_file_entry_shape(raw, index=index)
        if relative in files:
            _fail(E_INVENTORY, f"duplicate manifest path: {relative}")
        files[relative] = raw
    required_entrypoints = frozenset(
        {"terminal"} if module_name == "vc-terminal" else {"frame"}
    )
    raw_entrypoints = payload["entrypoints"]
    if not isinstance(raw_entrypoints, dict):
        _fail(E_SCHEMA, "entrypoints must be an object")
    _expect_keys(
        raw_entrypoints,
        required=required_entrypoints,
        context="entrypoints",
    )
    entrypoints: dict[str, str] = {}
    for name in required_entrypoints:
        relative = _relative_path(
            raw_entrypoints[name], field=f"entrypoints.{name}"
        ).as_posix()
        entry = files.get(relative)
        if entry is None or entry["kind"] != "executable":
            _fail(E_ENTRYPOINT, f"module entrypoint is not executable: {relative}")
        entrypoints[name] = relative
    return _ModuleManifest(
        module=module_name,
        version=version,
        git_sha=git_sha,
        dirty=payload["dirty"],
        architecture=architecture,
        minimum_macos=minimum_macos,
        files=files,
        entrypoints=entrypoints,
    )


def verify_module(root: str | Path, *, require_clean: bool = False) -> dict[str, Any]:
    """Verify one explicit unsigned vc-terminal or vc-frame module directory."""
    module_root = Path(root)
    if not module_root.is_dir() or module_root.is_symlink():
        _fail(E_MISSING, f"module root is not a directory: {module_root}")
    manifest_relative = Path("module-manifest.json")
    payload = _load_json(module_root / manifest_relative)
    manifest = _validate_module_manifest(payload, context="module manifest")
    if require_clean and manifest.dirty:
        _fail(E_PROOF, "release policy rejects a dirty module receipt")
    validated = _validate_files(
        module_root,
        payload["files"],
        manifest_relative=manifest_relative,
        architecture=manifest.architecture,
        minimum_macos=manifest.minimum_macos,
    )
    entrypoints = _validate_entrypoints(
        module_root,
        payload["entrypoints"],
        validated.entries,
        required_names=frozenset(manifest.entrypoints),
    )
    _verify_macho_closure(
        module_root,
        validated.entries,
        validated.machos,
        entrypoints=entrypoints,
    )
    return payload


def _validate_product_modules(raw_modules: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(raw_modules, list) or len(raw_modules) != 2:
        _fail(E_SCHEMA, "product modules must contain terminal and frame receipts")
    modules: dict[str, Mapping[str, Any]] = {}
    required = {
        "module",
        "manifest_path",
        "manifest_sha256",
        "assembly_receipt_path",
        "assembly_receipt_sha256",
        "git_sha",
    }
    for index, item in enumerate(raw_modules):
        if not isinstance(item, dict):
            _fail(E_SCHEMA, f"modules[{index}] must be an object")
        _expect_keys(item, required=required, context=f"modules[{index}]")
        name = _expect_string(item["module"], field=f"modules[{index}].module")
        if name not in SUPPORTED_MODULES or name in modules:
            _fail(E_SCHEMA, f"invalid or duplicate product module: {name!r}")
        _relative_path(item["manifest_path"], field=f"modules[{index}].manifest_path")
        _expect_sha256(
            item["manifest_sha256"], field=f"modules[{index}].manifest_sha256"
        )
        _relative_path(
            item["assembly_receipt_path"],
            field=f"modules[{index}].assembly_receipt_path",
        )
        _expect_sha256(
            item["assembly_receipt_sha256"],
            field=f"modules[{index}].assembly_receipt_sha256",
        )
        _expect_git_sha(item["git_sha"], field="git_sha")
        modules[name] = item
    if set(modules) != SUPPORTED_MODULES:
        _fail(E_SCHEMA, "product must bind vc-terminal and vc-frame")
    return modules


def _validate_assembly_receipt(
    payload: Mapping[str, Any], *, module: str, manifest_sha256: str
) -> list[Mapping[str, Any]]:
    required = {"schema", "module", "module_manifest_sha256", "files"}
    _expect_keys(payload, required=required, context=f"{module} assembly receipt")
    if payload["schema"] != ASSEMBLY_SCHEMA:
        _fail(E_SCHEMA, f"assembly schema must be {ASSEMBLY_SCHEMA}")
    if payload["module"] != module:
        _fail(E_PROOF, f"assembly receipt identity mismatch: {module}")
    if (
        _expect_sha256(
            payload["module_manifest_sha256"],
            field=f"{module}.assembly.module_manifest_sha256",
        )
        != manifest_sha256
    ):
        _fail(E_PROOF, f"assembly receipt does not bind module manifest: {module}")
    raw_files = payload["files"]
    if not isinstance(raw_files, list) or not raw_files:
        _fail(E_SCHEMA, f"{module} assembly files must be a non-empty array")
    files: list[Mapping[str, Any]] = []
    module_paths: set[str] = set()
    product_paths: set[str] = set()
    for index, mapping in enumerate(raw_files):
        context = f"{module}.assembly.files[{index}]"
        if not isinstance(mapping, dict):
            _fail(E_SCHEMA, f"{context} must be an object")
        _expect_keys(
            mapping,
            required={
                "module_path",
                "product_path",
                "unsigned_sha256",
                "product_sha256",
                "transformation",
            },
            context=context,
        )
        module_path = _relative_path(
            mapping["module_path"], field=f"{context}.module_path"
        ).as_posix()
        product_path = _relative_path(
            mapping["product_path"], field=f"{context}.product_path"
        ).as_posix()
        _expect_sha256(mapping["unsigned_sha256"], field=f"{context}.unsigned_sha256")
        _expect_sha256(mapping["product_sha256"], field=f"{context}.product_sha256")
        transformation = _expect_string(
            mapping["transformation"], field=f"{context}.transformation"
        )
        if transformation not in {"identity", "codesign"}:
            _fail(E_SCHEMA, f"{context}.transformation is unsupported")
        if module_path in module_paths or product_path in product_paths:
            _fail(E_INVENTORY, f"duplicate assembly file mapping in {module}")
        module_paths.add(module_path)
        product_paths.add(product_path)
        files.append(mapping)
    return files


def _verify_product_module_receipts(
    app: Path,
    modules: Mapping[str, Mapping[str, Any]],
    product_files: Mapping[str, Mapping[str, Any]],
    product_entrypoints: Mapping[str, str],
    *,
    architecture: str,
    minimum_macos: str,
    require_clean: bool,
) -> None:
    claimed_product_paths: set[str] = set()
    for name, binding in modules.items():
        manifest_path = _relative_path(
            binding["manifest_path"], field=f"modules.{name}.manifest_path"
        ).as_posix()
        manifest_entry = product_files.get(manifest_path)
        if manifest_entry is None or manifest_entry["kind"] not in {
            "config",
            "resource",
        }:
            _fail(
                E_PROOF,
                f"module receipt is not product-manifest-bound: {manifest_path}",
            )
        receipt_path = app / manifest_path
        expected_hash = _expect_sha256(
            binding["manifest_sha256"], field=f"modules.{name}.manifest_sha256"
        )
        if _sha256(receipt_path) != expected_hash:
            _fail(E_PROOF, f"embedded module receipt hash mismatch: {name}")
        receipt_payload = _load_json(receipt_path)
        receipt = _validate_module_manifest(
            receipt_payload, context=f"embedded {name} module manifest"
        )
        if receipt.module != name:
            _fail(E_PROOF, f"embedded module receipt identity mismatch: {name}")
        if receipt.git_sha != binding["git_sha"]:
            _fail(E_PROOF, f"embedded module Git SHA mismatch: {name}")
        if (
            receipt.architecture != architecture
            or receipt.minimum_macos != minimum_macos
        ):
            _fail(E_PLATFORM, f"embedded module platform mismatch: {name}")
        if require_clean and receipt.dirty:
            _fail(E_PROOF, f"release policy rejects dirty embedded module: {name}")

        assembly_path = _relative_path(
            binding["assembly_receipt_path"],
            field=f"modules.{name}.assembly_receipt_path",
        ).as_posix()
        assembly_entry = product_files.get(assembly_path)
        if assembly_entry is None or assembly_entry["kind"] not in {
            "config",
            "resource",
        }:
            _fail(
                E_PROOF,
                f"assembly receipt is not product-manifest-bound: {assembly_path}",
            )
        assembly_receipt_path = app / assembly_path
        expected_assembly_hash = _expect_sha256(
            binding["assembly_receipt_sha256"],
            field=f"modules.{name}.assembly_receipt_sha256",
        )
        if _sha256(assembly_receipt_path) != expected_assembly_hash:
            _fail(E_PROOF, f"embedded assembly receipt hash mismatch: {name}")
        assembly_payload = _load_json(assembly_receipt_path)
        mappings = _validate_assembly_receipt(
            assembly_payload,
            module=name,
            manifest_sha256=expected_hash,
        )
        mapped_module_paths: set[str] = set()
        entrypoint_name = "terminal" if name == "vc-terminal" else "frame"
        mapped_entrypoint = ""
        for mapping in mappings:
            module_path = str(mapping["module_path"])
            product_path = str(mapping["product_path"])
            module_entry = receipt.files.get(module_path)
            product_entry = product_files.get(product_path)
            if module_entry is None or product_entry is None:
                _fail(E_PROOF, f"unbound copied module file: {name}:{module_path}")
            if product_path in claimed_product_paths:
                _fail(
                    E_INVENTORY,
                    f"product file claimed by multiple modules: {product_path}",
                )
            claimed_product_paths.add(product_path)
            mapped_module_paths.add(module_path)
            if mapping["unsigned_sha256"] != module_entry["sha256"]:
                _fail(E_PROOF, f"unsigned module hash mismatch: {name}:{module_path}")
            if mapping["product_sha256"] != product_entry["sha256"]:
                _fail(E_PROOF, f"signed product hash mismatch: {name}:{module_path}")
            transformation = mapping["transformation"]
            if transformation == "identity":
                if module_entry["kind"] in {"executable", "dylib"}:
                    _fail(
                        E_PROOF,
                        f"Mach-O module file requires codesign transform: {name}:{module_path}",
                    )
                for field in ("sha256", "mode", "kind", "size", "dylibs"):
                    if module_entry[field] != product_entry[field]:
                        _fail(
                            E_PROOF,
                            f"identity transform changed {field}: {name}:{module_path}",
                        )
            else:
                if module_entry["kind"] not in {"executable", "dylib"}:
                    _fail(
                        E_PROOF,
                        f"codesign transform applied to non-code file: {name}:{module_path}",
                    )
                for field in ("mode", "kind", "dylibs"):
                    if module_entry[field] != product_entry[field]:
                        _fail(
                            E_PROOF,
                            f"codesign transform changed {field}: {name}:{module_path}",
                        )
                if module_entry["sha256"] == product_entry["sha256"]:
                    _fail(
                        E_PROOF,
                        f"codesign transform did not change bytes: {name}:{module_path}",
                    )
                _verify_assembler_signed_macho(
                    app / product_path,
                    relative=product_path,
                )
            if module_path == receipt.entrypoints[entrypoint_name]:
                mapped_entrypoint = product_path
        if mapped_module_paths != set(receipt.files):
            _fail(E_PROOF, f"module receipt inventory is not fully copied: {name}")
        if mapped_entrypoint != product_entrypoints[entrypoint_name]:
            _fail(E_ENTRYPOINT, f"product entrypoint is not bound to {name} receipt")


def verify_app(app_path: str | Path, *, require_clean: bool = False) -> dict[str, Any]:
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
        "build",
        "git_sha",
        "dirty",
        "architecture",
        "minimum_macos",
        "modules",
        "outer_bundle_code",
        "files",
        "entrypoints",
        "launch_contract",
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
    version = _expect_string(payload["version"], field="version")
    build = _expect_string(payload["build"], field="build")
    _expect_git_sha(payload["git_sha"], field="git_sha")
    if not isinstance(payload["dirty"], bool):
        _fail(E_SCHEMA, "dirty must be boolean")
    if require_clean and payload["dirty"]:
        _fail(E_PROOF, "release policy rejects a dirty product receipt")
    architecture, minimum_macos = _validate_platform(payload, context="product")
    modules = _validate_product_modules(payload["modules"])
    plist_path = app / "Contents/Info.plist"
    outer_relative, outer_entry, outer_macho = _validate_outer_bundle_code(
        app,
        payload["outer_bundle_code"],
        architecture=architecture,
        minimum_macos=minimum_macos,
        plist_path=plist_path,
    )
    validated = _validate_files(
        app,
        payload["files"],
        manifest_relative=manifest_relative,
        architecture=architecture,
        minimum_macos=minimum_macos,
        exclusions=(
            Path("Contents/_CodeSignature"),
            Path("Contents/CodeResources"),
            Path(outer_relative),
        ),
    )
    validated = _ValidatedFiles(
        entries={**validated.entries, outer_relative: outer_entry},
        machos={**validated.machos, outer_relative: outer_macho},
    )
    entrypoints = _validate_entrypoints(
        app,
        payload["entrypoints"],
        validated.entries,
        required_names=_APP_ENTRYPOINTS,
    )
    if entrypoints["app"] != f"Contents/MacOS/{PRODUCT_EXECUTABLE}":
        _fail(E_ENTRYPOINT, "app entrypoint must be Contents/MacOS/Vibecrafted")
    _validate_launch_contract(
        payload["launch_contract"],
        files=validated.entries,
        entrypoints=entrypoints,
    )

    try:
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        _fail(E_BUNDLE, f"invalid Info.plist: {exc}")
    if not isinstance(plist, dict):
        _fail(E_BUNDLE, "Info.plist top level must be a dictionary")
    if plist.get("CFBundleIdentifier") != PRODUCT_BUNDLE_ID:
        _fail(E_BUNDLE, f"Info.plist bundle id must be {PRODUCT_BUNDLE_ID}")
    if plist.get("CFBundleExecutable") != PRODUCT_EXECUTABLE:
        _fail(E_BUNDLE, f"Info.plist executable must be {PRODUCT_EXECUTABLE}")
    if plist.get("CFBundleShortVersionString") != version:
        _fail(E_BUNDLE, "Info.plist marketing version does not match product manifest")
    if plist.get("CFBundleVersion") != build:
        _fail(E_BUNDLE, "Info.plist build version does not match product manifest")
    nested_apps = sorted(
        path.relative_to(app).as_posix() for path in app.rglob("*.app") if path.is_dir()
    )
    if nested_apps:
        _fail(E_BUNDLE, f"nested customer app bundles are forbidden: {nested_apps}")
    _verify_product_module_receipts(
        app,
        modules,
        validated.entries,
        entrypoints,
        architecture=architecture,
        minimum_macos=minimum_macos,
        require_clean=require_clean,
    )
    _verify_macho_closure(
        app,
        validated.entries,
        validated.machos,
        entrypoints=entrypoints,
    )
    _verify_outer_bundle_signature(
        app,
        expected_identifier=str(payload["outer_bundle_code"]["codesign_identifier"]),
    )
    return payload


def _codesign_release_evidence(app: Path) -> dict[str, Any]:
    codesign = _required_tool("codesign", failure_code=E_PROOF)
    display = subprocess.run(
        [codesign, "--display", "--verbose=4", str(app)],
        check=False,
        capture_output=True,
        text=True,
    )
    if display.returncode != 0:
        _fail(E_PROOF, "final app signature metadata is unreadable")
    metadata = f"{display.stdout}\n{display.stderr}"

    def field(pattern: str, name: str) -> str:
        match = re.search(pattern, metadata, flags=re.MULTILINE | re.IGNORECASE)
        if match is None:
            _fail(E_PROOF, f"final app signature has no {name}")
        return match.group(1).strip()

    requirement_result = subprocess.run(
        [codesign, "--display", "--requirements", "-", str(app)],
        check=False,
        capture_output=True,
        text=True,
    )
    if requirement_result.returncode != 0:
        _fail(E_PROOF, "final app designated requirement is unreadable")
    requirement_text = f"{requirement_result.stdout}\n{requirement_result.stderr}"
    requirement_match = re.search(
        r"designated\s*=>\s*(.+)$", requirement_text, re.MULTILINE
    )
    if requirement_match is None:
        _fail(E_PROOF, "final app has no designated requirement")
    entitlements_result = subprocess.run(
        [codesign, "--display", "--entitlements", ":-", str(app)],
        check=False,
        capture_output=True,
    )
    entitlement_bytes = entitlements_result.stdout + entitlements_result.stderr
    plist_start = entitlement_bytes.find(b"<?xml")
    if plist_start >= 0:
        try:
            entitlements = plistlib.loads(entitlement_bytes[plist_start:])
        except plistlib.InvalidFileException as exc:
            _fail(E_PROOF, f"final app entitlements are malformed: {exc}")
    else:
        entitlements = {}
    if not isinstance(entitlements, dict):
        _fail(E_PROOF, "final app entitlements are not a dictionary")
    return {
        "cdhash": field(r"^CDHash=([0-9a-f]+)$", "CDHash"),
        "team_id": field(r"^TeamIdentifier=(.+)$", "TeamIdentifier"),
        "designated_requirement": requirement_match.group(1).strip(),
        "hardened_runtime": re.search(
            r"^CodeDirectory .*flags=.*\(runtime\)", metadata, re.MULTILINE
        )
        is not None,
        "entitlements": entitlements,
    }


def verify_release_output(
    receipt_path: str | Path,
    signature_path: str | Path,
    *,
    app_path: str | Path,
    dmg_path: str | Path,
) -> dict[str, Any]:
    """Verify W4's one external signed release identity against live artifacts."""
    receipt = Path(receipt_path)
    _verify_release_signature(receipt, Path(signature_path))
    payload = _load_json(receipt)
    canonical = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    try:
        actual_receipt = receipt.read_bytes()
    except OSError as exc:
        _fail(E_MISSING, f"release output cannot be read: {exc}")
    if actual_receipt != canonical:
        _fail(E_PROOF, "release output must be canonical JSON")
    required = {
        "schema",
        "product_manifest_sha256",
        "outer_executable",
        "code_resources_sha256",
        "dmg",
        "modules",
        "source_revisions",
    }
    _expect_keys(payload, required=required, context="release output")
    if payload["schema"] != RELEASE_OUTPUT_SCHEMA:
        _fail(E_SCHEMA, f"release output schema must be {RELEASE_OUTPUT_SCHEMA}")
    app = Path(app_path)
    dmg = Path(dmg_path)
    if not app.is_absolute() or not dmg.is_absolute():
        _fail(
            E_PATH, "release verification requires explicit absolute app and DMG paths"
        )
    product = verify_app(app, require_clean=True)
    product_manifest = app / "Contents/Resources/product-manifest.json"
    if _expect_sha256(
        payload["product_manifest_sha256"], field="product_manifest_sha256"
    ) != _sha256(product_manifest):
        _fail(E_HASH, "release output product manifest hash mismatch")
    outer = payload["outer_executable"]
    if not isinstance(outer, dict):
        _fail(E_SCHEMA, "release output outer_executable must be an object")
    _expect_keys(
        outer,
        required={
            "sha256",
            "code_sha256",
            "cdhash",
            "team_id",
            "designated_requirement",
            "hardened_runtime",
            "entitlements",
        },
        context="release output outer_executable",
    )
    executable = app / product["outer_bundle_code"]["path"]
    if _expect_sha256(outer["sha256"], field="outer_executable.sha256") != _sha256(
        executable
    ):
        _fail(E_HASH, "release output raw outer executable hash mismatch")
    if _expect_sha256(
        outer["code_sha256"], field="outer_executable.code_sha256"
    ) != _macho_code_sha256(executable):
        _fail(E_HASH, "release output Mach-O code identity mismatch")
    policy = _release_policy()
    observed_signer = _codesign_release_evidence(app)
    expected_signer = {
        "cdhash": _expect_string(outer["cdhash"], field="outer_executable.cdhash"),
        "team_id": outer["team_id"],
        "designated_requirement": outer["designated_requirement"],
        "hardened_runtime": outer["hardened_runtime"],
        "entitlements": outer["entitlements"],
    }
    if re.fullmatch(r"[0-9a-f]{40,64}", expected_signer["cdhash"]) is None:
        _fail(E_SCHEMA, "outer_executable.cdhash must be lowercase hexadecimal")
    if expected_signer != observed_signer:
        _fail(E_PROOF, "release output signer evidence does not match the final app")
    if expected_signer != {
        "cdhash": observed_signer["cdhash"],
        "team_id": policy["team_id"],
        "designated_requirement": policy["designated_requirement"],
        "hardened_runtime": policy["hardened_runtime"],
        "entitlements": policy["entitlements"],
    }:
        _fail(E_PROOF, "final app signer evidence violates packaged release policy")
    code_resources = app / "Contents/_CodeSignature/CodeResources"
    if not code_resources.is_file() or code_resources.is_symlink():
        _fail(E_MISSING, "final app CodeResources is missing")
    if _expect_sha256(
        payload["code_resources_sha256"], field="code_resources_sha256"
    ) != _sha256(code_resources):
        _fail(E_HASH, "release output CodeResources hash mismatch")
    raw_dmg = payload["dmg"]
    if not isinstance(raw_dmg, dict):
        _fail(E_SCHEMA, "release output dmg must be an object")
    _expect_keys(raw_dmg, required={"sha256", "size"}, context="release output dmg")
    if not dmg.is_file() or dmg.is_symlink():
        _fail(E_MISSING, "release DMG is missing")
    if raw_dmg["size"] != dmg.stat().st_size or isinstance(raw_dmg["size"], bool):
        _fail(E_SIZE, "release output DMG size mismatch")
    if _expect_sha256(raw_dmg["sha256"], field="dmg.sha256") != _sha256(dmg):
        _fail(E_HASH, "release output DMG hash mismatch")
    modules = payload["modules"]
    if not isinstance(modules, dict):
        _fail(E_SCHEMA, "release output modules must be an object")
    _expect_keys(modules, required=SUPPORTED_MODULES, context="release output modules")
    product_modules = {item["module"]: item for item in product["modules"]}
    for name in sorted(SUPPORTED_MODULES):
        value = modules[name]
        if not isinstance(value, dict):
            _fail(E_SCHEMA, f"release output module {name} must be an object")
        _expect_keys(
            value,
            required={"manifest_sha256", "assembly_receipt_sha256"},
            context=f"release output module {name}",
        )
        binding = product_modules[name]
        if value != {
            "manifest_sha256": binding["manifest_sha256"],
            "assembly_receipt_sha256": binding["assembly_receipt_sha256"],
        }:
            _fail(E_PROOF, f"release output module identity mismatch: {name}")
    revisions = payload["source_revisions"]
    expected_revisions = {
        "vibecrafted": product["git_sha"],
        "vc-terminal": product_modules["vc-terminal"]["git_sha"],
        "vc-frame": product_modules["vc-frame"]["git_sha"],
    }
    if revisions != expected_revisions:
        _fail(E_PROOF, "release output source revisions do not match the product")
    for name, revision in expected_revisions.items():
        _expect_git_sha(revision, field=f"source_revisions.{name}")
    return payload


def _validate_identity(
    value: Any,
    *,
    field: str,
    receipt_root: Path,
    artifact: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, f"{field} must be an object")
    digest_field = f"{artifact}_manifest_sha256"
    required = {"version", "manifest_path", digest_field, "source_revision"}
    _expect_keys(value, required=required, context=field)
    relative = _relative_path(
        value["manifest_path"], field=f"{field}.manifest_path"
    ).as_posix()
    manifest_path = receipt_root / relative
    _inside_payload(receipt_root, manifest_path, context=f"{field}.manifest_path")
    if not manifest_path.is_file() or manifest_path.is_symlink():
        _fail(E_MISSING, f"{field} manifest referent is missing: {relative}")
    expected_hash = _expect_sha256(value[digest_field], field=f"{field}.{digest_field}")
    if _sha256(manifest_path) != expected_hash:
        _fail(E_HASH, f"{field} manifest referent hash mismatch")
    manifest = _load_json(manifest_path)
    expected_schema = (
        PRODUCT_SCHEMA if artifact == "product" else "vibecrafted.runtime-generation.v1"
    )
    if manifest.get("schema") != expected_schema:
        _fail(E_TRANSACTION, f"{field} manifest referent has the wrong schema")
    expected_relative = f"manifests/{artifact}-manifest.json"
    if relative != expected_relative:
        _fail(
            E_TRANSACTION,
            f"{field} manifest referent must use canonical path {expected_relative}",
        )
    if artifact == "product":
        try:
            validate_schema_document(manifest)
        except ProductContractError as exc:
            _fail(E_TRANSACTION, f"{field} product manifest is incomplete: {exc}")
    else:
        try:
            _validate_runtime_generation_manifest(manifest, field=field)
        except ProductContractError as exc:
            _fail(E_TRANSACTION, f"{field} runtime manifest is incomplete: {exc}")
    version = _expect_string(value["version"], field=f"{field}.version")
    if manifest.get("version") != version:
        _fail(E_TRANSACTION, f"{field} version does not match manifest referent")
    source_revision = _expect_git_sha(
        value["source_revision"], field=f"{field}.source_revision"
    )
    revision_field = "git_sha" if artifact == "product" else "source_revision"
    if manifest.get(revision_field) != source_revision:
        _fail(
            E_TRANSACTION, f"{field} source revision does not match manifest referent"
        )
    return {
        "version": version,
        "manifest_path": relative,
        digest_field: expected_hash,
        "source_revision": source_revision,
    }


def _validate_runtime_generation_manifest(
    manifest: Mapping[str, Any], *, field: str
) -> None:
    required = {
        "schema",
        "version",
        "source_fingerprint",
        "owner_repo",
        "source_revision",
        "entrypoint",
        "hashes",
    }
    _expect_keys(manifest, required=required, context=f"{field} runtime manifest")
    fingerprint = _expect_sha256(
        manifest["source_fingerprint"], field=f"{field}.source_fingerprint"
    )
    if not fingerprint:  # pragma: no cover - _expect_sha256 either returns or fails.
        _fail(E_TRANSACTION, f"{field} runtime source fingerprint is missing")
    owner_repo = _expect_string(manifest["owner_repo"], field=f"{field}.owner_repo")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", owner_repo) is None:
        _fail(E_TRANSACTION, f"{field} runtime owner_repo is invalid")
    entrypoint = _relative_path(
        manifest["entrypoint"], field=f"{field}.entrypoint"
    ).as_posix()
    if entrypoint != "vibecrafted-core/vibecrafted_core/deck/vibecrafted":
        _fail(E_TRANSACTION, f"{field} runtime entrypoint is not canonical")
    hashes = manifest["hashes"]
    required_hashes = {
        "VERSION",
        "scripts/vibecrafted",
        "runtime/generated/vc-frame/config.kdl",
        "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
    }
    if not isinstance(hashes, dict) or set(hashes) != required_hashes:
        _fail(E_TRANSACTION, f"{field} runtime hash inventory is incomplete")
    for relative, digest in hashes.items():
        _relative_path(relative, field=f"{field}.hashes.path")
        _expect_sha256(digest, field=f"{field}.hashes.{relative}")


def _validate_release_state(
    value: Any, *, field: str, receipt_root: Path
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, f"{field} must be an object")
    state = value.get("state")
    if state == "absent":
        _expect_keys(value, required={"state"}, context=field)
        return {"state": "absent"}
    if state != "present":
        _fail(E_SCHEMA, f"{field}.state must be present or absent")
    _expect_keys(value, required={"state", "app", "runtime"}, context=field)
    return {
        "state": "present",
        "app": _validate_identity(
            value["app"],
            field=f"{field}.app",
            receipt_root=receipt_root,
            artifact="product",
        ),
        "runtime": _validate_identity(
            value["runtime"],
            field=f"{field}.runtime",
            receipt_root=receipt_root,
            artifact="runtime",
        ),
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
    previous = _validate_release_state(
        payload["previous"], field="previous", receipt_root=path.parent
    )
    new = _validate_release_state(payload["new"], field="new", receipt_root=path.parent)
    active = _validate_release_state(
        payload["active"], field="active", receipt_root=path.parent
    )
    if new["state"] != "present":
        _fail(E_TRANSACTION, "transaction new release must be present")
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


def _validate_proof_artifact(root: Path, value: Any, *, field: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, f"{field} must be an object")
    _expect_keys(value, required={"path", "sha256", "size"}, context=field)
    relative = _relative_path(value["path"], field=f"{field}.path").as_posix()
    expected_hash = _expect_sha256(value["sha256"], field=f"{field}.sha256")
    expected_size = value["size"]
    if (
        not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 0
    ):
        _fail(E_SCHEMA, f"{field}.size must be a non-negative integer")
    artifact = root / relative
    _inside_payload(root, artifact, context=field)
    if not artifact.is_file() or artifact.is_symlink():
        _fail(E_MISSING, f"walk-around proof artifact is missing: {relative}")
    if artifact.stat().st_size != expected_size:
        _fail(E_SIZE, f"walk-around proof artifact size mismatch: {relative}")
    if _sha256(artifact) != expected_hash:
        _fail(E_HASH, f"walk-around proof artifact hash mismatch: {relative}")
    return relative, expected_hash


def _walkaround_probe_id(name: str) -> str:
    return f"io.vetcoders.vibecrafted.walkaround.{name}.v1"


def _walkaround_proof_digest(name: str, proof: Mapping[str, Any]) -> str:
    return _canonical_digest({"name": name, "proof": proof})


def _validate_walkaround_proofs(
    raw_proofs: Any,
    *,
    receipt_root: Path,
    release_output_sha256: str,
) -> tuple[dict[str, Mapping[str, Any]], tuple[str, ...]]:
    if not isinstance(raw_proofs, dict):
        _fail(E_SCHEMA, "walk-around proofs must be an object")
    _expect_keys(raw_proofs, required=_WALKAROUND_CHECKS, context="proofs")
    artifacts: set[str] = set()
    proofs: dict[str, Mapping[str, Any]] = {}
    proof_digests: list[str] = []
    for name in sorted(_WALKAROUND_CHECKS):
        proof = raw_proofs[name]
        if not isinstance(proof, dict):
            _fail(E_SCHEMA, f"proofs.{name} must be an object")
        _expect_keys(
            proof,
            required={
                "producer",
                "probe_id",
                "command",
                "exit_code",
                "inputs",
                "before",
                "after",
                "stdout",
                "stderr",
            },
            context=f"proofs.{name}",
        )
        if proof["producer"] != WALKAROUND_SEAL_ISSUER:
            _fail(E_PROOF, f"walk-around proof has untrusted producer: {name}")
        if proof["probe_id"] != _walkaround_probe_id(name):
            _fail(E_PROOF, f"walk-around proof has wrong probe identity: {name}")
        command = proof["command"]
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and item for item in command)
        ):
            _fail(E_SCHEMA, f"proofs.{name}.command must be a non-empty argv array")
        if proof["exit_code"] != 0 or isinstance(proof["exit_code"], bool):
            _fail(E_PROOF, f"walk-around proof failed: {name}")
        inputs = proof["inputs"]
        if not isinstance(inputs, dict):
            _fail(E_SCHEMA, f"proofs.{name}.inputs must be an object")
        _expect_keys(
            inputs,
            required={"release_output_sha256"},
            context=f"proofs.{name}.inputs",
        )
        if (
            _expect_sha256(
                inputs["release_output_sha256"],
                field=f"proofs.{name}.inputs.release_output_sha256",
            )
            != release_output_sha256
        ):
            _fail(E_PROOF, f"walk-around proof inputs do not bind release: {name}")
        state_hashes: dict[str, str] = {}
        for artifact_name in ("before", "after", "stdout", "stderr"):
            relative, artifact_hash = _validate_proof_artifact(
                receipt_root,
                proof[artifact_name],
                field=f"proofs.{name}.{artifact_name}",
            )
            if relative in artifacts:
                _fail(E_PROOF, f"walk-around proof artifact reused: {relative}")
            artifacts.add(relative)
            state_hashes[artifact_name] = artifact_hash
        if (
            name in _STATE_TRANSITION_CHECKS
            and state_hashes["before"] == state_hashes["after"]
        ):
            _fail(E_PROOF, f"walk-around state transition did not change state: {name}")
        proofs[name] = proof
        proof_digests.append(_walkaround_proof_digest(name, proof))
    return proofs, tuple(proof_digests)


def _walkaround_subject_digest(payload: Mapping[str, Any]) -> str:
    return _canonical_digest(
        {
            "schema": payload["schema"],
            "dmg_path": payload["dmg_path"],
            "mount_path": payload["mount_path"],
            "app_path": payload["app_path"],
            "release_output": payload["release_output"],
            "release_signature": payload["release_signature"],
        }
    )


def _walkaround_assertion_digest(proof_digests: Sequence[str]) -> str:
    return _canonical_digest({"proofs": list(proof_digests)})


def _verify_trusted_runner_attestation(
    receipt_root: Path,
    value: Any,
    *,
    trusted_public_key: Path,
    payload: Mapping[str, Any],
    proof_digests: Sequence[str],
) -> None:
    if not isinstance(value, dict):
        _fail(E_SCHEMA, "trusted_runner must be an object")
    _expect_keys(value, required={"attestation", "signature"}, context="trusted_runner")
    attestation_relative, _ = _validate_proof_artifact(
        receipt_root, value["attestation"], field="trusted_runner.attestation"
    )
    signature_relative, _ = _validate_proof_artifact(
        receipt_root, value["signature"], field="trusted_runner.signature"
    )
    attestation_path = receipt_root / attestation_relative
    signature_path = receipt_root / signature_relative
    attestation = _load_json(attestation_path)
    required = {
        "schema",
        "runner_id",
        "subject_sha256",
        "assertion_sha256",
        "probe_ids",
    }
    _expect_keys(attestation, required=required, context="trusted runner attestation")
    if attestation["schema"] != WALKAROUND_RUNNER_ID:
        _fail(E_PROOF, "trusted runner attestation has the wrong schema")
    if attestation["runner_id"] != WALKAROUND_RUNNER_ID:
        _fail(E_PROOF, "trusted runner attestation has the wrong runner identity")
    if attestation["subject_sha256"] != _walkaround_subject_digest(payload):
        _fail(E_PROOF, "trusted runner attestation does not bind release subject")
    if attestation["assertion_sha256"] != _walkaround_assertion_digest(proof_digests):
        _fail(E_PROOF, "trusted runner attestation does not bind proof set")
    expected_probe_ids = [
        _walkaround_probe_id(name) for name in sorted(_WALKAROUND_CHECKS)
    ]
    if attestation["probe_ids"] != expected_probe_ids:
        _fail(E_PROOF, "trusted runner attestation does not bind canonical probes")
    if not trusted_public_key.is_file() or trusted_public_key.is_symlink():
        _fail(E_MISSING, "explicit trusted runner public key is missing")
    openssl = _release_openssl()
    result = subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-verify",
            str(trusted_public_key),
            "-signature",
            str(signature_path),
            str(attestation_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, "walk-around runner attestation signature is invalid")


def _verify_walkaround_delivery_seal(
    receipt_root: Path,
    seal_artifact: Any,
    *,
    payload: Mapping[str, Any],
    proof_digests: tuple[str, ...],
) -> DeliverySeal:
    relative, _ = _validate_proof_artifact(
        receipt_root,
        seal_artifact,
        field="delivery_seal",
    )
    seal_path = receipt_root / relative
    if seal_path.name != "delivery-seal.json":
        _fail(
            E_PROOF, "walk-around seal must use the canonical delivery-seal.json name"
        )
    reconstruction = reconstruct_seal(seal_path.parent)
    if not reconstruction.verified or reconstruction.seal is None:
        detail = ", ".join(
            str(item.get("component", "unknown")) for item in reconstruction.mismatches
        )
        _fail(E_PROOF, f"walk-around delivery seal is stale: {detail or 'unknown'}")
    seal = reconstruction.seal
    if seal.issuer != WALKAROUND_SEAL_ISSUER:
        _fail(E_PROOF, "walk-around delivery seal has the wrong issuer")
    if seal.cut_id != WALKAROUND_SCOPE:
        _fail(E_PROOF, "walk-around delivery seal has the wrong cut identity")
    if (
        seal.declared_scope != WALKAROUND_SCOPE
        or seal.checked_scope != WALKAROUND_SCOPE
    ):
        _fail(E_PROOF, "walk-around delivery seal did not check the declared scope")
    if seal.unverified_surfaces:
        _fail(E_PROOF, "walk-around delivery seal carries unverified surfaces")
    if tuple(seal.runtime_probe_sha256) != proof_digests:
        _fail(E_PROOF, "walk-around proofs are not bound by the delivery seal")
    if seal.subject_evidence_sha256 != _walkaround_subject_digest(payload):
        _fail(E_PROOF, "walk-around release subject is not bound by the delivery seal")
    if seal.assertion_evidence_sha256 != _walkaround_assertion_digest(proof_digests):
        _fail(E_PROOF, "walk-around assertion set is not bound by the delivery seal")
    try:
        proof_contract = DeliveryProofContract.from_payload(
            _load_json(seal_path.parent / "delivery-proof-contract.json")
        )
        proof_result = ProofResult.from_payload(
            _load_json(seal_path.parent / "proof/result.json")
        )
    except ContractError as exc:
        _fail(E_PROOF, f"walk-around delivery proof contract is invalid: {exc}")
    if proof_contract.id != seal.proof_id or proof_result.proof_id != seal.proof_id:
        _fail(E_PROOF, "walk-around delivery proof identity does not match the seal")
    if (
        proof_contract.delivery_scope != WALKAROUND_SCOPE
        or proof_contract.integration_target != payload["app_path"]
    ):
        _fail(E_PROOF, "walk-around delivery proof targets the wrong product scope")
    expected_runtime_probes = tuple(
        {
            "id": name,
            "probe_id": _walkaround_probe_id(name),
            "evidence_sha256": digest,
        }
        for name, digest in zip(sorted(_WALKAROUND_CHECKS), proof_digests, strict=True)
    )
    if tuple(proof_contract.runtime_probes) != expected_runtime_probes:
        _fail(E_PROOF, "walk-around delivery proof does not declare every sealed probe")
    if proof_result.contract_sha256 != proof_contract.content_digest():
        _fail(E_PROOF, "walk-around proof result does not bind its proof contract")
    if (
        proof_result.state is not ProofState.PASSED
        or not proof_result.subject_executed
        or not proof_result.assertion_consumed_subject_output
        or proof_result.refusal_reasons
    ):
        _fail(E_PROOF, "walk-around delivery proof did not reach a clean PASS")
    if not proof_result.assertion_results or not all(
        result.get("passed") is True and result.get("valid") is True
        for result in proof_result.assertion_results
    ):
        _fail(E_PROOF, "walk-around delivery proof assertions are incomplete")
    if not proof_result.negative_control_results or not all(
        result.get("detected_falsehood") is True and result.get("valid") is True
        for result in proof_result.negative_control_results
    ):
        _fail(E_PROOF, "walk-around delivery proof negative controls are incomplete")
    return seal


def _attached_image_mounts() -> set[tuple[Path, Path]]:
    hdiutil = _required_tool("hdiutil", failure_code=E_PROOF)
    result = subprocess.run(
        [hdiutil, "info", "-plist"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, "hdiutil could not prove the mounted DMG identity")
    try:
        payload = plistlib.loads(result.stdout)
    except plistlib.InvalidFileException as exc:
        _fail(E_PROOF, f"hdiutil returned invalid mount evidence: {exc}")
    if not isinstance(payload, dict):
        _fail(E_PROOF, "hdiutil mount evidence must be a dictionary")
    mounts: set[tuple[Path, Path]] = set()
    images = payload.get("images", [])
    if not isinstance(images, list):
        _fail(E_PROOF, "hdiutil mount evidence has invalid images")
    for image in images:
        if not isinstance(image, dict) or not isinstance(image.get("image-path"), str):
            continue
        image_path = Path(image["image-path"]).resolve(strict=False)
        entities = image.get("system-entities", [])
        if not isinstance(entities, list):
            continue
        for entity in entities:
            if isinstance(entity, dict) and isinstance(entity.get("mount-point"), str):
                mounts.add(
                    (image_path, Path(entity["mount-point"]).resolve(strict=False))
                )
    return mounts


def _expected_runner_commands(app: Path, dmg: Path) -> dict[str, list[str]]:
    return {
        name: [
            WALKAROUND_RUNNER_EXECUTABLE,
            name,
            "--app",
            str(app),
            "--dmg",
            str(dmg),
        ]
        for name in sorted(_WALKAROUND_CHECKS)
    }


def _live_release_commands(app: Path, dmg: Path) -> dict[str, list[str]]:
    return {
        "codesign": [
            "codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app),
        ],
        "app_notarization": ["xcrun", "stapler", "validate", str(app)],
        "dmg_notarization": ["xcrun", "stapler", "validate", str(dmg)],
        "gatekeeper": [
            "spctl",
            "--assess",
            "--type",
            "execute",
            "--verbose=4",
            str(app),
        ],
    }


def _verify_recorded_live_commands(
    proofs: Mapping[str, Mapping[str, Any]], *, app: Path, dmg: Path
) -> None:
    for name, expected in _expected_runner_commands(app, dmg).items():
        recorded = list(proofs[name]["command"])
        normalized = [Path(recorded[0]).name, *recorded[1:]]
        if normalized != expected:
            _fail(E_PROOF, f"walk-around proof recorded the wrong {name} command")


def _run_live_release_checks(app: Path, dmg: Path) -> None:
    for name, command in _live_release_commands(app, dmg).items():
        executable = _required_tool(command[0], failure_code=E_PROOF)
        _run_tool(
            [executable, *command[1:]],
            failure_code=E_PROOF,
            context=f"live walk-around check failed ({name})",
        )


def _verify_walkaround(
    receipt_path: Path,
    *,
    trusted_runner_public_key: Path,
    attached_mounts: set[tuple[Path, Path]],
    run_live_checks: bool,
    release_output_verifier: Any = None,
) -> dict[str, Any]:
    path = receipt_path
    payload = _load_json(path)
    required = {
        "schema",
        "dmg_path",
        "mount_path",
        "app_path",
        "release_output",
        "release_signature",
        "proofs",
        "trusted_runner",
        "delivery_seal",
    }
    _expect_keys(payload, required=required, context="walk-around receipt")
    if payload["schema"] != WALKAROUND_SCHEMA:
        _fail(E_SCHEMA, f"walk-around schema must be {WALKAROUND_SCHEMA}")
    dmg_path = Path(_expect_string(payload["dmg_path"], field="dmg_path"))
    if not dmg_path.is_absolute():
        _fail(E_PATH, "walk-around dmg_path must be absolute")
    mount_path = Path(_expect_string(payload["mount_path"], field="mount_path"))
    app_path = Path(_expect_string(payload["app_path"], field="app_path"))
    if not mount_path.is_absolute() or not app_path.is_absolute():
        _fail(E_PATH, "walk-around mount_path and app_path must be absolute")
    if not dmg_path.is_file():
        _fail(E_MISSING, f"walk-around DMG is missing: {dmg_path}")
    if not mount_path.is_dir() or mount_path.is_symlink():
        _fail(E_MISSING, f"walk-around mount is missing: {mount_path}")
    dmg_resolved = dmg_path.resolve()
    mount_resolved = mount_path.resolve()
    app_resolved = app_path.resolve(strict=False)
    expected_app = mount_resolved / "Vibecrafted.app"
    if app_resolved != expected_app or not app_path.is_dir() or app_path.is_symlink():
        _fail(E_PATH, "walk-around app must be the mounted top-level Vibecrafted.app")
    if (dmg_resolved, mount_resolved) not in attached_mounts:
        _fail(E_PROOF, "walk-around mount is not attached from the exact DMG")
    mounted_apps = sorted(
        item.name
        for item in mount_path.iterdir()
        if item.is_dir() and item.suffix == ".app"
    )
    if mounted_apps != ["Vibecrafted.app"]:
        _fail(E_BUNDLE, f"mounted DMG customer app set is invalid: {mounted_apps}")

    release_relative, release_hash = _validate_proof_artifact(
        path.parent, payload["release_output"], field="release_output"
    )
    signature_relative, _ = _validate_proof_artifact(
        path.parent, payload["release_signature"], field="release_signature"
    )
    if (
        release_relative != "release-output.json"
        or signature_relative != "release-output.json.sig"
    ):
        _fail(E_PROOF, "walk-around must reference canonical release-output artifacts")
    verifier = release_output_verifier or verify_release_output
    release_payload = verifier(
        path.parent / release_relative,
        path.parent / signature_relative,
        app_path=app_path,
        dmg_path=dmg_path,
    )
    _expect_sha256(release_payload["dmg"]["sha256"], field="release_output.dmg.sha256")
    _expect_sha256(
        release_payload["product_manifest_sha256"],
        field="release_output.product_manifest_sha256",
    )

    proofs, proof_digests = _validate_walkaround_proofs(
        payload["proofs"],
        receipt_root=path.parent,
        release_output_sha256=release_hash,
    )
    _verify_recorded_live_commands(proofs, app=app_path, dmg=dmg_path)
    _verify_trusted_runner_attestation(
        path.parent,
        payload["trusted_runner"],
        trusted_public_key=trusted_runner_public_key,
        payload=payload,
        proof_digests=proof_digests,
    )
    _verify_walkaround_delivery_seal(
        path.parent,
        payload["delivery_seal"],
        payload=payload,
        proof_digests=proof_digests,
    )
    if run_live_checks:
        _run_live_release_checks(app_path, dmg_path)
    return payload


def verify_walkaround(
    receipt_path: str | Path,
) -> dict[str, Any]:
    """Verify evidence against the release-policy trust root and mounted DMG."""
    return _verify_walkaround(
        Path(receipt_path),
        trusted_runner_public_key=_trusted_runner_public_key(),
        attached_mounts=_attached_image_mounts(),
        run_live_checks=True,
    )


def _fixture_entry(
    root: Path,
    relative: str,
    *,
    kind: str,
    dylibs: Sequence[str] | None = None,
) -> dict[str, Any]:
    path = root / relative
    if dylibs is None and kind in {"executable", "dylib"}:
        observed = _observed_macho(path, relative=relative, kind=kind)
        dylibs = () if observed is None else observed.dependencies
    return {
        "path": relative,
        "sha256": _sha256(path),
        "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
        "kind": kind,
        "size": path.stat().st_size,
        "dylibs": list(dylibs or ()),
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


def _write_fixture_macho(path: Path) -> None:
    xcrun = _required_tool("xcrun", failure_code=E_PROOF)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            xcrun,
            "--sdk",
            "macosx",
            "clang",
            "-arch",
            "arm64",
            "-mmacosx-version-min=14.0",
            "-x",
            "c",
            "-",
            "-o",
            str(path),
        ],
        input="int main(void) { return 0; }\n",
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(E_PROOF, f"self-test could not compile Mach-O fixture: {result.stderr}")


def _self_test() -> int:
    expected_failures: list[int] = []
    with tempfile.TemporaryDirectory(prefix="vibecrafted-product-contract-") as tmp:
        root = Path(tmp)
        module = root / "vc-terminal-module"
        executable = module / "bin/vc-terminal"
        _write_fixture_macho(executable)
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
            _fixture_entry(module, "bin/vc-terminal", kind="executable")
        ]
        module_manifest["files"][0]["dylibs"].append(
            "/opt/homebrew/lib/libescape.dylib"
        )
        _write_json(manifest_path, module_manifest)
        try:
            verify_module(module)
        except ProductContractError as exc:
            expected_failures.append(exc.code)
        module_manifest["files"] = [
            _fixture_entry(module, "bin/vc-terminal", kind="executable")
        ]
        _write_json(manifest_path, module_manifest)
        verify_module(module)

        mount = root / "mounted"
        app = mount / "Vibecrafted.app"
        app_executable = app / "Contents/MacOS/Vibecrafted"
        terminal = app / "Contents/Helpers/vc-terminal"
        frame = app / "Contents/Helpers/vc-frame"
        product_shell = app / _LAUNCH_SHELL
        for target in (app_executable, terminal, frame, product_shell):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(executable, target)
        codesign = _required_tool("codesign", failure_code=E_PROOF)
        for target in (terminal, frame, product_shell):
            _run_tool(
                [codesign, "--force", "--sign", "-", str(target)],
                failure_code=E_PROOF,
                context=f"self-test could not sign {target.name}",
            )
        terminal_config = app / _LAUNCH_CONFIG
        terminal_config.parent.mkdir(parents=True, exist_ok=True)
        terminal_config.write_text("[shell]\nprogram = 'vc-start'\n", encoding="utf-8")
        plist_path = app / "Contents/Info.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with plist_path.open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleIdentifier": PRODUCT_BUNDLE_ID,
                    "CFBundleExecutable": PRODUCT_EXECUTABLE,
                    "CFBundleShortVersionString": "1.0.0",
                    "CFBundleVersion": "1",
                },
                handle,
            )
        terminal_product_entry = _fixture_entry(
            app, "Contents/Helpers/vc-terminal", kind="executable"
        )
        frame_product_entry = _fixture_entry(
            app, "Contents/Helpers/vc-frame", kind="executable"
        )

        def module_binding(
            *,
            module_name: str,
            git_sha: str,
            entrypoint: str,
            product_entry: Mapping[str, Any],
        ) -> dict[str, Any]:
            source_path = f"bin/{module_name}"
            source_entry = dict(module_manifest["files"][0])
            source_entry["path"] = source_path
            receipt = {
                "schema": MODULE_SCHEMA,
                "module": module_name,
                "version": "1.0.0",
                "git_sha": git_sha,
                "dirty": False,
                "architecture": "arm64",
                "minimum_macos": "14.0",
                "files": [source_entry],
                "entrypoints": {entrypoint: source_path},
            }
            receipt_relative = (
                f"Contents/Resources/module-receipts/{module_name}/module-manifest.json"
            )
            _write_json(app / receipt_relative, receipt)
            receipt_hash = _sha256(app / receipt_relative)
            assembly = {
                "schema": ASSEMBLY_SCHEMA,
                "module": module_name,
                "module_manifest_sha256": receipt_hash,
                "files": [
                    {
                        "module_path": source_path,
                        "product_path": product_entry["path"],
                        "unsigned_sha256": source_entry["sha256"],
                        "product_sha256": product_entry["sha256"],
                        "transformation": "codesign",
                    }
                ],
            }
            assembly_relative = f"Contents/Resources/module-receipts/{module_name}/assembly-receipt.json"
            _write_json(app / assembly_relative, assembly)
            return {
                "module": module_name,
                "manifest_path": receipt_relative,
                "manifest_sha256": receipt_hash,
                "assembly_receipt_path": assembly_relative,
                "assembly_receipt_sha256": _sha256(app / assembly_relative),
                "git_sha": git_sha,
            }

        terminal_binding = module_binding(
            module_name="vc-terminal",
            git_sha="4" * 40,
            entrypoint="terminal",
            product_entry=terminal_product_entry,
        )
        frame_binding = module_binding(
            module_name="vc-frame",
            git_sha="6" * 40,
            entrypoint="frame",
            product_entry=frame_product_entry,
        )
        observed_outer = _observed_macho(
            app_executable,
            relative="Contents/MacOS/Vibecrafted",
            kind="executable",
        )
        if observed_outer is None:
            _fail(E_PLATFORM, "self-test outer executable is not Mach-O")
        product_manifest: dict[str, Any] = {
            "schema": PRODUCT_SCHEMA,
            "product": PRODUCT_NAME,
            "bundle_id": PRODUCT_BUNDLE_ID,
            "bundle_executable": PRODUCT_EXECUTABLE,
            "version": "1.0.0",
            "build": "1",
            "git_sha": "2" * 40,
            "dirty": False,
            "architecture": "arm64",
            "minimum_macos": "14.0",
            "modules": [terminal_binding, frame_binding],
            "outer_bundle_code": {
                "identity": OUTER_BUNDLE_CODE_IDENTITY,
                "path": "Contents/MacOS/Vibecrafted",
                "mode": "0755",
                "kind": "executable",
                "architecture": "arm64",
                "minimum_macos": "14.0",
                "dylibs": list(observed_outer.dependencies),
                "code_identity": MACHO_CODE_IDENTITY,
                "code_sha256": _macho_code_sha256(app_executable),
                "info_plist_sha256": _sha256(plist_path),
                "codesign_identifier": PRODUCT_BUNDLE_ID,
            },
            "files": [
                _fixture_entry(app, "Contents/Info.plist", kind="config"),
                terminal_product_entry,
                frame_product_entry,
                _fixture_entry(app, terminal_binding["manifest_path"], kind="config"),
                _fixture_entry(app, frame_binding["manifest_path"], kind="config"),
                _fixture_entry(
                    app, terminal_binding["assembly_receipt_path"], kind="config"
                ),
                _fixture_entry(
                    app, frame_binding["assembly_receipt_path"], kind="config"
                ),
                _fixture_entry(app, _LAUNCH_CONFIG, kind="config"),
                _fixture_entry(app, _LAUNCH_SHELL, kind="executable"),
            ],
            "entrypoints": {
                "app": "Contents/MacOS/Vibecrafted",
                "terminal": "Contents/Helpers/vc-terminal",
                "frame": "Contents/Helpers/vc-frame",
            },
            "launch_contract": _canonical_launch_contract(),
        }
        _write_json(app / "Contents/Resources/product-manifest.json", product_manifest)
        _run_tool(
            [codesign, "--force", "--sign", "-", str(app)],
            failure_code=E_PROOF,
            context="self-test could not sign outer app bundle",
        )
        verify_app(app)

        transaction_product = root / "manifests/product-manifest.json"
        transaction_runtime = root / "manifests/runtime-manifest.json"
        transaction_product_payload = dict(product_manifest)
        transaction_product_payload["git_sha"] = "c" * 40
        _write_json(transaction_product, transaction_product_payload)
        _write_json(
            transaction_runtime,
            {
                "schema": "vibecrafted.runtime-generation.v1",
                "version": "1.0.0",
                "source_fingerprint": "d" * 64,
                "owner_repo": "vetcoders/vibecrafted",
                "source_revision": "e" * 40,
                "entrypoint": "vibecrafted-core/vibecrafted_core/deck/vibecrafted",
                "hashes": {
                    "VERSION": "1" * 64,
                    "scripts/vibecrafted": "2" * 64,
                    "runtime/generated/vc-frame/config.kdl": "3" * 64,
                    "vibecrafted-core/vibecrafted_core/deck/vibecrafted": "4" * 64,
                },
            },
        )
        new = {
            "state": "present",
            "app": {
                "version": "1.0.0",
                "manifest_path": "manifests/product-manifest.json",
                "product_manifest_sha256": _sha256(transaction_product),
                "source_revision": "c" * 40,
            },
            "runtime": {
                "version": "1.0.0",
                "manifest_path": "manifests/runtime-manifest.json",
                "runtime_manifest_sha256": _sha256(transaction_runtime),
                "source_revision": "e" * 40,
            },
        }
        transaction = root / "transaction.json"
        _write_json(
            transaction,
            {
                "schema": TRANSACTION_SCHEMA,
                "transaction_id": "self-test",
                "previous": {"state": "absent"},
                "new": new,
                "active": new,
                "outcome": "activated",
            },
        )
        verify_transaction(transaction)

        dmg = root / "synthetic.dmg"
        dmg.write_bytes(b"synthetic-dmg\n")
        walkaround = root / "walkaround.json"
        release_output = root / "release-output.json"
        release_signature = root / "release-output.json.sig"
        release_payload = {
            "product_manifest_sha256": _sha256(
                app / "Contents/Resources/product-manifest.json"
            ),
            "dmg": {"sha256": _sha256(dmg), "size": dmg.stat().st_size},
        }
        _write_json(release_output, release_payload)
        release_signature.write_bytes(b"self-test-release-signature")

        def proof_artifact(artifact: Path) -> dict[str, Any]:
            return {
                "path": artifact.relative_to(root).as_posix(),
                "sha256": _sha256(artifact),
                "size": artifact.stat().st_size,
            }

        proofs: dict[str, Any] = {}
        expected_commands = _expected_runner_commands(app, dmg)
        for name in sorted(_WALKAROUND_CHECKS):
            before = root / f"proofs/{name}.before"
            after = root / f"proofs/{name}.after"
            stdout = root / f"proofs/{name}.stdout"
            stderr = root / f"proofs/{name}.stderr"
            stdout.parent.mkdir(parents=True, exist_ok=True)
            before.write_text(f"{name}: before\n", encoding="utf-8")
            after.write_text(f"{name}: after\n", encoding="utf-8")
            stdout.write_text(f"{name}: passed\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")

            proofs[name] = {
                "producer": WALKAROUND_SEAL_ISSUER,
                "probe_id": _walkaround_probe_id(name),
                "command": expected_commands[name],
                "exit_code": 0,
                "inputs": {
                    "release_output_sha256": _sha256(release_output),
                },
                "before": proof_artifact(before),
                "after": proof_artifact(after),
                "stdout": proof_artifact(stdout),
                "stderr": proof_artifact(stderr),
            }
        walkaround_payload: dict[str, Any] = {
            "schema": WALKAROUND_SCHEMA,
            "dmg_path": str(dmg),
            "mount_path": str(mount),
            "app_path": str(app),
            "release_output": proof_artifact(release_output),
            "release_signature": proof_artifact(release_signature),
            "proofs": proofs,
        }
        proof_digests = tuple(
            _walkaround_proof_digest(name, proofs[name])
            for name in sorted(_WALKAROUND_CHECKS)
        )
        openssl = _required_tool("openssl", failure_code=E_PROOF)
        runner_private_key = root / "trusted-runner-private.pem"
        runner_public_key = root / "trusted-runner-public.pem"
        _run_tool(
            [
                openssl,
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(runner_private_key),
            ],
            failure_code=E_PROOF,
            context="self-test could not create trusted runner key",
        )
        _run_tool(
            [
                openssl,
                "pkey",
                "-in",
                str(runner_private_key),
                "-pubout",
                "-out",
                str(runner_public_key),
            ],
            failure_code=E_PROOF,
            context="self-test could not export trusted runner key",
        )
        runner_attestation = root / "trusted-runner/attestation.json"
        runner_signature = root / "trusted-runner/attestation.sig"
        _write_json(
            runner_attestation,
            {
                "schema": WALKAROUND_RUNNER_ID,
                "runner_id": WALKAROUND_RUNNER_ID,
                "subject_sha256": _walkaround_subject_digest(walkaround_payload),
                "assertion_sha256": _walkaround_assertion_digest(proof_digests),
                "probe_ids": [
                    _walkaround_probe_id(name) for name in sorted(_WALKAROUND_CHECKS)
                ],
            },
        )
        _run_tool(
            [
                openssl,
                "dgst",
                "-sha256",
                "-sign",
                str(runner_private_key),
                "-out",
                str(runner_signature),
                str(runner_attestation),
            ],
            failure_code=E_PROOF,
            context="self-test could not sign trusted runner attestation",
        )
        walkaround_payload["trusted_runner"] = {
            "attestation": proof_artifact(runner_attestation),
            "signature": proof_artifact(runner_signature),
        }
        seal_root = root / "delivery-run"
        seal_artifacts = {
            "execution_envelope_sha256": seal_root / "execution-envelope.json",
            "delivery_proof_contract_sha256": seal_root
            / "delivery-proof-contract.json",
            "proof_result_sha256": seal_root / "proof/result.json",
            "report_sha256": seal_root / "report.md",
            "transcript_sha256": seal_root / "transcript.log",
            "control_plane_snapshot_sha256": seal_root / "control-plane-snapshot.json",
        }
        runtime_probes = tuple(
            {
                "id": name,
                "probe_id": _walkaround_probe_id(name),
                "evidence_sha256": digest,
            }
            for name, digest in zip(
                sorted(_WALKAROUND_CHECKS), proof_digests, strict=True
            )
        )
        proof_contract = DeliveryProofContract(
            schema=DeliveryProofContract.SCHEMA,
            id="walkaround-proof",
            execution_envelope_sha256="sha256:" + "0" * 64,
            subject={"producer_id": "walkaround.subject", "argv": ["walkaround"]},
            witness={"expected_outcome": "all product checks pass"},
            oracle=None,
            assertion={"id": "walkaround", "kind": "sealed-runtime-probes"},
            negative_controls=({"id": "tamper-proof"},),
            delivery_scope=WALKAROUND_SCOPE,
            integration_target=str(app),
            runtime_probes=runtime_probes,
        )
        proof_result = ProofResult(
            schema=ProofResult.SCHEMA,
            proof_id=proof_contract.id,
            state=ProofState.PASSED,
            evidence=({"role": "subject", "exit_code": 0},),
            assertion_results=({"id": "walkaround", "passed": True, "valid": True},),
            negative_control_results=(
                {"id": "tamper-proof", "detected_falsehood": True, "valid": True},
            ),
            subject_executed=True,
            assertion_consumed_subject_output=True,
            refusal_reasons=(),
            contract_sha256=proof_contract.content_digest(),
            executor_sha256="sha256:" + "1" * 64,
            evaluated_at="2026-01-01T00:00:00+00:00",
        )
        _write_json(
            seal_artifacts["delivery_proof_contract_sha256"],
            proof_contract.to_payload(),
        )
        _write_json(seal_artifacts["proof_result_sha256"], proof_result.to_payload())
        for field, artifact in seal_artifacts.items():
            if field in {"delivery_proof_contract_sha256", "proof_result_sha256"}:
                continue
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(f"self-test {field}\n", encoding="utf-8")
        artifact_digests = {
            field: f"sha256:{_sha256(artifact)}"
            for field, artifact in seal_artifacts.items()
        }
        seal = DeliverySeal(
            schema=DeliverySeal.SCHEMA,
            seal_id="sha256:" + "a" * 64,
            issued_at="2026-01-01T00:00:00+00:00",
            issuer=WALKAROUND_SEAL_ISSUER,
            run_id="walkaround-self-test",
            lifecycle_id="unified-product-self-test",
            cut_id=WALKAROUND_SCOPE,
            proof_id=proof_contract.id,
            run_identity_sha256="sha256:" + "b" * 64,
            liveness_evidence_sha256=(),
            execution_envelope_sha256=artifact_digests["execution_envelope_sha256"],
            delivery_proof_contract_sha256=artifact_digests[
                "delivery_proof_contract_sha256"
            ],
            proof_result_sha256=artifact_digests["proof_result_sha256"],
            executor_source_sha256="sha256:" + "c" * 64,
            executor_version="self-test",
            subject_evidence_sha256=_walkaround_subject_digest(walkaround_payload),
            witness_sha256="sha256:" + "d" * 64,
            oracle_evidence_sha256=None,
            assertion_evidence_sha256=_walkaround_assertion_digest(proof_digests),
            negative_control_evidence_sha256=("sha256:" + "e" * 64,),
            repo="vetcoders/vibecrafted",
            branch="self-test",
            baseline_head="1" * 40,
            final_head="2" * 40,
            scoped_dirty_status_sha256="sha256:" + "f" * 64,
            commit_range="1" * 40 + ".." + "2" * 40,
            declared_scope=WALKAROUND_SCOPE,
            checked_scope=WALKAROUND_SCOPE,
            runtime_probe_sha256=proof_digests,
            report_sha256=artifact_digests["report_sha256"],
            transcript_sha256=artifact_digests["transcript_sha256"],
            control_plane_snapshot_sha256=artifact_digests[
                "control_plane_snapshot_sha256"
            ],
            unverified_surfaces=(),
        )
        seal_path = seal_root / "delivery-seal.json"
        _write_json(seal_path, seal.to_payload())
        walkaround_payload["delivery_seal"] = proof_artifact(seal_path)
        _write_json(walkaround, walkaround_payload)
        _verify_walkaround(
            walkaround,
            trusted_runner_public_key=runner_public_key,
            attached_mounts={(dmg.resolve(), mount.resolve())},
            run_live_checks=False,
            release_output_verifier=lambda *args, **kwargs: release_payload,
        )

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
    module.add_argument("--require-clean", action="store_true")
    app = commands.add_parser("app", help="verify an assembled app bundle")
    app.add_argument("path", type=Path)
    app.add_argument("--require-clean", action="store_true")
    transaction = commands.add_parser(
        "transaction", help="verify an app/runtime activation receipt"
    )
    transaction.add_argument("path", type=Path)
    schema = commands.add_parser("schema", help="validate one public contract JSON")
    schema.add_argument("path", type=Path)
    walkaround = commands.add_parser(
        "walkaround", help="verify a mounted-DMG walk-around receipt"
    )
    walkaround.add_argument("path", type=Path)
    release_output = commands.add_parser(
        "release-output", help="verify the externally signed final release identity"
    )
    release_output.add_argument("path", type=Path)
    release_output.add_argument("signature", type=Path)
    release_output.add_argument("--app", type=Path, required=True)
    release_output.add_argument("--dmg", type=Path, required=True)
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
            verify_module(args.path, require_clean=args.require_clean)
        elif args.command == "app":
            verify_app(args.path, require_clean=args.require_clean)
        elif args.command == "transaction":
            verify_transaction(args.path)
        elif args.command == "schema":
            validate_schema_document(_load_json(args.path))
        elif args.command == "walkaround":
            verify_walkaround(args.path)
        elif args.command == "release-output":
            verify_release_output(
                args.path,
                args.signature,
                app_path=args.app,
                dmg_path=args.dmg,
            )
        else:  # pragma: no cover - argparse owns the command set.
            _fail(E_SCHEMA, f"unsupported command: {args.command}")
    except ProductContractError as exc:
        print(f"VCPC{exc.code:03d}: {exc}", file=sys.stderr)
        return exc.code
    print(f"verified {args.command}: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

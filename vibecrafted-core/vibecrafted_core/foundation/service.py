from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tomllib
import uuid
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

from vibecrafted_core.runtime_paths import vibecrafted_home
from vibecrafted_core.package_resources import resource_path

from .capabilities import capability_delta
from .data_authority import inventory_sources
from .model import (
    CapabilityClassification,
    DestructiveChangeLease,
    EvidenceState,
    FoundationReceipt,
    FoundationStatus,
    PremiseStatus,
    RepoRelation,
    SourceStatus,
)
from .premises import evaluate_premises, premise_set_hash
from .repository import collect_repository_authority
from .lease import dirty_snapshot_hash, lease_budget_hash


class FoundationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(cast(Any, value)).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_payload(receipt: FoundationReceipt | dict[str, Any]) -> dict[str, Any]:
    payload = _jsonable(receipt)
    payload["receipt_hash"] = ""
    issuer = payload.get("issuer")
    if isinstance(issuer, dict):
        issuer["signature"] = ""
    return payload


def receipt_hash(receipt: FoundationReceipt | dict[str, Any]) -> str:
    raw = json.dumps(
        canonical_payload(receipt),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_config(root: str | Path) -> dict[str, Any]:
    path = Path(root).resolve() / "vibecrafted.toml"
    if not path.is_file():
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise FoundationError(f"invalid foundation config {path}: {exc}") from exc
    foundation = payload.get("vibecrafted", {}).get("foundation", {})
    return dict(foundation) if isinstance(foundation, dict) else {}


def foundation_state_dir(root: str | Path) -> Path:
    canonical = str(Path(root).resolve())
    repo_key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return vibecrafted_home() / "foundation" / repo_key


def _issuer_key(root: str | Path, *, create: bool) -> bytes:
    state_dir = foundation_state_dir(root)
    key_path = state_dir / "issuer.key"
    if create:
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            # This directory contains the local issuer key; group/other access is forbidden.
            # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
            os.chmod(state_dir, 0o700)
        except OSError:
            pass
        if not key_path.exists():
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32))
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    try:
        key = key_path.read_bytes()
    except OSError as exc:
        raise FoundationError(
            f"trusted Foundation issuer key unavailable: {exc}"
        ) from exc
    if len(key) < 32:
        raise FoundationError("trusted Foundation issuer key is invalid")
    return key


def _signature_payload(payload: FoundationReceipt | dict[str, Any]) -> bytes:
    value = _jsonable(payload)
    issuer = value.get("issuer")
    if isinstance(issuer, dict):
        issuer["signature"] = ""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _plan_identity(path: str | Path) -> tuple[str, str]:
    target = Path(path).expanduser().resolve()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise FoundationError(f"cannot bind executable plan {target}: {exc}") from exc
    canonical = "\n".join(
        line for line in text.splitlines() if _BINDING_PATTERN.fullmatch(line) is None
    )
    if text.endswith("\n"):
        canonical += "\n"
    return str(target), hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _schema_reasons(payload: dict[str, Any]) -> list[str]:
    """Validate the receipt against the packaged v1 contract without a runtime dep."""
    try:
        schema = json.loads(
            resource_path("schemas", "foundation.schema.v1.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"packaged Foundation schema unavailable: {exc}"]
    reasons: list[str] = []
    required = set(schema.get("required") or ())
    missing = sorted(required - set(payload))
    if missing:
        reasons.append("receipt schema missing fields: " + ", ".join(missing))
    if schema.get("additionalProperties") is False:
        extras = sorted(set(payload) - set(schema.get("properties") or {}))
        if extras:
            reasons.append("receipt schema unknown fields: " + ", ".join(extras))
    if payload.get("schema_id") != schema.get("$id"):
        reasons.append("unsupported schema_id")
    if payload.get("status") not in set(
        schema.get("properties", {}).get("status", {}).get("enum", ())
    ):
        reasons.append("invalid receipt status")
    repository = payload.get("repository")
    repo_schema = schema.get("$defs", {}).get("repository", {})
    if not isinstance(repository, dict):
        reasons.append("receipt repository must be an object")
    else:
        repo_missing = sorted(set(repo_schema.get("required") or ()) - set(repository))
        if repo_missing:
            reasons.append(
                "receipt repository missing fields: " + ", ".join(repo_missing)
            )
        evidence_required = set(
            schema.get("$defs", {}).get("evidence", {}).get("required") or ()
        )
        for name in (
            "authority_sha",
            "branch",
            "head",
            "upstream",
            "merge_base",
            "dirty",
            "detached",
            "shallow",
            "submodules",
            "worktrees",
            "ahead",
            "behind",
        ):
            evidence = repository.get(name)
            if not isinstance(evidence, dict) or evidence_required - set(evidence):
                reasons.append(f"receipt repository evidence invalid: {name}")
    for name in (
        "normative_sources",
        "premises",
        "capability_delta",
        "decision_reasons",
    ):
        if not isinstance(payload.get(name), list):
            reasons.append(f"receipt schema field must be an array: {name}")
    for name in ("bindings", "supervisor_decision", "bootstrap", "issuer"):
        if not isinstance(payload.get(name), dict):
            reasons.append(f"receipt schema field must be an object: {name}")
    issuer = payload.get("issuer") or {}
    if isinstance(issuer, dict):
        if set(issuer) != {"algorithm", "key_id", "issued_by", "signature"}:
            reasons.append("receipt issuer proof is incomplete")
        if issuer.get("algorithm") != "hmac-sha256":
            reasons.append("unsupported receipt issuer algorithm")
        if not re.fullmatch(r"[0-9a-f]{16}", str(issuer.get("key_id") or "")):
            reasons.append("invalid receipt issuer key_id")
        if not re.fullmatch(r"[0-9a-f]{64}", str(issuer.get("signature") or "")):
            reasons.append("invalid receipt issuer signature")
    return reasons


def latest_receipt_path(root: str | Path) -> Path:
    return foundation_state_dir(root) / "latest.json"


def _write_receipt(receipt: FoundationReceipt, path: Path) -> FoundationReceipt:
    key = _issuer_key(receipt.repository.root, create=True)
    key_id = hashlib.sha256(key).hexdigest()[:16]
    issued = replace(
        receipt,
        issuer={
            "algorithm": "hmac-sha256",
            "key_id": key_id,
            "issued_by": receipt.created_by,
            "signature": "",
        },
    )
    hashed = replace(issued, receipt_hash=receipt_hash(issued))
    signature = hmac.new(key, _signature_payload(hashed), hashlib.sha256).hexdigest()
    sealed = replace(hashed, issuer={**hashed.issuer, "signature": signature})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(_jsonable(sealed), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return sealed


def seal_repository(
    root: str | Path,
    *,
    authority_ref: str = "",
    authority_source: str = "operator",
    run_id: str = "",
    created_by: str = "operator",
    output: str | Path | None = None,
    fetch: bool = True,
    bootstrap: dict[str, Any] | None = None,
    plan_path: str | Path | None = None,
    lease: DestructiveChangeLease | dict[str, Any] | None = None,
) -> tuple[FoundationReceipt, Path]:
    repo = Path(root).resolve()
    config = load_config(repo)
    configured_ref = str(config.get("authority") or "")
    if authority_ref and configured_ref and authority_ref != configured_ref:
        raise FoundationError(
            f"conflicting authority: operator={authority_ref} repo_config={configured_ref}"
        )
    selected_ref = authority_ref or configured_ref
    if not selected_ref:
        raise FoundationError(
            "explicit authority is required; remote order and feature upstream are not authority"
        )
    source = authority_source if authority_ref else "repo_config"
    receipt_id = f"fnd-{uuid.uuid4().hex[:16]}"
    repository = collect_repository_authority(
        repo,
        authority_ref=selected_ref,
        authority_source=source,
        receipt_id=receipt_id,
        fetch=fetch,
    )
    declarations = config.get("normative_sources", ())
    if not isinstance(declarations, list):
        declarations = ()
    discovery = config.get("normative_discovery_globs", ())
    if not isinstance(discovery, list):
        discovery = ()
    sources, unbound = inventory_sources(repo, declarations, discovery_globs=discovery)
    premise_declarations = config.get("premises", ())
    if not isinstance(premise_declarations, list):
        premise_declarations = ()
    premises = evaluate_premises(repo, premise_declarations)
    classifications = config.get("capability_classifications", {})
    if not isinstance(classifications, dict):
        classifications = {}
    try:
        losses = capability_delta(repo, selected_ref, classifications=classifications)
    except RuntimeError as exc:
        losses = ()
        capability_error = str(exc)
    else:
        capability_error = ""

    reasons: list[str] = []
    if repository.authority_sha.state is not EvidenceState.KNOWN:
        reasons.append(f"authority unavailable: {repository.authority_sha.error_kind}")
    if repository.relation in {
        RepoRelation.BEHIND,
        RepoRelation.DIVERGED,
        RepoRelation.UNRELATED,
        RepoRelation.UNKNOWN,
    }:
        reasons.append(f"unsafe authority relation: {repository.relation.value}")
    if repository.authority_only_commits:
        reasons.append(
            f"authority has {len(repository.authority_only_commits)} missing commit(s)"
        )
    if (
        repository.detached.state is not EvidenceState.KNOWN
        or repository.detached.value
    ):
        reasons.append("detached HEAD requires operator waiver")
    if repository.shallow.state is not EvidenceState.KNOWN or repository.shallow.value:
        reasons.append("shallow repository cannot prove ancestry")
    if repository.dirty.state is not EvidenceState.KNOWN:
        reasons.append("dirty state is unknown")
    for source_item in sources:
        if source_item.status is not SourceStatus.BOUND:
            reasons.append(
                f"normative source {source_item.identity}: {source_item.status.value}"
            )
    if unbound:
        reasons.append(f"unbound live normative source(s): {len(unbound)}")
    for premise in premises:
        if premise.critical and premise.status not in {
            PremiseStatus.VERIFIED,
            PremiseStatus.WAIVED,
        }:
            reasons.append(f"critical premise {premise.id}: {premise.status.value}")
    for loss in losses:
        if loss.classification in {
            CapabilityClassification.MISSING,
            CapabilityClassification.UNKNOWN,
        }:
            reasons.append(f"unclassified authority capability loss: {loss.identity}")
    if capability_error:
        reasons.append(f"capability inventory error: {capability_error}")

    status = FoundationStatus.BLOCKED if reasons else FoundationStatus.SEALED
    premise_hash = premise_set_hash(premises)
    bindings: dict[str, Any] = {
        "authority_ref": selected_ref,
        "authority_sha": repository.authority_sha.value
        if repository.authority_sha.state is EvidenceState.KNOWN
        else None,
        "premise_set_hash": premise_hash,
        "dirty_snapshot_hash": dirty_snapshot_hash(repo),
    }
    if plan_path:
        bindings["plan_path"], bindings["plan_hash"] = _plan_identity(plan_path)
    approved_lease: DestructiveChangeLease | None
    if isinstance(lease, DestructiveChangeLease):
        approved_lease = lease
    elif isinstance(lease, dict):
        allowed_paths = tuple(str(item) for item in lease.get("allowed_paths", ()))
        expected_symbols = tuple(
            str(item) for item in lease.get("expected_deleted_symbols", ())
        )
        approved_by = str(lease.get("approved_by") or created_by)
        approved_hash = lease_budget_hash(
            allowed_paths=allowed_paths,
            max_deleted_files=int(lease.get("max_deleted_files", 0)),
            max_deleted_loc=int(lease.get("max_deleted_loc", 0)),
            expected_deleted_symbols=expected_symbols,
            risk_class=str(lease.get("risk_class") or "destructive"),
            approved_by=approved_by,
        )
        approved_lease = DestructiveChangeLease(
            allowed_paths=allowed_paths,
            max_deleted_files=int(lease.get("max_deleted_files", 0)),
            max_deleted_loc=int(lease.get("max_deleted_loc", 0)),
            expected_deleted_symbols=expected_symbols,
            risk_class=str(lease.get("risk_class") or "destructive"),
            approved_budget_hash=approved_hash,
            approved_by=approved_by,
            recovery_checkpoint_ref="",
            dirty_snapshot_hash=bindings["dirty_snapshot_hash"],
        )
        bindings["lease_hash"] = approved_hash
    else:
        approved_lease = None
    receipt = FoundationReceipt(
        receipt_id=receipt_id,
        repo_id=repo.name,
        run_id=run_id,
        created_at=_now(),
        created_by=created_by,
        status=status,
        repository=repository,
        normative_sources=sources,
        premises=premises,
        capability_delta=losses,
        lease=approved_lease,
        bindings=bindings,
        supervisor_decision={
            "allowed": status is FoundationStatus.SEALED,
            "decided_at": _now(),
            "workflow": "foundation seal",
            "evidence_ref": repository.snapshot_ref,
        },
        decision_reasons=tuple(reasons),
        bootstrap=bootstrap or {},
    )
    path = Path(output).expanduser().resolve() if output else latest_receipt_path(repo)
    return _write_receipt(receipt, path), path


def load_receipt(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundationError(
            f"cannot read Foundation receipt {target}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FoundationError("Foundation receipt must be a JSON object")
    return payload


def verify_receipt(
    path: str | Path,
    *,
    root: str | Path | None = None,
    plan_path: str | Path | None = None,
    refresh_authority: bool = True,
) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    payload = load_receipt(target)
    reasons: list[str] = _schema_reasons(payload)
    expected_hash = str(payload.get("receipt_hash") or "")
    if not expected_hash or receipt_hash(payload) != expected_hash:
        reasons.append("receipt hash mismatch")
    issuer = payload.get("issuer") or {}
    try:
        issuer_key = _issuer_key(
            root or (payload.get("repository") or {}).get("root") or ".",
            create=False,
        )
    except FoundationError as exc:
        reasons.append(str(exc))
    else:
        if hashlib.sha256(issuer_key).hexdigest()[:16] != str(
            issuer.get("key_id") or ""
        ):
            reasons.append("receipt issuer key mismatch")
        expected_signature = hmac.new(
            issuer_key, _signature_payload(payload), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(
            expected_signature, str(issuer.get("signature") or "")
        ):
            reasons.append("receipt issuer signature mismatch")
    if payload.get("status") != FoundationStatus.SEALED.value:
        reasons.append(f"receipt status is {payload.get('status') or 'unknown'}")
    repository = payload.get("repository") or {}
    repo = Path(root or repository.get("root") or ".").expanduser().resolve()
    if str(repo) != str(Path(repository.get("root") or "").expanduser().resolve()):
        reasons.append("repository root binding mismatch")

    def git_value(*args: str) -> str:
        import subprocess

        result = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    current_head = git_value("rev-parse", "HEAD")
    sealed_head = str((repository.get("head") or {}).get("value") or "")
    if not current_head or current_head != sealed_head:
        reasons.append("live HEAD drifted from receipt")
    sealed_dirty = str((payload.get("bindings") or {}).get("dirty_snapshot_hash") or "")
    try:
        current_dirty = dirty_snapshot_hash(repo)
    except RuntimeError as exc:
        reasons.append(f"dirty state refresh failed: {exc}")
    else:
        if not sealed_dirty or current_dirty != sealed_dirty:
            reasons.append("dirty Living Tree drifted from receipt")
    authority_ref = str(repository.get("authority_ref") or "")
    if refresh_authority and "/" in authority_ref:
        import subprocess

        remote, branch_name = authority_ref.split("/", 1)
        refreshed = subprocess.run(
            [
                "git",
                "fetch",
                "--no-tags",
                remote,
                f"+refs/heads/{branch_name}:refs/remotes/{remote}/{branch_name}",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if refreshed.returncode != 0:
            reasons.append(
                "authority refresh failed: "
                + (
                    (refreshed.stderr or refreshed.stdout).strip()
                    or f"exit {refreshed.returncode}"
                )
            )
    current_authority = (
        git_value("rev-parse", "--verify", authority_ref) if authority_ref else ""
    )
    sealed_authority = str((repository.get("authority_sha") or {}).get("value") or "")
    if not current_authority or current_authority != sealed_authority:
        reasons.append("authority ref drifted from receipt")
    for source in payload.get("normative_sources") or []:
        if (
            not isinstance(source, dict)
            or source.get("status") != SourceStatus.BOUND.value
        ):
            continue
        source_path = Path(str(source.get("path") or ""))
        expected = str((source.get("digest") or {}).get("value") or "")
        if not source_path.exists():
            reasons.append(f"normative source disappeared: {source.get('identity')}")
            continue
        try:
            from .data_authority import _hash_path

            actual = _hash_path(source_path)
        except OSError as exc:
            reasons.append(
                f"normative source unreadable: {source.get('identity')}: {exc}"
            )
            continue
        if actual != expected:
            reasons.append(f"normative source drifted: {source.get('identity')}")
    premise_declarations: list[dict[str, Any]] = []
    for premise in payload.get("premises") or []:
        if not isinstance(premise, dict):
            reasons.append("receipt premise is malformed")
            continue
        premise_declarations.append(
            {
                key: premise.get(key)
                for key in (
                    "id",
                    "critical",
                    "probe",
                    "expected",
                    "evidence_ref",
                    "drift_policy",
                    "expires_at",
                )
            }
        )
    refreshed_premises = evaluate_premises(repo, premise_declarations)
    for premise in refreshed_premises:
        if premise.critical and premise.status not in {
            PremiseStatus.VERIFIED,
            PremiseStatus.WAIVED,
        }:
            reasons.append(
                f"critical premise drifted: {premise.id}: {premise.status.value}"
            )
    sealed_premise_hash = str(
        (payload.get("bindings") or {}).get("premise_set_hash") or ""
    )
    if premise_set_hash(refreshed_premises) != sealed_premise_hash:
        reasons.append("critical premise set drifted from receipt")
    if plan_path:
        bindings = parse_plan_bindings(plan_path)
        actual_plan_path, actual_plan_hash = _plan_identity(plan_path)
        receipt_bindings = payload.get("bindings") or {}
        if receipt_bindings.get("plan_path") != actual_plan_path:
            reasons.append("receipt plan path binding mismatch")
        if receipt_bindings.get("plan_hash") != actual_plan_hash:
            reasons.append("receipt plan content hash mismatch")
        required = {
            "foundation_receipt_hash": expected_hash,
            "foundation_authority_ref": authority_ref,
            "foundation_authority_sha": sealed_authority,
            "foundation_premise_set_hash": str(
                (payload.get("bindings") or {}).get("premise_set_hash") or ""
            ),
        }
        for binding_key, expected_value in required.items():
            if bindings.get(binding_key) != expected_value:
                reasons.append(f"plan binding mismatch: {binding_key}")
    return {
        "allowed": not reasons,
        "status": FoundationStatus.SEALED.value
        if not reasons
        else FoundationStatus.BLOCKED.value,
        "reasons": reasons,
        "receipt_path": str(target),
        "receipt_hash": expected_hash,
        "authority_ref": authority_ref,
        "authority_sha": sealed_authority,
        "premise_set_hash": str(
            (payload.get("bindings") or {}).get("premise_set_hash") or ""
        ),
        "lease": payload.get("lease"),
        "bindings": payload.get("bindings") or {},
    }


_BINDING_PATTERN = re.compile(
    r"^(foundation_(?:receipt_path|receipt_hash|authority_ref|authority_sha|premise_set_hash|lease_hash)):\s*[\"']?([^\"'\n]+?)\s*[\"']?$",
    re.MULTILINE,
)


def parse_plan_bindings(path: str | Path) -> dict[str, str]:
    target = Path(path).expanduser().resolve()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {key: value.strip() for key, value in _BINDING_PATTERN.findall(text)}


def preflight_launch(
    *,
    root: str | Path,
    workflow: str,
    can_modify_code: bool,
    plan_path: str | Path | None = None,
    receipt_path: str | Path | None = None,
) -> dict[str, Any]:
    repo = Path(root).expanduser().resolve()
    config = load_config(repo)
    required = bool(config.get("required", False))
    if not can_modify_code:
        return {
            "allowed": True,
            "status": "UNSEALED" if not receipt_path else "OBSERVED",
            "reasons": [],
            "workflow": workflow,
        }
    git_managed = (repo / ".git").exists()
    if not required and not receipt_path and git_managed:
        return {
            "allowed": False,
            "status": FoundationStatus.BLOCKED.value,
            "reasons": [
                "Git repository has no explicit Foundation authority configuration"
            ],
            "workflow": workflow,
        }
    if not required and not receipt_path:
        return {
            "allowed": True,
            "status": "UNMANAGED",
            "reasons": ["repository has not enabled Foundation enforcement"],
            "workflow": workflow,
        }
    bindings = parse_plan_bindings(plan_path) if plan_path else {}
    if plan_path and not bindings:
        return {
            "allowed": False,
            "status": FoundationStatus.BLOCKED.value,
            "reasons": ["executable write artifact has no Foundation bindings"],
            "workflow": workflow,
        }
    selected = str(receipt_path or bindings.get("foundation_receipt_path") or "")
    if not selected:
        # Fail-closed discovery: a repository that already sealed its truth
        # keeps the receipt at latest_receipt_path(). Binding it implicitly is
        # safe because verify_receipt() below re-validates authority drift,
        # hash, and root binding — a stale or foreign receipt still BLOCKS.
        # Without this, every public deck launch (which has no frontmatter
        # bindings) dies with "no bound Foundation receipt" even on a freshly
        # sealed repo.
        candidate = latest_receipt_path(repo)
        if candidate.is_file():
            selected = str(candidate)
    if not selected:
        return {
            "allowed": False,
            "status": FoundationStatus.BLOCKED.value,
            "reasons": [
                "write launch has no bound Foundation receipt "
                "(seal one with: vibecrafted foundation seal)"
            ],
            "workflow": workflow,
        }
    result = verify_receipt(
        selected, root=repo, plan_path=plan_path if bindings else None
    )
    result["workflow"] = workflow
    return result

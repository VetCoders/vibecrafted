from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
import uuid
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

from vibecrafted_core.runtime_paths import vibecrafted_home

from .capabilities import capability_delta
from .data_authority import inventory_sources
from .model import (
    CapabilityClassification,
    EvidenceState,
    FoundationReceipt,
    FoundationStatus,
    PremiseStatus,
    RepoRelation,
    SourceStatus,
)
from .premises import evaluate_premises, premise_set_hash
from .repository import collect_repository_authority


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


def latest_receipt_path(root: str | Path) -> Path:
    return foundation_state_dir(root) / "latest.json"


def _write_receipt(receipt: FoundationReceipt, path: Path) -> FoundationReceipt:
    sealed = replace(receipt, receipt_hash=receipt_hash(receipt))
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
        bindings={
            "authority_ref": selected_ref,
            "authority_sha": repository.authority_sha.value
            if repository.authority_sha.state is EvidenceState.KNOWN
            else None,
            "premise_set_hash": premise_hash,
        },
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
    reasons: list[str] = []
    if payload.get("schema_id") != "vibecrafted.foundation.v1":
        reasons.append("unsupported schema_id")
    expected_hash = str(payload.get("receipt_hash") or "")
    if not expected_hash or receipt_hash(payload) != expected_hash:
        reasons.append("receipt hash mismatch")
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
    if plan_path:
        bindings = parse_plan_bindings(plan_path)
        required = {
            "foundation_receipt_hash": expected_hash,
            "foundation_authority_ref": authority_ref,
            "foundation_authority_sha": sealed_authority,
            "foundation_premise_set_hash": str(
                (payload.get("bindings") or {}).get("premise_set_hash") or ""
            ),
        }
        for key, expected in required.items():
            if bindings.get(key) != expected:
                reasons.append(f"plan binding mismatch: {key}")
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
        return {
            "allowed": False,
            "status": FoundationStatus.BLOCKED.value,
            "reasons": ["write launch has no bound Foundation receipt"],
            "workflow": workflow,
        }
    result = verify_receipt(
        selected, root=repo, plan_path=plan_path if bindings else None
    )
    result["workflow"] = workflow
    return result

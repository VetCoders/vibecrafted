from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .model import EvidenceValue, NormativeSource, SourceStatus


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def inventory_sources(
    root: str | Path,
    declarations: Iterable[dict[str, Any]],
    *,
    discovery_globs: Iterable[str] = (),
) -> tuple[tuple[NormativeSource, ...], tuple[str, ...]]:
    repo = Path(root).resolve()
    sources: list[NormativeSource] = []
    bound: set[Path] = set()
    for declaration in declarations:
        raw_path = str(declaration.get("path") or "")
        path = (repo / raw_path).resolve() if raw_path else repo / "<missing>"
        identity = str(declaration.get("identity") or raw_path or "unnamed")
        provenance = str(declaration.get("provenance") or "unknown")
        required = str(declaration.get("required_provenance") or "")
        if not raw_path or not path.exists():
            sources.append(
                NormativeSource(
                    identity=identity,
                    path=str(path),
                    digest=EvidenceValue.unknown(error_kind="missing_source"),
                    provenance=provenance,
                    required_provenance=required,
                    status=SourceStatus.MISSING,
                    error="normative source is missing",
                )
            )
            continue
        try:
            digest = _hash_path(path)
        except OSError as exc:
            sources.append(
                NormativeSource(
                    identity=identity,
                    path=str(path),
                    digest=EvidenceValue.failed(
                        error_kind="unreadable_source", error=str(exc)
                    ),
                    provenance=provenance,
                    required_provenance=required,
                    status=SourceStatus.UNREADABLE,
                    error=str(exc),
                )
            )
            continue
        bound.add(path)
        status = SourceStatus.BOUND
        error = ""
        if required and provenance != required:
            status = SourceStatus.UNBOUND
            error = f"requires provenance {required}, got {provenance}"
        sources.append(
            NormativeSource(
                identity=identity,
                path=str(path),
                digest=EvidenceValue.known(digest, evidence=f"sha256:{path}"),
                schema_version=str(declaration.get("schema_version") or ""),
                oracle_identity=str(declaration.get("oracle_identity") or ""),
                oracle_version=str(declaration.get("oracle_version") or ""),
                provenance=provenance,
                required_provenance=required,
                coverage=tuple(str(item) for item in declaration.get("coverage", ())),
                status=status,
                error=error,
            )
        )

    unbound: list[str] = []
    for pattern in discovery_globs:
        for candidate in sorted(repo.glob(pattern)):
            resolved = candidate.resolve()
            if resolved not in bound:
                unbound.append(str(resolved))
    return tuple(sources), tuple(dict.fromkeys(unbound))

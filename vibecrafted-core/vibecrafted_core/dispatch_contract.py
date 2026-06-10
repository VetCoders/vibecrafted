from __future__ import annotations

import re
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .workflow import SUPPORTED_WORKFLOWS

SCHEMA_VERSION = "vibecrafted.dispatch.v1"
MATCHER_TYPES = {"contains", "equals", "matches", "not_contains", "exit_code"}
READ_MUTATIONS = {"forbid", "allow-report-only", "allow"}
TIMEOUT_POLICIES = {"repair", "fail", "continue"}
CRITICAL_FAIL_POLICIES = {"break", "continue"}
FORBIDDEN_COMMAND_NEEDLES = (
    "git reset --hard",
    "git clean -fd",
    "git clean -xdf",
    "rm -rf /",
)


@dataclass(frozen=True)
class DispatchMeta:
    name: str
    repo: str
    description: str = ""
    baseline: dict[str, Any] = field(default_factory=dict)
    reports_dir: str = ""
    tracker: str = ""


@dataclass(frozen=True)
class DispatchPolicy:
    repair_rounds: int = 0
    on_critical_fail: str = "break"
    on_timeout: str = "fail"
    concurrency: int = 1
    await_config: dict[str, Any] = field(default_factory=dict)
    verify_executor: str = "supervisor"
    allow_concurrency: bool = False


@dataclass(frozen=True)
class DispatchCommon:
    text: str = ""


@dataclass(frozen=True)
class DispatchPhase:
    title: str
    detail: str = ""


@dataclass(frozen=True)
class DispatchMatcher:
    kind: str
    expected: str | int


@dataclass(frozen=True)
class DispatchVerify:
    run: str
    matchers: tuple[DispatchMatcher, ...]


@dataclass(frozen=True)
class DispatchRecovery:
    on: str = ""
    goto: str = ""
    max_loops: int | None = None


@dataclass(frozen=True)
class DispatchCut:
    id: str
    phase: str
    agent: str
    workflow: str
    resolved_workflow: str
    critical: bool = False
    mode: str = "write"
    prompt: str = ""
    brief: str = ""
    extra: str = ""
    mutation: str = ""
    observational: bool = False
    verify: tuple[DispatchVerify, ...] = ()
    recovery: DispatchRecovery | None = None


@dataclass(frozen=True)
class DispatchContract:
    schema: str
    meta: DispatchMeta
    policy: DispatchPolicy
    common: DispatchCommon
    phases: tuple[DispatchPhase, ...]
    cuts: tuple[DispatchCut, ...]
    workflow_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchDoctorResult:
    ok: bool
    errors: tuple[str, ...]
    contract: DispatchContract | None = None


class DispatchContractError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


def load_dispatch_contract(path: str | Path) -> DispatchContract:
    source = Path(path).expanduser()
    return parse_dispatch_contract(
        source.read_text(encoding="utf-8"), base_dir=source.parent
    )


def doctor_dispatch_contract(
    text: str, *, base_dir: str | Path | None = None
) -> DispatchDoctorResult:
    try:
        return DispatchDoctorResult(
            ok=True,
            errors=(),
            contract=parse_dispatch_contract(text, base_dir=base_dir),
        )
    except DispatchContractError as exc:
        return DispatchDoctorResult(ok=False, errors=exc.errors, contract=None)


def parse_dispatch_contract(
    text: str, *, base_dir: str | Path | None = None
) -> DispatchContract:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise DispatchContractError([f"toml: {exc}"]) from exc

    errors: list[str] = []
    if not isinstance(raw, dict):
        raise DispatchContractError(["dispatch root must be a TOML table"])

    schema = _string(raw.get("schema"))
    if schema != SCHEMA_VERSION:
        errors.append(f"schema: unsupported schema {schema!r}")

    meta = _parse_meta(raw.get("meta"), errors)
    policy = _parse_policy(raw.get("policy"), errors)
    common = _parse_common(raw.get("common"))
    workflow_map = _parse_workflow_map(
        raw.get("workflow_map") or raw.get("workflows"), errors
    )
    phases = _parse_phases(raw.get("phases"), errors)
    cuts = _parse_cuts(
        raw.get("cuts"),
        phases=phases,
        workflow_map=workflow_map,
        base_dir=Path(base_dir).expanduser() if base_dir else None,
        errors=errors,
    )

    if policy.concurrency > 1 and not policy.allow_concurrency:
        errors.append(
            "policy.concurrency: values greater than 1 require allow_concurrency = true"
        )

    _validate_recovery_targets(cuts, phases, errors)

    if errors:
        raise DispatchContractError(errors)

    return DispatchContract(
        schema=schema,
        meta=meta,
        policy=policy,
        common=common,
        phases=tuple(phases),
        cuts=tuple(cuts),
        workflow_map=workflow_map,
    )


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def _parse_meta(value: Any, errors: list[str]) -> DispatchMeta:
    if not isinstance(value, dict):
        errors.append("meta: table is required")
        return DispatchMeta(name="", repo="")
    name = _string(value.get("name"))
    repo = _string(value.get("repo"))
    if not repo:
        errors.append("meta.repo: required")
    return DispatchMeta(
        name=name,
        repo=repo,
        description=_string(value.get("description")),
        baseline=_dict(value.get("baseline")),
        reports_dir=_string(value.get("reports_dir")),
        tracker=_string(value.get("tracker")),
    )


def _parse_policy(value: Any, errors: list[str]) -> DispatchPolicy:
    raw = value if isinstance(value, dict) else {}
    on_timeout = _string(raw.get("on_timeout")) or "fail"
    if on_timeout not in TIMEOUT_POLICIES:
        errors.append(f"policy.on_timeout: unsupported value {on_timeout!r}")
    on_critical_fail = _string(raw.get("on_critical_fail")) or "break"
    if on_critical_fail not in CRITICAL_FAIL_POLICIES:
        errors.append(
            f"policy.on_critical_fail: unsupported value {on_critical_fail!r}"
        )
    concurrency = _int(raw.get("concurrency"), 1)
    if concurrency < 1:
        errors.append("policy.concurrency: must be at least 1")
    return DispatchPolicy(
        repair_rounds=max(0, _int(raw.get("repair_rounds"), 0)),
        on_critical_fail=on_critical_fail,
        on_timeout=on_timeout,
        concurrency=concurrency,
        await_config=_dict(raw.get("await")),
        verify_executor=_string(raw.get("verify_executor")) or "supervisor",
        allow_concurrency=bool(
            raw.get("allow_concurrency")
            or raw.get("enable_concurrency")
            or raw.get("parallel_enabled")
        ),
    )


def _parse_common(value: Any) -> DispatchCommon:
    raw = value if isinstance(value, dict) else {}
    return DispatchCommon(text=_string(raw.get("text")))


def _parse_workflow_map(value: Any, errors: list[str]) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append("workflow_map: table is required when present")
        return {}

    result: dict[str, str] = {}
    for raw_name, raw_target in value.items():
        name = _string(raw_name)
        target = _string(raw_target)
        if not name or not target:
            errors.append("workflow_map: names and targets must be non-empty strings")
            continue
        if target not in SUPPORTED_WORKFLOWS:
            errors.append(f"workflow_map.{name}: target {target!r} is not supported")
            continue
        result[name] = target
    return result


def _parse_phases(value: Any, errors: list[str]) -> list[DispatchPhase]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("phases: array of tables is required")
        return []

    phases: list[DispatchPhase] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"phases[{index}]: table is required")
            continue
        title = _string(item.get("title"))
        if not title:
            errors.append(f"phases[{index}].title: required")
            continue
        if title in seen:
            errors.append(f"phases[{index}].title: duplicate phase {title!r}")
            continue
        seen.add(title)
        phases.append(DispatchPhase(title=title, detail=_string(item.get("detail"))))
    return phases


def _parse_cuts(
    value: Any,
    *,
    phases: list[DispatchPhase],
    workflow_map: dict[str, str],
    base_dir: Path | None,
    errors: list[str],
) -> list[DispatchCut]:
    if not isinstance(value, list) or not value:
        errors.append("cuts: at least one cut table is required")
        return []

    phase_titles = {phase.title for phase in phases}
    cuts: list[DispatchCut] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"cuts[{index}]: table is required")
            continue
        cut_id = _string(item.get("id"))
        if not cut_id:
            errors.append(f"cuts[{index}].id: required")
        elif cut_id in seen_ids:
            errors.append(f"cuts[{index}].id: duplicate cut id {cut_id!r}")
        seen_ids.add(cut_id)

        phase = _string(item.get("phase"))
        if phase and phase_titles and phase not in phase_titles:
            errors.append(f"cuts[{index}].phase: unknown phase {phase!r}")

        workflow = _string(item.get("workflow"))
        resolved_workflow = workflow_map.get(workflow, workflow)
        if resolved_workflow not in SUPPORTED_WORKFLOWS:
            errors.append(f"cuts[{index}].workflow: unsupported workflow {workflow!r}")

        prompt = _string(item.get("prompt"))
        brief = _string(item.get("brief"))
        if not prompt and not brief:
            errors.append(f"cuts[{index}]: prompt or brief is required")
        if brief:
            _validate_brief_path(brief, base_dir, index, errors)

        mode = _string(item.get("mode")) or "write"
        mutation = _string(item.get("mutation"))
        observational = bool(item.get("observational") or item.get("observe"))
        verify = _parse_verify(item.get("verify"), index, errors)
        if not verify and not (mode == "read" and observational):
            errors.append(
                f"cuts[{index}].verify: required unless observational READ is explicit"
            )
        if mode == "read":
            if not mutation:
                errors.append(f"cuts[{index}].mutation: required for READ cuts")
            elif mutation not in READ_MUTATIONS:
                errors.append(f"cuts[{index}].mutation: unsupported value {mutation!r}")

        cuts.append(
            DispatchCut(
                id=cut_id,
                phase=phase,
                agent=_string(item.get("agent")),
                workflow=workflow,
                resolved_workflow=resolved_workflow,
                critical=bool(item.get("critical")),
                mode=mode,
                prompt=prompt,
                brief=brief,
                extra=_string(item.get("extra")),
                mutation=mutation,
                observational=observational,
                verify=tuple(verify),
                recovery=_parse_recovery(item.get("recovery"), index, errors),
            )
        )
    return cuts


def _parse_verify(
    value: Any, cut_index: int, errors: list[str]
) -> list[DispatchVerify]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"cuts[{cut_index}].verify: array of tables is required")
        return []

    verifiers: list[DispatchVerify] = []
    for index, item in enumerate(value):
        prefix = f"cuts[{cut_index}].verify[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: table is required")
            continue
        run = _string(item.get("run"))
        if not run:
            errors.append(f"{prefix}.run: required")
        _validate_command(run, prefix, errors)
        matchers = _parse_matchers(item.get("expect"), prefix, errors)
        verifiers.append(DispatchVerify(run=run, matchers=tuple(matchers)))
    return verifiers


def _parse_matchers(
    value: Any, prefix: str, errors: list[str]
) -> list[DispatchMatcher]:
    if not isinstance(value, dict) or not value:
        errors.append(f"{prefix}.expect: non-empty matcher table is required")
        return []

    matchers: list[DispatchMatcher] = []
    for kind, expected in value.items():
        if kind not in MATCHER_TYPES:
            errors.append(f"{prefix}.expect.{kind}: unsupported matcher")
            continue
        if kind == "exit_code":
            if isinstance(expected, bool) or not isinstance(expected, int):
                errors.append(f"{prefix}.expect.exit_code: integer expected")
                continue
            matchers.append(DispatchMatcher(kind=kind, expected=expected))
            continue
        if not isinstance(expected, str):
            errors.append(f"{prefix}.expect.{kind}: string expected")
            continue
        if kind == "matches":
            try:
                re.compile(expected)
            except re.error as exc:
                errors.append(f"{prefix}.expect.matches: invalid regex: {exc}")
                continue
        matchers.append(DispatchMatcher(kind=kind, expected=expected))
    return matchers


def _parse_recovery(
    value: Any, cut_index: int, errors: list[str]
) -> DispatchRecovery | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append(f"cuts[{cut_index}].recovery: table is required")
        return None
    max_loops = value.get("max_loops")
    loops = (
        max_loops
        if isinstance(max_loops, int) and not isinstance(max_loops, bool)
        else None
    )
    if max_loops is not None and loops is None:
        errors.append(f"cuts[{cut_index}].recovery.max_loops: integer expected")
    return DispatchRecovery(
        on=_string(value.get("on")),
        goto=_string(value.get("goto")),
        max_loops=loops,
    )


def _validate_recovery_targets(
    cuts: list[DispatchCut], phases: list[DispatchPhase], errors: list[str]
) -> None:
    cut_ids = {cut.id for cut in cuts if cut.id}
    phase_titles = {phase.title for phase in phases}
    for index, cut in enumerate(cuts):
        if cut.recovery is None or not cut.recovery.goto:
            continue
        target = cut.recovery.goto
        if target not in cut_ids and target not in phase_titles:
            errors.append(f"cuts[{index}].recovery.goto: unknown target {target!r}")


def _validate_brief_path(
    brief: str, base_dir: Path | None, cut_index: int, errors: list[str]
) -> None:
    path = Path(brief).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    if not path.is_file():
        errors.append(f"cuts[{cut_index}].brief: file is missing or unreadable")


def _validate_command(run: str, prefix: str, errors: list[str]) -> None:
    if not run:
        return
    normalized = " ".join(shlex.split(run)) if _can_shlex(run) else run
    lowered = normalized.lower()
    for needle in FORBIDDEN_COMMAND_NEEDLES:
        if needle in lowered:
            errors.append(f"{prefix}.run: forbidden hard-stop command {needle!r}")


def _can_shlex(value: str) -> bool:
    try:
        shlex.split(value)
    except ValueError:
        return False
    return True


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}

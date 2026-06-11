from __future__ import annotations

import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecrafted_core.workflow import SUPPORTED_WORKFLOWS

from .model import (
    CRITICAL_FAIL_POLICIES,
    MATCHER_TYPES,
    READ_MUTATIONS,
    SCHEMA_VERSION,
    TIMEOUT_POLICIES,
    Baton,
    Common,
    Cut,
    Dispatch,
    Matcher,
    Meta,
    Phase,
    Policy,
    Recovery,
    Verify,
)

FORBIDDEN_COMMAND_NEEDLES = (
    "--no-verify",
    "git reset --hard",
    "git clean -fd",
    "git clean -xdf",
    "git push",
    "make release",
    "release",
    "rm -rf /",
    "vc-release",
    "vibecrafted release",
)


@dataclass(frozen=True)
class DispatchDoctorResult:
    ok: bool
    errors: tuple[str, ...]
    dispatch: Dispatch | None = None


class DispatchSchemaError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


def load_dispatch(path: str | Path) -> Dispatch:
    source = Path(path).expanduser()
    return parse_dispatch(source.read_text(encoding="utf-8"), base_dir=source.parent)


def doctor_dispatch(
    text: str, *, base_dir: str | Path | None = None
) -> DispatchDoctorResult:
    try:
        dispatch = parse_dispatch(text, base_dir=base_dir)
        policy_errors = _doctor_policy_errors(dispatch)
        if policy_errors:
            return DispatchDoctorResult(
                ok=False,
                errors=tuple(policy_errors),
                dispatch=dispatch,
            )
        return DispatchDoctorResult(
            ok=True,
            errors=(),
            dispatch=dispatch,
        )
    except DispatchSchemaError as exc:
        return DispatchDoctorResult(ok=False, errors=exc.errors, dispatch=None)


def parse_dispatch(text: str, *, base_dir: str | Path | None = None) -> Dispatch:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise DispatchSchemaError([f"toml: {exc}"]) from exc

    if not isinstance(raw, dict):
        raise DispatchSchemaError(["dispatch root must be a TOML table"])

    errors: list[str] = []
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
    base = Path(base_dir).expanduser() if base_dir is not None else None
    cuts = _parse_cuts(
        raw.get("cuts"),
        phases=phases,
        workflow_map=workflow_map,
        base_dir=base,
        errors=errors,
    )

    if policy.concurrency > 1 and not policy.allow_concurrency:
        errors.append(
            "policy.concurrency: values greater than 1 require allow_concurrency = true"
        )

    _validate_recovery_targets(cuts, phases, errors)

    if errors:
        raise DispatchSchemaError(errors)

    return Dispatch(
        schema=schema,
        meta=meta,
        policy=policy,
        common=common,
        phases=tuple(phases),
        cuts=tuple(cuts),
        workflow_map=workflow_map,
    )


def render_cell_prompt(
    dispatch: Dispatch, cut: Cut, *, baton: Baton | None = None
) -> str:
    active_baton = baton if baton is not None else dispatch.empty_baton()
    variables = {
        "repo": dispatch.meta.repo,
        "id": cut.id,
        "agent": cut.agent,
        "workflow": cut.workflow,
        "resolved_workflow": cut.resolved_workflow,
        "reports_dir": dispatch.meta.reports_dir,
        "tracker": dispatch.meta.tracker,
        "baton": active_baton.to_json(),
    }
    body = _brief_or_prompt(cut)
    parts = [dispatch.common.text, body, cut.extra, active_baton.to_json()]
    rendered = [_format_known(part, variables).strip() for part in parts if part]
    return "\n\n".join(part for part in rendered if part).rstrip() + "\n"


def _brief_or_prompt(cut: Cut) -> str:
    if cut.brief:
        path = Path(cut.brief).expanduser()
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return cut.prompt


def _format_known(text: str, variables: dict[str, str]) -> str:
    rendered = text
    for name, value in variables.items():
        rendered = rendered.replace("{" + name + "}", value)
    return rendered


def _parse_meta(value: Any, errors: list[str]) -> Meta:
    if not isinstance(value, dict):
        errors.append("meta: table is required")
        return Meta(name="", repo="")
    name = _string(value.get("name"))
    repo = _string(value.get("repo"))
    if not repo:
        errors.append("meta.repo: required")
    return Meta(
        name=name,
        repo=repo,
        description=_string(value.get("description")),
        baseline=_dict(value.get("baseline")),
        reports_dir=_string(value.get("reports_dir")),
        tracker=_string(value.get("tracker")),
    )


def _parse_policy(value: Any, errors: list[str]) -> Policy:
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
    return Policy(
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


def _parse_common(value: Any) -> Common:
    raw = value if isinstance(value, dict) else {}
    return Common(text=_string(raw.get("text")))


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


def _parse_phases(value: Any, errors: list[str]) -> list[Phase]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("phases: array of tables is required")
        return []

    phases: list[Phase] = []
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
        phases.append(Phase(title=title, detail=_string(item.get("detail"))))
    return phases


def _parse_cuts(
    value: Any,
    *,
    phases: list[Phase],
    workflow_map: dict[str, str],
    base_dir: Path | None,
    errors: list[str],
) -> list[Cut]:
    if not isinstance(value, list) or not value:
        errors.append("cuts: at least one cut table is required")
        return []

    phase_titles = {phase.title for phase in phases}
    cuts: list[Cut] = []
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
            if mutation and mutation not in READ_MUTATIONS:
                errors.append(f"cuts[{index}].mutation: unsupported value {mutation!r}")

        cuts.append(
            Cut(
                id=cut_id,
                phase=phase,
                agent=_string(item.get("agent")),
                workflow=workflow,
                resolved_workflow=resolved_workflow,
                critical=bool(item.get("critical")),
                mode=mode,
                prompt=prompt,
                brief=_resolve_brief(brief, base_dir),
                extra=_string(item.get("extra")),
                mutation=mutation,
                observational=observational,
                verify=tuple(verify),
                recovery=_parse_recovery(item.get("recovery"), index, errors),
            )
        )
    return cuts


def _doctor_policy_errors(dispatch: Dispatch) -> list[str]:
    errors: list[str] = []
    for index, cut in enumerate(dispatch.cuts):
        if cut.mode == "read" and not cut.mutation:
            errors.append(f"cuts[{index}].mutation: required for READ cuts")
    return errors


def _parse_verify(value: Any, cut_index: int, errors: list[str]) -> list[Verify]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"cuts[{cut_index}].verify: array of tables is required")
        return []

    verifiers: list[Verify] = []
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
        verifiers.append(Verify(run=run, matchers=tuple(matchers)))
    return verifiers


def _parse_matchers(value: Any, prefix: str, errors: list[str]) -> list[Matcher]:
    if not isinstance(value, dict) or not value:
        errors.append(f"{prefix}.expect: non-empty matcher table is required")
        return []

    matchers: list[Matcher] = []
    for kind, expected in value.items():
        if kind not in MATCHER_TYPES:
            errors.append(f"{prefix}.expect.{kind}: unsupported matcher")
            continue
        if kind == "exit_code":
            if isinstance(expected, bool) or not isinstance(expected, int):
                errors.append(f"{prefix}.expect.exit_code: integer expected")
                continue
            matchers.append(Matcher(kind=kind, expected=expected))
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
        matchers.append(Matcher(kind=kind, expected=expected))
    return matchers


def _parse_recovery(value: Any, cut_index: int, errors: list[str]) -> Recovery | None:
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
    return Recovery(
        on=_string(value.get("on")),
        goto=_string(value.get("goto")),
        max_loops=loops,
    )


def _validate_recovery_targets(
    cuts: list[Cut], phases: list[Phase], errors: list[str]
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


def _resolve_brief(brief: str, base_dir: Path | None) -> str:
    if not brief:
        return ""
    path = Path(brief).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return str(path)


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


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}

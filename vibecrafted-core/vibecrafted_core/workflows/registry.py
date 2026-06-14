from __future__ import annotations

import os
from pathlib import Path

from ..runtime_paths import vibecrafted_tools_home
from .model import WorkflowCadence, WorkflowDefinition


def _direct(
    id: str,
    *,
    cadence: WorkflowCadence,
    lifecycle_order: int,
    tooling: tuple[str, ...] = (),
) -> WorkflowDefinition:
    return WorkflowDefinition(
        id=id,
        cadence=cadence,
        lifecycle_order=lifecycle_order,
        tooling=tooling,
    )


WORKFLOW_DEFINITIONS: dict[str, WorkflowDefinition] = {
    "audit": _direct(
        "audit",
        cadence="read",
        lifecycle_order=70,
        tooling=("vc-init", "vc-loctree", "vc-aicx", "vc-research"),
    ),
    "decorate": _direct(
        "decorate",
        cadence="write",
        lifecycle_order=102,
        tooling=("vc-init", "vc-decorate"),
    ),
    "delegate": _direct(
        "delegate",
        cadence="write",
        lifecycle_order=25,
        tooling=("vc-init", "vc-delegate"),
    ),
    "dou": _direct(
        "dou",
        cadence="read",
        lifecycle_order=90,
        tooling=("vc-init", "vc-intents", "vc-loctree"),
    ),
    "followup": _direct(
        "followup",
        cadence="read",
        lifecycle_order=50,
        tooling=("vc-init", "vc-intents", "vc-loctree"),
    ),
    "hydrate": _direct(
        "hydrate",
        cadence="write",
        lifecycle_order=100,
        tooling=("vc-init", "vc-operator", "vc-decorate"),
    ),
    "implement": WorkflowDefinition(
        id="implement",
        cadence="write",
        lifecycle_order=20,
        aliases=("justdo",),
        tooling=("vc-init", "vc-operator", "vc-agents"),
    ),
    "intents": _direct(
        "intents",
        cadence="read",
        lifecycle_order=45,
        tooling=("vc-init", "vc-intents", "vc-loctree"),
    ),
    "marbles": WorkflowDefinition(
        id="marbles",
        cadence="write",
        lifecycle_order=60,
        input_policy="optional",
        runtime_kind="supervised_marbles",
        supports_count=True,
        supports_depth=True,
        tooling=("vc-init", "vc-marbles"),
    ),
    "ownership": _direct(
        "ownership",
        cadence="write",
        lifecycle_order=15,
        tooling=("vc-init", "vc-ownership"),
    ),
    "partner": _direct(
        "partner",
        cadence="meta",
        lifecycle_order=5,
        tooling=("vc-init", "vc-partner", "vc-scaffold"),
    ),
    "polarize": _direct(
        "polarize",
        cadence="write",
        lifecycle_order=80,
        tooling=("vc-init", "vc-polarize"),
    ),
    "prune": WorkflowDefinition(
        id="prune",
        cadence="read",
        lifecycle_order=55,
        input_policy="optional_with_default",
        default_prompt_file="default_prompt.md",
        tooling=("vc-init", "vc-loctree"),
    ),
    "release": _direct(
        "release",
        cadence="write",
        lifecycle_order=110,
        tooling=("vc-init", "vc-release"),
    ),
    "research": WorkflowDefinition(
        id="research",
        cadence="read",
        lifecycle_order=12,
        default_agent="swarm",
        runtime_kind="supervised_research",
        tooling=("vc-init", "vc-research"),
    ),
    "review": _direct(
        "review",
        cadence="read",
        lifecycle_order=30,
        tooling=("vc-init", "vc-loctree", "vc-review", "vc-screenscribe", "vc-prview"),
    ),
    "scaffold": _direct(
        "scaffold",
        cadence="read",
        lifecycle_order=10,
        tooling=("vc-init", "vc-loctree", "vc-research"),
    ),
    "workflow": _direct(
        "workflow",
        cadence="write",
        lifecycle_order=40,
        tooling=("vc-init", "vc-research", "vc-justdo"),
    ),
}

SUPPORTED_WORKFLOWS = frozenset(WORKFLOW_DEFINITIONS)
WORKFLOW_ALIASES = {
    alias: definition.id
    for definition in WORKFLOW_DEFINITIONS.values()
    for alias in definition.aliases
}


def workflow_definition(workflow_id: str) -> WorkflowDefinition | None:
    resolved = WORKFLOW_ALIASES.get(workflow_id, workflow_id)
    return WORKFLOW_DEFINITIONS.get(resolved)


def workflow_runtime_kind(workflow_id: str) -> str:
    definition = workflow_definition(workflow_id)
    return definition.runtime_kind if definition is not None else "direct_agent"


def workflow_lifecycle() -> tuple[WorkflowDefinition, ...]:
    return tuple(
        sorted(WORKFLOW_DEFINITIONS.values(), key=lambda item: item.lifecycle_order)
    )


def _source_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workflow_dirs(workflow_id: str) -> list[Path]:
    candidates: list[Path] = []
    override = str(os.environ.get("VIBECRAFTED_WORKFLOWS_DIR") or "").strip()
    if override:
        candidates.append(Path(override).expanduser() / workflow_id)
    candidates.extend(
        [
            _source_root() / "runtime" / "workflows" / workflow_id,
            vibecrafted_tools_home()
            / "vibecrafted-local"
            / "runtime"
            / "workflows"
            / workflow_id,
            Path(__file__).resolve().parent / workflow_id,
        ]
    )
    return candidates


def workflow_default_prompt(workflow_id: str) -> str:
    definition = workflow_definition(workflow_id)
    if definition is None or not definition.default_prompt_file:
        return ""
    for directory in _workflow_dirs(definition.id):
        path = directory / definition.default_prompt_file
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
    return ""

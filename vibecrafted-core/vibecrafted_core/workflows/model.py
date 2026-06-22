from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkflowCadence = Literal["read", "write", "meta"]
WorkflowInputPolicy = Literal["required", "optional", "optional_with_default"]
WorkflowRuntimeKind = Literal[
    "direct_agent",
    "supervised_marbles",
    "supervised_research",
]


@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    cadence: WorkflowCadence
    lifecycle_order: int
    default_agent: str = "claude"
    input_policy: WorkflowInputPolicy = "required"
    runtime_kind: WorkflowRuntimeKind = "direct_agent"
    aliases: tuple[str, ...] = ()
    default_prompt_file: str = ""
    terminal_layout: str = ""
    supports_count: bool = False
    supports_depth: bool = False
    tooling: tuple[str, ...] = ()

    @property
    def requires_input(self) -> bool:
        return self.input_policy == "required"

    @property
    def can_use_default_prompt(self) -> bool:
        return self.input_policy == "optional_with_default"

    @property
    def can_modify_code(self) -> bool:
        return self.cadence == "write"


@dataclass(frozen=True)
class WorkflowStage:
    id: str
    workflow: str
    phase: WorkflowCadence
    order: int
    name: str = ""
    tooling: tuple[str, ...] = ()
    next_stage: str = ""
    fallback_stage: str = ""
    audit_after: str = ""
    transition: str = "success"

    @property
    def can_modify_code(self) -> bool:
        return self.phase == "write"


@dataclass(frozen=True)
class WorkflowManifest:
    id: str
    name: str
    description: str
    stages: tuple[WorkflowStage, ...]
    entry_stage: str = ""

    def stage(self, stage_id: str) -> WorkflowStage | None:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        return None

    @property
    def first_stage(self) -> WorkflowStage:
        if self.entry_stage:
            stage = self.stage(self.entry_stage)
            if stage is not None:
                return stage
        return self.stages[0]

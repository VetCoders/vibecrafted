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
    supports_count: bool = False
    supports_depth: bool = False
    tooling: tuple[str, ...] = ()

    @property
    def requires_input(self) -> bool:
        return self.input_policy == "required"

    @property
    def can_use_default_prompt(self) -> bool:
        return self.input_policy == "optional_with_default"

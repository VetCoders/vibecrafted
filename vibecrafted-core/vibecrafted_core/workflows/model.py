"""Typed data model for workflow definitions, ship-lifecycle stages, and manifests."""

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
    """Static, immutable contract for one `vibecrafted <workflow>` invocation."""

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
        """True when the workflow refuses to launch without an explicit prompt."""
        return self.input_policy == "required"

    @property
    def can_use_default_prompt(self) -> bool:
        """True when a missing prompt falls back to `default_prompt_file` on disk."""
        return self.input_policy == "optional_with_default"

    @property
    def can_modify_code(self) -> bool:
        """True for write-cadence workflows; read/meta workflows never mutate code."""
        return self.cadence == "write"


@dataclass(frozen=True)
class WorkflowStage:
    """One stage in a `WorkflowManifest`'s lifecycle: pins, transitions, and artifacts."""

    id: str
    workflow: str
    phase: WorkflowCadence
    order: int
    name: str = ""
    tooling: tuple[str, ...] = ()
    # Optional per-stage agent pin; empty = the current baton holder runs it.
    agent: str = ""
    # Optional per-stage model pin; empty = runner default.
    model: str = ""
    next_stage: str = ""
    fallback_stage: str = ""
    audit_after: str = ""
    transition: str = "success"
    transition_conditions: tuple[str, ...] = ()
    allowed_artifacts: tuple[str, ...] = ()

    @property
    def can_modify_code(self) -> bool:
        """True for write-phase stages; read/meta stages never mutate code."""
        return self.phase == "write"


@dataclass(frozen=True)
class WorkflowManifest:
    """A named, ordered sequence of stages (e.g. the vc-ship lifecycle)."""

    id: str
    name: str
    description: str
    stages: tuple[WorkflowStage, ...]
    entry_stage: str = ""
    human_controls: tuple[str, ...] = ()

    def stage(self, stage_id: str) -> WorkflowStage | None:
        """Look up a stage by id; ``None`` when the manifest has no such stage."""
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        return None

    @property
    def first_stage(self) -> WorkflowStage:
        """Resolve the manifest's entry point: ``entry_stage`` if set, else stages[0]."""
        if self.entry_stage:
            stage = self.stage(self.entry_stage)
            if stage is not None:
                return stage
        return self.stages[0]

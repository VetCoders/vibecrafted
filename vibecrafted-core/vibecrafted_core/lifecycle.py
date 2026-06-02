from __future__ import annotations

from enum import Enum


class RunState(str, Enum):
    CREATED = "created"
    BRIEF_RENDERED = "brief_rendered"
    PROCESS_SPAWNED = "process_spawned"
    PROMPT_DELIVERED = "prompt_delivered"
    FIRST_OUTPUT_SEEN = "first_output_seen"
    ACTIVE = "active"
    ARTIFACT_SEEN = "artifact_seen"
    REPORT_STARTED = "report_started"
    REPORT_VALIDATED = "report_validated"
    COMPLETED = "completed"
    POSTHOOK_RUNNING = "posthook_running"
    CLOSED = "closed"
    PROMPT_NOT_DELIVERED = "prompt_not_delivered"
    NO_FIRST_OUTPUT = "no_first_output"
    IDLE = "idle"
    STALLED = "stalled"
    PROCESS_DEAD = "process_dead"
    REPORT_MISSING = "report_missing"
    REPORT_INVALID = "report_invalid"
    CONTRACT_FAILED = "contract_failed"
    RECOVERY_REQUIRED = "recovery_required"
    FAILED = "failed"
    GHOST = "ghost"


class EventKind(str, Enum):
    LIFECYCLE = "lifecycle"
    ARTIFACT = "artifact"
    SUPERVISOR = "supervisor"
    TRIGGER = "trigger"


FINAL_STATES = frozenset(
    {
        RunState.CLOSED,
        RunState.COMPLETED,
        RunState.CONTRACT_FAILED,
        RunState.FAILED,
        RunState.GHOST,
        RunState.PROCESS_DEAD,
    }
)

NEGATIVE_STATES = frozenset(
    {
        RunState.PROMPT_NOT_DELIVERED,
        RunState.NO_FIRST_OUTPUT,
        RunState.IDLE,
        RunState.STALLED,
        RunState.PROCESS_DEAD,
        RunState.REPORT_MISSING,
        RunState.REPORT_INVALID,
        RunState.CONTRACT_FAILED,
        RunState.RECOVERY_REQUIRED,
        RunState.FAILED,
        RunState.GHOST,
    }
)

ALLOWED_TRANSITIONS = {
    RunState.CREATED: {
        RunState.BRIEF_RENDERED,
        RunState.PROCESS_SPAWNED,
        RunState.PROMPT_NOT_DELIVERED,
        RunState.FAILED,
    },
    RunState.BRIEF_RENDERED: {
        RunState.PROCESS_SPAWNED,
        RunState.PROMPT_DELIVERED,
        RunState.PROMPT_NOT_DELIVERED,
        RunState.FAILED,
    },
    RunState.PROCESS_SPAWNED: {
        RunState.PROMPT_DELIVERED,
        RunState.FIRST_OUTPUT_SEEN,
        RunState.ACTIVE,
        RunState.NO_FIRST_OUTPUT,
        RunState.PROCESS_DEAD,
        RunState.FAILED,
        RunState.COMPLETED,
    },
    RunState.PROMPT_DELIVERED: {
        RunState.FIRST_OUTPUT_SEEN,
        RunState.ACTIVE,
        RunState.NO_FIRST_OUTPUT,
        RunState.STALLED,
        RunState.PROCESS_DEAD,
        RunState.FAILED,
    },
    RunState.FIRST_OUTPUT_SEEN: {
        RunState.ACTIVE,
        RunState.ARTIFACT_SEEN,
        RunState.REPORT_STARTED,
        RunState.COMPLETED,
        RunState.PROCESS_DEAD,
        RunState.FAILED,
    },
    RunState.ACTIVE: {
        RunState.ARTIFACT_SEEN,
        RunState.REPORT_STARTED,
        RunState.IDLE,
        RunState.STALLED,
        RunState.COMPLETED,
        RunState.PROCESS_DEAD,
        RunState.FAILED,
    },
    RunState.ARTIFACT_SEEN: {
        RunState.REPORT_STARTED,
        RunState.REPORT_VALIDATED,
        RunState.REPORT_MISSING,
        RunState.REPORT_INVALID,
        RunState.COMPLETED,
        RunState.CONTRACT_FAILED,
    },
    RunState.REPORT_STARTED: {
        RunState.REPORT_VALIDATED,
        RunState.REPORT_INVALID,
        RunState.COMPLETED,
        RunState.CONTRACT_FAILED,
    },
    RunState.REPORT_VALIDATED: {
        RunState.COMPLETED,
        RunState.POSTHOOK_RUNNING,
        RunState.CLOSED,
    },
    RunState.COMPLETED: {
        RunState.POSTHOOK_RUNNING,
        RunState.CLOSED,
    },
    RunState.POSTHOOK_RUNNING: {
        RunState.CLOSED,
        RunState.RECOVERY_REQUIRED,
        RunState.FAILED,
    },
    RunState.PROMPT_NOT_DELIVERED: {RunState.RECOVERY_REQUIRED, RunState.FAILED},
    RunState.NO_FIRST_OUTPUT: {RunState.RECOVERY_REQUIRED, RunState.FAILED},
    RunState.IDLE: {RunState.ACTIVE, RunState.STALLED, RunState.RECOVERY_REQUIRED},
    RunState.STALLED: {RunState.RECOVERY_REQUIRED, RunState.FAILED},
    RunState.PROCESS_DEAD: {RunState.RECOVERY_REQUIRED, RunState.FAILED},
    RunState.REPORT_MISSING: {RunState.RECOVERY_REQUIRED, RunState.CONTRACT_FAILED},
    RunState.REPORT_INVALID: {RunState.RECOVERY_REQUIRED, RunState.CONTRACT_FAILED},
    RunState.CONTRACT_FAILED: {RunState.RECOVERY_REQUIRED},
    RunState.RECOVERY_REQUIRED: {RunState.FAILED},
    RunState.FAILED: set(),
    RunState.GHOST: set(),
    RunState.CLOSED: set(),
}


def coerce_state(value: RunState | str) -> RunState:
    if isinstance(value, RunState):
        return value
    return RunState(value)


def is_final_state(value: RunState | str) -> bool:
    return coerce_state(value) in FINAL_STATES


def is_negative_state(value: RunState | str) -> bool:
    return coerce_state(value) in NEGATIVE_STATES


def transition_allowed(current: RunState | str, next_state: RunState | str) -> bool:
    current_state = coerce_state(current)
    target_state = coerce_state(next_state)
    if current_state == target_state:
        return True
    return target_state in ALLOWED_TRANSITIONS[current_state]

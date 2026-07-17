"""Versioned, machine-readable workflow capability surface.

Clients (GUIs, MCP servers, downstream planners) need to know what a
``vibecrafted <workflow>`` invocation actually executes WITHOUT parsing help
text or user configs: runtime kind, execution target, how requested agents are
honored, where the research lane selection came from, and which configured
tokens were dropped as unsupported. This module serializes the already-typed
registry (:mod:`.workflows.registry`) plus the live research picking policy
(:mod:`.research_config`) into one stable JSON payload — it does not fork the
policy, it exposes it.

Read-only by contract: composing the payload launches nothing, mutates no
config, and writes nothing to the control plane.

Naming note: ``vibecrafted.capabilities.v1`` (see :mod:`.capabilities`) is the
foundation-binary probe schema (loct/aicx). This surface is a different
concern and carries its own schema id.
"""

from __future__ import annotations

from typing import Any

from .research_config import (
    DEFAULT_RESEARCH_AGENTS,
    SUPPORTED_RESEARCH_AGENTS,
    ResearchAgentSelection,
    resolve_research_runtime_config,
)
from .workflow import SUPPORTED_AGENTS
from .workflows import registry as workflow_registry

WORKFLOW_CAPABILITIES_SCHEMA = "vibecrafted.workflow_capabilities.v1"
WORKFLOW_CAPABILITIES_SCHEMA_VERSION = 1

# Mirror of build_launch_command's supervised_marbles substitution
# (`spec.agent if spec.agent != "swarm" else "codex"`): a swarm request on a
# single-agent supervised loop is honored as codex, and that truth belongs in
# the declared surface, not only in the launch path.
MARBLES_SWARM_FALLBACK_AGENT = "codex"


def _synthesizer_payload(selection: ResearchAgentSelection) -> dict[str, Any]:
    return {
        "agent": selection.synthesizer,
        "model": selection.synthesizer_model,
        "source": selection.synthesizer_source,
        # With no explicit synthesizer the runtime resumes the last surviving
        # research lane (see workflow_runtime._run_research_synthesis).
        "fallback": "last_surviving_lane",
    }


def _selection_payload(selection: ResearchAgentSelection) -> dict[str, Any]:
    return {
        "source": selection.source,
        "agents": list(selection.agents),
        "unsupported_configured": list(selection.ignored),
        "lane_models": dict(selection.lane_models or {}),
        "synthesizer": _synthesizer_payload(selection),
    }


def _workflow_record(
    definition: Any, selection: ResearchAgentSelection
) -> dict[str, Any]:
    is_research = definition.runtime_kind == "supervised_research"
    record: dict[str, Any] = {
        "name": definition.id,
        "aliases": list(definition.aliases),
        "cadence": definition.cadence,
        "lifecycle_order": definition.lifecycle_order,
        "can_modify_code": definition.can_modify_code,
        "input_policy": definition.input_policy,
        "runtime_kind": definition.runtime_kind,
        "execution_target": "swarm" if is_research else "single_agent",
        "default_agent": definition.default_agent,
        # Post-56975f0b truth: research rejects unknown positional agents at
        # launch (fail-closed) and honors known ones as synthesizer/lanes;
        # every other workflow runs the requested agent as-is.
        "requested_agent_policy": "fail_closed" if is_research else "honored",
        "supports_count": definition.supports_count,
        "supports_depth": definition.supports_depth,
        "terminal_layout": definition.terminal_layout,
        "tooling": list(definition.tooling),
    }
    if is_research:
        record["positional_agent_semantics"] = {
            "single": "synthesizer_override",
            "multiple": "lanes_with_first_as_synthesizer",
            "unsupported_token": "launch_rejected",
            "execution_agent": "swarm",
        }
        record["selection_source"] = selection.source
        record["effective_agents"] = list(selection.agents)
        record["unsupported_configured"] = list(selection.ignored)
        record["synthesizer"] = _synthesizer_payload(selection)
    if definition.runtime_kind == "supervised_marbles":
        record["swarm_agent_fallback"] = MARBLES_SWARM_FALLBACK_AGENT
    return record


def workflow_capabilities_payload() -> dict[str, Any]:
    """Describe every workflow's execution contract as one versioned payload.

    The research selection reflects the live env/config/manifest/builtin
    precedence at call time; unsupported configured tokens (e.g. a dead
    ``gemini`` still listed in an operator config) are reported in
    ``unsupported_configured`` instead of being silently dropped.
    """
    selection = resolve_research_runtime_config()
    return {
        "schema": WORKFLOW_CAPABILITIES_SCHEMA,
        "schema_version": WORKFLOW_CAPABILITIES_SCHEMA_VERSION,
        "agents": sorted(SUPPORTED_AGENTS),
        "research": {
            "supported_agents": list(SUPPORTED_RESEARCH_AGENTS),
            "default_agents": list(DEFAULT_RESEARCH_AGENTS),
            "selection": _selection_payload(selection),
        },
        "workflows": [
            _workflow_record(definition, selection)
            for definition in workflow_registry.workflow_lifecycle()
        ],
    }


def render_capabilities_lines(payload: dict[str, Any]) -> list[str]:
    """Human-readable projection of the capability payload for the bare CLI."""
    selection = payload["research"]["selection"]
    lines = [
        f"schema:   {payload['schema']} (v{payload['schema_version']})",
        f"agents:   {', '.join(payload['agents'])}",
        "research: "
        f"lanes={', '.join(selection['agents']) or 'none'} "
        f"source={selection['source']} "
        f"synthesizer={selection['synthesizer']['agent'] or 'last-survivor'}",
    ]
    if selection["unsupported_configured"]:
        lines.append(
            "research: unsupported configured tokens: "
            + ", ".join(selection["unsupported_configured"])
        )
    lines.append("")
    header = f"{'workflow':<12} {'runtime_kind':<20} {'target':<13} policy"
    lines.append(header)
    lines.append("-" * len(header))
    for record in payload["workflows"]:
        lines.append(
            f"{record['name']:<12} {record['runtime_kind']:<20} "
            f"{record['execution_target']:<13} {record['requested_agent_policy']}"
        )
    return lines

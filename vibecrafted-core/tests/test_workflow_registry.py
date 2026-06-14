from __future__ import annotations

from pathlib import Path

from vibecrafted_core import workflow
from vibecrafted_core.workflows import registry


def test_registry_keeps_supported_workflows_explicit() -> None:
    assert registry.workflow_definition("workflow") is not None
    assert registry.workflow_definition("justdo").id == "implement"
    assert registry.SUPPORTED_WORKFLOWS == workflow.SUPPORTED_WORKFLOWS


def test_registry_classifies_workflow_runtime_kinds() -> None:
    assert registry.workflow_runtime_kind("workflow") == "direct_agent"
    assert registry.workflow_runtime_kind("prune") == "direct_agent"
    assert registry.workflow_runtime_kind("research") == "supervised_research"
    assert registry.workflow_runtime_kind("marbles") == "supervised_marbles"
    assert registry.workflow_definition("research").terminal_layout == "research"


def test_registry_models_input_policy() -> None:
    implement = registry.workflow_definition("implement")
    prune = registry.workflow_definition("prune")
    marbles = registry.workflow_definition("marbles")

    assert implement is not None
    assert implement.requires_input is True
    assert prune is not None
    assert prune.can_use_default_prompt is True
    assert marbles is not None
    assert marbles.requires_input is False
    assert marbles.supports_count is True
    assert marbles.supports_depth is True


def test_registry_models_read_write_lifecycle() -> None:
    assert registry.workflow_definition("scaffold").cadence == "read"
    assert registry.workflow_definition("workflow").cadence == "write"
    assert registry.workflow_definition("marbles").cadence == "write"
    assert registry.workflow_definition("audit").cadence == "read"
    assert registry.workflow_definition("dou").cadence == "read"

    lifecycle = registry.workflow_lifecycle()
    names = [item.id for item in lifecycle]
    assert names.index("scaffold") < names.index("implement")
    assert names.index("review") < names.index("workflow")
    assert names.index("marbles") < names.index("audit")
    assert names.index("dou") < names.index("hydrate")
    assert registry.workflow_definition("workflow").tooling == (
        "vc-init",
        "vc-research",
        "vc-justdo",
    )


def test_prune_default_prompt_is_runtime_workflow_asset() -> None:
    prompt = registry.workflow_default_prompt("prune")

    assert "Repository health / prune discovery run." in prompt
    assert "Do not remove anything based on vibes." in prompt
    assert Path("runtime/workflows/prune/default_prompt.md").is_file()


def test_prune_default_prompt_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "prune"
    custom.mkdir()
    (custom / "default_prompt.md").write_text("custom prune prompt\n", encoding="utf-8")
    monkeypatch.setenv("VIBECRAFTED_WORKFLOWS_DIR", str(tmp_path))

    assert registry.workflow_default_prompt("prune") == "custom prune prompt"

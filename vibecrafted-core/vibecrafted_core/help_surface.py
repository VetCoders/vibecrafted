"""Canonical human-facing help for Vibecrafted workflow launchers.

The workflow registry owns execution semantics.  This module is the single
presentation layer for the Python entrypoint, installed ``vc-*`` wrappers, and
the shell deck when core is available.  Keeping the renderer here prevents the
three public entry paths from teaching three different products.
"""

from __future__ import annotations

from dataclasses import dataclass

from .package_resources import skills_path
from .workflows.registry import workflow_definition, workflow_manifest

AGENT_SELECTOR = "<claude|codex|agy|junie|grok>"


@dataclass(frozen=True)
class WorkflowHelp:
    summary: str
    flow: tuple[str, ...]
    examples: tuple[str, ...]
    notes: tuple[str, ...] = ()


WORKFLOW_HELP: dict[str, WorkflowHelp] = {
    "audit": WorkflowHelp(
        "READ-ONLY falsification of a completed plan or multi-task implementation.",
        (
            "recover the claimed scope",
            "build a requirements matrix",
            "prove or refute every claim",
            "issue a findings-first verdict",
        ),
        (
            'vibecrafted audit codex --prompt "Verify this completed plan against runtime truth"',
            "vc-audit claude --file /path/to/completed-plan.md",
        ),
    ),
    "decorate": WorkflowHelp(
        "Late-stage visual finishing and experience-coherence pass.",
        (
            "detect the existing design language",
            "audit system consistency",
            "finish the visible surface",
            "verify the real experience",
        ),
        (
            'vibecrafted decorate codex --prompt "Polish the release surface"',
            "vc-decorate claude --file /path/to/ui-brief.md",
        ),
    ),
    "delegate": WorkflowHelp(
        "Native in-session delegation for small, bounded implementation cuts.",
        (
            "capture the baseline",
            "cut independent ownership",
            "delegate with an exact handoff",
            "integrate and verify",
        ),
        (
            'vibecrafted delegate codex --prompt "Split these independent fixes"',
            "vc-delegate claude --file /path/to/delegation-brief.md",
        ),
    ),
    "dou": WorkflowHelp(
        "Definition of Undone audit across the entire product surface.",
        (
            "crawl the buyer-visible surface",
            "test install, trust, onboarding, and conversion",
            "collect unfinished gaps",
            "return an honest undone verdict",
        ),
        (
            'vibecrafted dou codex --prompt "Audit launch readiness"',
            "vc-dou claude --file /path/to/product-scope.md",
        ),
    ),
    "followup": WorkflowHelp(
        "Post-implementation direction audit for gaps, drift, regressions, and next leverage.",
        (
            "recover the implementation baseline",
            "audit trajectory and runtime truth",
            "name remaining gaps",
            "choose the next highest-leverage move",
        ),
        (
            'vibecrafted followup codex --prompt "Audit post-implementation direction"',
            "vc-followup claude --file /path/to/brief.md",
        ),
    ),
    "hydrate": WorkflowHelp(
        "Packaging and go-to-market hydration from audit findings to a usable product.",
        (
            "ingest DoU findings",
            "repair packaging, docs, and onboarding",
            "complete the go-to-market surface",
            "verify the user path",
        ),
        (
            'vibecrafted hydrate codex --prompt "Package this for first users"',
            "vc-hydrate claude --file /path/to/dou-report.md",
        ),
    ),
    "implement": WorkflowHelp(
        "Autonomous end-to-end implementation with followup and marbles built in.",
        (
            "vc-init and target the runtime owner",
            "implement the complete cut",
            "verify the real path",
            "run followup and converge if needed",
        ),
        (
            'vibecrafted implement codex --prompt "Ship the feature"',
            "vc-implement claude --file /path/to/brief.md",
        ),
        (
            f"Alias: vibecrafted justdo {AGENT_SELECTOR} [flags] / vc-justdo {AGENT_SELECTOR} [flags]",
        ),
    ),
    "intents": WorkflowHelp(
        "Plan-to-runtime truth audit across prior intent and present repository state.",
        (
            "recover planned intentions",
            "map current runtime ownership",
            "compare intent with landed code",
            "classify truth, drift, and missing work",
        ),
        (
            'vibecrafted intents codex --prompt "Which planned changes actually landed?"',
            "vc-intents claude --file /path/to/plan.md",
        ),
    ),
    "justdo": WorkflowHelp(
        "Convenient alias for vc-implement, kept for existing agents and scripts.",
        (
            "vc-init and target the runtime owner",
            "implement the complete cut",
            "verify the real path",
            "run followup and converge if needed",
        ),
        (
            'vibecrafted implement codex --prompt "Ship the feature"',
            'vibecrafted justdo codex --prompt "Ship the feature"',
            "vc-justdo claude --file /path/to/brief.md",
        ),
        (
            f"Alias: vibecrafted justdo {AGENT_SELECTOR} [flags] / vc-justdo {AGENT_SELECTOR} [flags]",
            "Runs the same workflow as implement; it is not a second implementation engine.",
        ),
    ),
    "marbles": WorkflowHelp(
        "Counterexample-guided convergence that keeps fixing what is still wrong.",
        (
            "map the remaining cracks",
            "L1 fix and verify",
            "L2…LN repeat against new evidence",
            "settle only when the surface holds",
        ),
        (
            "vibecrafted marbles codex --count 3 --depth 3",
            'vc-marbles claude --prompt "Loop until clean"',
            "vc-marbles resume marb-134707",
        ),
        (
            "Runtime shape: one dedicated orchestrator tab; --count N runs sequential L1…LN rounds inside it; no per-round child tabs.",
            "Controls: pause, stop, resume, session, inspect, delete, gc.",
        ),
    ),
    "ownership": WorkflowHelp(
        "Full-spectrum operational ownership across code, runtime, docs, packaging, and ship surface.",
        (
            "take the product baseline",
            "choose the target architecture",
            "drive implementation and stabilization",
            "finish the outward ship surface",
        ),
        (
            'vibecrafted ownership codex --prompt "Take this product from A to Z"',
            "vc-ownership claude --file /path/to/product-brief.md",
        ),
    ),
    "partner": WorkflowHelp(
        "Collaborative debugging, architecture triage, and shared steering with the operator.",
        (
            "map the live problem",
            "surface competing shapes",
            "steer the decision together",
            "carry the chosen cut forward",
        ),
        (
            'vibecrafted partner codex --prompt "Help me choose the right architecture"',
            "vc-partner claude --file /path/to/context.md",
        ),
    ),
    "paste": WorkflowHelp(
        "Turn clipboard or stdin content into a prepared Vibecrafted prompt.",
        (
            "read the supplied text",
            "bind it to a skill",
            "prepare the prompt",
            "print or launch",
        ),
        (
            "pbpaste | vibecrafted paste --skill workflow --dry-run",
            "vibecrafted paste --skill implement --print-prompt",
        ),
    ),
    "polarize": WorkflowHelp(
        "Post-marbles simplification that strips excess back to one defensible truth.",
        (
            "run the prism preflight",
            "name competing truths",
            "choose one product contract",
            "align code, docs, and regression proof",
        ),
        (
            'vibecrafted polarize codex --prompt "Choose one launch thesis after marbles"',
            "vc-polarize claude --file /path/to/marbles-report.md",
        ),
    ),
    "prune": WorkflowHelp(
        "Runtime and publish-cone cleanup with hard cuts and proof.",
        (
            "map runtime participation",
            "separate live truth from parked surfaces",
            "remove only proven dead weight",
            "verify install and publish cones",
        ),
        (
            'vibecrafted prune codex --prompt "Remove proven dead runtime surfaces"',
            "vc-prune claude --file /path/to/prune-scope.md",
        ),
    ),
    "release": WorkflowHelp(
        "Final outward ship stage: safe, visible, deployable, discoverable, and reversible.",
        (
            "prove repo and runtime readiness",
            "build and sign release artifacts",
            "publish or deploy",
            "verify and preserve rollback truth",
        ),
        (
            'vibecrafted release codex --prompt "Prepare the release"',
            "vc-release claude --file /path/to/release-brief.md",
        ),
    ),
    "research": WorkflowHelp(
        "Multi-agent research pass for ground truth before implementation.",
        (
            "co-define the question",
            "gather independent evidence",
            "compare disagreement",
            "synthesize one decision-ready report",
        ),
        (
            'vibecrafted research --prompt "Find the strongest runtime design"',
            "vc-research codex agy --file /path/to/research-plan.md",
        ),
    ),
    "review": WorkflowHelp(
        "Bounded PR, branch, commit-range, or artifact-pack review with findings-first output.",
        (
            "map the bounded change",
            "generate review evidence",
            "falsify behavior and assumptions",
            "report findings before summary",
        ),
        (
            'vibecrafted review codex --prompt "Review PR #14"',
            "vc-review claude --file /path/to/review-scope.md",
        ),
    ),
    "scaffold": WorkflowHelp(
        "Founder-first architecture planning from a vague idea to one executable plan.",
        (
            "capture native-language intent",
            "form the thesis",
            "define evidence obligations",
            "write one implementation plan",
        ),
        (
            'vibecrafted scaffold codex --prompt "Shape this product idea"',
            "vc-scaffold claude --file /path/to/idea.md",
        ),
    ),
    "workflow": WorkflowHelp(
        "Examine → Research → Implement pipeline for repo-impacting work.",
        (
            "examine with vc-init and Loctree",
            "research only where evidence is missing",
            "implement the complete cut",
            "verify and report",
        ),
        (
            'vibecrafted workflow codex --prompt "Examine and implement the fix"',
            "vc-workflow claude --file /path/to/brief.md",
        ),
    ),
}


def has_workflow_help(topic: str) -> bool:
    return topic.removeprefix("vc-") in WORKFLOW_HELP


def _skill_version(topic: str) -> str:
    try:
        path = skills_path() / f"vc-{topic}" / "SKILL.md"
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return ""
    for line in lines[1:40]:
        if line == "---":
            break
        if line.startswith("version:"):
            return line.partition(":")[2].strip().strip("\"'")
    return ""


def render_root_help(version: str) -> str:
    ship = workflow_manifest("vc-ship")
    cycle = " → ".join(stage.workflow for stage in ship.stages) if ship else ""
    return f"""
⚒  𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. {version} — release engine for AI-developed software
─────────────────────────────────────────

Usage:
  vibecrafted <command> [args]
  vibecrafted <skill> <agent> [-p <prompt> | -f <file>]

Commands:
  init [agent]         Orient an agent in this repo
  <skill> <agent>      Run a workflow with an agent
  resume <agent>       Continue a previous session
  status               Today's agent activity
  doctor               Installation health — pass/fail
  update               Update to the latest release
  help [topic|--all]   This deck · full reference

Ship cycle:
  {cycle}
  More workflows: vibecrafted help --all

Agents:  claude · codex · agy · junie · grok

Examples:
  vibecrafted init claude
  vibecrafted implement codex -p "Ship dark mode"
  vibecrafted marbles claude -p "Loop until clean"
""".lstrip("\n")


def _usage_lines(topic: str) -> list[str]:
    if topic == "research":
        return [
            "  vibecrafted research [agents...] [flags]",
            "  vc-research [agents...] [flags]",
        ]
    if topic == "paste":
        return ["  vibecrafted paste [--skill <workflow>] [flags]"]
    canonical = "implement" if topic == "justdo" else topic
    wrapper = "vc-implement" if topic == "justdo" else f"vc-{topic}"
    lines = [
        f"  vibecrafted {canonical} {AGENT_SELECTOR} [flags]",
        f"  {wrapper} {AGENT_SELECTOR} [flags]",
    ]
    if topic == "justdo":
        lines.append(f"  vibecrafted justdo {AGENT_SELECTOR} [flags]")
    if topic == "marbles":
        lines.extend(
            [
                "  vibecrafted marbles <pause|stop|resume|session|inspect|delete> [args]",
                "  vc-marbles <pause|stop|resume|session|inspect|delete> [args]",
                "  vibecrafted marbles gc [args] / vc-marbles gc [args]",
            ]
        )
    return lines


def _option_lines(topic: str) -> list[str]:
    if topic == "paste":
        return [
            "  --skill <workflow>              Workflow to prepare (default: workflow)",
            "  --root <path>                   Repository root",
            "  --print-prompt                  Print the prepared prompt",
            "  --dry-run                       Resolve without launching",
            "  --json                          Machine-readable output",
        ]
    lines = [
        "  -p, --prompt <text>            Inline prompt",
        "  -f, --file <path.md>           Input file as prompt context",
        "  --runtime <terminal|headless>  Execution surface",
        "  --root <path>                  Repository root",
        "  --model <name>                 Agent model override",
    ]
    definition = workflow_definition(topic)
    if definition and definition.supports_count:
        label = "Sequential convergence rounds" if topic == "marbles" else "Loop count"
        lines.append(f"  --count <n>                    {label}")
    if definition and definition.supports_depth:
        lines.append("  --depth <n>                    Plan crawl depth")
    if topic == "research":
        lines.extend(
            [
                "  --synthesizer <agent>         Synthesis agent override",
                "  --synthesizer-model <name>    Synthesis model override",
            ]
        )
    lines.append("  --json                          Machine-readable launch receipt")
    return lines


def render_workflow_help(topic: str) -> str:
    requested = topic.removeprefix("vc-")
    spec = WORKFLOW_HELP.get(requested)
    if spec is None:
        raise ValueError(f"Unsupported workflow help topic: {topic}")
    definition = workflow_definition(requested)
    version = _skill_version(requested)
    metadata: list[str] = []
    if version:
        metadata.append(f"version {version}")
    if definition:
        input_label = definition.input_policy.replace("_", " ")
        metadata.append(f"{definition.cadence.upper()} · input {input_label}")

    lines = [
        f"⚒  {requested}",
        "─────────────────────────────────────────",
    ]
    if metadata:
        lines.append(f"  {' · '.join(metadata)}")
    lines.extend([f"  {spec.summary}", "", "Usage:", *_usage_lines(requested)])
    if spec.notes:
        lines.extend(["", *[f"  {note}" for note in spec.notes]])
    lines.extend(
        [
            "",
            "Flow:",
            f"  {' → '.join(spec.flow)}",
            "",
            "Options:",
            *_option_lines(requested),
            "",
            "Examples:",
            *[f"  {example}" for example in spec.examples],
            "",
        ]
    )
    return "\n".join(lines)

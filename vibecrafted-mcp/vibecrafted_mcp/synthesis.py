"""Synthesis stubs for vibecrafted-mcp v0.1.

The full synthesis layer (live failure score, unmade decisions, unverified
claims, cross-machine drift) lands in v0.2. v0.1 ships the wiring and
deterministic, low-cost signals so callers can already reason about repo
risk without paying for the full synthesis pass.

Each helper here returns a small structured dict that the v0.1 cold-start
brief can splice in. None of these functions perform IO outside what the
core ground-truth call already did, so they are cheap to compose.
"""

from __future__ import annotations

from typing import Any


def live_failure_score(
    repo_state: dict[str, Any], doctor: dict[str, Any]
) -> dict[str, Any]:
    """Cheap heuristic risk score combining git dirt and doctor signals.

    Score is bounded in [0, 100]. Higher = more likely something is broken
    or in motion. The full v0.2 implementation will fold in marbles loop
    history and recent failed runs from the control plane.
    """
    score = 0
    reasons: list[str] = []

    status = repo_state.get("status") or {}
    unstaged = int(status.get("unstaged") or 0)
    staged = int(status.get("staged") or 0)
    untracked = int(status.get("untracked") or 0)
    behind = int(repo_state.get("behind") or 0)
    ahead = int(repo_state.get("ahead") or 0)
    stashes = int(repo_state.get("stashes") or 0)

    if unstaged or staged:
        delta = unstaged + staged
        score += min(20, delta * 2)
        reasons.append(f"living tree: {staged} staged / {unstaged} unstaged")
    if untracked:
        score += min(10, untracked)
        reasons.append(f"{untracked} untracked path(s)")
    if behind:
        score += min(20, behind * 4)
        reasons.append(f"behind upstream by {behind}")
    if ahead > 5:
        score += 10
        reasons.append(f"ahead by {ahead} (long unpushed branch)")
    if stashes:
        score += min(10, stashes * 5)
        reasons.append(f"{stashes} stash(es) parked")

    failures = int(doctor.get("failures") or 0)
    warnings = int(doctor.get("warnings") or 0)
    if failures:
        score += min(40, failures * 20)
        reasons.append(f"doctor: {failures} failure(s)")
    if warnings:
        score += min(15, warnings * 3)
        reasons.append(f"doctor: {warnings} warning(s)")

    score = max(0, min(100, score))
    band = "low" if score < 25 else "moderate" if score < 60 else "high"
    return {"score": score, "band": band, "reasons": reasons}


def unmade_decisions(repo_state: dict[str, Any]) -> list[str]:
    """Surface decisions the operator likely still owes the tree.

    v0.1 only fires on strong, deterministic signals from git ground
    truth. v0.2 will pull aicx intentions and cross-reference them with
    landed commits to detect plans that never shipped.
    """
    pending: list[str] = []
    status = repo_state.get("status") or {}
    if int(status.get("staged") or 0) and not int(status.get("unstaged") or 0):
        pending.append("staged changes are ready to commit")
    if int(repo_state.get("ahead") or 0) and not int(repo_state.get("behind") or 0):
        pending.append("local commits are ahead of upstream — consider push")
    if int(repo_state.get("behind") or 0):
        pending.append("upstream is ahead — pull/rebase before continuing")
    if int(repo_state.get("stashes") or 0):
        pending.append("stash entries are unresolved")
    return pending


def unverified_claims() -> list[str]:
    """Reminders the agent should treat as unproven on cold start.

    Static today; v0.2 will derive these from aicx outcomes that never
    received a verifying signal in subsequent sessions.
    """
    return [
        "perception layer (loctree) was not invoked yet — call mcp__loctree-mcp__context",
        "intentions layer (aicx) was not queried yet — call mcp__aicx-mcp__aicx_intents",
        "no quality gate has been run in this session",
    ]

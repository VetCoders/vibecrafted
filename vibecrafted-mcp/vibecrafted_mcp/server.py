"""FastMCP server exposing vibecrafted-core as the third sense (ground truth).

The server is intentionally a thin wrapper. v0.1 closes the cold-start
contract:

    mcp__loctree-mcp__context()        # perception (external)
    mcp__aicx-mcp__aicx_intents()      # intentions (external)
    mcp__vibecrafted__vc_repo_full()   # ground truth (this server)

It also surfaces a slim ``vc_init`` synthesis call so a single tool
invocation can hand an agent a usable cold-start brief without dragging
in heavyweight context. v0.2 will grow ``vc_init`` into the full
synthesis layer (live failure score, unmade decisions, unverified
claims, cross-machine drift) — v0.1 ships the wiring and stubs.
"""

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from vibecrafted_core import (
    control_plane as _control_plane,
    doctor as _doctor,
    git as _git,
)

from . import synthesis as _synthesis


SLIM_MAX_COMMITS = 5
SLIM_MAX_DOCTOR_FINDINGS = 8
SLIM_BUDGET_BYTES = 5 * 1024


@contextmanager
def _override_vibecrafted_home(home: str | None) -> Iterator[None]:
    """Temporarily set VIBECRAFTED_HOME for the wrapped call.

    vibecrafted-core resolves the operator home through the
    ``VIBECRAFTED_HOME`` env var, so this is the single supported way to
    point the control plane at an alternate home directory from the MCP
    surface.
    """
    if not home:
        yield
        return
    previous = os.environ.get("VIBECRAFTED_HOME")
    os.environ["VIBECRAFTED_HOME"] = str(Path(home).expanduser())
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("VIBECRAFTED_HOME", None)
        else:
            os.environ["VIBECRAFTED_HOME"] = previous


def _trim_recent_commits(state: dict[str, Any], limit: int) -> dict[str, Any]:
    commits = state.get("recent_commits") or []
    if len(commits) > limit:
        state = dict(state)
        state["recent_commits"] = commits[:limit]
    return state


def _doctor_payload(slim: bool) -> dict[str, Any]:
    """Return a doctor summary, degrading gracefully when unavailable.

    ``doctor_run`` reaches into ``scripts/vetcoders_install.py`` which is
    only present in a vibecrafted source checkout. When the package is
    consumed standalone (e.g. installed from PyPI in a foreign repo) the
    import fails — we surface that as a structured ``unavailable`` record
    rather than crashing the whole tool call.
    """
    try:
        findings = _doctor.doctor_run()
    except Exception as exc:  # noqa: BLE001 — bubbling reason to caller
        return {
            "ok": 0,
            "warnings": 0,
            "failures": 0,
            "healthy": True,
            "unavailable": True,
            "reason": f"{type(exc).__name__}: {exc}",
            "findings": [],
        }
    payload = _doctor.doctor_summary(findings)
    if slim:
        payload = dict(payload)
        payload["findings"] = payload["findings"][:SLIM_MAX_DOCTOR_FINDINGS]
    return payload


def _filter_events_by_run(
    events: list[dict[str, Any]], run_id: str, limit: int
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("run_id") or "") == run_id:
            matched.append(event)
            if len(matched) >= limit:
                break
    return matched


def _read_run_event_tail(
    run_id: str, home: str | None, limit: int = 50
) -> list[dict[str, Any]]:
    """Walk the global event stream and return events for a single run.

    The core helper exposes a global tail without a ``run_id`` filter, so
    we read a generous window and filter manually. The stream is
    append-only and small in practice (operator-scale, not telemetry-
    scale), so this stays cheap.
    """
    with _override_vibecrafted_home(home):
        stream = _control_plane.event_stream_path()
        if not stream.exists():
            return []
        try:
            text = stream.read_text(encoding="utf-8")
        except OSError:
            return []
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _filter_events_by_run(list(reversed(events)), run_id, limit)


def build_server() -> Any:
    """Construct and return the FastMCP server instance.

    Kept as a builder function so tests can instantiate a fresh server
    per case without relying on import-time global state.
    """
    from fastmcp import FastMCP

    mcp = FastMCP("vibecrafted")

    @mcp.tool
    def vc_repo_full(project: str = ".") -> dict[str, Any]:
        """Git ground truth for ``project``.

        Returns branch, ahead/behind vs upstream, dirt counts, stashes,
        worktrees, remotes, and the most recent commits. Read-only.

        Token budget: ~3-6k tokens for typical repos. Dominated by
        ``recent_commits``; trim with ``vc_init(slim=True)`` when calling
        as part of a cold-start brief.
        """
        return _git.repo_full(project)

    @mcp.tool
    def vc_doctor(project: str | None = None) -> dict[str, Any]:
        """Runtime health summary from the vibecrafted installer doctor.

        ``project`` is accepted for forward compatibility with v0.2
        (per-project doctor scopes); v0.1 always reports the operator-
        global state derived from ``$VIBECRAFTED_HOME``.

        Token budget: ~2-4k tokens. Returns ``unavailable=true`` when the
        installer module is not reachable from the current import path.
        """
        del project  # v0.1 ignores; preserved for forward compatibility
        return _doctor_payload(slim=False)

    @mcp.tool
    def vc_board_status(home: str | None = None) -> dict[str, Any]:
        """Operator control-plane snapshot: active runs, recent runs, events.

        ``home`` overrides ``$VIBECRAFTED_HOME`` for this call so an
        operator with multiple frameworks installed can probe a specific
        one without mutating their shell.

        Token budget: ~3-10k tokens depending on event tail and run
        count. The shape is shared with ``vc_init`` for consistency.
        """
        with _override_vibecrafted_home(home):
            return _control_plane.sync_state()

    @mcp.tool
    def vc_init(project: str = ".", slim: bool = True) -> dict[str, Any]:
        """Cold-start synthesis: 3 senses + v0.1 insight stubs.

        Composes git ground truth, doctor health, control-plane state,
        and synthesis hints (live failure score, unmade decisions,
        unverified claims). When ``slim=True`` (default) the response is
        kept under ~5KB by trimming recent commits and doctor findings.

        Use this as the first call when bootstrapping an agent; follow
        up with ``mcp__loctree-mcp__context`` and
        ``mcp__aicx-mcp__aicx_intents`` for the perception and
        intentions senses.

        Token budget: ~5KB slim (default), ~15-20KB full.
        """
        repo_state = _git.repo_full(project)
        doctor_state = _doctor_payload(slim=slim)
        with _override_vibecrafted_home(None):
            board = _control_plane.sync_state()
        if slim:
            repo_state = _trim_recent_commits(repo_state, SLIM_MAX_COMMITS)
            board = {
                "generated_at": board.get("generated_at"),
                "active_run_count": len(board.get("active_runs") or []),
                "recent_run_count": len(board.get("recent_runs") or []),
                "warnings": (board.get("warnings") or [])[:5],
            }
        payload: dict[str, Any] = {
            "ground_truth": repo_state,
            "doctor": doctor_state,
            "board": board,
            "perception_hint": "use mcp__loctree-mcp__context() for full perception",
            "intentions_hint": "use mcp__aicx-mcp__aicx_intents() for full intentions",
            "synthesis": {
                "live_failure_score": _synthesis.live_failure_score(
                    repo_state, doctor_state
                ),
                "unmade_decisions": _synthesis.unmade_decisions(repo_state),
                "unverified_claims": _synthesis.unverified_claims(),
            },
        }
        if slim:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            payload["_slim"] = {
                "bytes": len(encoded),
                "budget_bytes": SLIM_BUDGET_BYTES,
                "within_budget": len(encoded) <= SLIM_BUDGET_BYTES,
            }
        return payload

    @mcp.resource("vibecrafted://board/runs")
    def board_runs() -> dict[str, Any]:
        """Snapshot of the operator board: active + recent runs."""
        snapshot = _control_plane.sync_state()
        return {
            "generated_at": snapshot.get("generated_at"),
            "active_runs": snapshot.get("active_runs") or [],
            "recent_runs": snapshot.get("recent_runs") or [],
            "warnings": snapshot.get("warnings") or [],
        }

    @mcp.resource("vibecrafted://control-plane/events/{run_id}")
    def event_stream(run_id: str) -> list[dict[str, Any]]:
        """Last 50 events for a specific run from the operator stream."""
        return _read_run_event_tail(run_id, home=None, limit=50)

    return mcp


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``vibecrafted-mcp`` (stdio FastMCP server)."""
    parser = argparse.ArgumentParser(
        prog="vibecrafted-mcp",
        description=(
            "MCP server exposing vibecrafted ground truth (git), runtime "
            "doctor, and operator board state to agents. Speaks stdio by "
            "default — wire it into your agent's mcp.config."
        ),
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio",),
        help="Transport to expose the server on (only stdio in v0.1).",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the package version and exit.",
    )
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__

        print(__version__)
        return 0

    server = build_server()
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())

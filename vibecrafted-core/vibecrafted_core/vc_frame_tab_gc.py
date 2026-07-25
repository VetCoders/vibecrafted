"""Bounded, proof-gated cleanup for vc-frame run tabs.

Run artifacts are durable state.  A terminal tab is only a transient viewer and
must not become an unbounded second history store.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BUCKET_SESSIONS = ("Finalized runs", "Failed runs", "Needs attention")
TERMINAL_TRIAGE = {"finalized", "failed", "needs_attention"}
PROTECTED_TAB_NAMES = {"Start here", "Shell"}


@dataclass(frozen=True)
class TabRef:
    session: str
    tab_id: int
    name: str
    position: int
    active: bool
    focused_elsewhere: bool
    reason: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _default_runner(
    argv: Sequence[str], *, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            list(argv),
            124,
            stdout=str(exc.stdout or ""),
            stderr=f"timed out: {exc}",
        )


def _run(
    runner: Runner,
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    return runner(list(argv), env=env)


def list_tabs(
    binary: str,
    session: str,
    *,
    env: Mapping[str, str],
    runner: Runner = _default_runner,
) -> list[dict[str, Any]]:
    session_env = dict(env)
    session_env["VC_FRAME_SESSION_NAME"] = session
    proc = _run(
        runner,
        [binary, "action", "list-tabs", "--json"],
        env=session_env,
    )
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout)
    except (TypeError, json.JSONDecodeError):
        return []
    return (
        [tab for tab in payload if isinstance(tab, dict)]
        if isinstance(payload, list)
        else []
    )


def durable_run_ids(control_plane: Path) -> set[str]:
    """Return runs with both committed triage metadata and non-empty scrollback."""
    finished = control_plane / "finished_runs"
    durable: set[str] = set()
    if not finished.is_dir():
        return durable
    for run_dir in finished.iterdir():
        if not run_dir.is_dir():
            continue
        meta = run_dir / "meta.json"
        scrollback = run_dir / "scrollback.txt"
        try:
            if meta.stat().st_size > 0 and scrollback.stat().st_size > 0:
                durable.add(run_dir.name)
        except OSError:
            continue
    return durable


def terminal_origins(control_plane: Path, durable: set[str]) -> set[tuple[str, str]]:
    """Read exact source tabs whose successful triage receipt is durable."""
    runtime_runs = control_plane / "runtime_runs"
    origins: set[tuple[str, str]] = set()
    if not runtime_runs.is_dir():
        return origins
    for meta in runtime_runs.glob("*/meta.json"):
        try:
            payload = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        run_id = str(payload.get("run_id", "") or "").strip()
        session = str(payload.get("origin_session", "") or "").strip()
        tab = str(payload.get("origin_tab", "") or "").strip()
        triage = str(payload.get("triage", "") or "").strip()
        pending = bool(payload.get("triage_pending", False))
        if (
            run_id in durable
            and triage in TERMINAL_TRIAGE
            and not pending
            and session
            and tab == run_id
        ):
            origins.add((session, tab))
    return origins


def _tab_ref(session: str, tab: Mapping[str, Any], reason: str) -> TabRef | None:
    try:
        tab_id = int(tab["tab_id"])
        position = int(tab.get("position", 0))
    except (KeyError, TypeError, ValueError):
        return None
    name = str(tab.get("name", "") or "")
    return TabRef(
        session=session,
        tab_id=tab_id,
        name=name,
        position=position,
        active=bool(tab.get("active", False)),
        focused_elsewhere=bool(tab.get("other_focused_clients", [])),
        reason=reason,
    )


def plan_tab_cleanup(
    tabs_by_session: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    durable: set[str],
    origins: set[tuple[str, str]],
    bucket_tab_limit: int,
) -> list[TabRef]:
    """Choose only inactive, unobserved tabs backed by durable capture."""
    candidates: dict[tuple[str, int], TabRef] = {}

    for session, tab_name in origins:
        for tab in tabs_by_session.get(session, ()):
            if str(tab.get("name", "") or "") != tab_name:
                continue
            ref = _tab_ref(session, tab, "redundant-origin")
            if ref and not ref.active and not ref.focused_elsewhere:
                candidates[(session, ref.tab_id)] = ref

    limit = max(0, bucket_tab_limit)
    for session in BUCKET_SESSIONS:
        eligible: list[TabRef] = []
        for tab in tabs_by_session.get(session, ()):
            name = str(tab.get("name", "") or "")
            if name in PROTECTED_TAB_NAMES or name not in durable:
                continue
            ref = _tab_ref(session, tab, "durable-bucket-view")
            if ref:
                eligible.append(ref)
        eligible.sort(key=lambda item: item.position, reverse=True)
        keep_ids = {item.tab_id for item in eligible[:limit]}
        for ref in eligible:
            if (
                ref.tab_id not in keep_ids
                and not ref.active
                and not ref.focused_elsewhere
            ):
                candidates[(session, ref.tab_id)] = ref

    return sorted(candidates.values(), key=lambda item: (item.session, item.position))


def collect_cleanup(
    binary: str,
    control_plane: Path,
    *,
    bucket_tab_limit: int,
    env: Mapping[str, str],
    runner: Runner = _default_runner,
) -> list[TabRef]:
    durable = durable_run_ids(control_plane)
    origins = terminal_origins(control_plane, durable)
    sessions = set(BUCKET_SESSIONS)
    # Reconcile only the ambient operator session. Historical receipts can name
    # dead sessions, and asking vc-frame for tabs in a dead session may block
    # while it attempts a resurrection. Every live operator seat runs this GC
    # itself, so its own duplicates are still repaired deterministically.
    ambient_sessions = {
        str(env.get(name, "") or "").strip()
        for name in ("VC_FRAME_SESSION_NAME", "ZELLIJ_SESSION_NAME")
    }
    ambient_sessions.discard("")
    sessions.update(session for session, _ in origins if session in ambient_sessions)
    tabs = {
        session: list_tabs(binary, session, env=env, runner=runner)
        for session in sessions
    }
    return plan_tab_cleanup(
        tabs,
        durable=durable,
        origins=origins,
        bucket_tab_limit=bucket_tab_limit,
    )


def close_tab(
    binary: str,
    tab: TabRef,
    *,
    env: Mapping[str, str],
    runner: Runner = _default_runner,
) -> bool:
    session_env = dict(env)
    session_env["VC_FRAME_SESSION_NAME"] = tab.session
    proc = _run(
        runner,
        [binary, "action", "close-tab-by-id", str(tab.tab_id)],
        env=session_env,
    )
    if proc.returncode != 0:
        return False
    remaining = list_tabs(binary, tab.session, env=env, runner=runner)
    return all(item.get("tab_id") != tab.tab_id for item in remaining)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vc-frame-bin", required=True)
    parser.add_argument("--control-plane", type=Path, required=True)
    parser.add_argument("--bucket-tab-limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    env = dict(os.environ)
    candidates = collect_cleanup(
        args.vc_frame_bin,
        args.control_plane,
        bucket_tab_limit=args.bucket_tab_limit,
        env=env,
    )
    closed: list[TabRef] = []
    if args.apply:
        closed = [
            tab for tab in candidates if close_tab(args.vc_frame_bin, tab, env=env)
        ]

    if not args.quiet or (args.apply and len(closed) != len(candidates)):
        mode = "applied" if args.apply else "dry-run"
        print(
            f"vc_frame-tab-gc: {mode}; "
            f"candidates={len(candidates)} closed={len(closed)}"
        )
        for tab in candidates:
            state = "closed" if tab in closed else "candidate"
            print(f"  {state}: {tab.session}/{tab.name} id={tab.tab_id} ({tab.reason})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

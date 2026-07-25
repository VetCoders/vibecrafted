from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibecrafted_core.vc_frame_tab_gc import (
    BUCKET_SESSIONS,
    collect_cleanup,
    durable_run_ids,
    plan_tab_cleanup,
    terminal_origins,
)


def tab(tab_id: int, name: str, position: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tab_id": tab_id,
        "name": name,
        "position": position,
        "active": False,
        "other_focused_clients": [],
    }
    payload.update(overrides)
    return payload


def durable_run(control_plane: Path, run_id: str, **receipt: Any) -> None:
    finished = control_plane / "finished_runs" / run_id
    finished.mkdir(parents=True)
    (finished / "meta.json").write_text("{}\n", encoding="utf-8")
    (finished / "scrollback.txt").write_text("real output\n", encoding="utf-8")

    runtime = control_plane / "runtime_runs" / run_id
    runtime.mkdir(parents=True)
    payload = {
        "run_id": run_id,
        "origin_session": "vibecrafted",
        "origin_tab": run_id,
        "triage": "needs_attention",
        "triage_pending": False,
        **receipt,
    }
    (runtime / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


def test_durable_origins_require_capture_and_confirmed_receipt(tmp_path: Path) -> None:
    cp = tmp_path / "control_plane"
    durable_run(cp, "impl-good")
    durable_run(cp, "impl-pending", triage_pending=True)
    (cp / "finished_runs" / "impl-empty").mkdir()
    (cp / "finished_runs" / "impl-empty" / "meta.json").write_text("{}")
    (cp / "finished_runs" / "impl-empty" / "scrollback.txt").write_text("")

    durable = durable_run_ids(cp)

    assert durable == {"impl-good", "impl-pending"}
    assert terminal_origins(cp, durable) == {("vibecrafted", "impl-good")}


def test_plan_closes_redundant_origin_and_all_durable_bucket_views() -> None:
    run_id = "impl-260725-120000-00000"
    tabs = {
        "vibecrafted": [
            tab(1, "Shell", 0),
            tab(7, run_id, 1),
            tab(8, "work-live", 2, active=True),
        ],
        "Needs attention": [
            tab(0, "Start here", 0),
            tab(1, "Shell", 1),
            tab(4, run_id, 2),
            tab(5, "not-durable", 3),
        ],
    }

    plan = plan_tab_cleanup(
        tabs,
        durable={run_id},
        origins={("vibecrafted", run_id)},
        bucket_tab_limit=0,
    )

    assert [(item.session, item.tab_id, item.reason) for item in plan] == [
        ("Needs attention", 4, "durable-bucket-view"),
        ("vibecrafted", 7, "redundant-origin"),
    ]


def test_plan_never_closes_active_or_other_client_tabs() -> None:
    run_id = "impl-260725-120000-00000"
    tabs = {
        "vibecrafted": [tab(7, run_id, 1, active=True)],
        "Needs attention": [
            tab(4, run_id, 2, other_focused_clients=[9]),
        ],
    }

    assert (
        plan_tab_cleanup(
            tabs,
            durable={run_id},
            origins={("vibecrafted", run_id)},
            bucket_tab_limit=0,
        )
        == []
    )


def test_bucket_limit_keeps_newest_durable_view() -> None:
    tabs = {
        "Finalized runs": [
            tab(2, "impl-old", 2),
            tab(3, "impl-new", 3),
        ]
    }
    plan = plan_tab_cleanup(
        tabs,
        durable={"impl-old", "impl-new"},
        origins=set(),
        bucket_tab_limit=1,
    )
    assert [(item.name, item.tab_id) for item in plan] == [("impl-old", 2)]


def test_collect_uses_exact_session_environment(tmp_path: Path) -> None:
    cp = tmp_path / "control_plane"
    durable_run(cp, "impl-good")
    seen_sessions: list[str] = []

    class Proc:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def runner(argv: list[str], *, env: dict[str, str]) -> Proc:
        assert argv[-3:] == ["list-tabs", "--json"] or argv[-2:] == [
            "list-tabs",
            "--json",
        ]
        seen_sessions.append(env["VC_FRAME_SESSION_NAME"])
        return Proc()

    assert (
        collect_cleanup(
            "/fake/vc-frame",
            cp,
            bucket_tab_limit=0,
            env={"VC_FRAME_SESSION_NAME": "vibecrafted"},
            runner=runner,
        )
        == []
    )
    assert set(seen_sessions) == {*BUCKET_SESSIONS, "vibecrafted"}

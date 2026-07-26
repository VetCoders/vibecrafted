from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import vibecrafted_core.guardian as guardian_module
from vibecrafted_core.guardian import (
    BoundedBackoff,
    GuardianAlreadyRunning,
    GuardianNotification,
    GuardianProtocolError,
    GuardianRecoveryAdapter,
    GuardianState,
    GuardianWorker,
    ReconcileDecision,
    SettlementRevision,
    SSEFrame,
    SSEHeartbeat,
    iter_sse,
    notification_for,
    notify_operator,
    parse_settlement_revision,
    single_instance_lock,
)


class FakeResponse:
    def __init__(
        self,
        lines: Iterable[str],
        *,
        content_type: str = "text/event-stream; charset=utf-8",
        status: int = 200,
    ) -> None:
        self._lines = [line.encode("utf-8") for line in lines]
        self.headers = {"Content-Type": content_type}
        self.status = status
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._lines)

    def close(self) -> None:
        self.closed = True


class FakeJSONResponse:
    def __init__(
        self,
        payload: object,
        *,
        content_type: str = "application/json",
        status: int = 200,
    ) -> None:
        self._body = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )
        self.headers = {"Content-Type": content_type}
        self.status = status
        self.closed = False

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]

    def close(self) -> None:
        self.closed = True


class QueueOpener:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def __call__(self, request: Any, *, timeout: float) -> Any:
        self.calls.append(
            (
                request.full_url,
                {key.lower(): value for key, value in request.header_items()},
                timeout,
            )
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, (FakeResponse, FakeJSONResponse))
        return outcome


def settlement_data(
    run_id: str,
    revision: int,
    tui: str,
    *,
    verdict: str | None = None,
    reason: str = "proof checked",
    source: str = "await",
) -> str:
    verdict_by_tui = {
        "f": "finalized",
        "n": "needs_attention",
        "x": "failed",
    }
    return json.dumps(
        {
            "ts": "2026-07-26T06:00:00+00:00",
            "run_id": run_id,
            "kind": "settlement.changed",
            "message": f"settlement revision {revision}",
            "payload": {
                "schema": "vibecrafted.settlement-event.v1",
                "run_id": run_id,
                "previous": None,
                "current": {
                    "verdict": verdict or verdict_by_tui[tui],
                    "tui": tui,
                },
                "reason": reason,
                "source": source,
                "settled_at": "2026-07-26T06:00:00+00:00",
                "claim_digest": "claim-123",
                "waived": False,
                "revision": revision,
            },
        },
        separators=(",", ":"),
    )


def frame(cursor: int, data: str) -> list[str]:
    return [f"id: {cursor}\n", f"data: {data}\n", "\n"]


def heartbeat() -> list[str]:
    return [": ping\n", "\n"]


def settlement_event(
    run_id: str,
    revision: int,
    tui: str,
    *,
    source: str = "await",
) -> SettlementRevision:
    event = parse_settlement_revision(
        settlement_data(run_id, revision, tui, source=source)
    )
    assert event is not None
    return event


def resumable_projection(
    event: SettlementRevision,
    root: Path,
) -> dict[str, object]:
    return {
        "run_id": event.run_id,
        "state": "recovery_required",
        "agent": "codex",
        "skill": "implement",
        "root": str(root),
        "exit_code": -9,
        "liveness": "terminal",
        "worker_alive": False,
        "recovery_required": True,
        "stop_reason": "signal_exit",
        "attempt": 0,
        "settlement_tui": event.tui,
        "settlement_verdict": event.verdict,
        "settlement_source": event.source,
        "settlement_revision": event.revision,
        "commit_sha": "abc123",
        "controls": {
            "native_resume_candidate": {
                "agent": "codex",
                "agent_session_id": "019-native-session",
            }
        },
    }


def test_iter_sse_only_emits_complete_numeric_frames_and_ping() -> None:
    items = list(
        iter_sse(
            [
                "id: nope\n",
                "data: ignored\n",
                "\n",
                "id: 12\n",
                "data: first\n",
                "data: second\n",
                "\n",
                ": ping\n",
                "\n",
                "id: 13\n",
                "data: incomplete\n",
            ]
        )
    )

    assert items == [
        SSEFrame(cursor=12, data="first\nsecond"),
        SSEHeartbeat(),
    ]


def test_parse_settlement_revision_rejects_schema_or_tui_contradiction() -> None:
    valid = settlement_data("run-a", 3, "n")
    event = parse_settlement_revision(valid)
    assert event == SettlementRevision(
        run_id="run-a",
        revision=3,
        verdict="needs_attention",
        tui="n",
        reason="proof checked",
        source="await",
        settled_at="2026-07-26T06:00:00+00:00",
    )

    contradiction = settlement_data("run-a", 3, "n", verdict="failed")
    assert parse_settlement_revision(contradiction) is None

    wrong_schema = json.loads(valid)
    wrong_schema["payload"]["schema"] = "vibecrafted.settlement-event.v0"
    assert parse_settlement_revision(json.dumps(wrong_schema)) is None


def test_first_heartbeat_opens_gate_then_f_n_x_are_exactly_once(
    tmp_path: Path,
) -> None:
    opener = QueueOpener(
        FakeResponse(
            [
                *frame(100, settlement_data("historical", 1, "x")),
                *heartbeat(),
            ]
        ),
        FakeResponse(
            [
                *frame(100, settlement_data("historical", 1, "x")),
                *frame(200, settlement_data("run-f", 1, "f")),
                *frame(300, settlement_data("run-n", 1, "n")),
                *frame(301, settlement_data("run-n", 1, "n")),
                *frame(400, settlement_data("run-x", 1, "x")),
            ]
        ),
    )
    notifications: list[GuardianNotification] = []
    reconciled: list[tuple[str, int]] = []
    resumed: list[tuple[str, int]] = []
    resume_keys: list[str] = []

    def reconcile(event: SettlementRevision) -> ReconcileDecision:
        reconciled.append(event.key)
        return ReconcileDecision(request_resume=True, reason="test request")

    def resume(event: SettlementRevision, key: str) -> bool:
        resumed.append(event.key)
        resume_keys.append(key)
        return True

    state_path = tmp_path / "guardian" / "state.json"
    state = GuardianState.load(state_path)
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=notifications.append,
        reconciler=reconcile,
        resume=resume,
        opener=opener,
    )

    baseline = worker.consume_connection()
    active = worker.consume_connection()

    assert baseline.frames == 1
    assert baseline.heartbeats == 1
    assert baseline.claimed == 1
    assert baseline.completed_baseline is True
    assert active.frames == 5
    assert active.claimed == 3
    assert active.completed_actions == 3
    assert [(notice.event.run_id, notice.severity) for notice in notifications] == [
        ("run-f", "info"),
        ("run-n", "warning"),
        ("run-x", "critical"),
    ]
    assert reconciled == [("run-f", 1), ("run-n", 1), ("run-x", 1)]
    assert resumed == [("run-n", 1)]
    assert resume_keys == ["settlement:run-n:1"]
    assert state.cursor == 400
    assert state.baseline_complete is True

    reloaded = GuardianState.load(state_path)
    assert reloaded.cursor == 400
    assert reloaded.baseline_complete is True
    assert set(reloaded.processed) == {
        ("historical", 1),
        ("run-f", 1),
        ("run-n", 1),
        ("run-x", 1),
    }
    url, headers, timeout = opener.calls[0]
    assert url == "http://127.0.0.1:3024/api/control/events?since=0"
    assert headers["last-event-id"] == "0"
    assert headers["accept"] == "text/event-stream"
    assert timeout == 30.0
    assert opener.calls[1][0].endswith("/api/control/events?since=0")


def test_disconnect_before_first_ping_keeps_suppressing_after_reconnect(
    tmp_path: Path,
) -> None:
    opener = QueueOpener(
        FakeResponse(frame(90, settlement_data("old", 1, "n"))),
        FakeResponse(heartbeat()),
        FakeResponse(
            [
                *frame(90, settlement_data("old", 1, "n")),
                *frame(180, settlement_data("new", 1, "n")),
            ]
        ),
    )
    notifications: list[GuardianNotification] = []
    state = GuardianState.load(tmp_path / "state.json")
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=notifications.append,
        opener=opener,
    )

    worker.consume_connection()
    assert state.baseline_complete is False
    assert notifications == []

    worker.consume_connection()
    assert state.baseline_complete is True
    assert notifications == []

    worker.consume_connection()
    assert [notice.event.run_id for notice in notifications] == ["new"]
    assert opener.calls[1][0].endswith("/api/control/events?since=90")
    assert opener.calls[1][1]["last-event-id"] == "90"
    assert opener.calls[2][0].endswith("/api/control/events?since=0")


def test_rotation_accepts_lower_cursor_but_keeps_revision_dedupe(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state = GuardianState(
        path=state_path,
        cursor=999,
        baseline_complete=True,
        processed=[("run-a", 1)],
    )
    state.persist()
    state = GuardianState.load(state_path)
    opener = QueueOpener(
        FakeResponse(
            [
                *frame(120, settlement_data("new-prefix", 1, "n")),
                *frame(240, settlement_data("run-a", 1, "n")),
                *frame(1_200, settlement_data("run-a", 2, "f")),
            ]
        )
    )
    notifications: list[GuardianNotification] = []
    reconciled: list[tuple[str, int]] = []

    def reconcile(event: SettlementRevision) -> ReconcileDecision:
        reconciled.append(event.key)
        return ReconcileDecision()

    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=notifications.append,
        reconciler=reconcile,
        opener=opener,
    )

    worker.consume_connection()

    assert state.cursor == 1_200
    assert [notice.event.key for notice in notifications] == [
        ("new-prefix", 1),
        ("run-a", 2),
    ]
    assert reconciled == [("new-prefix", 1), ("run-a", 2)]
    assert opener.calls[0][0].endswith("/api/control/events?since=0")
    assert GuardianState.load(state_path).cursor == 1_200


def test_non_settlement_and_malformed_frames_only_advance_cursor(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    non_settlement = json.dumps({"run_id": "run-a", "kind": "progress", "payload": {}})
    opener = QueueOpener(
        FakeResponse(
            [
                *frame(10, non_settlement),
                *frame(20, "{not-json"),
                *frame(30, settlement_data("run-a", 1, "n", verdict="failed")),
            ]
        )
    )
    notifications: list[GuardianNotification] = []
    state = GuardianState(
        path=tmp_path / "state.json",
        baseline_complete=True,
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=notifications.append,
        opener=opener,
    )

    with caplog.at_level(logging.CRITICAL, logger="vibecrafted_core.guardian"):
        stats = worker.consume_connection()

    assert stats.frames == 3
    assert stats.claimed == 0
    assert state.cursor == 30
    assert notifications == []
    assert "quarantined invalid settlement frame" in caplog.text
    dead_letters = list((state.path.parent / "dead_letters").glob("*.json"))
    assert len(dead_letters) == 1
    dead_letter = json.loads(dead_letters[0].read_text(encoding="utf-8"))
    assert dead_letter["schema"] == "vibecrafted.guardian-dead-letter.v1"
    assert dead_letter["sse_cursor"] == 30
    assert dead_letter["reason"] == "invalid settlement.changed contract"


def test_processed_history_is_unbounded_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = GuardianState(path=path)

    assert state.suppress(10, ("a", 1)) is True
    assert state.suppress(20, ("b", 1)) is True
    assert state.suppress(30, ("c", 1)) is True
    assert state.processed == [("a", 1), ("b", 1), ("c", 1)]

    loaded = GuardianState.load(path)
    assert loaded.cursor == 30
    assert loaded.processed == [("a", 1), ("b", 1), ("c", 1)]


def test_failed_claim_persist_does_not_poison_in_memory_dedupe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GuardianState(
        path=tmp_path / "state.json",
        baseline_complete=True,
    )
    event = parse_settlement_revision(settlement_data("run-loss", 1, "n"))
    assert event is not None

    def fail_write(_path: Path, _payload: Mapping[str, object]) -> Path:
        raise OSError("disk unavailable")

    with monkeypatch.context() as scoped:
        scoped.setattr(guardian_module, "atomic_write_json", fail_write)
        with pytest.raises(OSError, match="disk unavailable"):
            state.claim(10, event)

    assert state.cursor == 0
    assert state.processed == []
    assert state.pending == {}
    assert state.claim(10, event) is True
    assert state.pending == {("run-loss", 1): event}


def test_pending_action_survives_kill_window_and_is_recovered_once(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    event = parse_settlement_revision(settlement_data("run-pending", 2, "n"))
    assert event is not None
    before_crash = GuardianState(path=path, baseline_complete=True)
    assert before_crash.claim(44, event) is True

    recovered = GuardianState.load(path)
    notifications: list[GuardianNotification] = []
    reconciled: list[str] = []

    def reconcile(item: SettlementRevision) -> ReconcileDecision:
        reconciled.append(item.idempotency_key)
        return ReconcileDecision()

    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=recovered,
        notifier=notifications.append,
        reconciler=reconcile,
        opener=QueueOpener(FakeResponse([])),
    )

    worker.consume_connection()

    assert [item.event.key for item in notifications] == [("run-pending", 2)]
    assert reconciled == ["settlement:run-pending:2"]
    completed = GuardianState.load(path)
    assert completed.pending == {}
    assert completed.processed == [("run-pending", 2)]

    duplicate_notifications: list[GuardianNotification] = []
    duplicate_worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=completed,
        notifier=duplicate_notifications.append,
        opener=QueueOpener(
            FakeResponse(frame(88, settlement_data("run-pending", 2, "n")))
        ),
    )
    duplicate_worker.consume_connection()
    assert duplicate_notifications == []


def test_resume_failure_stays_pending_and_retries_with_same_key(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    state = GuardianState(path=path, baseline_complete=True)
    opener = QueueOpener(
        FakeResponse(frame(50, settlement_data("run-retry", 1, "n"))),
        FakeResponse([]),
    )
    resume_keys: list[str] = []

    def resume(_event: SettlementRevision, key: str) -> object:
        resume_keys.append(key)
        if len(resume_keys) == 1:
            raise OSError("transient resume failure")
        return {"accepted": True, "idempotency_key": key}

    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=lambda _notification: None,
        reconciler=lambda _event: ReconcileDecision(request_resume=True),
        resume=resume,
        opener=opener,
    )

    failed = worker.consume_connection()
    assert failed.action_failures == 1
    assert state.pending.keys() == {("run-retry", 1)}
    assert state.processed == []

    recovered = worker.consume_connection()
    assert recovered.completed_actions == 1
    assert recovered.action_failures == 0
    assert resume_keys == [
        "settlement:run-retry:1",
        "settlement:run-retry:1",
    ]
    assert state.pending == {}
    assert state.processed == [("run-retry", 1)]


def test_recovery_adapter_accepts_once_and_deduplicates_replayed_revision(
    tmp_path: Path,
) -> None:
    event = settlement_event("run-native", 7, "n", source="trust")
    projection_opener = QueueOpener(
        FakeJSONResponse(resumable_projection(event, tmp_path))
    )
    guard_calls: list[dict[str, object]] = []
    resume_calls: list[dict[str, object]] = []

    def enforce_guard(**kwargs: object) -> object:
        guard_calls.append(dict(kwargs))
        return SimpleNamespace(allowed=True)

    def native_resume(
        run_id: str,
        source_dir: str | Path,
        *,
        expected_agent: str,
        idempotency_key: str,
    ) -> Mapping[str, object]:
        resume_calls.append(
            {
                "run_id": run_id,
                "source_dir": source_dir,
                "expected_agent": expected_agent,
                "idempotency_key": idempotency_key,
            }
        )
        return {
            "accepted": True,
            "deduplicated": True,
            "idempotency_key": idempotency_key,
        }

    recovery = GuardianRecoveryAdapter(
        server_url="http://127.0.0.1:3024",
        opener=projection_opener,
        guard_enforcer=enforce_guard,
        native_resumer=native_resume,
    )
    state = GuardianState(
        path=tmp_path / "guardian-state.json",
        baseline_complete=True,
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=lambda _notification: None,
        reconciler=recovery.reconcile,
        resume=recovery.resume,
        opener=QueueOpener(
            FakeResponse(
                [
                    *frame(
                        70,
                        settlement_data(
                            event.run_id,
                            event.revision,
                            event.tui,
                            source=event.source,
                        ),
                    ),
                    *frame(
                        71,
                        settlement_data(
                            event.run_id,
                            event.revision,
                            event.tui,
                            source=event.source,
                        ),
                    ),
                ]
            )
        ),
    )

    stats = worker.consume_connection()

    assert stats.frames == 2
    assert stats.claimed == 1
    assert stats.completed_actions == 1
    assert projection_opener.calls == [
        (
            "http://127.0.0.1:3024/api/control/runs/run-native",
            {"accept": "application/json", "cache-control": "no-cache"},
            5.0,
        )
    ]
    assert guard_calls == [
        {
            "repo": tmp_path,
            "sha": "abc123",
            "skill": "implement",
        }
    ]
    assert resume_calls == [
        {
            "run_id": "run-native",
            "source_dir": tmp_path,
            "expected_agent": "codex",
            "idempotency_key": "settlement:run-native:7",
        }
    ]
    assert state.pending == {}
    assert state.processed == [("run-native", 7)]


@pytest.mark.parametrize(
    ("tui", "overrides", "reason"),
    [
        ("n", {"settlement_revision": 8}, "stale_or_mismatched_settlement"),
        (
            "n",
            {"settlement_verdict": "failed"},
            "stale_or_mismatched_settlement",
        ),
        ("n", {"settlement_tui": "x"}, "stale_or_mismatched_settlement"),
        ("n", {"worker_alive": True}, "worker_not_confirmed_dead"),
        ("n", {"recovery_required": False}, "recovery_not_required"),
        ("n", {"stop_reason": "manual_stop"}, "manual_stop_or_cancel"),
        ("x", {}, "settlement_x_not_resumable"),
        ("f", {}, "settlement_f_not_resumable"),
        (
            "n",
            {"controls": {"native_resume_candidate": None}},
            "native_resume_candidate_missing",
        ),
        (
            "n",
            {
                "controls": {
                    "native_resume_candidate": {
                        "agent": "codex",
                        "agent_session_id": "unknown",
                    }
                }
            },
            "native_resume_identity_missing",
        ),
        ("n", {"attempt": 1}, "automatic_attempt_budget_exhausted"),
        (
            "n",
            {"state": "running", "liveness": "active", "exit_code": None},
            "run_not_terminal",
        ),
    ],
    ids=[
        "stale-revision",
        "verdict-mismatch",
        "tui-mismatch",
        "worker-live",
        "recovery-false",
        "manual-stop",
        "x-critical",
        "f-finalized",
        "candidate-missing",
        "candidate-identity-missing",
        "attempt-budget",
        "non-terminal",
    ],
)
def test_recovery_adapter_blocks_unsafe_projection(
    tmp_path: Path,
    tui: str,
    overrides: dict[str, object],
    reason: str,
) -> None:
    event = settlement_event(f"run-{tui}", 7, tui, source="trust")
    projection = resumable_projection(event, tmp_path)
    projection.update(overrides)
    opener = QueueOpener(FakeJSONResponse(projection))

    def must_not_guard(**_kwargs: object) -> object:
        raise AssertionError("vc-guard must not run before projection policy passes")

    recovery = GuardianRecoveryAdapter(
        server_url="http://127.0.0.1:3024",
        opener=opener,
        guard_enforcer=must_not_guard,
        native_resumer=lambda *_args, **_kwargs: {
            "accepted": True,
        },
    )

    decision = recovery.reconcile(event)

    assert decision == ReconcileDecision(request_resume=False, reason=reason)
    assert len(opener.calls) == 1


def test_recovery_adapter_never_resumes_auto_needs_attention(
    tmp_path: Path,
) -> None:
    event = settlement_event("run-auto", 1, "n", source="auto")
    recovery = GuardianRecoveryAdapter(
        server_url="http://127.0.0.1:3024",
        opener=QueueOpener(FakeJSONResponse(resumable_projection(event, tmp_path))),
        guard_enforcer=lambda **_kwargs: pytest.fail(
            "vc-guard must not authorize an automatic settlement"
        ),
        native_resumer=lambda *_args, **_kwargs: pytest.fail(
            "native resume must not run for an automatic settlement"
        ),
    )

    assert recovery.reconcile(event) == ReconcileDecision(
        request_resume=False,
        reason="vc_trust_authority_missing",
    )


def test_recovery_adapter_obeys_vc_guard_block(tmp_path: Path) -> None:
    event = settlement_event("run-guarded", 2, "n", source="trust")
    recovery = GuardianRecoveryAdapter(
        server_url="http://127.0.0.1:3024",
        opener=QueueOpener(FakeJSONResponse(resumable_projection(event, tmp_path))),
        guard_enforcer=lambda **_kwargs: SimpleNamespace(allowed=False),
        native_resumer=lambda *_args, **_kwargs: pytest.fail(
            "native resume must not run after a vc-guard block"
        ),
    )

    assert recovery.reconcile(event) == ReconcileDecision(
        request_resume=False,
        reason="vc_guard_blocked",
    )


@pytest.mark.parametrize("failure_stage", ["http", "guard"])
def test_recovery_truth_or_guard_error_keeps_event_pending(
    tmp_path: Path,
    failure_stage: str,
) -> None:
    event = settlement_event(
        f"run-{failure_stage}-error",
        1,
        "n",
        source="trust",
    )

    def guard_enforcer(**_kwargs: object) -> object:
        if failure_stage == "guard":
            raise OSError("trust journal unavailable")
        return SimpleNamespace(allowed=True)

    if failure_stage == "http":
        projection_opener = QueueOpener(urllib.error.URLError("projection down"))
    else:
        projection_opener = QueueOpener(
            FakeJSONResponse(resumable_projection(event, tmp_path))
        )

    recovery = GuardianRecoveryAdapter(
        server_url="http://127.0.0.1:3024",
        opener=projection_opener,
        guard_enforcer=guard_enforcer,
        native_resumer=lambda *_args, **_kwargs: {"accepted": True},
    )
    state = GuardianState(
        path=tmp_path / "guardian-state.json",
        baseline_complete=True,
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=state,
        notifier=lambda _notification: None,
        reconciler=recovery.reconcile,
        resume=recovery.resume,
        opener=QueueOpener(
            FakeResponse(
                frame(
                    50,
                    settlement_data(event.run_id, 1, "n", source=event.source),
                )
            )
        ),
    )

    stats = worker.consume_connection()

    assert stats.action_failures == 1
    assert state.pending == {event.key: event}
    assert state.processed == []


def test_reconnect_backoff_is_nonzero_and_bounded(tmp_path: Path) -> None:
    opener = QueueOpener(
        urllib.error.URLError("down-1"),
        urllib.error.URLError("down-2"),
        urllib.error.URLError("down-3"),
        urllib.error.URLError("down-4"),
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(path=tmp_path / "state.json"),
        opener=opener,
    )
    delays: list[float] = []

    worker.run_forever(
        backoff=BoundedBackoff(initial=0.1, maximum=0.2),
        sleep=delays.append,
        max_connections=4,
    )

    assert delays == [0.1, 0.2, 0.2]
    assert len(opener.calls) == 4


def test_single_ping_flapping_does_not_reset_backoff(tmp_path: Path) -> None:
    opener = QueueOpener(
        FakeResponse(heartbeat()),
        FakeResponse(heartbeat()),
        FakeResponse(heartbeat()),
        FakeResponse(heartbeat()),
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(
            path=tmp_path / "state.json",
            baseline_complete=True,
        ),
        opener=opener,
    )
    delays: list[float] = []

    worker.run_forever(
        backoff=BoundedBackoff(initial=0.1, maximum=0.2),
        sleep=delays.append,
        max_connections=4,
    )

    assert delays == [0.1, 0.2, 0.2]


def test_armed_connection_periodically_reattaches_on_heartbeat(
    tmp_path: Path,
) -> None:
    response = FakeResponse(
        [
            *heartbeat(),
            *heartbeat(),
            *frame(10, settlement_data("after-boundary", 1, "n")),
        ]
    )
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(
            path=tmp_path / "state.json",
            baseline_complete=True,
        ),
        opener=QueueOpener(response),
        replay_heartbeats=2,
    )

    stats = worker.consume_connection()

    assert stats.heartbeats == 2
    assert stats.frames == 0
    assert response.closed is True


def test_single_instance_lock_refuses_second_owner(tmp_path: Path) -> None:
    lock = tmp_path / "guardian.lock"

    with (
        single_instance_lock(lock),
        pytest.raises(GuardianAlreadyRunning),
        single_instance_lock(lock),
    ):
        pass

    with single_instance_lock(lock):
        pass


def test_protocol_rejects_non_sse_response(tmp_path: Path) -> None:
    response = FakeResponse([], content_type="application/json")
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(path=tmp_path / "state.json"),
        opener=QueueOpener(response),
    )

    with pytest.raises(GuardianProtocolError):
        worker.consume_connection()
    assert response.closed is True


def test_readiness_is_announced_only_after_valid_sse_response(tmp_path: Path) -> None:
    announced: list[str] = []
    valid = FakeResponse([])
    valid_reconnect = FakeResponse([])
    worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(path=tmp_path / "valid-state.json"),
        opener=QueueOpener(valid, valid_reconnect),
        ready_callback=lambda: announced.append("ready"),
    )

    worker.consume_connection()
    worker.consume_connection()

    assert announced == ["ready"]

    rejected: list[str] = []
    invalid = FakeResponse([], status=404)
    invalid_worker = GuardianWorker(
        server_url="http://127.0.0.1:3024",
        state=GuardianState(path=tmp_path / "invalid-state.json"),
        opener=QueueOpener(invalid),
        ready_callback=lambda: rejected.append("ready"),
    )
    with pytest.raises(GuardianProtocolError, match="HTTP 404"):
        invalid_worker.consume_connection()
    assert rejected == []


def test_ready_receipt_is_atomic_and_removed_only_by_owner(tmp_path: Path) -> None:
    ready_file = tmp_path / "guardian.ready.json"

    guardian_module.write_ready_receipt(
        ready_file,
        nonce="owner-nonce",
        server_url="http://127.0.0.1:3024",
        pid=4321,
    )

    payload = json.loads(ready_file.read_text(encoding="utf-8"))
    assert payload == {
        "schema": guardian_module.GUARDIAN_READY_SCHEMA,
        "nonce": "owner-nonce",
        "pid": 4321,
        "server_url": "http://127.0.0.1:3024",
    }
    assert (
        guardian_module.remove_ready_receipt_if_owned(
            ready_file,
            nonce="other-nonce",
            pid=4321,
        )
        is False
    )
    assert ready_file.is_file()
    assert (
        guardian_module.remove_ready_receipt_if_owned(
            ready_file,
            nonce="owner-nonce",
            pid=4321,
        )
        is True
    )
    assert not ready_file.exists()


def test_notification_mapping_and_macos_log_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = SettlementRevision(
        run_id="run-x",
        revision=4,
        verdict="failed",
        tui="x",
        reason='bad "proof"\nnow',
        source="trust",
        settled_at="2026-07-26T06:00:00+00:00",
    )
    notification = notification_for(event)
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    with caplog.at_level(logging.INFO, logger="vibecrafted_core.guardian"):
        notify_operator(
            notification,
            platform="darwin",
            which=lambda _name: "/usr/bin/osascript",
            runner=runner,
        )

    assert notification.severity == "critical"
    assert "Vibecrafted x: failed" in caplog.text
    assert calls[0][:2] == ["/usr/bin/osascript", "-e"]
    assert calls[0][3:] == [
        "--",
        "Vibecrafted x: failed",
        'run-x · r4 · bad "proof"\nnow',
    ]


def test_invalid_server_origin_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="origin"):
        GuardianWorker(
            server_url="http://127.0.0.1:3024/api/control/events",
            state=GuardianState(path=tmp_path / "state.json"),
        )

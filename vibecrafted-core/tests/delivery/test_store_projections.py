"""Storage, delivery-event, and three-axis projection regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecrafted_core import control_plane
from vibecrafted_core.delivery import DeliveryStore, DeliveryStoreError
from vibecrafted_core.delivery.model import (
    DeliveryProofContract,
    DeliveryRecord,
    DeliveryState,
    ExecutionEnvelope,
    ExecutionEvidence,
    ProofResult,
    ProofState,
)
from vibecrafted_core.delivery.seal import SealComponents, issue_seal
from vibecrafted_core.events import (
    DELIVERY_EVENT_KINDS,
    DeliveryEventKind,
    append_delivery_event,
)

ZERO = "sha256:" + "0" * 64


def _envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(
        schema=ExecutionEnvelope.SCHEMA,
        agent="codex",
        repo="vetcoders/vibecrafted",
        root="/repo",
        branch="feat/reduce-wrong-assumptions",
        expected_head="a" * 40,
        upstream_ref="origin/feat/reduce-wrong-assumptions",
        upstream_relation={"ahead": 0, "behind": 0},
        dirty_policy="living-tree-scoped",
        baseline_status_digest=ZERO,
        protected_paths=(),
        owned_paths=("vibecrafted-core/vibecrafted_core/delivery/store.py",),
        brief_path="/brief.md",
        brief_sha256=ZERO,
    )


def _contract(envelope: ExecutionEnvelope) -> DeliveryProofContract:
    return DeliveryProofContract(
        schema=DeliveryProofContract.SCHEMA,
        id="dpk-w4-store",
        execution_envelope_sha256=envelope.content_digest(),
        subject={"producer_id": "subject.test", "public_surface": "/bin/echo"},
        witness={"input": "test.py", "expected_outcome": "tests pass"},
        oracle=None,
        assertion={"kind": "pytest", "expected_exit": 0},
        negative_controls=({"id": "red-first", "mutation": "missing test"},),
        delivery_scope="checkout",
        integration_target=None,
        runtime_probes=(),
    )


def _execution(contract: DeliveryProofContract) -> ExecutionEvidence:
    return ExecutionEvidence(
        schema=ExecutionEvidence.SCHEMA,
        evidence_id="subject-1",
        parent_contract_id=contract.id,
        run_id="impl-1",
        role="subject",
        argv=("/bin/echo", "ok"),
        cwd="/repo",
        environment={},
        resolved_executable="/bin/echo",
        executable_version=None,
        executable_sha256=ZERO,
        started_at="2026-07-20T18:00:00+00:00",
        ended_at="2026-07-20T18:00:01+00:00",
        elapsed_ms=1000,
        timeout_seconds=30.0,
        exit_code=0,
        stdout_sha256=ZERO,
        stderr_sha256=ZERO,
        stdout_excerpt="ok",
        stderr_excerpt="",
        input_digests={"contract": contract.content_digest()},
        output_digests={"stdout": ZERO},
        repo_before={"head": "a" * 40},
        repo_after={"head": "a" * 40},
        run_identity_sha256=None,
        liveness_evidence_sha256=(),
    )


def _proof(contract: DeliveryProofContract) -> ProofResult:
    return ProofResult(
        schema=ProofResult.SCHEMA,
        proof_id=contract.id,
        state=ProofState.PASSED,
        evidence=({"role": "subject", "sha256": ZERO},),
        assertion_results=({"id": "pytest", "passed": True},),
        negative_control_results=({"id": "red-first", "detected_falsehood": True},),
        subject_executed=True,
        assertion_consumed_subject_output=True,
        refusal_reasons=(),
        contract_sha256=contract.content_digest(),
        executor_sha256=ZERO,
        evaluated_at="2026-07-20T18:00:02+00:00",
    )


def _record(proof: ProofResult) -> DeliveryRecord:
    return DeliveryRecord(
        schema=DeliveryRecord.SCHEMA,
        record_id="record-1",
        proof_result_sha256=proof.content_digest(),
        declared_scope="checkout",
        checked_scope="checkout",
        target_identity={"repo": "vetcoders/vibecrafted"},
        commit_provenance={"final_head": "a" * 40},
        runtime_probe_results=(),
        state=DeliveryState.DELIVERED,
        refusal_reasons=(),
        recorded_at="2026-07-20T18:00:03+00:00",
    )


def _seal_components(
    envelope: ExecutionEnvelope,
    contract: DeliveryProofContract,
    proof: ProofResult,
) -> SealComponents:
    return SealComponents(
        run_id="impl-1",
        lifecycle_id="lifecycle-1",
        cut_id="dpk-w4",
        proof_id=proof.proof_id,
        run_identity_sha256=ZERO,
        liveness_evidence_sha256=(),
        execution_envelope_sha256=envelope.content_digest(),
        delivery_proof_contract_sha256=contract.content_digest(),
        proof_result_sha256=proof.content_digest(),
        executor_source_sha256=ZERO,
        executor_version="v1",
        subject_evidence_sha256=ZERO,
        witness_sha256=ZERO,
        oracle_evidence_sha256=None,
        assertion_evidence_sha256=ZERO,
        negative_control_evidence_sha256=(ZERO,),
        repo="vetcoders/vibecrafted",
        branch="feat/reduce-wrong-assumptions",
        baseline_head="a" * 40,
        final_head="a" * 40,
        scoped_dirty_status_sha256=ZERO,
        commit_range="a..a",
    )


def test_store_round_trip_materializes_canonical_layout(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path / "run")
    envelope = _envelope()
    contract = _contract(envelope)
    execution = _execution(contract)
    proof = _proof(contract)
    record = _record(proof)
    seal = issue_seal(
        record,
        issuer="vc-ship.test",
        components=_seal_components(envelope, contract, proof),
        issued_at="2026-07-20T18:00:04+00:00",
    )

    store.write_execution_envelope(envelope)
    store.write_proof_contract(contract)
    store.write_execution(execution, sequence=1)
    store.write_assertions(
        [{"id": "pytest", "passed": True}], source_digests={"subject": ZERO}
    )
    store.write_negative_controls(
        [{"id": "red-first", "detected_falsehood": True}],
        source_digests={"assertions": ZERO},
    )
    store.write_proof_result(proof)
    store.write_delivery_record(record)
    store.write_delivery_seal(seal)

    assert store.read_execution_envelope() == envelope
    assert store.read_proof_contract() == contract
    assert store.read_execution("subject", sequence=1) == execution
    assert store.read_assertions()["schema"] == "vibecrafted.proof-assertions.v1"
    assert store.read_negative_controls()["source_digests"] == {"assertions": ZERO}
    assert store.read_proof_result() == proof
    assert store.read_delivery_record() == record
    assert store.read_delivery_seal() == seal
    assert {
        str(path.relative_to(store.run_dir)) for path in store.run_dir.rglob("*.json")
    } == {
        "execution-envelope.json",
        "delivery-proof-contract.json",
        "proof/executions/subject-1.json",
        "proof/assertions.json",
        "proof/negative-controls.json",
        "proof/result.json",
        "delivery-record.json",
        "delivery-seal.json",
    }


def test_interrupted_temporary_write_never_corrupts_canonical_file(
    tmp_path: Path,
) -> None:
    store = DeliveryStore(tmp_path / "run")
    envelope = _envelope()
    canonical = store.write_execution_envelope(envelope)
    canonical.with_name(f"{canonical.name}.tmp.interrupted").write_text(
        '{"schema":', encoding="utf-8"
    )

    assert store.read_execution_envelope() == envelope


def test_derived_records_require_source_digests(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path / "run")
    with pytest.raises(DeliveryStoreError, match="source_digests"):
        store.write_assertions([], source_digests={})


def test_all_delivery_events_use_existing_append_only_stream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    for kind in DeliveryEventKind:
        event = append_delivery_event(kind, "impl-1", kind.value, {"source": ZERO})
        assert event["kind"] == kind.value

    emitted = control_plane.read_event_tail(limit=len(DELIVERY_EVENT_KINDS))
    assert {event["kind"] for event in emitted} == set(DELIVERY_EVENT_KINDS)


def test_t13_completed_artifact_without_seal_is_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "impl-t13"
    run_dir = home / "control_plane" / "runtime_runs" / run_id
    run_dir.mkdir(parents=True)
    report = run_dir / "report.md"
    report.write_text("bytes are not proof\n", encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "exit_code": 0,
                "artifact_ok": True,
                "report": str(report),
            }
        ),
        encoding="utf-8",
    )
    # Even a delivered record is not the seal and cannot promote this axis.
    proof = _proof(_contract(_envelope()))
    DeliveryStore(run_dir).write_delivery_record(_record(proof))

    axes = control_plane.read_delivery_axes(run_id)

    assert axes.to_payload() == {
        "execution_state": "exited",
        "proof_state": "undeclared",
        "delivery_state": "unverified",
    }


def test_legacy_run_projects_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "legacy-1"
    legacy_dir = home / "artifacts" / "legacy"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / f"{run_id}.meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "completed", "artifact_ok": True}),
        encoding="utf-8",
    )

    assert control_plane.read_delivery_axes(run_id).to_payload() == {
        "execution_state": "exited",
        "proof_state": "undeclared",
        "delivery_state": "unverified",
    }


def test_unknown_proof_contract_schema_projects_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "impl-unknown-contract"
    run_dir = home / "control_plane" / "runtime_runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "running"}), encoding="utf-8"
    )
    (run_dir / "delivery-proof-contract.json").write_text(
        '{"schema": "vibecrafted.delivery-proof.v999"}\n', encoding="utf-8"
    )

    axes = control_plane.read_delivery_axes(run_id)

    assert axes.proof_state is ProofState.INVALID
    assert axes.delivery_state is DeliveryState.UNVERIFIED


def test_valid_seal_and_malformed_seal_project_without_legacy_inference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    run_id = "impl-seal"
    run_dir = home / "control_plane" / "runtime_runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "completed", "exit_code": 0}),
        encoding="utf-8",
    )
    store = DeliveryStore(run_dir)
    envelope = _envelope()
    contract = _contract(envelope)
    proof = _proof(contract)
    record = _record(proof)
    store.write_proof_contract(contract)
    store.write_proof_result(proof)
    store.write_delivery_seal(
        issue_seal(
            record,
            issuer="vc-ship.test",
            components=_seal_components(envelope, contract, proof),
        )
    )

    assert control_plane.read_delivery_axes(run_id).to_payload() == {
        "execution_state": "exited",
        "proof_state": "passed",
        "delivery_state": "sealed",
    }

    (run_dir / "delivery-seal.json").write_text(
        '{"schema": "unknown"}\n', encoding="utf-8"
    )
    assert (
        control_plane.read_delivery_axes(run_id).delivery_state
        is DeliveryState.INVALIDATED
    )

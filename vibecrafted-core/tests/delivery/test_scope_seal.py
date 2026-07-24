"""Red-first suite for delivery scope qualification and the content-addressed seal.

Every test maps to a row of the spec §15 T-matrix owned by this cut
(T12-T19) or to a normative field list in §7.7/§7.8 and §8.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from vibecrafted_core.delivery.model import (
    DeliveryProofContract,
    DeliverySeal,
    DeliveryState,
    ExecutionState,
    ProofResult,
    ProofState,
)
from vibecrafted_core.delivery.proof import run_proof
from vibecrafted_core.delivery.scope import (
    SCOPE_NONE,
    DeliveryScope,
    InstalledEvidence,
    RuntimeProbe,
    ScopeEvidence,
    qualify_scope,
)
from vibecrafted_core.delivery.seal import (
    DEFAULT_SEAL_LAYOUT,
    SealAuthorityError,
    SealComponents,
    SealRefusedError,
    issue_seal,
    reconstruct_seal,
    write_seal,
)
from vibecrafted_core.delivery.store import (
    DELIVERY_SEAL_PATH,
    EXECUTION_ENVELOPE_PATH,
    PROOF_CONTRACT_PATH,
    PROOF_RESULT_PATH,
)

ZERO = "sha256:" + "0" * 64


def test_default_seal_layout_matches_canonical_run_directory() -> None:
    assert Path(DEFAULT_SEAL_LAYOUT.seal) == DELIVERY_SEAL_PATH
    assert Path(DEFAULT_SEAL_LAYOUT.envelope) == EXECUTION_ENVELOPE_PATH
    assert Path(DEFAULT_SEAL_LAYOUT.contract) == PROOF_CONTRACT_PATH
    assert Path(DEFAULT_SEAL_LAYOUT.proof_result) == PROOF_RESULT_PATH
    assert DEFAULT_SEAL_LAYOUT.report == "report.md"
    assert DEFAULT_SEAL_LAYOUT.transcript == "transcript.log"
    assert DEFAULT_SEAL_LAYOUT.control_plane == "control-plane-snapshot.json"


def _contract(
    scope: str = "checkout",
    *,
    integration_target: str | None = None,
    runtime_probes: Sequence[Mapping[str, Any]] = (),
) -> DeliveryProofContract:
    return DeliveryProofContract(
        schema=DeliveryProofContract.SCHEMA,
        id="dpk-w3-test",
        execution_envelope_sha256=ZERO,
        subject={
            "producer_id": "subject.test",
            "public_surface": "/bin/echo",
            "argv": ["/bin/echo", "x"],
        },
        witness={"input": "witness.txt", "expected_outcome": "prints x"},
        oracle=None,
        assertion={
            "id": "a1",
            "kind": "stdout-contract",
            "actual": "subject.stdout",
            "required_patterns": ["x"],
        },
        negative_controls=({"id": "nc", "mutation": "remove_isolated_actual"},),
        delivery_scope=scope,
        integration_target=integration_target,
        runtime_probes=tuple(runtime_probes),
    )


def _proof(
    state: ProofState = ProofState.PASSED,
    *,
    relevant_stable: bool | None = True,
) -> ProofResult:
    assertion_results: list[Mapping[str, Any]] = [
        {"id": "a1", "kind": "stdout-contract", "passed": True, "valid": True}
    ]
    if relevant_stable is not None:
        assertion_results.append(
            {
                "kind": "relevant_path_digests",
                "before": {},
                "after": {},
                "stable": relevant_stable,
            }
        )
    return ProofResult(
        schema=ProofResult.SCHEMA,
        proof_id="dpk-w3-test",
        state=state,
        evidence=({"role": "subject", "exit_code": 0},),
        assertion_results=tuple(assertion_results),
        negative_control_results=(
            {"id": "nc", "detected_falsehood": True, "valid": True},
        ),
        subject_executed=True,
        assertion_consumed_subject_output=True,
        refusal_reasons=(),
        contract_sha256=ZERO,
        executor_sha256=ZERO,
        evaluated_at="2026-07-20T18:00:00.000+00:00",
    )


def _evidence(root: Path, **overrides: Any) -> ScopeEvidence:
    base: dict[str, Any] = {
        "repo": "vetcoders/vibecrafted",
        "repo_root": str(root),
        "branch": "feat/reduce-wrong-assumptions",
        "baseline_head": "a" * 40,
        "final_head": "b" * 40,
        "commit_range": f"{'a' * 40}..{'b' * 40}",
        "artifact_ok": True,
    }
    base.update(overrides)
    return ScopeEvidence(**base)


def _components(**overrides: Any) -> SealComponents:
    base: dict[str, Any] = {
        "run_id": "run-1",
        "lifecycle_id": "lc-1",
        "cut_id": "dpk-w3",
        "proof_id": "dpk-w3-test",
        "run_identity_sha256": ZERO,
        "liveness_evidence_sha256": (ZERO,),
        "execution_envelope_sha256": ZERO,
        "delivery_proof_contract_sha256": ZERO,
        "proof_result_sha256": ZERO,
        "executor_source_sha256": ZERO,
        "executor_version": "vibecrafted.proof-engine.v1",
        "subject_evidence_sha256": ZERO,
        "witness_sha256": ZERO,
        "oracle_evidence_sha256": None,
        "assertion_evidence_sha256": ZERO,
        "negative_control_evidence_sha256": (ZERO,),
        "repo": "vetcoders/vibecrafted",
        "branch": "feat/reduce-wrong-assumptions",
        "baseline_head": "a" * 40,
        "final_head": "b" * 40,
        "scoped_dirty_status_sha256": ZERO,
        "commit_range": f"{'a' * 40}..{'b' * 40}",
        "runtime_probe_sha256": (),
        "report_sha256": ZERO,
        "transcript_sha256": ZERO,
        "control_plane_snapshot_sha256": ZERO,
        "unverified_surfaces": ("installed", "live"),
    }
    base.update(overrides)
    return SealComponents(**base)


# --------------------------------------------------------------------------
# checkout scope + T12/T13
# --------------------------------------------------------------------------


def test_checkout_scope_delivers_on_passed_proof(tmp_path: Path) -> None:
    record = qualify_scope(_proof(), _contract("checkout"), _evidence(tmp_path))

    assert record.state is DeliveryState.DELIVERED
    assert record.declared_scope == "checkout"
    assert record.checked_scope == "checkout"
    assert record.refusal_reasons == ()
    assert record.commit_provenance["final_head"] == "b" * 40
    assert record.target_identity["repo"] == "vetcoders/vibecrafted"


@pytest.mark.parametrize(
    "state",
    [
        ExecutionState.INTERRUPTED,
        ExecutionState.TIMED_OUT,
        ExecutionState.FAILED,
        ExecutionState.RUNNING,
    ],
)
def test_t12_non_exited_execution_refuses_delivery(
    tmp_path: Path, state: ExecutionState
) -> None:
    """T12: interrupted/partial/timed_out never advances delivery."""
    record = qualify_scope(
        _proof(),
        _contract("checkout"),
        _evidence(tmp_path, execution_state=state, artifact_ok=True),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert record.checked_scope == SCOPE_NONE
    assert any("execution" in reason for reason in record.refusal_reasons)


def test_t12_nonzero_exit_refuses_delivery(tmp_path: Path) -> None:
    record = qualify_scope(
        _proof(),
        _contract("checkout"),
        _evidence(tmp_path, execution_exit_code=101),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("101" in reason for reason in record.refusal_reasons)


def test_t13_artifact_without_proof_is_unverified(tmp_path: Path) -> None:
    """T13: bytes on disk are presence, never proof."""
    record = qualify_scope(
        None, _contract("checkout"), _evidence(tmp_path, artifact_ok=True)
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert "no_proof" in record.refusal_reasons
    assert record.target_identity["artifact_ok"] is True


@pytest.mark.parametrize(
    "state", [ProofState.FAILED, ProofState.INVALID, ProofState.STALE]
)
def test_non_passed_proof_refuses_delivery(tmp_path: Path, state: ProofState) -> None:
    record = qualify_scope(_proof(state), _contract("checkout"), _evidence(tmp_path))

    assert record.state is DeliveryState.UNVERIFIED
    assert any(state.value in reason for reason in record.refusal_reasons)


def test_relevant_path_drift_refuses_delivery(tmp_path: Path) -> None:
    record = qualify_scope(
        _proof(relevant_stable=False), _contract("checkout"), _evidence(tmp_path)
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("drift" in reason for reason in record.refusal_reasons)


def test_declared_scope_must_match_contract(tmp_path: Path) -> None:
    record = qualify_scope(
        _proof(), _contract("checkout"), _evidence(tmp_path), declared_scope="live"
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("contract" in reason for reason in record.refusal_reasons)


# --------------------------------------------------------------------------
# T15 installed
# --------------------------------------------------------------------------


def test_t15_installed_scope_refuses_repo_local_executable(tmp_path: Path) -> None:
    """T15: a binary inside the repo root is the checkout, not an installation."""
    repo_binary = tmp_path / "target" / "debug" / "vc"
    repo_binary.parent.mkdir(parents=True)
    repo_binary.write_text("#!/bin/sh\n", encoding="utf-8")

    record = qualify_scope(
        _proof(),
        _contract("installed"),
        _evidence(
            tmp_path,
            installed=InstalledEvidence(
                resolved_path=str(repo_binary),
                provenance_marker="vc 1.0.0",
                provenance_commit="b" * 40,
                smoke=RuntimeProbe(
                    probe_id="smoke",
                    target="vc --version",
                    performed=True,
                    passed=True,
                    observed_effect="vc 1.0.0",
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert record.checked_scope != "installed"
    assert any("repo root" in reason for reason in record.refusal_reasons)


def test_t15_installed_scope_requires_provenance_and_smoke(tmp_path: Path) -> None:
    installed_root = tmp_path.parent / "installed-prefix"
    installed_root.mkdir(exist_ok=True)
    binary = installed_root / "vc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    record = qualify_scope(
        _proof(),
        _contract("installed"),
        _evidence(
            tmp_path,
            installed=InstalledEvidence(
                resolved_path=str(binary),
                provenance_marker=None,
                provenance_commit=None,
                smoke=None,
            ),
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    reasons = " ".join(record.refusal_reasons)
    assert "provenance" in reasons
    assert "smoke" in reasons


def test_installed_scope_delivers_with_full_evidence(tmp_path: Path) -> None:
    installed_root = tmp_path.parent / "installed-prefix-ok"
    installed_root.mkdir(exist_ok=True)
    binary = installed_root / "vc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    record = qualify_scope(
        _proof(),
        _contract("installed"),
        _evidence(
            tmp_path,
            installed=InstalledEvidence(
                resolved_path=str(binary),
                provenance_marker="vc 1.0.0+bbbbbbb",
                provenance_commit="b" * 40,
                smoke=RuntimeProbe(
                    probe_id="smoke",
                    target=str(binary),
                    performed=True,
                    passed=True,
                    observed_effect="vc 1.0.0",
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.DELIVERED
    assert record.checked_scope == "installed"


def test_installed_scope_refuses_provenance_commit_mismatch(tmp_path: Path) -> None:
    installed_root = tmp_path.parent / "installed-prefix-drift"
    installed_root.mkdir(exist_ok=True)
    binary = installed_root / "vc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    record = qualify_scope(
        _proof(),
        _contract("installed"),
        _evidence(
            tmp_path,
            installed=InstalledEvidence(
                resolved_path=str(binary),
                provenance_marker="vc 0.9.0",
                provenance_commit="c" * 40,
                smoke=RuntimeProbe(
                    probe_id="smoke",
                    target=str(binary),
                    performed=True,
                    passed=True,
                    observed_effect="vc 0.9.0",
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("provenance commit" in reason for reason in record.refusal_reasons)


# --------------------------------------------------------------------------
# T16 live
# --------------------------------------------------------------------------


def test_t16_live_scope_without_probe_refuses(tmp_path: Path) -> None:
    """T16: a green local test can never satisfy `live`."""
    record = qualify_scope(_proof(), _contract("live"), _evidence(tmp_path))

    assert record.state is DeliveryState.UNVERIFIED
    assert record.checked_scope != "live"
    assert any("runtime probe" in reason for reason in record.refusal_reasons)


def test_live_scope_delivers_with_passing_probe(tmp_path: Path) -> None:
    record = qualify_scope(
        _proof(),
        _contract("live"),
        _evidence(
            tmp_path,
            runtime_probes=(
                RuntimeProbe(
                    probe_id="health",
                    target="https://vibecrafted.example/health",
                    performed=True,
                    passed=True,
                    observed_effect="200 ok",
                    evidence_sha256=ZERO,
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.DELIVERED
    assert record.checked_scope == "live"
    assert record.runtime_probe_results[0]["probe_id"] == "health"


def test_live_scope_refuses_destructive_probe(tmp_path: Path) -> None:
    """§13: destructive live probes are forbidden, not merely discouraged."""
    record = qualify_scope(
        _proof(),
        _contract("live"),
        _evidence(
            tmp_path,
            runtime_probes=(
                RuntimeProbe(
                    probe_id="wipe",
                    target="prod-db",
                    performed=True,
                    passed=True,
                    observed_effect="dropped",
                    destructive=True,
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("destructive" in reason for reason in record.refusal_reasons)


def test_live_scope_refuses_failed_probe(tmp_path: Path) -> None:
    record = qualify_scope(
        _proof(),
        _contract("live"),
        _evidence(
            tmp_path,
            runtime_probes=(
                RuntimeProbe(
                    probe_id="health",
                    target="https://vibecrafted.example/health",
                    performed=True,
                    passed=False,
                    observed_effect="503",
                ),
            ),
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("health" in reason for reason in record.refusal_reasons)


# --------------------------------------------------------------------------
# T17 integrated + branch reachability
# --------------------------------------------------------------------------


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_t17_integrated_refuses_commit_not_reachable_from_target(
    repo_with_remote: tuple[Path, Path],
) -> None:
    """T17: a local side commit is not integration."""
    work, _remote = repo_with_remote
    side = work / "side.txt"
    side.write_text("side work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(work), "add", "side.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "commit", "-q", "-m", "unpushed side commit"],
        check=True,
    )
    unreachable = _head(work)

    record = qualify_scope(
        _proof(),
        _contract("integrated", integration_target="origin/main"),
        _evidence(
            work,
            repo_root=str(work),
            final_head=unreachable,
            integration_target="origin/main",
            fetch_remote="origin",
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert record.checked_scope != "integrated"
    assert any("not reachable" in reason for reason in record.refusal_reasons)


def test_t17_integrated_delivers_reachable_commit(
    repo_with_remote: tuple[Path, Path],
) -> None:
    work, _remote = repo_with_remote
    reachable = _head(work)

    record = qualify_scope(
        _proof(),
        _contract("integrated", integration_target="origin/main"),
        _evidence(
            work,
            repo_root=str(work),
            final_head=reachable,
            integration_target="origin/main",
            fetch_remote="origin",
        ),
    )

    assert record.state is DeliveryState.DELIVERED
    assert record.checked_scope == "integrated"
    assert record.target_identity["integration_target"] == "origin/main"


def test_integrated_without_target_refuses(temp_git_repo: Path) -> None:
    record = qualify_scope(
        _proof(),
        _contract("integrated"),
        _evidence(
            temp_git_repo, repo_root=str(temp_git_repo), final_head=_head(temp_git_repo)
        ),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("integration_target" in reason for reason in record.refusal_reasons)


def test_branch_scope_delivers_for_reachable_commit(temp_git_repo: Path) -> None:
    branch = subprocess.run(
        ["git", "-C", str(temp_git_repo), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    record = qualify_scope(
        _proof(),
        _contract("branch"),
        _evidence(
            temp_git_repo,
            repo_root=str(temp_git_repo),
            branch=branch,
            final_head=_head(temp_git_repo),
        ),
    )

    assert record.state is DeliveryState.DELIVERED
    assert record.checked_scope == "branch"


def test_branch_scope_refuses_unknown_commit(temp_git_repo: Path) -> None:
    record = qualify_scope(
        _proof(),
        _contract("branch"),
        _evidence(temp_git_repo, repo_root=str(temp_git_repo), final_head="0" * 40),
    )

    assert record.state is DeliveryState.UNVERIFIED
    assert any("not reachable" in reason for reason in record.refusal_reasons)


def test_scope_ladder_is_not_a_label_edit(tmp_path: Path) -> None:
    """§8: `checkout` never becomes `installed` by renaming the label."""
    evidence = _evidence(tmp_path)
    checkout = qualify_scope(_proof(), _contract("checkout"), evidence)
    relabelled = qualify_scope(_proof(), _contract("installed"), evidence)

    assert checkout.state is DeliveryState.DELIVERED
    assert relabelled.state is DeliveryState.UNVERIFIED
    assert relabelled.checked_scope != "installed"


def test_delivery_scope_enum_covers_spec_section_8() -> None:
    assert {scope.value for scope in DeliveryScope} == {
        "checkout",
        "branch",
        "integrated",
        "installed",
        "live",
    }


# --------------------------------------------------------------------------
# Seal issuance — authority, determinism (T19/T20), §7.8 binding set
# --------------------------------------------------------------------------


def _delivered_record(tmp_path: Path) -> Any:
    return qualify_scope(_proof(), _contract("checkout"), _evidence(tmp_path))


def test_seal_refuses_without_issuer(tmp_path: Path) -> None:
    with pytest.raises(SealAuthorityError):
        issue_seal(_delivered_record(tmp_path), issuer="  ", components=_components())


def test_seal_refuses_unverified_record(tmp_path: Path) -> None:
    unverified = qualify_scope(None, _contract("checkout"), _evidence(tmp_path))

    with pytest.raises(SealRefusedError):
        issue_seal(unverified, issuer="vc-ship", components=_components())


def test_seal_refuses_scope_downgrade(tmp_path: Path) -> None:
    """A record whose checked scope fell short can never be sealed at declared."""
    record = qualify_scope(_proof(), _contract("live"), _evidence(tmp_path))

    with pytest.raises(SealRefusedError):
        issue_seal(record, issuer="vc-ship", components=_components())


def test_t19_seal_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    """T19: identical inputs produce a byte-identical seal identity."""
    record = _delivered_record(tmp_path)
    first = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(),
        issued_at="2026-07-20T18:00:00+00:00",
    )
    second = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(),
        issued_at="2026-07-20T18:00:00+00:00",
    )

    assert first.seal_id == second.seal_id
    assert first.canonical_json() == second.canonical_json()
    assert first.content_digest() == second.content_digest()


def test_t20_same_input_rerun_same_digest_different_event_time(tmp_path: Path) -> None:
    """T20: event time moves, content identity does not."""
    record = _delivered_record(tmp_path)
    first = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(),
        issued_at="2026-07-20T18:00:00+00:00",
    )
    second = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(),
        issued_at="2026-07-21T09:30:00+00:00",
    )

    assert first.issued_at != second.issued_at
    assert first.content_digest() == second.content_digest()
    assert first.seal_id == second.seal_id


def test_seal_digest_changes_when_any_component_changes(tmp_path: Path) -> None:
    record = _delivered_record(tmp_path)
    baseline = issue_seal(record, issuer="vc-ship", components=_components())
    drifted = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(executor_source_sha256="sha256:" + "f" * 64),
    )

    assert baseline.content_digest() != drifted.content_digest()


def test_seal_binds_every_spec_component(tmp_path: Path) -> None:
    """§7.8: the binding set is normative — never silently narrowed."""
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=_components()
    )
    payload = seal.to_payload()

    for field_name in (
        "schema",
        "seal_id",
        "issued_at",
        "issuer",
        "run_id",
        "lifecycle_id",
        "cut_id",
        "proof_id",
        "run_identity_sha256",
        "liveness_evidence_sha256",
        "execution_envelope_sha256",
        "delivery_proof_contract_sha256",
        "proof_result_sha256",
        "executor_source_sha256",
        "executor_version",
        "subject_evidence_sha256",
        "witness_sha256",
        "assertion_evidence_sha256",
        "negative_control_evidence_sha256",
        "repo",
        "branch",
        "baseline_head",
        "final_head",
        "scoped_dirty_status_sha256",
        "commit_range",
        "declared_scope",
        "checked_scope",
        "runtime_probe_sha256",
        "report_sha256",
        "transcript_sha256",
        "control_plane_snapshot_sha256",
        "unverified_surfaces",
    ):
        assert field_name in payload, f"seal must bind {field_name}"

    assert "issued_at" not in seal.identity_payload()
    assert seal.declared_scope == "checkout"
    assert seal.checked_scope == "checkout"


# --------------------------------------------------------------------------
# T14 reconstruction from disk
# --------------------------------------------------------------------------


def _materialize_run_dir(run_dir: Path) -> SealComponents:
    """Write the on-disk artifacts a seal binds and return matching components."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / DEFAULT_SEAL_LAYOUT.proof_result).parent.mkdir(
        parents=True, exist_ok=True
    )
    contract = _contract("checkout")
    proof = _proof()

    (run_dir / DEFAULT_SEAL_LAYOUT.envelope).write_text(
        json.dumps({"schema": "vibecrafted.execution-envelope.v1", "agent": "claude"}),
        encoding="utf-8",
    )
    (run_dir / DEFAULT_SEAL_LAYOUT.contract).write_text(
        json.dumps(contract.to_payload()), encoding="utf-8"
    )
    (run_dir / DEFAULT_SEAL_LAYOUT.proof_result).write_text(
        json.dumps(proof.to_payload()), encoding="utf-8"
    )
    (run_dir / DEFAULT_SEAL_LAYOUT.report).write_text("# report\n", encoding="utf-8")
    (run_dir / DEFAULT_SEAL_LAYOUT.transcript).write_text(
        "transcript\n", encoding="utf-8"
    )
    (run_dir / DEFAULT_SEAL_LAYOUT.control_plane).write_text(
        json.dumps({"events": []}), encoding="utf-8"
    )

    from vibecrafted_core.delivery.seal import digest_file

    return _components(
        execution_envelope_sha256=digest_file(run_dir / DEFAULT_SEAL_LAYOUT.envelope),
        delivery_proof_contract_sha256=digest_file(
            run_dir / DEFAULT_SEAL_LAYOUT.contract
        ),
        proof_result_sha256=digest_file(run_dir / DEFAULT_SEAL_LAYOUT.proof_result),
        report_sha256=digest_file(run_dir / DEFAULT_SEAL_LAYOUT.report),
        transcript_sha256=digest_file(run_dir / DEFAULT_SEAL_LAYOUT.transcript),
        control_plane_snapshot_sha256=digest_file(
            run_dir / DEFAULT_SEAL_LAYOUT.control_plane
        ),
    )


def test_t14_reconstruct_seal_round_trip(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    components = _materialize_run_dir(run_dir)
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=components
    )
    write_seal(run_dir, seal)

    result = reconstruct_seal(run_dir)

    assert result.status == "verified"
    assert result.mismatches == ()
    assert result.seal is not None
    assert result.seal.content_digest() == seal.content_digest()


def test_t14_reconstruction_fails_when_verifier_digest_mutated(tmp_path: Path) -> None:
    """T14: the verifier changed after PASS — the seal must stop reconstructing."""
    run_dir = tmp_path / "run"
    components = _materialize_run_dir(run_dir)
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=components
    )
    write_seal(run_dir, seal)

    stored = json.loads(
        (run_dir / DEFAULT_SEAL_LAYOUT.proof_result).read_text(encoding="utf-8")
    )
    stored["executor_sha256"] = "sha256:" + "e" * 64
    (run_dir / DEFAULT_SEAL_LAYOUT.proof_result).write_text(
        json.dumps(stored), encoding="utf-8"
    )

    result = reconstruct_seal(run_dir)

    assert result.status == "stale"
    assert any(item["component"] == "proof_result_sha256" for item in result.mismatches)


def test_t14_reconstruction_fails_on_any_bound_artifact_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    components = _materialize_run_dir(run_dir)
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=components
    )
    write_seal(run_dir, seal)

    (run_dir / DEFAULT_SEAL_LAYOUT.report).write_text("# tampered\n", encoding="utf-8")

    result = reconstruct_seal(run_dir)

    assert result.status == "stale"
    assert any(item["component"] == "report_sha256" for item in result.mismatches)


def test_t14_reconstruction_reports_missing_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    components = _materialize_run_dir(run_dir)
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=components
    )
    write_seal(run_dir, seal)
    (run_dir / DEFAULT_SEAL_LAYOUT.transcript).unlink()

    result = reconstruct_seal(run_dir)

    assert result.status == "stale"
    assert any(item["observed"] == "missing" for item in result.mismatches)


def test_reconstruct_seal_without_seal_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "empty-run"
    run_dir.mkdir()

    result = reconstruct_seal(run_dir)

    assert result.status == "missing"
    assert result.seal is None


def test_written_seal_reloads_through_contract_reader(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    components = _materialize_run_dir(run_dir)
    seal = issue_seal(
        _delivered_record(tmp_path), issuer="vc-ship", components=components
    )
    path = write_seal(run_dir, seal)

    reloaded = DeliverySeal.from_payload(json.loads(path.read_text(encoding="utf-8")))

    assert reloaded.content_digest() == seal.content_digest()


# --------------------------------------------------------------------------
# T18 end-to-end through the real proof engine
# --------------------------------------------------------------------------


def test_t18_e2e_proof_to_checkout_delivery_to_seal(
    two_producers: tuple[dict[str, object], dict[str, object]],
    temp_git_repo: Path,
) -> None:
    """T18/T19: real subprocess proof → checkout delivery → issued seal."""
    subject, _oracle = two_producers
    contract = DeliveryProofContract(
        schema=DeliveryProofContract.SCHEMA,
        id="dpk-w3-e2e",
        execution_envelope_sha256=ZERO,
        subject=subject,
        witness={
            "input": str(subject["public_surface"]),
            "expected_outcome": "subject prints its own marker",
        },
        oracle=None,
        assertion={
            "id": "e2e",
            "kind": "stdout-contract",
            "actual": "subject.stdout",
            "required_patterns": ["subject"],
            "expected_exit": 0,
        },
        negative_controls=(
            {"id": "drop-output", "mutation": "remove_isolated_actual"},
        ),
        delivery_scope="checkout",
        integration_target=None,
        runtime_probes=(),
    )

    proof = run_proof(contract, run_id="e2e-run")
    assert proof.state is ProofState.PASSED, proof.refusal_reasons
    assert proof.subject_executed is True
    assert proof.assertion_consumed_subject_output is True
    assert proof.negative_control_results[0]["detected_falsehood"] is True

    record = qualify_scope(
        proof,
        contract,
        _evidence(
            temp_git_repo,
            repo_root=str(temp_git_repo),
            final_head=_head(temp_git_repo),
        ),
    )
    assert record.state is DeliveryState.DELIVERED
    assert record.checked_scope == "checkout"

    seal = issue_seal(
        record,
        issuer="vc-ship",
        components=_components(proof_result_sha256=proof.content_digest()),
    )
    assert seal.issuer == "vc-ship"
    assert seal.proof_id == "dpk-w3-test"
    assert seal.content_digest().startswith("sha256:")

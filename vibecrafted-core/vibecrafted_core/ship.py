from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import loop, ui
from .delivery import seal
from .delivery.model import DeliverySeal, DeliveryState, ProofState
from .delivery.proof import ENGINE_VERSION
from .delivery.store import DeliveryStore, DeliveryStoreError, atomic_write_json
from .events import DeliveryEventKind, append_event
from .lifecycle_runner import (
    LifecycleRunSpec,
    _control_verbs,
    delivery_axes_for_receipt,
    run_lifecycle,
)

SUPPORTED_AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok"}

DEFAULT_SHIP_PROMPT = (
    "Run the full Vibecrafted lifecycle for this repository. Load Context Atlas, "
    "start at the selected lifecycle checkpoint, preserve READ/WRITE phase "
    "boundaries, and hand off through the manifest runner."
)

SHIP_ISSUER = "vc-ship"
SHIP_SEAL_LAYOUT = seal.DEFAULT_SEAL_LAYOUT
SEAL_REFUSAL_PATH = Path("delivery-seal-refusal.json")
ZERO_DIGEST = "sha256:" + "0" * 64
EventSink = Callable[[str, str, str, dict[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ShipSealResult:
    delivery_state: DeliveryState
    seal: DeliverySeal | None
    refusal_reasons: tuple[str, ...]
    event: Mapping[str, Any]


def _digest_if_file(path: Path) -> str:
    return seal.digest_file(path) if path.is_file() else ""


def _execution_digest(store: DeliveryStore, role: str) -> str | None:
    try:
        return store.read_execution(role).content_digest()
    except DeliveryStoreError:
        return None


def _seal_components(
    store: DeliveryStore, *, run_id: str, lifecycle_id: str, cut_id: str
) -> seal.SealComponents:
    envelope = store.read_execution_envelope()
    contract = store.read_proof_contract()
    proof = store.read_proof_result()
    record = store.read_delivery_record()
    subject_digest = _execution_digest(store, "subject") or ZERO_DIGEST
    oracle_digest = _execution_digest(store, "oracle")
    witness_raw = contract.witness.get("input")
    witness = Path(str(witness_raw or ""))
    if not witness.is_absolute():
        witness = Path(str(contract.subject.get("cwd") or envelope.root)) / witness
    report = store.path(SHIP_SEAL_LAYOUT.report)
    transcript = store.path(SHIP_SEAL_LAYOUT.transcript)
    control_plane = store.path(SHIP_SEAL_LAYOUT.control_plane)
    unverified = ["run_identity", "liveness"]
    for name, path in (
        ("report", report),
        ("transcript", transcript),
        ("control_plane_snapshot", control_plane),
    ):
        if not path.is_file():
            unverified.append(name)
    provenance = record.commit_provenance
    return seal.SealComponents(
        run_id=run_id,
        lifecycle_id=lifecycle_id,
        cut_id=cut_id,
        proof_id=proof.proof_id,
        run_identity_sha256=ZERO_DIGEST,
        liveness_evidence_sha256=(),
        execution_envelope_sha256=seal.digest_file(
            store.path(SHIP_SEAL_LAYOUT.envelope)
        ),
        delivery_proof_contract_sha256=seal.digest_file(
            store.path(SHIP_SEAL_LAYOUT.contract)
        ),
        proof_result_sha256=seal.digest_file(store.path(SHIP_SEAL_LAYOUT.proof_result)),
        executor_source_sha256=proof.executor_sha256,
        executor_version=ENGINE_VERSION,
        subject_evidence_sha256=subject_digest,
        witness_sha256=_digest_if_file(witness),
        oracle_evidence_sha256=oracle_digest,
        assertion_evidence_sha256=_digest_if_file(store.path("proof/assertions.json")),
        negative_control_evidence_sha256=(
            _digest_if_file(store.path("proof/negative-controls.json")),
        ),
        repo=envelope.repo,
        branch=envelope.branch,
        baseline_head=str(provenance.get("baseline_head") or envelope.expected_head),
        final_head=str(provenance.get("final_head") or envelope.expected_head),
        scoped_dirty_status_sha256=envelope.baseline_status_digest,
        commit_range=str(provenance.get("commit_range") or ""),
        report_sha256=_digest_if_file(report),
        transcript_sha256=_digest_if_file(transcript),
        control_plane_snapshot_sha256=_digest_if_file(control_plane),
        unverified_surfaces=tuple(unverified),
    )


def seal_delivery_run(
    run_dir: str | Path,
    *,
    run_id: str,
    lifecycle_id: str,
    cut_id: str,
    event_sink: EventSink = append_event,
) -> ShipSealResult:
    """Issue or explicitly refuse a seal from canonical on-disk inputs.

    This function is the shipping-authority boundary. Kernel consumers can
    produce passed proofs and delivered records, but only this vc-ship step
    calls ``seal.issue_seal`` and persists ``delivery-seal.json``.
    """

    store = DeliveryStore(run_dir)
    try:
        proof = store.read_proof_result()
        record = store.read_delivery_record()
        reasons = list(proof.refusal_reasons) + list(record.refusal_reasons)
        if proof.state is not ProofState.PASSED:
            reasons.insert(0, f"proof.{proof.state.value}: seal refused")
        if record.state is not DeliveryState.DELIVERED:
            reasons.insert(0, f"delivery.{record.state.value}: seal refused")
        if reasons:
            raise seal.SealRefusedError("; ".join(dict.fromkeys(reasons)))
        components = _seal_components(
            store, run_id=run_id, lifecycle_id=lifecycle_id, cut_id=cut_id
        )
        issued = seal.issue_seal(record, issuer=SHIP_ISSUER, components=components)
        store.write_delivery_seal(issued)
    except (DeliveryStoreError, seal.SealError, OSError, ValueError) as exc:
        reason = str(exc)
        refusal = {
            "schema": "vibecrafted.delivery-seal-refusal.v1",
            "run_id": run_id,
            "issuer": SHIP_ISSUER,
            "delivery_state": DeliveryState.UNVERIFIED.value,
            "reason": reason,
        }
        atomic_write_json(store.path(SEAL_REFUSAL_PATH), refusal)
        event = event_sink(
            "delivery.seal_refused", run_id, "vc-ship refused DeliverySeal", refusal
        )
        return ShipSealResult(
            delivery_state=DeliveryState.UNVERIFIED,
            seal=None,
            refusal_reasons=(reason,),
            event=event,
        )

    event_payload = {
        "seal_id": issued.seal_id,
        "issuer": issued.issuer,
        "delivery_state": DeliveryState.SEALED.value,
        "declared_scope": issued.declared_scope,
        "checked_scope": issued.checked_scope,
    }
    event = event_sink(
        DeliveryEventKind.DELIVERY_SEALED.value,
        run_id,
        "vc-ship issued DeliverySeal",
        event_payload,
    )
    return ShipSealResult(
        delivery_state=DeliveryState.SEALED,
        seal=issued,
        refusal_reasons=(),
        event=event,
    )


def build_ship_prompt(agent: str, checkpoint: str, prompt: str) -> str:
    return "\n".join(
        [
            "VC-SHIP interactive supervisor loop.",
            "",
            f"agent: {agent}",
            f"checkpoint: {checkpoint}",
            "",
            "Rules:",
            "- Keep LOOP active until the ship checkpoint is genuinely handled.",
            "- Before final answer, run: vc-loop next",
            "- Complete only with: vc-loop complete --promise VC_SHIP_DONE",
            "- Use Loctree + AICX as constant context when prior intent matters.",
            "",
            "--- INPUT ---",
            prompt,
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in _control_verbs():
        from .lifecycle_control import lifecycle_control_main

        return lifecycle_control_main(args_list, workflow_id="vc-ship")
    parser = argparse.ArgumentParser(prog="vc-ship")
    parser.add_argument("agent", nargs="?", default="codex")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("-f", "--file", default="")
    parser.add_argument("-p", "--prompt", default="")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--root", default="")
    parser.add_argument("--start-stage", default="")
    parser.add_argument("--await-stages", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--loop-only", action="store_true")
    args = parser.parse_args(args_list)

    if args.agent not in SUPPORTED_AGENTS:
        ui.err(
            f"unknown agent: {args.agent}",
            fix="use one of: claude · codex · gemini · agy · junie · grok",
        )
        return 1
    if args.loop_only:
        prompt = args.prompt or DEFAULT_SHIP_PROMPT
        if args.file:
            prompt = Path(args.file).expanduser().read_text(encoding="utf-8")
        loop_prompt = build_ship_prompt(
            args.agent, args.checkpoint or "scaffold", prompt
        )
        return loop.main(
            [
                "start",
                "--prompt",
                loop_prompt,
                "--completion-promise",
                "VC_SHIP_DONE",
                "--max-iterations",
                str(args.max_iterations),
            ]
        )

    # Operator invariant: stage workers fly VISIBLY, in vc-frame tabs, whenever
    # a live operator session can host them. Route through the same resolution
    # the rest of the fleet uses (cli._default_runtime → "terminal" on live
    # session/TTY, "headless" only as the degrade-not-die fallback) instead of
    # hardcoding headless. Continuations inherit spec.runtime via the baton.
    from .cli import _default_runtime

    root = args.root or str(Path.cwd())
    state = run_lifecycle(
        LifecycleRunSpec(
            workflow_id="vc-ship",
            agent=args.agent,
            # The default prompt must not shadow --file: the runner resolves
            # `spec.prompt or read(spec.file)`, so a --file mission needs an
            # empty prompt to actually reach the stage workers.
            prompt=args.prompt or ("" if args.file else DEFAULT_SHIP_PROMPT),
            file=args.file,
            root=root,
            runtime=_default_runtime(args.runtime, root),
            await_stages=args.await_stages,
            start_stage=args.start_stage or args.checkpoint or "scaffold",
        )
    )
    print("==================== VC-SHIP LIFECYCLE RECEIPT ====================")
    print(f"run_id:     {state.get('run_id')}")
    print(f"workflow:   {state.get('workflow')}")
    print(f"status:     {state.get('status')}")
    axes = delivery_axes_for_receipt(str(state.get("status") or ""), state)
    print(f"execution:  {axes['execution_state']}")
    print(f"proof:      {axes['proof_state']}")
    print(f"delivery:   {axes['delivery_state']}")
    print(f"state:      {state.get('state_path')}")
    print(f"report:     {state.get('report_path')}")
    print("===================================================================")
    return 0 if state.get("status") in {"launching", "completed"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

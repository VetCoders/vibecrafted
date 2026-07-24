"""Fail-closed import boundary for legacy dispatch verifier commands."""

from __future__ import annotations

from typing import Any


def import_verify_run(command: str) -> dict[str, Any]:
    """Wrap ``Verify.run`` as an unqualified historical assertion.

    The adapter preserves the command for reconstruction while making the
    absence of subject binding explicit.  It is not a ProofResult and cannot
    become seal authority on its own.
    """

    value = str(command or "").strip()
    if not value:
        raise ValueError("legacy Verify.run command must not be empty")
    return {
        "schema": "vibecrafted.legacy-verify-assertion.v1",
        "kind": "legacy-verify-run",
        "run": value,
        "qualification": "unqualified",
        "subject_output_bound": False,
        "proof_state": "undeclared",
        "delivery_state": "unverified",
        "seal_eligible": False,
        "refusal_reason": "legacy Verify.run has no qualified subject evidence",
    }

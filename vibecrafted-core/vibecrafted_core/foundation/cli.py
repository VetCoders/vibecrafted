from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .service import (
    FoundationError,
    latest_receipt_path,
    seal_repository,
    verify_receipt,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibecrafted foundation")
    sub = parser.add_subparsers(dest="action", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--root", default=".")
    seal.add_argument("--authority", default="")
    seal.add_argument("--authority-source", default="operator")
    seal.add_argument("--run-id", default="")
    seal.add_argument("--created-by", default="operator")
    seal.add_argument("--output", default="")
    seal.add_argument("--plan", default="")
    seal.add_argument("--lease", default="")
    seal.add_argument("--no-fetch", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--root", default=".")
    verify.add_argument("--receipt", default="")
    verify.add_argument("--plan", default="")
    status = sub.add_parser("status")
    status.add_argument("--root", default=".")
    status.add_argument("--receipt", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "seal":
            lease = None
            if args.lease:
                lease_payload = json.loads(
                    Path(args.lease).expanduser().read_text(encoding="utf-8")
                )
                if not isinstance(lease_payload, dict):
                    raise FoundationError("destructive lease must be a JSON object")
                lease = lease_payload
            receipt, path = seal_repository(
                args.root,
                authority_ref=args.authority,
                authority_source=args.authority_source,
                run_id=args.run_id,
                created_by=args.created_by,
                output=args.output or None,
                fetch=not args.no_fetch,
                plan_path=args.plan or None,
                lease=lease,
            )
            payload = {
                "status": receipt.status.value,
                "receipt_path": str(path),
                "receipt_hash": receipt.receipt_hash,
                "authority_ref": receipt.repository.authority_ref,
                "authority_sha": receipt.repository.authority_sha.value,
                "relation": receipt.repository.relation.value,
                "decision_reasons": list(receipt.decision_reasons),
            }
        else:
            target = (
                Path(args.receipt).expanduser()
                if args.receipt
                else latest_receipt_path(args.root)
            )
            payload = verify_receipt(
                target, root=args.root, plan_path=getattr(args, "plan", "") or None
            )
    except FoundationError as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"SEALED", "OBSERVED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

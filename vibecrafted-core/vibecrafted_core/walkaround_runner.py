"""Installed trust boundary for Vibecrafted release and walk-around verification."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import product_contract


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser(
        "trust-probe",
        help="verify a domain-separated challenge with the packaged release key",
    )
    probe.add_argument("challenge", type=Path)
    probe.add_argument("signature", type=Path)
    verify = commands.add_parser(
        "verify",
        help="verify the signed release output and mounted-DMG walk-around",
    )
    verify.add_argument("release_output", type=Path)
    verify.add_argument("release_signature", type=Path)
    verify.add_argument("app", type=Path)
    verify.add_argument("dmg", type=Path)
    verify.add_argument("walkaround", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "trust-probe":
            product_contract.verify_trust_probe(args.challenge, args.signature)
        else:
            product_contract.verify_walkaround(
                args.walkaround,
                release_output_path=args.release_output,
                release_signature_path=args.release_signature,
                app_path=args.app,
                dmg_path=args.dmg,
            )
    except product_contract.ProductContractError as exc:
        print(f"VCPC{exc.code:03d}: {exc}", file=sys.stderr)
        return exc.code
    print(f"verified {args.command}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

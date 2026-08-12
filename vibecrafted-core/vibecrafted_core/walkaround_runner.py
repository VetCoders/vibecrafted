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
        "verify-release",
        help="verify the signed release output and its selected DMG/app",
    )
    verify.add_argument("--release-output", type=Path, required=True)
    verify.add_argument("--signature", type=Path, required=True)
    walkaround = commands.add_parser(
        "walkaround",
        help="verify canonical walk-around evidence for one signed release",
    )
    walkaround.add_argument("--release-output", type=Path, required=True)
    walkaround.add_argument("--signature", type=Path, required=True)
    walkaround.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "trust-probe":
            product_contract.verify_trust_probe(args.challenge, args.signature)
        elif args.command == "verify-release":
            product_contract.verify_release_output(args.release_output, args.signature)
        else:
            product_contract.produce_walkaround(
                args.release_output,
                args.signature,
                args.output,
            )
    except product_contract.ProductContractError as exc:
        print(f"VCPC{exc.code:03d}: {exc}", file=sys.stderr)
        return exc.code
    print(f"verified {args.command}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

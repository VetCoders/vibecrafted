from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .model import Dispatch
from .schema import doctor_dispatch


@dataclass(frozen=True)
class DoctorError:
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    errors: tuple[DoctorError, ...]
    dispatch: Dispatch | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [error.to_dict() for error in self.errors],
        }


def diagnose_text(text: str, *, base_dir: str | Path | None = None) -> DoctorReport:
    result = doctor_dispatch(text, base_dir=base_dir)
    errors = tuple(_structured_error(error) for error in result.errors)
    return DoctorReport(ok=not errors, errors=errors, dispatch=result.dispatch)


def diagnose_file(path: str | Path) -> DoctorReport:
    source = Path(path).expanduser()
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        return DoctorReport(
            ok=False,
            errors=(DoctorError(path=str(source), message=f"unreadable file: {exc}"),),
            dispatch=None,
        )
    return diagnose_text(text, base_dir=source.parent)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dispatch-doctor",
        description="Validate a vibecrafted.dispatch.v1 TOML file.",
    )
    parser.add_argument("dispatch_file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = diagnose_file(args.dispatch_file)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    elif report.ok:
        print("dispatch-doctor: ok")
    else:
        for error in report.errors:
            print(f"{error.path}: {error.message}")
    return 0 if report.ok else 1


def _structured_error(error: str) -> DoctorError:
    path, separator, message = error.partition(":")
    if not separator:
        return DoctorError(path="dispatch", message=error)
    return DoctorError(path=path.strip() or "dispatch", message=message.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

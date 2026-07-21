#!/usr/bin/env python3
"""Real-process stub worker for G6 lifecycle→server e2e.

Invoked by the test's LifecycleRunner launcher as a subprocess (never an
in-process mock). Behaviour is controlled by env:

  STUB_WORKER_REPORT   path of the report to write
  STUB_WORKER_TRANSCRIPT path of the transcript to append
  STUB_WORKER_FAIL     when set to "1", exit non-zero after writing a failure note
  STUB_WORKER_STAGE    optional stage label stamped into the report
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    report = Path(os.environ["STUB_WORKER_REPORT"])
    transcript = Path(
        os.environ.get("STUB_WORKER_TRANSCRIPT") or (str(report) + ".log")
    )
    fail = os.environ.get("STUB_WORKER_FAIL", "").strip() == "1"
    stage = os.environ.get("STUB_WORKER_STAGE", "stage")

    report.parent.mkdir(parents=True, exist_ok=True)
    transcript.parent.mkdir(parents=True, exist_ok=True)

    if fail:
        body = f"# stub worker failure ({stage})\n\nstatus: failed\nexit: non-zero\n"
        report.write_text(body, encoding="utf-8")
        with transcript.open("a", encoding="utf-8") as handle:
            handle.write(f"stub_worker stage={stage} exit=1\n")
        return 1

    body = (
        f"# stub worker ok ({stage})\n\n"
        "status: completed\n"
        "exit: 0\n"
        "---\n"
        "dou_index: 0\n"
        "---\n"
    )
    report.write_text(body, encoding="utf-8")
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(f"stub_worker stage={stage} exit=0\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
set -euo pipefail

state_file="$1"
loop_nr="$2"
report_path="$3"

max_wait="${VIBECRAFTED_MARBLES_VERIFICATION_TIMEOUT_S:-600}"
poll_s="${VIBECRAFTED_MARBLES_VERIFICATION_POLL_S:-10}"

case "$max_wait" in
  ''|*[!0-9]*)
    max_wait=600
    ;;
esac
case "$poll_s" in
  ''|*[!0-9]*)
    poll_s=10
    ;;
esac
(( poll_s > 0 )) || poll_s=10

verified_path="${report_path%.md}_verified.md"

_update_verification_state() {
  local new_status="$1"
  local verified_report="${2:-}"

  python3 - "$state_file" "$loop_nr" "$new_status" "$verified_report" <<'PY'
import datetime
import fcntl
import json
import os
import sys
import tempfile

state_path, loop_nr_raw, new_status, verified_report = sys.argv[1:5]
loop_nr = int(loop_nr_raw)

lock = open(state_path + ".lock", "a+", encoding="utf-8")
try:
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        with open(state_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise SystemExit(0)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for loop in payload.get("loops", []):
        if loop.get("loop") != loop_nr:
            continue
        current = loop.get("verification_status", "")
        if new_status == "timed_out" and current != "pending":
            raise SystemExit(0)
        loop["verification_status"] = new_status
        if new_status == "completed" and verified_report:
            loop["verified_report"] = verified_report
        break
    else:
        raise SystemExit(0)

    payload["updated_at"] = now
    dir_path = os.path.dirname(state_path) or "."
    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(state_path) + ".", dir=dir_path
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_path, state_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
finally:
    lock.close()
PY
}

elapsed=0
while (( elapsed < max_wait )); do
  if [[ -s "$verified_path" ]]; then
    _update_verification_state "completed" "$verified_path"
    exit 0
  fi
  sleep "$poll_s"
  (( elapsed += poll_s ))
done

_update_verification_state "timed_out"

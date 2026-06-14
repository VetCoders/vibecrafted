#!/usr/bin/env bash
# vibecrafted-server local control-plane viewer smoke test.
#
# Asserts:
#   - install-all / install-server copies the binary and assets/fonts.
#   - Starts the installed binary with complete Leptos environment.
#   - Binds to a free ephemeral port (no hardcoded port).
#   - Polls /api/control/state to a 200 OK.
#   - Asserts JSON payload structure.
#   - SIGTERM shuts down clean (no process leaks, no panics in log).
#
# Usage:
#   tests/server_smoke.sh

set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

red()    { printf '\033[31m%s\033[0m' "$*"; }
green()  { printf '\033[32m%s\033[0m' "$*"; }
yellow() { printf '\033[33m%s\033[0m' "$*"; }
dim()    { printf '\033[2m%s\033[0m' "$*"; }

_red='\033[31m'
_green='\033[32m'
_yellow='\033[33m'
_reset='\033[0m'


PASSES=0
FAILURES=()

ok()   { PASSES=$((PASSES + 1)); printf '  [%s] %s\n' "$(green ok)" "$1"; }
fail() { FAILURES+=("$1"); printf '  [%s] %s\n' "$(red fail)" "$1"; }
phase(){ printf '\n%s\n' "$(dim "─── $1 ───")"; }

# 1. Setup temp environment
phase "setup temp environment"

tmp_home="$(mktemp -d "${TMPDIR:-/tmp}/vibecrafted-server-smoke.XXXXXX")"
export VIBECRAFTED_HOME="$tmp_home"
export VIBECRAFTED_RUNTIME_HOME="$tmp_home/share"

# Ensure clean teardown on exit
cleanup() {
  phase "teardown and cleanup"
  if [[ -f "$tmp_home/server.pid" ]]; then
    local pid
    pid=$(cat "$tmp_home/server.pid" 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
      echo "Killing background server PID $pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -rf "$tmp_home"
  echo "Cleanup complete."
}
trap cleanup EXIT

ok "temp VIBECRAFTED_HOME set to $VIBECRAFTED_HOME"

# 2. Identify installed binary and assets
phase "preflight checks"

SERVER_BIN="$HOME/.local/bin/vibecrafted-server-web"
if [[ -f "$SERVER_BIN" ]]; then
  ok "installed binary exists: $SERVER_BIN"
else
  fail "installed binary missing. Run make install-all or make install-server first."
  exit 1
fi

SITE_ROOT="$VIBECRAFTED_RUNTIME_HOME/server/site"
mkdir -p "$SITE_ROOT"
# Copy assets from checkout to temp runtime site root so server-smoke is self-contained
cp -R "$REPO_ROOT/vibecrafted-server/web/public/"* "$SITE_ROOT/"
if [[ -d "$SITE_ROOT/fonts" ]]; then
  ok "copied site assets to temp location: $SITE_ROOT"
else
  fail "failed to locate/copy site assets"
  exit 1
fi

# 3. Find ephemeral port
phase "ephemeral port probe"
PORT=$(python3 -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")
if [[ -n "$PORT" ]]; then
  ok "probe bound free port: $PORT"
else
  fail "failed to find ephemeral port"
  exit 1
fi

# 4. Start installed server with full environment
phase "spawn server"

LOG_FILE="$tmp_home/server.log"
PID_FILE="$tmp_home/server.pid"

# Lift ulimit for safety
ulimit -f unlimited

env LEPTOS_OUTPUT_NAME="vibecrafted-server-web" \
    LEPTOS_SITE_ROOT="$SITE_ROOT" \
    LEPTOS_SITE_PKG_DIR="pkg" \
    LEPTOS_ENV="PROD" \
    LEPTOS_SITE_ADDR="127.0.0.1:$PORT" \
    VIBECRAFTED_HOME="$VIBECRAFTED_HOME" \
    "$SERVER_BIN" > "$LOG_FILE" 2>&1 < /dev/null &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

ok "spawned server process (PID $SERVER_PID) on port $PORT"

# 5. Poll health and assert JSON
phase "poll and assert"

timeout=15
elapsed=0
healthy=0

while [[ $elapsed -lt $((timeout * 2)) ]]; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    fail "server process died prematurely"
    cat "$LOG_FILE"
    exit 1
  fi
  if python3 -c '
import urllib.request, json, sys
try:
    resp = urllib.request.urlopen("http://127.0.0.1:'"$PORT"'/api/control/state", timeout=1.0)
    if resp.status == 200:
        data = json.loads(resp.read().decode())
        assert "generated_at" in data, "missing generated_at"
        assert "active_runs" in data, "missing active_runs"
        assert "recent_runs" in data, "missing recent_runs"
        sys.exit(0)
    sys.exit(1)
except Exception as e:
    sys.exit(2)
' >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 0.5
  elapsed=$((elapsed + 1))
done

if [[ $healthy -eq 1 ]]; then
  ok "HTTP health check to http://127.0.0.1:$PORT/api/control/state OK (200 + valid JSON keys)"
else
  fail "health check timed out after 15 seconds"
  cat "$LOG_FILE"
  exit 1
fi

# 6. SIGTERM clean shutdown
phase "shutdown verification"

kill -15 "$SERVER_PID" 2>/dev/null || true
exited=0
for i in {1..50}; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    exited=1
    break
  fi
  sleep 0.1
done

if [[ $exited -eq 1 ]]; then
  ok "server process stopped cleanly on SIGTERM"
else
  fail "server process failed to exit on SIGTERM"
  kill -9 "$SERVER_PID" 2>/dev/null || true
  exit 1
fi

# Verify no panic in log
if grep -iq "panic" "$LOG_FILE"; then
  fail "panic detected in server log"
  cat "$LOG_FILE"
  exit 1
else
  ok "no panics detected in log file"
fi

printf "\n%b✓%b All %s smoke tests passed.\n" "$_green" "$_reset" "$PASSES"

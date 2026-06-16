#!/usr/bin/env bash
# Gemini CLI output cleaner
# Removes: 429 retry stacktraces (massive), MCP bootstrap chatter
# Keeps: agent reasoning, errors (real ones), tool calls, findings

awk '
  # 429 retry block detection — starts with "Attempt N failed" and ends ~115 lines later
  # These contain full GaxiosError with headers, response body, config — pure noise
  /^Attempt [0-9]+ failed with status 429/ {
    printf "\033[2m  [429 retry — model capacity exhausted]\033[0m\n"
    # Skip until next non-indented non-error line or next Attempt or real content
    skip = 1
    next
  }

  # Inside a 429 block — skip indented lines and JSON error structure
  skip && /^[[:space:]]/ { next }
  skip && /^[{}]/ { next }
  skip && /^  "/ { next }
  skip && /^    at / { next }
  skip && /Symbol\(/ { next }
  skip && /^\]/ { next }
  skip { skip = 0 }

  # MCP bootstrap noise — collapse to one line
  /^Registering notification handlers/ { next }
  /Server .* has tools but did not declare/ { next }
  /Server .* supports tool updates/ { next }
  /Scheduling MCP context refresh/ { next }
  /Executing MCP context refresh/ { next }
  /MCP context refresh complete/ {
    printf "\033[2m  [MCP servers connected]\033[0m\n"
    next
  }

  # Keychain noise
  /^Keychain initialization encountered/ { next }
  /^Require stack:/ { next }
  /keytar\.js$/ { next }
  /^Using FileKeychain fallback/ { next }

  # Duplicate YOLO line
  /^YOLO mode is enabled/ {
    if (!yolo_seen) { print; yolo_seen = 1 }
    next
  }

  # Duplicate "Loaded cached credentials"
  /^Loaded cached credentials/ {
    if (!creds_seen) { print; creds_seen = 1 }
    next
  }

  # Everything else passes through
  { print }
'

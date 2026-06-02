#!/usr/bin/env bash
# Normalize UniFFI generated files so build runs do not leave whitespace churn.

set -euo pipefail

BRIDGE_DIR="${1:-app/Vibecrafted/Bridge}"

perl -0pi -e 's/[ \t]+$//mg; s/\n+\z/\n/' \
  "${BRIDGE_DIR}/vibecrafted_shell_ffi.swift" \
  "${BRIDGE_DIR}/vibecrafted_shell_ffiFFI.h"

#!/usr/bin/env bash
# common.sh — thin aggregator, sources all library modules.
# Consumer interface unchanged: `source "$SCRIPT_DIR/common.sh"`

_SPAWN_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)"

# Load order matters: util first (no deps), then paths, then the rest.
source "$_SPAWN_LIB_DIR/util.sh"
source "$_SPAWN_LIB_DIR/paths.sh"
source "$_SPAWN_LIB_DIR/meta.sh"
source "$_SPAWN_LIB_DIR/frontier.sh"
source "$_SPAWN_LIB_DIR/lock.sh"
source "$_SPAWN_LIB_DIR/prompt.sh"
source "$_SPAWN_LIB_DIR/session_ambient.sh"
source "$_SPAWN_LIB_DIR/session.sh"
source "$_SPAWN_LIB_DIR/launcher_terminal.sh"
source "$_SPAWN_LIB_DIR/launcher_watch.sh"
source "$_SPAWN_LIB_DIR/launcher.sh"
source "$_SPAWN_LIB_DIR/zellij_monitor.sh"
source "$_SPAWN_LIB_DIR/zellij.sh"
source "$_SPAWN_LIB_DIR/ancestor.sh"
source "$_SPAWN_LIB_DIR/rotation.sh"

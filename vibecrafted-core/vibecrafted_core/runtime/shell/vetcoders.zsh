# Canonical zsh entrypoint. The implementation remains shell-compatible and
# lives next to this file; this is a real source shim, never a filesystem alias.
source "${${(%):-%N}:A:h}/vetcoders.sh"

"""Continuity kernel package — provider capability authority lives here.

`capabilities` is the ONE declarative provider capability table (spec §7);
every continuity surface (kernel resolver, deck, MCP, TUI) consumes it and
no other module may declare provider resume/fork capability.
"""

from __future__ import annotations

from .capabilities import (
    CAPABILITIES,
    EVIDENCE_ONLY,
    EXECUTABLE,
    PROBE_CONFIRMED,
    PROBE_EVIDENCE_ONLY,
    PROBE_FAILED,
    PROBE_UNSUPPORTED,
    SUPPORTED,
    TERMINAL_ONLY,
    UNSUPPORTED,
    UNVERIFIED,
    ProbeRecipe,
    ProbeResult,
    ProviderCapability,
    capability_for,
    capability_registry,
    clear_probe_cache,
    probe,
    probe_provider,
)

__all__ = [
    "CAPABILITIES",
    "EVIDENCE_ONLY",
    "EXECUTABLE",
    "PROBE_CONFIRMED",
    "PROBE_EVIDENCE_ONLY",
    "PROBE_FAILED",
    "PROBE_UNSUPPORTED",
    "SUPPORTED",
    "TERMINAL_ONLY",
    "UNSUPPORTED",
    "UNVERIFIED",
    "ProbeRecipe",
    "ProbeResult",
    "ProviderCapability",
    "capability_for",
    "capability_registry",
    "clear_probe_cache",
    "probe",
    "probe_provider",
]

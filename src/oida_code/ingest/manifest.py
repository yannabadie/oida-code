"""Detect project manifests (pyproject, setup.py, package.json, …).

Phase 1 exposes only ``default_python_commands`` — a deterministic default for
``AuditRequest.commands`` when no custom manifest probe is available. Real
manifest auto-detection is phase 2 (blueprint days 3-4).
"""

from __future__ import annotations

from oida_code.models.audit_request import CommandsSpec


def default_python_commands() -> CommandsSpec:
    """Return the stock Python verification commands for v0.

    These match the MVP scope (blueprint §4 ``Languages`` = Python only).
    """
    return CommandsSpec(
        lint="ruff check .",
        types="mypy .",
        tests="pytest -q",
    )


def detect_commands(repo_path: object) -> CommandsSpec:  # pragma: no cover - phase 2
    """Auto-detect verification commands from the repo manifest. Phase 2."""
    raise NotImplementedError(
        "Manifest auto-detection is a phase-2 concern (blueprint days 3-4)."
    )


__all__ = ["default_python_commands", "detect_commands"]

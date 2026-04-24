"""Translate between Pydantic ``NormalizedScenario`` and vendored ``Scenario``.

Phase 2. See blueprint §13 days 7-8.
"""

from __future__ import annotations


def pydantic_to_vendored(scenario: object) -> object:  # pragma: no cover - phase 2
    """Convert a :class:`NormalizedScenario` to the vendored dataclass form."""
    raise NotImplementedError("Scenario mapper is a phase-2 concern (blueprint §13).")


def vendored_to_pydantic(scenario: object) -> object:  # pragma: no cover - phase 2
    """Convert a vendored ``Scenario`` back to the Pydantic surface."""
    raise NotImplementedError("Scenario mapper is a phase-2 concern (blueprint §13).")


__all__ = ["pydantic_to_vendored", "vendored_to_pydantic"]

"""Deterministic OIDA scoring layer.

Re-exports the vendored ``OIDAAnalyzer`` (blueprint §2: reuse, do not rewrite).
The Pydantic ↔ dataclass mapper and verdict logic are phase-2 concerns.
"""

from oida_code.score.analyzer import (
    AnalyzerConfig,
    Event,
    OIDAAnalyzer,
    PatternLedger,
    Precondition,
    Scenario,
    load_scenario,
    save_report,
)

__all__ = [
    "AnalyzerConfig",
    "Event",
    "OIDAAnalyzer",
    "PatternLedger",
    "Precondition",
    "Scenario",
    "load_scenario",
    "save_report",
]

"""Central runtime configuration (thresholds, paths, feature flags).

Phase 1 exposes no public surface beyond module-level defaults derived from the
vendored ``AnalyzerConfig``. A richer config loader (per-project ``.oida.toml``)
is a phase-2 concern — see blueprint §13 days 5-6.
"""

from __future__ import annotations

from oida_code._vendor.oida_framework.analyzer import AnalyzerConfig

DEFAULT_ANALYZER_CONFIG: AnalyzerConfig = AnalyzerConfig()

__all__ = ["DEFAULT_ANALYZER_CONFIG"]

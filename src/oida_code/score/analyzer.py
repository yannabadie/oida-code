"""Thin re-export shim over the vendored OIDA core (blueprint §2, §7).

Every formula (grounding, Q_obs, mu, lambda_bias, V_dur, H_sys, V_net,
double-loop repair) is owned by ``oida_code._vendor.oida_framework``. This
module exists so callers can write::

    from oida_code.score.analyzer import OIDAAnalyzer

instead of reaching into the private ``_vendor`` namespace.
"""

from oida_code._vendor.oida_framework.analyzer import (
    AnalyzerConfig,
    OIDAAnalyzer,
    PatternLedger,
)
from oida_code._vendor.oida_framework.io import load_scenario, save_report
from oida_code._vendor.oida_framework.models import Event, Precondition, Scenario

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

"""Pydantic v2 I/O models for the ``oida-code`` public boundary.

See blueprint §5 for the schema contracts. The three top-level models are:

* :class:`AuditRequest` — raw audit intake (Pass 1 input)
* :class:`NormalizedScenario` — deterministic-scorer input (Pass 2 input)
* :class:`AuditReport` — final verdict + repair plan (pipeline output)
"""

from __future__ import annotations

from oida_code.models.audit_report import (
    AuditReport,
    CriticalFinding,
    RepairPlan,
    ReportSummary,
)
from oida_code.models.audit_request import (
    AuditRequest,
    CommandsSpec,
    IntentSpec,
    PolicySpec,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
    ScenarioConfig,
)

__all__ = [
    "AuditReport",
    "AuditRequest",
    "CommandsSpec",
    "CriticalFinding",
    "IntentSpec",
    "NormalizedEvent",
    "NormalizedScenario",
    "PolicySpec",
    "PreconditionSpec",
    "RepairPlan",
    "RepoSpec",
    "ReportSummary",
    "ScenarioConfig",
    "ScopeSpec",
]

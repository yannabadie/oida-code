"""Pydantic v2 I/O models for the ``oida-code`` public boundary.

See PLAN.md §9 for schema versions.

* v1 (Phase 0): :class:`AuditRequest`, :class:`NormalizedScenario`, :class:`AuditReport`.
* v1.1 (Phase 1): + :class:`Finding`, :class:`ToolEvidence`, :class:`ToolBudgets`,
  :data:`VerdictLabel`.
"""

from __future__ import annotations

from oida_code.models.audit_report import (
    AuditReport,
    CriticalFinding,
    RepairPlan,
    ReportSummary,
    VerdictLabel,
)
from oida_code.models.audit_request import (
    AuditRequest,
    CommandsSpec,
    IntentSpec,
    PolicySpec,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.evidence import (
    EvidenceKind,
    Finding,
    Severity,
    ToolBudgets,
    ToolEvidence,
    ToolStatus,
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
    "EvidenceKind",
    "Finding",
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
    "Severity",
    "ToolBudgets",
    "ToolEvidence",
    "ToolStatus",
    "VerdictLabel",
]

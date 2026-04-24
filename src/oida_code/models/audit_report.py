"""Pydantic v2 model for the final audit report (blueprint §9 + PLAN.md §6, §12).

Schema v1.1 (2026-04-24):

* ``ReportSummary.mean_*`` / ``total_v_net`` / ``debt_final`` /
  ``corrupt_success_ratio`` are ``Optional[float]`` — a Phase-1 deterministic
  audit emits ``null`` for fields that require the full OIDA fusion (Phase 5).
  See ADR-13 for why "silently emit 0.0" is the trap we avoid.
* ``AuditReport.tool_evidence`` carries per-runner evidence so deterministic
  reports are useful before the scorer is wired.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.models.evidence import ToolEvidence

VerdictLabel = Literal[
    "verified",
    "counterexample_found",
    "insufficient_evidence",
    "corrupt_success",
]
"""The only four defensible verdicts (PLAN.md §6)."""


class ReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: VerdictLabel
    mean_q_obs: float | None = None
    mean_grounding: float | None = None
    total_v_net: float | None = None
    debt_final: float | None = None
    corrupt_success_ratio: float | None = None


class CriticalFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    kind: str
    evidence: list[str]
    path: str
    line: int


class RepairPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reopen: list[str] = Field(default_factory=list)
    audit: list[str] = Field(default_factory=list)
    next_prompts: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """Top-level pipeline output (blueprint §9 + PLAN.md §12)."""

    model_config = ConfigDict(extra="forbid")

    summary: ReportSummary
    critical_findings: list[CriticalFinding] = Field(default_factory=list)
    repair: RepairPlan = Field(default_factory=RepairPlan)
    tool_evidence: list[ToolEvidence] = Field(default_factory=list)


__all__ = [
    "AuditReport",
    "CriticalFinding",
    "RepairPlan",
    "ReportSummary",
    "VerdictLabel",
]

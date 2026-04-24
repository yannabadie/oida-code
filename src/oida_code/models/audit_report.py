"""Pydantic v2 model for the final audit report (blueprint §5, §9)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str
    mean_q_obs: float
    mean_grounding: float
    total_v_net: float
    debt_final: float
    corrupt_success_ratio: float


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
    """Top-level pipeline output (blueprint §9)."""

    model_config = ConfigDict(extra="forbid")

    summary: ReportSummary
    critical_findings: list[CriticalFinding] = Field(default_factory=list)
    repair: RepairPlan = Field(default_factory=RepairPlan)


__all__ = [
    "AuditReport",
    "CriticalFinding",
    "RepairPlan",
    "ReportSummary",
]

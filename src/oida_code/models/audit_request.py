"""Pydantic v2 model for the raw audit request (blueprint §5 A)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RepoSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    revision: str
    base_revision: str


class IntentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    sources: list[str] = Field(default_factory=list)


class ScopeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changed_files: list[str] = Field(default_factory=list)
    language: str = "python"


class CommandsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lint: str = ""
    types: str = ""
    tests: str = ""


class PolicySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_critical_findings: int = 0
    min_mutation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    min_property_checks: int = Field(default=0, ge=0)


class AuditRequest(BaseModel):
    """Raw audit intake produced by ``oida-code inspect`` (blueprint §5 A)."""

    model_config = ConfigDict(extra="forbid")

    repo: RepoSpec
    intent: IntentSpec = Field(default_factory=IntentSpec)
    scope: ScopeSpec = Field(default_factory=ScopeSpec)
    commands: CommandsSpec = Field(default_factory=CommandsSpec)
    policy: PolicySpec = Field(default_factory=PolicySpec)


__all__ = [
    "AuditRequest",
    "CommandsSpec",
    "IntentSpec",
    "PolicySpec",
    "RepoSpec",
    "ScopeSpec",
]

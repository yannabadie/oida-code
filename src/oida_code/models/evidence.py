"""Per-tool evidence + individual findings (Phase 1, advisor-vetted shape).

These models are the bridge between ``verify/*`` runners and the downstream
``score/verdict`` + ``report/*`` consumers. Every runner returns a
:class:`ToolEvidence` — never raises on missing binary, timeout, or non-zero
exit — so the CLI can treat CodeQL absence identically to semgrep absence:
``status="tool_missing"``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "warning", "info", "hint"]
"""Normalized severity across tools."""

EvidenceKind = Literal["static", "regression", "property", "mutation"]
"""What kind of evidence produced this finding.

* ``static``     — lint, types, SAST (ruff, mypy, semgrep, codeql).
* ``regression`` — a test failure from the existing test suite.
* ``property``   — a Hypothesis counterexample (Phase 2).
* ``mutation``   — a surviving mutant from mutmut (Phase 2).
"""

ToolStatus = Literal["ok", "tool_missing", "timeout", "error", "skipped"]
"""Outcome of invoking a tool.

* ``ok``            — tool ran to completion; ``findings`` may be empty.
* ``tool_missing``  — executable not on PATH; no evidence produced.
* ``timeout``       — tool exceeded its budget.
* ``error``         — tool ran but crashed; ``stderr_excerpt`` carries context.
* ``skipped``       — tool deliberately not run (policy, phase gate, …).
"""


class Finding(BaseModel):
    """One actionable signal from a deterministic tool."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    rule_id: str
    severity: Severity
    path: str
    line: int = Field(default=0, ge=0)
    column: int = Field(default=0, ge=0)
    message: str
    evidence_kind: EvidenceKind = "static"


class ToolEvidence(BaseModel):
    """Uniform return shape for every verifier runner.

    The contract is strict: runners must populate ``status`` and never raise.
    When ``status != "ok"``, ``findings`` is empty and ``stderr_excerpt`` (if
    relevant) carries the diagnostic.
    """

    model_config = ConfigDict(extra="forbid")

    tool: str
    status: ToolStatus
    duration_ms: int = Field(default=0, ge=0)
    findings: list[Finding] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    tool_version: str | None = None
    stderr_excerpt: str | None = None


class ToolBudgets(BaseModel):
    """Per-tool wall-clock budgets in seconds.

    Defaults match the advisor recommendation: pytest needs the most, lint the
    least. A repo's ``AuditRequest.budgets`` may override any subset.
    """

    model_config = ConfigDict(extra="forbid")

    lint: int = Field(default=30, ge=1)
    types: int = Field(default=60, ge=1)
    tests: int = Field(default=600, ge=1)
    semgrep: int = Field(default=120, ge=1)
    codeql: int = Field(default=900, ge=1)
    hypothesis: int = Field(default=300, ge=1)
    mutmut: int = Field(default=600, ge=1)


__all__ = [
    "EvidenceKind",
    "Finding",
    "Severity",
    "ToolBudgets",
    "ToolEvidence",
    "ToolStatus",
]

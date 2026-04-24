"""Deterministic verdict resolution (PLAN.md §6, Phase 1 path).

Phase 1 scope: three of the four labels are reachable without the LLM /
trajectory scorer / full OIDA fusion:

* ``verified``              — every enabled tool ran, zero critical findings.
* ``counterexample_found``  — any error-severity static finding OR any
                              pytest regression OR any surviving mutant.
* ``insufficient_evidence`` — tools missing, timed out, or errored such that
                              no defensible "verified" claim can be made.

``corrupt_success`` stays dark until Phase 5 (needs ``V_net`` from the full
OIDA fusion).

``PolicySpec.min_mutation_score`` and ``min_property_checks`` are **not**
enforced in Phase 1 — their inputs (mutmut, hypothesis) ship in Phase 2.
The resolver flags this by setting the evidence-rationale line accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass

from oida_code.models.audit_report import CriticalFinding, VerdictLabel
from oida_code.models.audit_request import PolicySpec
from oida_code.models.evidence import Finding, ToolEvidence

_COUNTEREXAMPLE_KINDS = {"regression", "property", "mutation"}


@dataclass(frozen=True, slots=True)
class VerdictResolution:
    """Output of the deterministic resolver."""

    label: VerdictLabel
    rationale: list[str]
    critical_findings: list[CriticalFinding]


def _is_critical(finding: Finding) -> bool:
    return finding.severity == "error" or finding.evidence_kind in _COUNTEREXAMPLE_KINDS


def _to_critical(finding: Finding, index: int) -> CriticalFinding:
    return CriticalFinding(
        id=f"f{index}",
        title=finding.message[:140] or f"{finding.tool}:{finding.rule_id}",
        kind=f"{finding.tool}.{finding.rule_id}",
        evidence=[finding.evidence_kind, finding.tool],
        path=finding.path,
        line=finding.line,
    )


def _any_counterexample(evidence: list[ToolEvidence]) -> list[Finding]:
    out: list[Finding] = []
    for ev in evidence:
        if ev.status != "ok":
            continue
        for f in ev.findings:
            if f.evidence_kind in _COUNTEREXAMPLE_KINDS:
                out.append(f)
    return out


def _critical_static(evidence: list[ToolEvidence]) -> list[Finding]:
    out: list[Finding] = []
    for ev in evidence:
        if ev.status != "ok":
            continue
        for f in ev.findings:
            if f.evidence_kind == "static" and f.severity == "error":
                out.append(f)
    return out


def _reachable_tools(evidence: list[ToolEvidence]) -> tuple[list[str], list[str]]:
    ok = [ev.tool for ev in evidence if ev.status == "ok"]
    unreachable = [ev.tool for ev in evidence if ev.status != "ok"]
    return ok, unreachable


def resolve_verdict(
    evidence: list[ToolEvidence],
    policy: PolicySpec,
) -> VerdictResolution:
    """Resolve a verdict from deterministic ``ToolEvidence`` only.

    See module docstring for the Phase 1 state machine. This function is pure:
    it never hits the filesystem and never raises.
    """
    rationale: list[str] = []
    counterexamples = _any_counterexample(evidence)
    critical_static = _critical_static(evidence)

    combined = counterexamples + critical_static
    critical_findings = [_to_critical(f, i + 1) for i, f in enumerate(combined)]

    reachable_ok, unreachable = _reachable_tools(evidence)
    rationale.append(
        f"tools ok={sorted(set(reachable_ok))}; unreachable={sorted(set(unreachable))}"
    )

    if counterexamples:
        rationale.append(
            f"counterexample(s) found by {sorted({f.tool for f in counterexamples})} "
            f"(n={len(counterexamples)})"
        )
        return VerdictResolution(
            label="counterexample_found",
            rationale=rationale,
            critical_findings=critical_findings,
        )

    if len(critical_static) > policy.max_critical_findings:
        rationale.append(
            f"{len(critical_static)} error-severity static findings exceed "
            f"policy.max_critical_findings={policy.max_critical_findings}"
        )
        return VerdictResolution(
            label="counterexample_found",
            rationale=rationale,
            critical_findings=critical_findings,
        )

    if unreachable:
        rationale.append(
            "insufficient_evidence: one or more tools did not run cleanly; "
            "cannot claim verified without their signal."
        )
        return VerdictResolution(
            label="insufficient_evidence",
            rationale=rationale,
            critical_findings=critical_findings,
        )

    rationale.append(
        "all enabled tools returned ok with 0 critical findings "
        "(note: Phase-1 path — Hypothesis, mutmut, and agentic verifier not evaluated)."
    )
    return VerdictResolution(
        label="verified",
        rationale=rationale,
        critical_findings=critical_findings,
    )


__all__ = ["VerdictResolution", "resolve_verdict"]

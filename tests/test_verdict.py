"""Tests for :mod:`oida_code.score.verdict`."""

from __future__ import annotations

from oida_code.models.audit_request import PolicySpec
from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.score.verdict import resolve_verdict


def _evidence_ok(tool: str, findings: list[Finding] | None = None) -> ToolEvidence:
    return ToolEvidence(
        tool=tool,
        status="ok",
        findings=findings or [],
    )


def _evidence_missing(tool: str) -> ToolEvidence:
    return ToolEvidence(tool=tool, status="tool_missing")


def _static_error(tool: str, rule: str = "X001") -> Finding:
    return Finding(
        tool=tool,
        rule_id=rule,
        severity="error",
        path="x.py",
        line=1,
        message="problem",
        evidence_kind="static",
    )


def _regression(tool: str = "pytest") -> Finding:
    return Finding(
        tool=tool,
        rule_id="tests.test_x::test_y",
        severity="error",
        path="tests/test_x.py",
        line=10,
        message="AssertionError",
        evidence_kind="regression",
    )


def test_all_clean_yields_verified() -> None:
    evidence = [_evidence_ok("ruff"), _evidence_ok("mypy"), _evidence_ok("pytest")]
    result = resolve_verdict(evidence, PolicySpec())
    assert result.label == "verified"
    assert result.critical_findings == []


def test_regression_yields_counterexample() -> None:
    evidence = [_evidence_ok("ruff"), _evidence_ok("pytest", [_regression()])]
    result = resolve_verdict(evidence, PolicySpec())
    assert result.label == "counterexample_found"
    assert len(result.critical_findings) == 1


def test_static_error_exceeds_threshold_yields_counterexample() -> None:
    evidence = [_evidence_ok("ruff", [_static_error("ruff")])]
    # default PolicySpec.max_critical_findings = 0 → any error pushes to counterexample
    result = resolve_verdict(evidence, PolicySpec())
    assert result.label == "counterexample_found"


def test_static_error_under_threshold_does_not_fail() -> None:
    evidence = [_evidence_ok("ruff", [_static_error("ruff")])]
    policy = PolicySpec(max_critical_findings=5)
    result = resolve_verdict(evidence, policy)
    # With higher tolerance + all tools ok, label is 'verified'.
    assert result.label == "verified"


def test_tool_missing_yields_insufficient_evidence() -> None:
    evidence = [_evidence_ok("ruff"), _evidence_missing("semgrep")]
    result = resolve_verdict(evidence, PolicySpec())
    assert result.label == "insufficient_evidence"


def test_corrupt_success_is_not_reachable_in_phase_1() -> None:
    # Phase 1 resolver never emits corrupt_success even on heavy evidence —
    # that label requires V_net from Phase 5 fusion.
    evidence = [_evidence_ok("ruff")]
    policy = PolicySpec()
    result = resolve_verdict(evidence, policy)
    assert result.label != "corrupt_success"

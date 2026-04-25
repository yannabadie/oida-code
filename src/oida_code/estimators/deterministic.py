"""E3.2 (QA/A14.md, ADR-24) — deterministic baseline estimators.

Pure deterministic estimators for the load-bearing OIDA fields. No LLM
is consulted from this module. Each estimator returns a
:class:`SignalEstimate` carrying its own provenance, confidence, and
warnings — never authoritative on its own at v0.4.x because:

* ``capability``    — needs LLM/intent analysis to be real (Phase 4).
                      The deterministic baseline returns a neutral
                      ``0.5`` with ``source="default"`` so the
                      readiness gate stays blocked.
* ``benefit``       — by ADR-24 §benefit, no signal without an intent
                      reference. Without :attr:`AuditRequest.intent`
                      we return ``source="missing"``.
* ``observability`` — has a deterministic surface (test files exist
                      vs not, negative-path patterns) but stays
                      ``source="heuristic"`` until real signals from
                      Phase-4 (logging detection, error-path coverage).
* ``completion``    — built directly from ``EventEvidenceView.pytest_*``;
                      ``source="test_result"`` on relevant tests,
                      ``"heuristic"`` on global-only signals.
* ``tests_pass``    — same view, weighted (``source="test_result"``).
* ``operator_accept`` — built from ruff/mypy findings on the event's
                      scope; ``source="static_analysis"`` when at least
                      one tool ran ok.

ADR-24 hard rule: defaults must be flagged ``is_default=True`` and the
confidence-0.0 contract is enforced by :class:`SignalEstimate`'s
validator.
"""

from __future__ import annotations

from collections.abc import Iterable

from oida_code.estimators.contracts import (
    EstimateField,
    EstimateSource,
    SignalEstimate,
)
from oida_code.models.audit_request import AuditRequest
from oida_code.score.event_evidence import (
    EventEvidenceView,
    event_completion_from_view,
    event_operator_accept_from_view,
    event_tests_pass_from_view,
)

_METHOD_VERSION = "e3.2-2026-04-25"


def _missing(field: EstimateField, event_id: str | None, *, reason: str) -> SignalEstimate:
    return SignalEstimate(
        field=field,
        event_id=event_id,
        value=0.5,
        confidence=0.0,
        source="missing",
        method_id=f"missing.{field}",
        method_version=_METHOD_VERSION,
        evidence_refs=(),
        warnings=(reason,),
        blockers=(reason,),
        is_default=False,
        is_authoritative=False,
    )


def _default(field: EstimateField, event_id: str | None, *, reason: str) -> SignalEstimate:
    return SignalEstimate(
        field=field,
        event_id=event_id,
        value=0.5,
        confidence=0.0,
        source="default",
        method_id=f"default.{field}",
        method_version=_METHOD_VERSION,
        evidence_refs=(),
        warnings=(reason,),
        blockers=(reason,),
        is_default=True,
        is_authoritative=False,
    )


# ---------------------------------------------------------------------------
# completion / tests_pass / operator_accept — already computed by
# EventEvidenceView; we re-pack them as SignalEstimates with provenance.
# ---------------------------------------------------------------------------


def estimate_completion(view: EventEvidenceView) -> SignalEstimate:
    if view.pytest_status == "tool_missing":
        return _missing("completion", view.event_id, reason="pytest tool missing")
    if view.pytest_relevant:
        value = event_completion_from_view(view)
        return SignalEstimate(
            field="completion",
            event_id=view.event_id,
            value=value,
            confidence=0.85 if view.pytest_passed else 0.7,
            source="test_result",
            method_id="completion.pytest_relevant",
            method_version=_METHOD_VERSION,
            evidence_refs=tuple(_finding_refs(view, "pytest")),
        )
    if view.pytest_global_passed is True:
        return SignalEstimate(
            field="completion",
            event_id=view.event_id,
            value=event_completion_from_view(view),
            confidence=0.4,
            source="heuristic",
            method_id="completion.pytest_global_only",
            method_version=_METHOD_VERSION,
            warnings=(
                "pytest global-green is a weak positive — does NOT close "
                "obligation sub-preconditions",
            ),
        )
    if view.pytest_global_passed is False:
        return SignalEstimate(
            field="completion",
            event_id=view.event_id,
            value=event_completion_from_view(view),
            confidence=0.3,
            source="heuristic",
            method_id="completion.pytest_global_failed",
            method_version=_METHOD_VERSION,
            warnings=("pytest globally failed but no relevant test for this event",),
        )
    return _missing("completion", view.event_id, reason="pytest produced no signal for this event")


def estimate_tests_pass(view: EventEvidenceView) -> SignalEstimate:
    base = estimate_completion(view)
    return SignalEstimate(
        field="tests_pass",
        event_id=view.event_id,
        value=event_tests_pass_from_view(view),
        confidence=base.confidence,
        source=base.source,
        method_id=base.method_id.replace("completion.", "tests_pass."),
        method_version=_METHOD_VERSION,
        evidence_refs=base.evidence_refs,
        warnings=base.warnings,
        blockers=base.blockers,
        is_default=base.is_default,
    )


def estimate_operator_accept(view: EventEvidenceView) -> SignalEstimate:
    if view.ruff_status == "tool_missing" and view.mypy_status == "tool_missing":
        return _missing(
            "operator_accept", view.event_id,
            reason="ruff and mypy both tool_missing",
        )
    has_findings = bool(view.ruff_findings or view.mypy_findings)
    has_tool_ok = view.ruff_status == "ok" or view.mypy_status == "ok"
    if not has_tool_ok:
        return _missing(
            "operator_accept", view.event_id,
            reason="neither ruff nor mypy produced ok status",
        )
    value = event_operator_accept_from_view(view)
    if has_findings:
        return SignalEstimate(
            field="operator_accept",
            event_id=view.event_id,
            value=value,
            confidence=0.7,
            source="static_analysis",
            method_id="operator_accept.scope_findings",
            method_version=_METHOD_VERSION,
            evidence_refs=tuple(
                _finding_refs(view, "ruff") + _finding_refs(view, "mypy")
            ),
        )
    return SignalEstimate(
        field="operator_accept",
        event_id=view.event_id,
        value=value,
        confidence=0.5,
        source="heuristic",
        method_id="operator_accept.no_scope_findings",
        method_version=_METHOD_VERSION,
        warnings=(
            "ruff/mypy ran ok but no findings touched this event's scope; "
            "absence of findings is a weak positive",
        ),
    )


# ---------------------------------------------------------------------------
# capability / benefit / observability — load-bearing for V_net
# ---------------------------------------------------------------------------


def estimate_capability(
    view: EventEvidenceView,
    request: AuditRequest | None = None,
) -> SignalEstimate:
    """Deterministic baseline for ``capability``.

    Without an LLM intent estimator we cannot decide whether the
    implementation has the *mechanisms* the intent requires. We return
    a default 0.5 so the readiness gate stays blocked. Phase 4 will
    replace this with a corroborated LLM estimate (capped at 0.6
    confidence by ADR-24 unless tool-grounded).
    """
    if request is None or not request.intent.summary.strip():
        return _missing(
            "capability", view.event_id,
            reason="no intent provided; capability cannot be assessed",
        )
    return _default(
        "capability", view.event_id,
        reason=(
            "deterministic capability baseline is structural default 0.5; "
            "Phase 4 LLM estimator required for real signal"
        ),
    )


def estimate_benefit(
    view: EventEvidenceView,
    request: AuditRequest | None = None,
) -> SignalEstimate:
    """Deterministic baseline for ``benefit``.

    ADR-24 §benefit: **no benefit without intent**. We refuse to infer
    benefit from code complexity, file size, or test count. Without a
    ticket / prompt / issue / PR description, the estimate is missing.
    """
    if request is None or not request.intent.summary.strip():
        return _missing(
            "benefit", view.event_id,
            reason="no intent reference; benefit cannot be inferred from code",
        )
    return _default(
        "benefit", view.event_id,
        reason=(
            "deterministic benefit baseline is structural default 0.5; "
            "Phase 4 LLM estimator required to map intent to value"
        ),
    )


def estimate_observability(view: EventEvidenceView) -> SignalEstimate:
    """Deterministic baseline for ``observability``.

    A weak heuristic: a test file in scope (``pytest_relevant=True``)
    is a small positive; otherwise we return ``missing`` since the
    deterministic surface for negative-path coverage / logging /
    error-surfacing detection is Phase-4 work.
    """
    if view.pytest_status == "tool_missing":
        return _missing(
            "observability", view.event_id,
            reason="pytest tool missing; cannot infer observability",
        )
    if view.pytest_relevant:
        return SignalEstimate(
            field="observability",
            event_id=view.event_id,
            value=0.6,
            confidence=0.4,
            source="heuristic",
            method_id="observability.test_file_present",
            method_version=_METHOD_VERSION,
            warnings=(
                "test file presence is a weak positive — does NOT imply "
                "negative-path or failure-surfacing coverage",
            ),
        )
    return _missing(
        "observability", view.event_id,
        reason=(
            "no relevant test file detected; deterministic observability "
            "estimator returns missing rather than fake-zero"
        ),
    )


# ---------------------------------------------------------------------------
# Bulk helper — produce all per-event deterministic estimates
# ---------------------------------------------------------------------------


def estimate_all_for_event(
    view: EventEvidenceView,
    request: AuditRequest | None = None,
) -> tuple[SignalEstimate, ...]:
    """Return one estimate per estimable field for the event in ``view``."""
    return (
        estimate_capability(view, request),
        estimate_benefit(view, request),
        estimate_observability(view),
        estimate_completion(view),
        estimate_tests_pass(view),
        estimate_operator_accept(view),
    )


def _finding_refs(view: EventEvidenceView, tool: str) -> list[str]:
    refs: list[str] = []
    findings: Iterable[object]
    if tool == "ruff":
        findings = view.ruff_findings
    elif tool == "mypy":
        findings = view.mypy_findings
    elif tool == "pytest":
        # pytest_relevant findings are derived but we don't store them
        # on the view today; emit a marker so the consumer knows the
        # source was a relevant test.
        return [f"pytest:{view.event_id}:relevant"]
    else:
        findings = ()
    for f in findings:
        refs.append(f"{tool}:{f.path}:{f.line}:{f.rule_id}")
    return refs


def _source_for(*, has_test_evidence: bool, has_static_evidence: bool) -> EstimateSource:
    """Helper kept for the readiness/ADR documentation; unused at runtime."""
    if has_test_evidence and has_static_evidence:
        return "tool"
    if has_test_evidence:
        return "test_result"
    if has_static_evidence:
        return "static_analysis"
    return "missing"


__all__ = [
    "estimate_all_for_event",
    "estimate_benefit",
    "estimate_capability",
    "estimate_completion",
    "estimate_observability",
    "estimate_operator_accept",
    "estimate_tests_pass",
]

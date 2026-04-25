"""E3.1 + E3.2 + E3.3 + E3.4 (QA/A14.md, ADR-24) — estimator tests.

Four groups:

* **E3.1 schema** — :class:`SignalEstimate` / :class:`EstimatorReport`
  invariants (default/missing/llm/heuristic source rules).
* **E3.2 deterministic** — capability/benefit/observability +
  completion/tests_pass/operator_accept baselines from
  :class:`EventEvidenceView`.
* **E3.3 LLM contracts** — :class:`LLMEstimatorOutput` cap and
  citation rules.
* **E3.4 readiness** — ``assess_estimator_readiness`` ladder
  (blocked / diagnostic_only / shadow_ready / official_ready_candidate)
  and the explicit "official summary fields stay null" guard.

NONE of these tests assert outcome prediction. They check the SHAPE of
the contracts, not the meaning of the values.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from oida_code.estimators.contracts import (
    EstimatorReport,
    SignalEstimate,
)
from oida_code.estimators.deterministic import (
    estimate_benefit,
    estimate_capability,
    estimate_completion,
    estimate_observability,
    estimate_operator_accept,
)
from oida_code.estimators.llm_contract import (
    LLM_CONFIDENCE_CAP_HYBRID,
    LLM_CONFIDENCE_CAP_LLM_ONLY,
    LLMEstimatorInput,
    LLMEstimatorOutput,
)
from oida_code.estimators.readiness import assess_estimator_readiness
from oida_code.models.audit_request import (
    AuditRequest,
    IntentSpec,
    RepoSpec,
    ScopeSpec,
)
from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
)
from oida_code.score.event_evidence import (
    EventEvidenceView,
    build_event_evidence_view,
)
from oida_code.score.experimental_shadow_fusion import (
    compute_experimental_shadow_fusion,
)
from oida_code.score.fusion_readiness import assess_fusion_readiness

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _est(**kwargs: object) -> SignalEstimate:
    """Build a SignalEstimate with sensible defaults."""
    base: dict[str, object] = {
        "field": "capability",
        "event_id": "e1",
        "value": 0.7,
        "confidence": 0.5,
        "source": "tool",
        "method_id": "test.method",
        "method_version": "1",
    }
    base.update(kwargs)
    return SignalEstimate(**base)  # type: ignore[arg-type]


def _ev(idx: int = 1, *, task: str = "src/a.py: x") -> NormalizedEvent:
    return NormalizedEvent(
        id=f"e{idx}",
        pattern_id=f"p_{idx}",
        task=task,
        capability=0.5,
        reversibility=0.5,
        observability=0.5,
        blast_radius=0.3,
        completion=0.5,
        tests_pass=0.5,
        operator_accept=0.5,
        benefit=0.5,
        preconditions=[],
        constitutive_parents=[],
        supportive_parents=[],
        invalidates_pattern=False,
    )


def _view(idx: int = 1, **overrides: object) -> EventEvidenceView:
    base: dict[str, object] = {
        "event_id": f"e{idx}",
        "scope": ("src/a.py",),
    }
    base.update(overrides)
    return EventEvidenceView(**base)  # type: ignore[arg-type]


def _request_with_intent(summary: str = "implement feature") -> AuditRequest:
    return AuditRequest(
        repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/a.py"], language="python"),
        intent=IntentSpec(summary=summary),
    )


# ---------------------------------------------------------------------------
# E3.1 — SignalEstimate / EstimatorReport schema invariants
# ---------------------------------------------------------------------------


def test_signal_estimate_default_forces_confidence_zero() -> None:
    with pytest.raises(ValidationError):
        _est(source="default", confidence=0.5, is_default=True)


def test_signal_estimate_default_must_set_is_default_true() -> None:
    with pytest.raises(ValidationError):
        _est(source="default", confidence=0.0, is_default=False)


def test_signal_estimate_default_cannot_be_authoritative() -> None:
    with pytest.raises(ValidationError):
        _est(
            source="default", confidence=0.0, is_default=True,
            is_authoritative=True,
        )


def test_signal_estimate_missing_forces_confidence_zero() -> None:
    with pytest.raises(ValidationError):
        _est(source="missing", confidence=0.4)


def test_signal_estimate_llm_cannot_be_authoritative() -> None:
    with pytest.raises(ValidationError):
        _est(source="llm", is_authoritative=True)


def test_signal_estimate_heuristic_cannot_be_authoritative() -> None:
    with pytest.raises(ValidationError):
        _est(source="heuristic", is_authoritative=True)


def test_signal_estimate_tool_can_be_authoritative() -> None:
    """Tool-grounded deterministic estimates may set authoritative=True
    for narrow fields (e.g. operator_accept from a green ruff/mypy)."""
    est = _est(
        field="operator_accept",
        source="tool",
        confidence=1.0,
        is_authoritative=True,
    )
    assert est.is_authoritative is True


def test_signal_estimate_is_frozen() -> None:
    est = _est()
    with pytest.raises(ValidationError):
        est.value = 0.99  # type: ignore[misc]


def test_estimator_report_official_candidate_requires_high_confidence() -> None:
    estimates = (
        _est(field="capability", confidence=0.6),
        _est(field="benefit", confidence=0.9),
        _est(field="observability", confidence=0.9),
    )
    with pytest.raises(ValidationError):
        EstimatorReport(status="official_ready_candidate", estimates=estimates)


def test_estimator_report_shadow_ready_rejects_default_estimate() -> None:
    estimates = (
        _est(field="capability", source="default", confidence=0.0, is_default=True),
        _est(field="benefit"),
        _est(field="observability"),
    )
    with pytest.raises(ValidationError):
        EstimatorReport(status="shadow_ready", estimates=estimates)


def test_estimator_report_blocked_accepts_any_estimates() -> None:
    estimates = (
        _est(field="capability", source="default", confidence=0.0, is_default=True),
        _est(field="benefit", source="missing", confidence=0.0),
    )
    rep = EstimatorReport(status="blocked", estimates=estimates)
    assert rep.status == "blocked"


def test_estimator_report_is_frozen() -> None:
    rep = EstimatorReport(status="blocked", estimates=())
    with pytest.raises(ValidationError):
        rep.status = "shadow_ready"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# E3.2 — deterministic baselines
# ---------------------------------------------------------------------------


def test_capability_missing_intent_is_blocked() -> None:
    """Without an intent, capability falls to source='missing'."""
    est = estimate_capability(_view(), request=None)
    assert est.source == "missing"
    assert est.is_default is False
    assert est.confidence == 0.0
    # missing source → blocks shadow_ready / official_ready_candidate via
    # EstimatorReport validator. Spot-check: a report claiming shadow_ready
    # with this estimate would fail validation.
    with pytest.raises(ValidationError):
        EstimatorReport(status="shadow_ready", estimates=(est,))


def test_capability_with_intent_returns_default_blocking() -> None:
    """Intent present but no LLM → deterministic baseline is the
    structural default 0.5; ``is_default=True`` blocks official fusion."""
    est = estimate_capability(_view(), request=_request_with_intent())
    assert est.source == "default"
    assert est.is_default is True
    assert est.confidence == 0.0


def test_capability_default_blocks_official_fusion() -> None:
    """The defaulting capability estimate cannot reach
    ``official_ready_candidate`` even when packaged with high-confidence
    estimates for the other fields — its own confidence is 0.0."""
    estimates = (
        estimate_capability(_view(), request=_request_with_intent()),
        _est(field="benefit", confidence=0.9),
        _est(field="observability", confidence=0.9),
    )
    with pytest.raises(ValidationError):
        EstimatorReport(
            status="official_ready_candidate", estimates=estimates,
        )


def test_capability_llm_only_is_diagnostic_not_authoritative() -> None:
    """An LLM-sourced capability estimate cannot be authoritative; the
    schema validator on SignalEstimate rejects the construction."""
    with pytest.raises(ValidationError):
        _est(field="capability", source="llm", is_authoritative=True)


def test_capability_tool_supported_contract_has_higher_confidence() -> None:
    """Sanity: a hypothetical tool-grounded capability estimate may
    carry higher confidence than the deterministic default (0.0)."""
    tool_est = _est(field="capability", source="tool", confidence=0.85)
    default_est = estimate_capability(_view(), request=_request_with_intent())
    assert tool_est.confidence > default_est.confidence


def test_benefit_missing_without_intent() -> None:
    est = estimate_benefit(_view(), request=None)
    assert est.source == "missing"


def test_benefit_not_inferred_from_code_complexity() -> None:
    """Even on a verbose-event surface, benefit stays default/missing
    until intent is provided. Code complexity is NOT a proxy for value."""
    big_view = _view(idx=1, scope=("src/big_module.py",))
    est = estimate_benefit(big_view, request=None)
    assert est.source == "missing"
    # And an event with intent goes to default, not heuristic-from-code.
    est2 = estimate_benefit(big_view, request=_request_with_intent())
    assert est2.source == "default"


def test_benefit_requires_intent_reference() -> None:
    """An empty / whitespace-only intent summary counts as missing."""
    request = AuditRequest(
        repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/a.py"], language="python"),
        intent=IntentSpec(summary="   "),
    )
    est = estimate_benefit(_view(), request=request)
    assert est.source == "missing"


def test_benefit_llm_only_confidence_capped() -> None:
    """LLM-only benefit estimate can't carry confidence > 0.6 (ADR-24)."""
    try:
        too_high = _est(field="benefit", source="llm", confidence=0.9)
    except ValidationError:
        pytest.fail("SignalEstimate must accept llm source with high confidence; "
                    "the cap is enforced by LLMEstimatorOutput, not SignalEstimate")
    # The cap fires when the estimate is bundled into LLMEstimatorOutput.
    with pytest.raises(ValidationError):
        LLMEstimatorOutput(
            estimates=(too_high,),
            cited_evidence_refs=("intent.md",),
        )


def test_observability_no_tests_no_logs_low_confidence() -> None:
    """Without any pytest evidence, observability returns missing."""
    view = _view(pytest_status="tool_missing")
    est = estimate_observability(view)
    assert est.source == "missing"


def test_observability_tests_only_medium_not_high() -> None:
    """A relevant test file present → observability heuristic with
    medium confidence (0.4), NOT high (>= 0.7)."""
    view = _view(pytest_status="ok", pytest_relevant=True, pytest_passed=True)
    est = estimate_observability(view)
    assert est.source == "heuristic"
    assert est.value == 0.6
    assert 0.3 <= est.confidence < 0.7


def test_observability_negative_path_test_increases_value() -> None:
    """Placeholder for a future Phase-4 signal — today's deterministic
    estimator returns the same heuristic regardless of negative-path
    coverage. Test stays as a marker so an integrator who wires this
    sees the gap."""
    view = _view(pytest_status="ok", pytest_relevant=True, pytest_passed=True)
    est = estimate_observability(view)
    # The deterministic baseline gives 0.6; a real negative-path
    # signal would raise this above 0.6 once wired.
    assert est.value == 0.6
    pytest.skip(
        "negative-path coverage is Phase-4 work; deterministic estimator "
        "returns 0.6 baseline only"
    )


def test_observability_logging_without_failure_path_is_weak() -> None:
    """Same future-signal placeholder for logging detection."""
    pytest.skip(
        "logging-without-failure-path detection is Phase-4 work; "
        "deterministic estimator returns missing without test evidence"
    )


def test_observability_missing_tool_does_not_imply_zero() -> None:
    """``tool_missing`` returns ``source='missing'`` (value 0.5),
    NOT ``source='tool'`` with value 0.0."""
    view = _view(pytest_status="tool_missing")
    est = estimate_observability(view)
    assert est.source == "missing"
    assert est.value == 0.5


def test_completion_missing_evidence_distinct_from_negative() -> None:
    """`source='missing'` (no signal) differs from a value of 0.2
    (real negative signal). The estimator must not conflate them."""
    missing = estimate_completion(_view(pytest_status="tool_missing"))
    negative = estimate_completion(
        _view(
            pytest_status="ok",
            pytest_relevant=True,
            pytest_passed=False,
        )
    )
    assert missing.source == "missing"
    assert negative.source == "test_result"
    assert negative.value == pytest.approx(0.2, abs=1e-9)


def test_operator_accept_missing_tools_returns_missing() -> None:
    est = estimate_operator_accept(
        _view(ruff_status="tool_missing", mypy_status="tool_missing")
    )
    assert est.source == "missing"


# ---------------------------------------------------------------------------
# E3.3 — LLM contract
# ---------------------------------------------------------------------------


def test_llm_input_is_frozen() -> None:
    inp = LLMEstimatorInput(
        intent="do thing",
        event=_ev(),
        evidence_view=_view(),
    )
    with pytest.raises(ValidationError):
        inp.intent = "different"  # type: ignore[misc]


def test_llm_output_caps_llm_only_confidence() -> None:
    over = _est(
        field="capability", source="llm",
        confidence=LLM_CONFIDENCE_CAP_LLM_ONLY + 0.01,
        evidence_refs=("intent.md",),
    )
    with pytest.raises(ValidationError):
        LLMEstimatorOutput(
            estimates=(over,),
            cited_evidence_refs=("intent.md",),
        )


def test_llm_output_caps_hybrid_confidence() -> None:
    over = _est(
        field="capability", source="hybrid",
        confidence=LLM_CONFIDENCE_CAP_HYBRID + 0.01,
        evidence_refs=("ruff:src/a.py:1:R001",),
    )
    with pytest.raises(ValidationError):
        LLMEstimatorOutput(
            estimates=(over,),
            cited_evidence_refs=("ruff:src/a.py:1:R001",),
        )


def test_llm_output_requires_citation_or_unsupported_marker() -> None:
    uncited = _est(
        field="capability", source="llm",
        confidence=LLM_CONFIDENCE_CAP_LLM_ONLY,
        evidence_refs=(),
    )
    with pytest.raises(ValidationError):
        LLMEstimatorOutput(
            estimates=(uncited,),
            cited_evidence_refs=(),
        )


def test_llm_output_zero_confidence_does_not_need_citation() -> None:
    """A 0-confidence LLM estimate (e.g. a refusal) doesn't need
    citation — it carries no signal."""
    refusal = _est(
        field="capability", source="llm", confidence=0.0,
        evidence_refs=(),
    )
    out = LLMEstimatorOutput(
        estimates=(refusal,),
        cited_evidence_refs=(),
    )
    assert out.estimates[0].confidence == 0.0


def test_llm_output_unsupported_claims_satisfy_citation_rule() -> None:
    """An LLM estimate without evidence_refs is allowed when the same
    field/event_id pair is listed in unsupported_claims."""
    uncited = _est(
        field="capability", source="llm",
        confidence=LLM_CONFIDENCE_CAP_LLM_ONLY,
        evidence_refs=(),
    )
    out = LLMEstimatorOutput(
        estimates=(uncited,),
        cited_evidence_refs=("intent.md",),
        unsupported_claims=(f"{uncited.field}@{uncited.event_id}",),
    )
    assert out.estimates


# ---------------------------------------------------------------------------
# E3.4 — readiness ladder + official-summary-null guard
# ---------------------------------------------------------------------------


def test_default_capability_blocks_official() -> None:
    """With intent but no LLM, capability estimate is default → status
    cannot be official_ready_candidate or shadow_ready."""
    scen = NormalizedScenario(name="t", description="", events=[_ev()])
    views = build_event_evidence_view(scen, None, event_scopes={"e1": ("src/a.py",)})
    rep = assess_estimator_readiness(scen, views, request=_request_with_intent())
    assert rep.status in ("blocked", "diagnostic_only")


def test_llm_only_capability_does_not_unlock_official() -> None:
    """A pure LLM-only EstimatorReport can't reach official_ready_candidate
    because the LLM cap (0.6) is below the candidate threshold (0.7)."""
    high_llm = _est(field="capability", source="llm", confidence=0.6)
    benefit = _est(field="benefit", confidence=0.95)
    observability = _est(field="observability", confidence=0.95)
    # Building the report at official_ready_candidate must fail.
    with pytest.raises(ValidationError):
        EstimatorReport(
            status="official_ready_candidate",
            estimates=(high_llm, benefit, observability),
        )


def test_missing_benefit_blocks_official() -> None:
    benefit_missing = _est(field="benefit", source="missing", confidence=0.0)
    capability = _est(field="capability", confidence=0.95)
    observability = _est(field="observability", confidence=0.95)
    with pytest.raises(ValidationError):
        EstimatorReport(
            status="official_ready_candidate",
            estimates=(capability, benefit_missing, observability),
        )


def test_observability_default_blocks_official() -> None:
    observability_default = _est(
        field="observability", source="default", confidence=0.0,
        is_default=True,
    )
    capability = _est(field="capability", confidence=0.95)
    benefit = _est(field="benefit", confidence=0.95)
    with pytest.raises(ValidationError):
        EstimatorReport(
            status="official_ready_candidate",
            estimates=(capability, benefit, observability_default),
        )


def test_all_estimators_present_can_reach_shadow_ready() -> None:
    """A scenario where every load-bearing field has a non-default,
    non-missing estimate (any positive confidence) can be packaged at
    status=shadow_ready."""
    capability = _est(field="capability", confidence=0.5)
    benefit = _est(field="benefit", confidence=0.5)
    observability = _est(field="observability", confidence=0.5)
    rep = EstimatorReport(
        status="shadow_ready",
        estimates=(capability, benefit, observability),
    )
    assert rep.status == "shadow_ready"


def test_official_ready_candidate_requires_high_confidence_all_fields() -> None:
    """Even with all fields tool-grounded, falling below 0.7 on any
    one breaks the candidate threshold."""
    capability = _est(field="capability", confidence=0.7)
    benefit = _est(field="benefit", confidence=0.7)
    observability = _est(field="observability", confidence=0.69)  # one short
    with pytest.raises(ValidationError):
        EstimatorReport(
            status="official_ready_candidate",
            estimates=(capability, benefit, observability),
        )


def test_official_summary_fields_still_null_in_e3() -> None:
    """End-to-end: even when an estimator report is shadow_ready, the
    shadow fusion's payload carries no official summary keys. ADR-22's
    pin against silent V_net leakage holds in E3 too."""
    scen = NormalizedScenario(name="t", description="", events=[_ev()])
    rep = assess_fusion_readiness(scen)
    shadow = compute_experimental_shadow_fusion(scen, rep)
    payload = shadow.model_dump()
    forbidden = {
        "total_v_net", "debt_final", "corrupt_success",
        "corrupt_success_ratio", "corrupt_success_verdict",
    }
    assert not (forbidden & set(payload.keys()))
    assert payload["authoritative"] is False


# ---------------------------------------------------------------------------
# Bonus: end-to-end estimator readiness from a real evidence view
# ---------------------------------------------------------------------------


def test_assess_readiness_produces_per_event_estimates() -> None:
    scen = NormalizedScenario(name="t", description="", events=[_ev()])
    pytest_ev = ToolEvidence(
        tool="pytest", status="ok",
        findings=[
            Finding(
                tool="pytest", rule_id="passed", severity="info",
                path="src/a.py", line=1, column=1, message="pass",
            ),
        ],
        counts={"total": 5, "failure": 0, "error": 0},
    )
    views = build_event_evidence_view(
        scen,
        [pytest_ev, ToolEvidence(tool="ruff", status="ok"),
         ToolEvidence(tool="mypy", status="ok")],
        event_scopes={"e1": ("src/a.py",)},
    )
    rep = assess_estimator_readiness(scen, views, request=_request_with_intent())
    # 6 estimates per event (capability/benefit/observability/completion/
    # tests_pass/operator_accept).
    assert len(rep.estimates) == 6
    # capability + benefit are still default (no LLM); status downgrades
    # to diagnostic_only or blocked.
    assert rep.status in ("blocked", "diagnostic_only")
    # And the report is frozen, so a downstream consumer can't quietly
    # promote it to shadow_ready.
    with pytest.raises(ValidationError):
        rep.status = "shadow_ready"  # type: ignore[misc]

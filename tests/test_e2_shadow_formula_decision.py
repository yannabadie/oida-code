"""E2 (QA/A13.md, ADR-23) — shadow formula decision tests.

E2 evaluates whether the E1.1 shadow formula is **structurally** stable,
monotone, explainable, and useful as a diagnostic. It does NOT validate
statistical prediction of outcomes.

Test groups:

* Monotonicity — each formula input moves base_pressure in the expected
  direction, on its own, with all else fixed.
* Edge confidence — the new optional ``edge_confidences`` parameter
  (ADR-23 §5 Option B) defaults to 0.6 and overrides per edge when given.
* Graph topology ablations — constitutive vs supportive channel
  separation holds across cycle / dense-star / long-chain shapes.
* Honesty invariants — real-zero grounding > missing grounding, and the
  shadow report still carries no official summary keys after smoke runs.

NONE of these tests assert outcome prediction. They check the SHAPE of
the diagnostic, not its meaning.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
)
from oida_code.models.trajectory import TrajectoryMetrics
from oida_code.score.experimental_shadow_fusion import (
    _ALPHA_CONSTITUTIVE,
    _ALPHA_SUPPORTIVE,
    _DEFAULT_EDGE_CONFIDENCE,
    ShadowFusionReport,
    compute_experimental_shadow_fusion,
)
from oida_code.score.fusion_readiness import (
    FusionReadinessReport,
    assess_fusion_readiness,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    *,
    idx: int = 1,
    capability: float = 0.5,
    benefit: float = 0.5,
    observability: float = 0.5,
    completion: float = 0.5,
    tests_pass: float = 0.5,
    operator_accept: float = 0.5,
    preconditions: list[PreconditionSpec] | None = None,
    constitutive_parents: list[str] | None = None,
    supportive_parents: list[str] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        id=f"e{idx}",
        pattern_id=f"p_precondition_x_{idx}",
        task=f"task {idx}",
        capability=capability,
        reversibility=0.5,
        observability=observability,
        blast_radius=0.3,
        completion=completion,
        tests_pass=tests_pass,
        operator_accept=operator_accept,
        benefit=benefit,
        preconditions=preconditions or [],
        constitutive_parents=constitutive_parents or [],
        supportive_parents=supportive_parents or [],
        invalidates_pattern=False,
    )


def _scen(events: list[NormalizedEvent]) -> NormalizedScenario:
    return NormalizedScenario(name="t", description="", events=events)


def _shadow(
    scenario: NormalizedScenario,
    *,
    readiness: FusionReadinessReport | None = None,
    trajectory_metrics: TrajectoryMetrics | None = None,
    edge_confidences: dict[tuple[str, str, str], float] | None = None,
) -> ShadowFusionReport:
    rep = readiness or assess_fusion_readiness(scenario)
    return compute_experimental_shadow_fusion(
        scenario,
        rep,
        trajectory_metrics=trajectory_metrics,
        edge_confidences=edge_confidences,
    )


def _trajectory(*, exploration_error: float, total_steps: int = 10) -> TrajectoryMetrics:
    """Synthetic trajectory whose derived shadow pressure equals
    ``exploration_error`` (because shadow takes max of expl/exploit and
    we set exploitation to the same value)."""
    return TrajectoryMetrics(
        exploration_error=exploration_error,
        exploitation_error=exploration_error,
        stale_score=0,
        no_progress_rate=exploration_error,
        total_steps=total_steps,
        progress_events_count=max(0, total_steps - round(exploration_error * total_steps)),
        exploration_steps=total_steps // 2,
        exploitation_steps=total_steps - total_steps // 2,
    )


def _fully_unverified(n: int) -> list[PreconditionSpec]:
    return [PreconditionSpec(name=f"p{i}", weight=1.0, verified=False) for i in range(n)]


def _partial_verified(n: int, verified_count: int) -> list[PreconditionSpec]:
    """``n`` equal-weight preconditions, ``verified_count`` of which are verified."""
    return [
        PreconditionSpec(name=f"p{i}", weight=1.0, verified=(i < verified_count))
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Monotonicity — each input moves base_pressure in the expected direction
# ---------------------------------------------------------------------------


def test_formula_monotonic_grounding() -> None:
    """As verified-fraction increases (real grounding model, never
    missing), base_pressure must monotonically decrease — the
    ``0.40 * (1 - grounding)`` term is strictly anti-monotone in
    grounding."""
    pressures: list[float] = []
    for verified in range(0, 5):  # 0..4 over 4 preconditions
        scen = _scen([
            _make_event(
                idx=1,
                completion=0.5,
                operator_accept=0.5,
                preconditions=_partial_verified(4, verified),
            )
        ])
        pressures.append(_shadow(scen).event_scores[0].base_pressure)
    # Strictly non-increasing across the sweep.
    for prev, nxt in pairwise(pressures):
        assert nxt <= prev + 1e-12, (
            f"grounding monotonicity broken: {pressures}"
        )
    # And actually decreasing (not flat) across the full range.
    assert pressures[0] > pressures[-1]


def test_formula_monotonic_completion() -> None:
    """As completion rises 0→1, base_pressure must monotonically
    decrease — the ``0.15 * (1 - completion)`` term is strictly
    anti-monotone in completion."""
    pressures: list[float] = []
    for completion in (0.0, 0.25, 0.5, 0.75, 1.0):
        scen = _scen([
            _make_event(
                idx=1,
                completion=completion,
                operator_accept=0.5,
                preconditions=_partial_verified(2, 1),
            )
        ])
        pressures.append(_shadow(scen).event_scores[0].base_pressure)
    for prev, nxt in pairwise(pressures):
        assert nxt <= prev + 1e-12, (
            f"completion monotonicity broken: {pressures}"
        )
    assert pressures[0] > pressures[-1]


def test_formula_monotonic_operator_accept() -> None:
    """As operator_accept rises 0→1, the static_failure_pressure term
    decreases linearly, so base_pressure must decrease."""
    pressures: list[float] = []
    for op in (0.0, 0.25, 0.5, 0.75, 1.0):
        scen = _scen([
            _make_event(
                idx=1,
                completion=0.5,
                operator_accept=op,
                preconditions=_partial_verified(2, 1),
            )
        ])
        pressures.append(_shadow(scen).event_scores[0].base_pressure)
    for prev, nxt in pairwise(pressures):
        assert nxt <= prev + 1e-12, (
            f"operator_accept monotonicity broken: {pressures}"
        )
    assert pressures[0] > pressures[-1]


def test_formula_monotonic_trajectory_pressure() -> None:
    """As trajectory error rises 0→1, base_pressure must monotonically
    increase — the ``0.25 * trajectory_pressure`` term is the only one
    in the formula that's monotone-INCREASING in its input, so this
    test guards the sign as well as the magnitude."""
    pressures: list[float] = []
    for err in (0.0, 0.25, 0.5, 0.75, 1.0):
        scen = _scen([
            _make_event(
                idx=1,
                completion=0.5,
                operator_accept=0.5,
                preconditions=_partial_verified(2, 1),
            )
        ])
        pressures.append(
            _shadow(scen, trajectory_metrics=_trajectory(exploration_error=err))
            .event_scores[0]
            .base_pressure
        )
    for prev, nxt in pairwise(pressures):
        assert nxt >= prev - 1e-12, (
            f"trajectory monotonicity broken: {pressures}"
        )
    assert pressures[-1] > pressures[0]


# ---------------------------------------------------------------------------
# Edge-confidence policy (ADR-23 §5 Option B)
# ---------------------------------------------------------------------------


def test_edge_confidence_default_is_0_6() -> None:
    """When ``edge_confidences`` is not passed, the propagation must
    match the spec: ``contribution = parent_pressure * 0.6 * alpha``.
    Constructed so that the parent's base pressure is non-trivial and
    the child's local base is below the propagated value."""
    parent_pre = _fully_unverified(1)  # grounding 0 → high pressure
    parent = _make_event(idx=1, completion=0.0, operator_accept=0.0, preconditions=parent_pre)
    child = _make_event(
        idx=2,
        completion=1.0,
        operator_accept=1.0,
        preconditions=_partial_verified(1, 1),  # all verified
        constitutive_parents=[parent.id],
    )
    shadow = _shadow(_scen([parent, child]))
    parent_p = shadow.event_scores[0].base_pressure
    child_base = shadow.event_scores[1].base_pressure
    child_debt = shadow.event_scores[1].shadow_debt_pressure
    expected = max(child_base, parent_p * _DEFAULT_EDGE_CONFIDENCE * _ALPHA_CONSTITUTIVE)
    assert child_debt == pytest.approx(expected, abs=1e-9), (
        f"default-confidence propagation off: child_debt={child_debt}, "
        f"expected={expected}, parent={parent_p}, child_base={child_base}"
    )


def test_edge_confidence_metadata_overrides_default() -> None:
    """When the integrator passes ``edge_confidences[(p, c, kind)] = X``,
    the propagation must use ``X`` instead of 0.6. Two runs with X=0.6
    and X=0.9 on the same scenario produce a higher debt pressure for
    the higher confidence (other inputs fixed)."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    child = _make_event(
        idx=2,
        completion=1.0,
        operator_accept=1.0,
        preconditions=_partial_verified(1, 1),
        constitutive_parents=[parent.id],
    )
    scen = _scen([parent, child])
    low = _shadow(
        scen,
        edge_confidences={(parent.id, child.id, "constitutive"): 0.3},
    )
    high = _shadow(
        scen,
        edge_confidences={(parent.id, child.id, "constitutive"): 0.9},
    )
    low_debt = low.event_scores[1].shadow_debt_pressure
    high_debt = high.event_scores[1].shadow_debt_pressure
    assert high_debt > low_debt, (
        f"edge_confidence override failed: low={low_debt}, high={high_debt}"
    )
    # And matches the analytical formula at high confidence.
    parent_p = high.event_scores[0].base_pressure
    child_base = high.event_scores[1].base_pressure
    expected_high = max(child_base, parent_p * 0.9 * _ALPHA_CONSTITUTIVE)
    assert high_debt == pytest.approx(expected_high, abs=1e-9)


def test_edge_confidence_unrelated_key_is_ignored() -> None:
    """An ``edge_confidences`` entry whose key doesn't match an actual
    edge in the scenario must NOT change propagation. Guard against
    stale keys leaking into the formula."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    child = _make_event(
        idx=2,
        completion=1.0,
        operator_accept=1.0,
        preconditions=_partial_verified(1, 1),
        constitutive_parents=[parent.id],
    )
    scen = _scen([parent, child])
    base_run = _shadow(scen)
    polluted = _shadow(
        scen,
        edge_confidences={
            ("nonexistent_parent", "nonexistent_child", "constitutive"): 0.99,
            # Wrong kind for the real edge:
            (parent.id, child.id, "supportive"): 0.99,
        },
    )
    assert (
        base_run.event_scores[1].shadow_debt_pressure
        == polluted.event_scores[1].shadow_debt_pressure
    ), "stale edge_confidences keys must not affect propagation"


# ---------------------------------------------------------------------------
# Graph topology ablations
# ---------------------------------------------------------------------------


def test_supportive_chain_does_not_raise_debt_channel() -> None:
    """A 5-link supportive chain with a failing root must NOT propagate
    via the constitutive (debt) channel. The supportive root touches
    only ``shadow_integrity_pressure`` of its descendants — debt
    channel stays at each event's local base pressure."""
    chain: list[NormalizedEvent] = []
    for i in range(5):
        if i == 0:
            ev = _make_event(
                idx=i + 1, completion=0.0, operator_accept=0.0,
                preconditions=_fully_unverified(1),
            )
        else:
            ev = _make_event(
                idx=i + 1,
                completion=0.95, operator_accept=0.95,
                preconditions=_partial_verified(1, 1),
                supportive_parents=[chain[i - 1].id],
            )
        chain.append(ev)
    shadow = _shadow(_scen(chain))
    by_id = {s.event_id: s for s in shadow.event_scores}
    # Every non-root child's debt channel == its local base pressure.
    for ev in chain[1:]:
        score = by_id[ev.id]
        assert score.shadow_debt_pressure == pytest.approx(
            score.base_pressure, abs=1e-9,
        ), f"event {ev.id} debt channel raised by supportive chain"
    # And at least one descendant's integrity channel is above its base.
    raised = [
        by_id[ev.id]
        for ev in chain[1:]
        if by_id[ev.id].shadow_integrity_pressure
        > by_id[ev.id].base_pressure + 1e-9
    ]
    assert raised, (
        "supportive chain failed to raise integrity channel — "
        "audit signal lost"
    )


def test_dense_supportive_star_remains_bounded() -> None:
    """A dense supportive star (10 parents → 1 child) must not blow
    past 1.0 on any channel and must converge in the 10-iter cap."""
    parents = [
        _make_event(
            idx=i + 1, completion=0.0, operator_accept=0.0,
            preconditions=_fully_unverified(1),
        )
        for i in range(10)
    ]
    child = _make_event(
        idx=99,
        completion=0.5, operator_accept=0.5,
        preconditions=_partial_verified(2, 1),
        supportive_parents=[p.id for p in parents],
    )
    shadow = _shadow(_scen([*parents, child]))
    for s in shadow.event_scores:
        assert 0.0 <= s.shadow_debt_pressure <= 1.0
        assert 0.0 <= s.shadow_integrity_pressure <= 1.0
        assert 0.0 <= s.graph_propagation_pressure <= 1.0
    assert shadow.graph_summary.propagation_iterations <= 10
    assert shadow.graph_summary.propagation_converged is True
    # The child's integrity_pressure equals max(base, max_parent_p * 0.6 * 0.40).
    by_id = {s.event_id: s for s in shadow.event_scores}
    child_score = by_id[child.id]
    parent_scores = [by_id[p.id] for p in parents]
    max_parent_p = max(p.base_pressure for p in parent_scores)
    expected = max(
        child_score.base_pressure,
        max_parent_p * _DEFAULT_EDGE_CONFIDENCE * _ALPHA_SUPPORTIVE,
    )
    assert child_score.shadow_integrity_pressure == pytest.approx(
        expected, abs=1e-9,
    ), (
        "dense star integrity channel should equal max(base, "
        "max_parent * conf * alpha_supportive)"
    )


def test_long_supportive_chain_converges() -> None:
    """A 6-link supportive chain converges within the iteration cap
    and the deepest descendant's integrity pressure is bounded by
    ``root_pressure * (conf * alpha)^depth``. We don't pin the value
    (depth-dependent), only that propagation terminates and stays in
    [0, 1]."""
    chain: list[NormalizedEvent] = []
    for i in range(6):
        if i == 0:
            ev = _make_event(
                idx=i + 1, completion=0.0, operator_accept=0.0,
                preconditions=_fully_unverified(1),
            )
        else:
            ev = _make_event(
                idx=i + 1,
                completion=0.95, operator_accept=0.95,
                preconditions=_partial_verified(1, 1),
                supportive_parents=[chain[i - 1].id],
            )
        chain.append(ev)
    shadow = _shadow(_scen(chain))
    assert shadow.graph_summary.propagation_iterations <= 10
    assert shadow.graph_summary.propagation_converged is True
    for s in shadow.event_scores:
        assert 0.0 <= s.shadow_integrity_pressure <= 1.0


def test_constitutive_only_propagates_to_debt_channel_only() -> None:
    """An edge tagged constitutive raises debt but not integrity above
    base in an isolated child. Integrity stays at child's local base
    because there's no supportive parent contribution."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    child = _make_event(
        idx=2,
        completion=0.95, operator_accept=0.95,
        preconditions=_partial_verified(1, 1),
        constitutive_parents=[parent.id],
    )
    shadow = _shadow(_scen([parent, child]))
    by_id = {s.event_id: s for s in shadow.event_scores}
    child_score = by_id[child.id]
    assert child_score.shadow_debt_pressure > child_score.base_pressure + 1e-9
    assert child_score.shadow_integrity_pressure == pytest.approx(
        child_score.base_pressure, abs=1e-9,
    )


def test_mixed_graph_propagates_to_both_channels() -> None:
    """A child with both a constitutive parent AND a supportive parent
    has both channels raised independently — neither contaminates the
    other."""
    cons_parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    sup_parent = _make_event(
        idx=2, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    child = _make_event(
        idx=3,
        completion=0.95, operator_accept=0.95,
        preconditions=_partial_verified(1, 1),
        constitutive_parents=[cons_parent.id],
        supportive_parents=[sup_parent.id],
    )
    shadow = _shadow(_scen([cons_parent, sup_parent, child]))
    by_id = {s.event_id: s for s in shadow.event_scores}
    cs = by_id[child.id]
    cons_p = by_id[cons_parent.id].base_pressure
    sup_p = by_id[sup_parent.id].base_pressure
    # Debt channel reflects the constitutive parent only.
    assert cs.shadow_debt_pressure == pytest.approx(
        max(cs.base_pressure, cons_p * _DEFAULT_EDGE_CONFIDENCE * _ALPHA_CONSTITUTIVE),
        abs=1e-9,
    )
    # Integrity channel reflects the supportive parent only.
    assert cs.shadow_integrity_pressure == pytest.approx(
        max(cs.base_pressure, sup_p * _DEFAULT_EDGE_CONFIDENCE * _ALPHA_SUPPORTIVE),
        abs=1e-9,
    )


def test_cycle_graph_bounded_and_deterministic_two_runs() -> None:
    """Re-asserts the E1 cycle invariant in the E2 ablation suite:
    a 3-event constitutive cycle terminates and is deterministic."""
    a = _make_event(idx=1, completion=0.0, constitutive_parents=["e3"])
    b = _make_event(idx=2, completion=0.0, constitutive_parents=["e1"])
    c = _make_event(idx=3, completion=0.0, constitutive_parents=["e2"])
    s1 = _shadow(_scen([a, b, c]))
    s2 = _shadow(_scen([a, b, c]))
    assert s1.model_dump() == s2.model_dump()
    assert s1.graph_summary.propagation_iterations <= 10


def test_empty_graph_local_only_warning() -> None:
    """A scenario with no edges produces the ``no graph edges`` warning
    and every event's debt/integrity channel collapses to base. Already
    asserted in E1 — re-stated here as an E2 ablation invariant."""
    shadow = _shadow(_scen([_make_event(idx=1), _make_event(idx=2)]))
    for s in shadow.event_scores:
        assert s.shadow_debt_pressure == s.base_pressure
        assert s.shadow_integrity_pressure == s.base_pressure
        assert s.graph_propagation_pressure == 0.0
    assert any("no graph edges" in w for w in shadow.warnings)


# ---------------------------------------------------------------------------
# Honesty invariants
# ---------------------------------------------------------------------------


def test_real_zero_grounding_greater_than_missing_grounding() -> None:
    """E1.1 invariant restated for E2: an event with N preconditions
    all unverified produces strictly higher base_pressure than an
    event with no preconditions extracted at all (the missing case
    contributes neutral 0.5 + warning, the real-zero case contributes
    1.0 to the grounding term)."""
    no_pre = _scen([_make_event(idx=1, completion=0.5, operator_accept=0.5)])
    real_zero = _scen([
        _make_event(
            idx=1, completion=0.5, operator_accept=0.5,
            preconditions=_fully_unverified(2),
        )
    ])
    no_pre_p = _shadow(no_pre).event_scores[0].base_pressure
    real_zero_p = _shadow(real_zero).event_scores[0].base_pressure
    assert real_zero_p > no_pre_p


def test_official_summary_fields_remain_null_after_shadow_smoke() -> None:
    """End-to-end smoke: build a non-trivial scenario with a graph,
    run shadow fusion, dump the report, and confirm the schema does
    NOT carry any of the official OIDA fusion keys. ADR-22's pin
    against silent V_net leakage is a structural property of the
    Pydantic model — this test guards against accidental schema
    drift introducing those keys."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_fully_unverified(1),
    )
    child = _make_event(
        idx=2, completion=0.95,
        preconditions=_partial_verified(2, 1),
        constitutive_parents=[parent.id],
    )
    shadow = _shadow(_scen([parent, child]))
    payload = shadow.model_dump()
    forbidden = {
        "total_v_net",
        "debt_final",
        "corrupt_success",
        "corrupt_success_ratio",
        "corrupt_success_verdict",
        "mean_q_obs",
        "mean_lambda_bias",
    }
    assert not (forbidden & set(payload.keys()))
    # And shadow report is still non-authoritative.
    assert payload["authoritative"] is False
    assert payload["readiness_status"] == "blocked"
    assert payload["status"] == "blocked_by_readiness"


# ---------------------------------------------------------------------------
# Variant placeholder — V2 dynamic-renormalized (NOT implemented)
# ---------------------------------------------------------------------------


def test_dynamic_renormalized_missing_components_if_implemented() -> None:
    """Placeholder for the V2 (dynamic-renormalized) variant. The E2
    decision (ADR-23, reports/e2_shadow_formula_decision.md) is to
    KEEP V1 with two minor revisions (already shipped in E1.1: missing
    grounding semantics + edge_confidences param). V2 was rejected in
    favour of the V1 + warning approach. This test stays as a marker
    so that if a future variant is added, the gap is visible."""
    pytest.skip(
        "V2 dynamic-renormalized formula not implemented; ADR-23 keeps V1 "
        "with the two revisions shipped in E1.1 (missing grounding + edge "
        "confidence override).",
    )

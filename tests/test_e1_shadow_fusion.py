"""E1 (QA/A11.md) — experimental shadow fusion + invariants + D2 ablation.

Two test groups:

* Invariants (10): the shadow report can never become authoritative;
  graph propagation respects constitutive vs supportive semantics;
  cycles are bounded; readiness gating is honoured.
* D2 fixture comparisons (4): on the hermetic traces, the relative
  pressure ordering matches the scenarios' intent.

Honesty: NONE of these tests assert outcome prediction or absolute
truth. They check the SHAPE of the diagnostic, not its meaning.
"""

from __future__ import annotations

from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
)
from oida_code.score.experimental_shadow_fusion import (
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
    preconditions: list | None = None,
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
) -> ShadowFusionReport:
    rep = readiness or assess_fusion_readiness(scenario)
    return compute_experimental_shadow_fusion(scenario, rep)


def _by_id(report: ShadowFusionReport) -> dict:
    return {s.event_id: s for s in report.event_scores}


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_shadow_report_is_never_authoritative() -> None:
    """ADR-22: authoritative is pinned to False by the type."""
    scenario = _scen([_make_event(idx=1)])
    shadow = _shadow(scenario)
    assert shadow.authoritative is False
    # Schema check — the field's only legal value is False.
    dumped = shadow.model_dump()
    assert dumped["authoritative"] is False


def test_shadow_does_not_populate_official_summary_fields() -> None:
    """The shadow report MUST NOT carry V_net / debt_final /
    corrupt_success keys, even as None."""
    scenario = _scen([_make_event(idx=1)])
    shadow = _shadow(scenario)
    dumped = shadow.model_dump()
    forbidden = {"total_v_net", "debt_final", "corrupt_success_ratio", "mean_q_obs"}
    assert not (forbidden & set(dumped.keys()))


def test_shadow_blocked_readiness_runs_and_marks_blocked() -> None:
    """When readiness is blocked, shadow still runs (opt-in behaviour
    in the CLI), but its status reflects the block."""
    scenario = _scen([_make_event(idx=1)])
    readiness = assess_fusion_readiness(scenario)
    assert readiness.is_blocked()  # default capability/benefit/observability
    shadow = _shadow(scenario, readiness=readiness)
    assert shadow.status == "blocked_by_readiness"
    assert shadow.readiness_status == "blocked"


def test_constitutive_parent_pressure_propagates_to_child() -> None:
    """Adding a high-pressure constitutive parent must NOT reduce the
    child's debt pressure; in general it raises it (max() propagation
    times alpha_constitutive=0.80)."""
    parent = _make_event(idx=1, completion=0.0)  # high local pressure
    child_alone = _make_event(idx=2)
    child_with_parent = _make_event(
        idx=3, constitutive_parents=[parent.id],
    )
    pressure_alone = _shadow(_scen([child_alone])).event_scores[0].shadow_debt_pressure
    pressure_with = (
        _shadow(_scen([parent, child_with_parent]))
        .event_scores[1]
        .shadow_debt_pressure
    )
    assert pressure_with >= pressure_alone, (
        "constitutive parent must not reduce child debt pressure"
    )


def test_supportive_parent_creates_audit_pressure_not_debt_invalidation() -> None:
    """Supportive parents propagate via the integrity (audit) channel
    with alpha_supportive=0.40. They should NOT propagate via the
    constitutive (debt) channel."""
    parent = _make_event(idx=1, completion=0.0)
    child = _make_event(idx=2, supportive_parents=[parent.id])
    shadow = _shadow(_scen([parent, child]))
    by_id = _by_id(shadow)
    # Child's integrity pressure should be at least its base; supportive
    # parent's contribution adds via max.
    assert (
        by_id["e2"].shadow_integrity_pressure
        >= by_id["e2"].base_pressure - 1e-9
    )
    # Crucially the parent must NOT have raised the child via the
    # constitutive (debt) channel.
    assert (
        by_id["e2"].shadow_debt_pressure == by_id["e2"].base_pressure
    ), (
        "supportive parent must NOT raise child debt pressure (that channel "
        "is reserved for constitutive edges)"
    )


def test_no_edges_degrades_to_local_pressure() -> None:
    """With no graph edges the shadow scores reduce to base_pressure
    on every event; propagation_iterations stays small."""
    scenario = _scen([_make_event(idx=1), _make_event(idx=2)])
    shadow = _shadow(scenario)
    for s in shadow.event_scores:
        assert s.shadow_debt_pressure == s.base_pressure
        assert s.shadow_integrity_pressure == s.base_pressure
        assert s.graph_propagation_pressure == 0.0
    assert any(
        "no graph edges" in w for w in shadow.warnings
    )


def test_cycle_propagation_is_bounded_and_deterministic() -> None:
    """A cycle a → b → a must not blow up; max() is idempotent so the
    propagation converges in O(n) iterations and produces the same
    output across two calls."""
    a = _make_event(idx=1, constitutive_parents=["e2"], completion=0.0)
    b = _make_event(idx=2, constitutive_parents=["e1"], completion=0.0)
    s1 = _shadow(_scen([a, b]))
    s2 = _shadow(_scen([a, b]))
    assert s1.model_dump() == s2.model_dump()
    assert s1.graph_summary.propagation_iterations <= 10
    # Both events end at the same propagated value (max() is symmetric
    # on a 2-cycle of equal-base events).
    assert (
        s1.event_scores[0].shadow_debt_pressure
        == s1.event_scores[1].shadow_debt_pressure
    )


def test_graph_presence_does_not_unlock_vnet() -> None:
    """ADR-22 §rejected #2: edges in the scenario must not promote the
    shadow report to authoritative. Verified by the type pinning, but
    re-asserted here as a behavioural check."""
    parent = _make_event(idx=1)
    child = _make_event(idx=2, constitutive_parents=[parent.id])
    shadow = _shadow(_scen([parent, child]))
    # Even with a real edge, status stays blocked_by_readiness because
    # capability/benefit/observability are still default-0.5.
    assert shadow.status == "blocked_by_readiness"
    assert shadow.authoritative is False


def test_corrupt_plausible_success_remains_candidate_not_official() -> None:
    """A high-completion + low-grounding scenario yields high shadow
    pressure but the report status stays blocked_by_readiness; no
    corrupt_success verdict is emitted."""
    scenario = _scen([
        _make_event(
            idx=1,
            completion=1.0,
            tests_pass=1.0,
            operator_accept=1.0,
            preconditions=[
                PreconditionSpec(name="guard_detected", weight=0.25, verified=True),
                PreconditionSpec(name="static_scope_clean", weight=0.25, verified=True),
                PreconditionSpec(name="regression_green_on_scope", weight=0.25, verified=True),
                PreconditionSpec(name="negative_path_tested", weight=0.25, verified=False),
            ],
        )
    ])
    shadow = _shadow(scenario)
    assert shadow.status == "blocked_by_readiness"
    assert shadow.authoritative is False
    # No "corrupt_success" *field* in the schema (the recommendation
    # string may *mention* it as part of the honesty disclaimer; that's
    # signal, not a violation).
    dumped = shadow.model_dump()
    forbidden_keys = {
        "corrupt_success", "corrupt_success_ratio", "corrupt_success_verdict",
    }
    assert not (forbidden_keys & set(dumped.keys()))


def test_shadow_scores_are_clipped_to_unit_interval() -> None:
    """Even with extreme inputs (failing parents stacked on a failing
    child), every per-event score stays in [0, 1]."""
    parent = _make_event(idx=1, completion=0.0, operator_accept=0.0)
    child = _make_event(
        idx=2,
        completion=0.0,
        operator_accept=0.0,
        constitutive_parents=[parent.id],
        supportive_parents=[parent.id],
    )
    shadow = _shadow(_scen([parent, child]))
    for s in shadow.event_scores:
        assert 0.0 <= s.base_pressure <= 1.0
        assert 0.0 <= s.shadow_debt_pressure <= 1.0
        assert 0.0 <= s.shadow_integrity_pressure <= 1.0
        assert 0.0 <= s.graph_propagation_pressure <= 1.0


# ---------------------------------------------------------------------------
# D2 fixture comparisons — relative pressure ordering only
# ---------------------------------------------------------------------------


def test_shadow_clean_success_low_pressure() -> None:
    """A scenario with high completion + verified preconditions
    produces lower base pressure than one with all defaults."""
    clean = _scen([
        _make_event(
            idx=1, completion=0.95, operator_accept=0.95,
            preconditions=[
                PreconditionSpec(name="x", weight=1.0, verified=True),
            ],
        )
    ])
    default = _scen([_make_event(idx=1)])
    clean_p = _shadow(clean).event_scores[0].base_pressure
    default_p = _shadow(default).event_scores[0].base_pressure
    assert clean_p < default_p, (
        f"clean ({clean_p}) should be < default ({default_p})"
    )


def test_shadow_migration_without_rollback_medium_pressure() -> None:
    """Migration with 1/4 verified preconditions yields lower
    grounding → higher shadow pressure than fully-verified migration."""
    partial = _scen([
        _make_event(
            idx=1,
            completion=0.8,
            preconditions=[
                PreconditionSpec(name="migration_marker_detected", weight=0.25, verified=True),
                PreconditionSpec(name="data_preservation_checked", weight=0.25, verified=False),
                PreconditionSpec(
                    name="rollback_or_idempotency_checked",
                    weight=0.25, verified=False,
                ),
                PreconditionSpec(name="migration_test_evidence", weight=0.25, verified=False),
            ],
        )
    ])
    full = _scen([
        _make_event(
            idx=1,
            completion=0.8,
            preconditions=[
                PreconditionSpec(name="migration_marker_detected", weight=0.25, verified=True),
                PreconditionSpec(name="data_preservation_checked", weight=0.25, verified=True),
                PreconditionSpec(
                    name="rollback_or_idempotency_checked",
                    weight=0.25, verified=True,
                ),
                PreconditionSpec(name="migration_test_evidence", weight=0.25, verified=True),
            ],
        )
    ])
    partial_p = _shadow(partial).event_scores[0].base_pressure
    full_p = _shadow(full).event_scores[0].base_pressure
    assert partial_p > full_p


def test_shadow_import_dependency_with_constitutive_edge_propagates() -> None:
    """A high-pressure constitutive parent must raise the child's
    shadow_debt_pressure above its standalone base pressure (Block-C
    ablation analogue)."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=[PreconditionSpec(name="x", weight=1.0, verified=False)],
    )
    child_no_parent = _make_event(
        idx=2,
        completion=0.95, operator_accept=0.95,
        preconditions=[PreconditionSpec(name="x", weight=1.0, verified=True)],
    )
    child_with_parent = _make_event(
        idx=3,
        completion=0.95, operator_accept=0.95,
        preconditions=[PreconditionSpec(name="x", weight=1.0, verified=True)],
        constitutive_parents=[parent.id],
    )
    no_parent = _shadow(_scen([child_no_parent])).event_scores[0]
    with_parent = _shadow(_scen([parent, child_with_parent])).event_scores[1]
    assert with_parent.shadow_debt_pressure > no_parent.shadow_debt_pressure


def test_shadow_corrupt_plausible_success_high_pressure_but_not_official() -> None:
    """corrupt_plausible scenario shape: high completion + missing
    critical sub-precondition. Shadow must show non-trivial debt
    pressure (driven by 1 - grounding < 1.0) AND stay
    blocked_by_readiness."""
    scenario = _scen([
        _make_event(
            idx=1,
            completion=1.0,
            operator_accept=1.0,
            preconditions=[
                PreconditionSpec(name="g1", weight=0.25, verified=True),
                PreconditionSpec(name="g2", weight=0.25, verified=True),
                PreconditionSpec(name="g3", weight=0.25, verified=True),
                PreconditionSpec(name="critical", weight=0.25, verified=False),
            ],
        )
    ])
    shadow = _shadow(scenario)
    assert shadow.status == "blocked_by_readiness"
    p = shadow.event_scores[0].base_pressure
    # 0.40 * (1 - 0.75) + 0.20 * 0 + 0.25 * 0 + 0.15 * 0 = 0.10 — non-trivial
    # given 25% of preconditions remain unverified.
    assert p > 0.05

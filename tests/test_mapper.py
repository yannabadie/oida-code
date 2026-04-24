"""Tests for :mod:`oida_code.score.mapper` (Phase 2).

Covers the two responsibilities of the mapper:

1. **Round-trip** — Pydantic ↔ vendored ``Scenario`` is lossless on all event
   fields (advisor-mandated abstraction commit point).
2. **Synthesis + evidence linker** — ``obligations_to_scenario`` fills event
   defaults from the documented table, and ``_link_evidence_to_obligations``
   upgrades ``open`` preconditions to ``closed`` when pytest is green.
"""

from __future__ import annotations

from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer
from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.evidence import Finding, ToolEvidence
from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
    ScenarioConfig,
)
from oida_code.models.obligation import Obligation
from oida_code.score.mapper import (
    _link_evidence_to_obligations,
    analyze_scenario,
    obligations_to_scenario,
    pydantic_to_vendored,
    vendored_to_pydantic,
)


def _make_event(idx: int = 1, *, verified: bool = False) -> NormalizedEvent:
    return NormalizedEvent(
        id=f"e{idx}",
        pattern_id=f"p_{idx}",
        task=f"task {idx}",
        capability=0.7,
        reversibility=0.4,
        observability=0.6,
        blast_radius=0.3,
        completion=0.8,
        tests_pass=0.9,
        operator_accept=1.0,
        benefit=0.5,
        preconditions=[PreconditionSpec(name="p1", weight=1.0, verified=verified)],
        constitutive_parents=[],
        supportive_parents=[],
        invalidates_pattern=False,
    )


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_roundtrip_preserves_all_event_fields() -> None:
    original = NormalizedScenario(
        name="rt",
        description="round-trip",
        config=ScenarioConfig(),
        events=[_make_event(1, verified=True), _make_event(2)],
    )
    vendored = pydantic_to_vendored(original)
    back = vendored_to_pydantic(vendored)
    # Compare via model_dump to ignore Pydantic object identity
    assert back.model_dump() == original.model_dump()


def test_roundtrip_preserves_scenario_config() -> None:
    original = NormalizedScenario(
        name="rt",
        description="",
        config=ScenarioConfig(m_baseline=0.05, q_baseline=0.4),
        events=[],
    )
    vendored = pydantic_to_vendored(original)
    # vendored config is a plain dict[str, float]
    assert vendored.config.get("m_baseline") == 0.05
    assert vendored.config.get("q_baseline") == 0.4


def test_analyze_scenario_returns_expected_keys() -> None:
    scenario = NormalizedScenario(
        name="smoke",
        description="",
        events=[_make_event(1)],
    )
    report = analyze_scenario(scenario)
    # Minimal shape contract expected by downstream verdict/report layers.
    assert "summary" in report
    summary = report["summary"]
    for key in ("event_count", "mean_q_obs", "mean_grounding", "total_v_net"):
        assert key in summary


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


def test_obligations_to_scenario_uses_documented_defaults() -> None:
    obligations = [
        Obligation(
            id="o-1",
            kind="precondition",
            scope="src/foo.py",
            description="x must be > 0",
        ),
    ]
    scenario = obligations_to_scenario(obligations)
    assert len(scenario.events) == 1
    ev = scenario.events[0]
    # Defaults documented in the mapper's default-origin table.
    assert ev.capability == 0.5
    assert ev.observability == 0.5
    assert ev.benefit == 0.5
    # Regression/tests_pass/operator_accept default to 0.5 when no evidence.
    assert ev.completion == 0.5
    assert ev.tests_pass == 0.5
    assert ev.operator_accept == 0.5


def test_obligations_to_scenario_empty_list_returns_empty_events() -> None:
    scenario = obligations_to_scenario([])
    assert scenario.events == []
    # Analyzer must handle this without crashing (advisor edge case).
    report = analyze_scenario(scenario)
    assert report["summary"]["event_count"] == 0


# ---------------------------------------------------------------------------
# Evidence linker
# ---------------------------------------------------------------------------


def _pytest_green(total: int = 5) -> ToolEvidence:
    return ToolEvidence(
        tool="pytest",
        status="ok",
        duration_ms=10,
        counts={"total": total, "failure": 0, "error": 0},
    )


def _pytest_red() -> ToolEvidence:
    return ToolEvidence(
        tool="pytest",
        status="ok",
        duration_ms=10,
        counts={"total": 5, "failure": 2, "error": 0},
    )


def test_linker_closes_precondition_when_pytest_green_and_scope_in_changed_files() -> None:
    ob = Obligation(
        id="o-1",
        kind="precondition",
        scope="src/foo.py",
        description="x > 0",
    )
    linked = _link_evidence_to_obligations(
        [ob], [_pytest_green()], changed_files=["src/foo.py"]
    )
    assert linked[0].status == "closed"


def test_linker_leaves_precondition_open_when_pytest_red() -> None:
    ob = Obligation(
        id="o-1",
        kind="precondition",
        scope="src/foo.py",
        description="x > 0",
    )
    linked = _link_evidence_to_obligations(
        [ob], [_pytest_red()], changed_files=["src/foo.py"]
    )
    assert linked[0].status == "open"


def test_linker_leaves_precondition_open_when_scope_not_in_changed_files() -> None:
    ob = Obligation(
        id="o-1",
        kind="precondition",
        scope="src/foo.py",
        description="x > 0",
    )
    linked = _link_evidence_to_obligations(
        [ob], [_pytest_green()], changed_files=["src/bar.py"]
    )
    assert linked[0].status == "open"


def test_linker_closes_api_contract_when_ruff_and_mypy_green_for_file() -> None:
    ob = Obligation(
        id="o-1",
        kind="api_contract",
        scope="src/app.py",
        description="GET /health returns 200",
    )
    ruff = ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={})
    mypy = ToolEvidence(tool="mypy", status="ok", duration_ms=5, findings=[], counts={})
    linked = _link_evidence_to_obligations(
        [ob], [ruff, mypy], changed_files=["src/app.py"]
    )
    assert linked[0].status == "closed"


def test_linker_leaves_api_contract_open_when_mypy_has_error_on_file() -> None:
    ob = Obligation(
        id="o-1",
        kind="api_contract",
        scope="src/app.py",
        description="GET /health returns 200",
    )
    ruff = ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={})
    mypy = ToolEvidence(
        tool="mypy",
        status="ok",
        duration_ms=5,
        findings=[
            Finding(
                tool="mypy",
                rule_id="assignment",
                severity="error",
                path="src/app.py",
                line=1,
                column=0,
                message="bad type",
                evidence_kind="static",
            )
        ],
        counts={"error": 1},
    )
    linked = _link_evidence_to_obligations(
        [ob], [ruff, mypy], changed_files=["src/app.py"]
    )
    assert linked[0].status == "open"


def test_linker_api_contract_falls_back_to_scope_path_when_no_changed_files() -> None:
    """When ``changed_files`` is empty the linker strips ``::symbol`` from the
    scope and uses the path half to match ruff/mypy findings."""
    ob = Obligation(
        id="o-1",
        kind="api_contract",
        scope="src/app.py::list_items",
        description="GET /items",
    )
    ruff = ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={})
    mypy = ToolEvidence(tool="mypy", status="ok", duration_ms=5, findings=[], counts={})
    linked = _link_evidence_to_obligations([ob], [ruff, mypy], changed_files=None)
    assert linked[0].status == "closed"


def test_linker_preserves_violated_status() -> None:
    ob = Obligation(
        id="o-1",
        kind="precondition",
        scope="src/foo.py",
        description="x > 0",
        status="violated",
    )
    linked = _link_evidence_to_obligations(
        [ob], [_pytest_green()], changed_files=["src/foo.py"]
    )
    assert linked[0].status == "violated"


def test_obligations_to_scenario_uses_request_changed_files_for_linking() -> None:
    """Integration: passing a request wires changed_files into the linker and
    grounding becomes non-zero when evidence supports it."""
    ob = Obligation(
        id="o-1",
        kind="precondition",
        scope="src/foo.py",
        description="x > 0",
    )
    request = AuditRequest(
        repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/foo.py"]),
    )
    scenario = obligations_to_scenario(
        [ob], request=request, tool_evidence=[_pytest_green()]
    )
    assert len(scenario.events) == 1
    # The synthesized precondition should carry verified=True.
    assert scenario.events[0].preconditions[0].verified is True

    # And feeding the scenario to the analyzer should yield non-zero grounding.
    vendored = pydantic_to_vendored(scenario)
    report = OIDAAnalyzer(vendored).analyze()
    assert report["summary"]["mean_grounding"] > 0.0


# ---------------------------------------------------------------------------
# Block B (ADR-20) — obligation → 1..N PreconditionSpec with weight conservation
# ---------------------------------------------------------------------------


import pytest  # noqa: E402 — grouped with Block B section

from oida_code.score.mapper import _preconditions_for  # noqa: E402


def _pytest_green_on(scope: str) -> ToolEvidence:
    return ToolEvidence(
        tool="pytest",
        status="ok",
        duration_ms=10,
        counts={"total": 3, "failure": 0, "error": 0},
        findings=[],
    )


def _static_clean() -> list[ToolEvidence]:
    return [
        ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={}),
        ToolEvidence(tool="mypy", status="ok", duration_ms=5, findings=[], counts={}),
    ]


def test_precondition_expands_to_multiple_children() -> None:
    """ADR-20 multiplicity: precondition → 4 named children."""
    ob = Obligation(
        id="o-pre-b1",
        kind="precondition",
        scope="src/foo.py::f",
        description="x > 0",
        weight=1,
    )
    children = _preconditions_for(ob, tool_evidence=[], changed_files=[])
    names = [c.name for c in children]
    assert names == [
        "guard_detected",
        "static_scope_clean",
        "regression_green_on_scope",
        "negative_path_tested",
    ]


def test_child_weights_sum_to_parent_weight() -> None:
    """ADR-20 weight conservation: children weights sum EXACTLY to parent."""
    for kind in (
        "precondition",
        "api_contract",
        "migration",
        "security_rule",
        "observability",
        "invariant",
    ):
        for weight in (1, 3, 7):
            ob = Obligation(
                id=f"o-{kind[:3]}-wconserv",
                kind=kind,  # type: ignore[arg-type]
                scope="src/foo.py::f",
                description="test",
                weight=weight,
            )
            children = _preconditions_for(ob, tool_evidence=[], changed_files=[])
            total = sum(c.weight for c in children)
            assert total == pytest.approx(float(weight), rel=1e-12), (
                f"weight conservation broken for kind={kind}, weight={weight}: "
                f"children sum to {total}, parent is {weight}"
            )


def test_api_contract_partial_grounding_static_green_only() -> None:
    """Static-clean-only evidence verifies 2/4 children of an api_contract
    obligation: endpoint_or_function_declared (extracted source) and
    static_shape_clean. Regression + error/auth path stay False."""
    ob = Obligation(
        id="o-api-b3",
        kind="api_contract",
        scope="src/app.py::list_items",
        description="GET /items",
        source="extracted",
        weight=1,
    )
    children = _preconditions_for(
        ob, tool_evidence=_static_clean(), changed_files=["src/app.py"]
    )
    verified = {c.name for c in children if c.verified}
    assert verified == {"endpoint_or_function_declared", "static_shape_clean"}
    # Partial grounding: strictly between 0 and 1
    vw = sum(c.weight for c in children if c.verified)
    tw = sum(c.weight for c in children)
    grounding = vw / tw
    assert 0.0 < grounding < 1.0
    assert grounding == pytest.approx(0.5, rel=1e-12)


def test_pytest_green_does_not_close_negative_path() -> None:
    """A precondition obligation with pytest-green + static-clean still
    leaves ``negative_path_tested`` unverified. Pytest-green is NOT
    blanket proof of all sub-conditions (ADR-20 rejected alternative #3)."""
    ob = Obligation(
        id="o-pre-b4",
        kind="precondition",
        scope="src/foo.py::f",
        description="x > 0",
        source="extracted",
        weight=1,
    )
    evidence = [*_static_clean(), _pytest_green_on("src/foo.py")]
    children = _preconditions_for(
        ob, tool_evidence=evidence, changed_files=["src/foo.py"]
    )
    by_name = {c.name: c for c in children}
    # 3 of 4 verified; negative path remains unverified.
    assert by_name["guard_detected"].verified is True
    assert by_name["static_scope_clean"].verified is True
    assert by_name["regression_green_on_scope"].verified is True
    assert by_name["negative_path_tested"].verified is False


def test_migration_marker_detected_but_rollback_unverified() -> None:
    """Migration extractor detects the marker, but rollback + data
    preservation need richer evidence than Phase-3.5 has. Even with
    full pytest-green, 3 of 4 children are ``verified=False``."""
    ob = Obligation(
        id="o-mig-b5",
        kind="migration",
        scope="migrations/001_init.sql",
        description="add users table",
        source="extracted",
        weight=1,
    )
    children = _preconditions_for(
        ob,
        tool_evidence=[_pytest_green_on("migrations/001_init.sql")],
        changed_files=["migrations/001_init.sql"],
    )
    by_name = {c.name: c for c in children}
    assert by_name["migration_marker_detected"].verified is True
    assert by_name["data_preservation_checked"].verified is False
    assert by_name["rollback_or_idempotency_checked"].verified is False
    # Migration test evidence: pytest ran green and scope is in changed.
    assert by_name["migration_test_evidence"].verified is True


def test_unexpanded_kind_returns_single_false_precondition() -> None:
    """Unknown obligation kind → single ``unexpanded_<kind>`` child
    with ``verified=False`` and parent weight. Guards against future
    enum values landing without a registered expander."""
    # Use model_construct to bypass the Literal validator.
    ob = Obligation.model_construct(
        id="o-new-kind01",
        kind="future_kind",  # type: ignore[arg-type]
        scope="src/x.py",
        description="future",
        weight=2,
    )
    children = _preconditions_for(ob, tool_evidence=[], changed_files=[])
    assert len(children) == 1
    assert children[0].name == "unexpanded_future_kind"
    assert children[0].verified is False
    assert children[0].weight == pytest.approx(2.0, rel=1e-12)


def test_existing_roundtrip_still_preserves_preconditions() -> None:
    """Block B acceptance #6: Pydantic ↔ vendored round-trip unchanged
    on multi-child events."""
    ob = Obligation(
        id="o-pre-b7",
        kind="precondition",
        scope="src/foo.py::f",
        description="x > 0",
        source="extracted",
        weight=1,
    )
    scenario = obligations_to_scenario(
        [ob],
        request=AuditRequest(
            repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
            scope=ScopeSpec(changed_files=["src/foo.py"]),
        ),
        tool_evidence=_static_clean(),
    )
    vendored = pydantic_to_vendored(scenario)
    back = vendored_to_pydantic(vendored)
    assert back.model_dump() == scenario.model_dump()
    # Each event must have 4 preconditions for the precondition kind.
    assert len(scenario.events[0].preconditions) == 4


def test_partial_grounding_example_half_verified() -> None:
    """ADR-20 acceptance #4 — partial verification yields partial
    grounding. parent weight=1, 4 children, 2 verified → grounding =
    sum(verified_weights) / 1 = 0.5, strictly between 0 and 1."""
    ob = Obligation(
        id="o-pre-b8",
        kind="precondition",
        scope="src/foo.py::f",
        description="x > 0",
        source="extracted",
        weight=1,
    )
    # guard_detected (extracted=True) + regression_green (pytest + changed)
    # = 2/4 verified; static_scope_clean False (no ruff/mypy) and
    # negative_path_tested False.
    children = _preconditions_for(
        ob,
        tool_evidence=[_pytest_green_on("src/foo.py")],
        changed_files=["src/foo.py"],
    )
    verified_weight = sum(c.weight for c in children if c.verified)
    total_weight = sum(c.weight for c in children)
    grounding = verified_weight / total_weight
    assert grounding == pytest.approx(0.5, rel=1e-12)
    assert 0.0 < grounding < 1.0

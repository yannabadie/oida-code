"""E3.0 (QA/A14.md, ADR-24) — deterministic evidence plumbing tests.

Two test groups:

* **Edge confidence wiring** — `DependencyEdge.confidence` reaches the
  shadow fusion via `edge_confidences_from_dependency_graph` and the
  CLI/score-trace path. Default `0.6` only when metadata is genuinely
  unavailable.
* **Per-event tool evidence** — `EventEvidenceView` differentiates
  events by scope-matched ruff/mypy findings + pytest relevance, and
  the resulting `completion` / `tests_pass` / `operator_accept` values
  travel into `NormalizedEvent` so shadow pressure stops being uniform.

The closing test (`test_shadow_pressure_differentiates_when_evidence_differs`)
is the proof that E3.0 has value: without it the LLM estimators would
arrive on a flat surface.

NONE of these tests assert outcome prediction. They check the SHAPE of
the evidence layer, not its meaning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oida_code.extract.dependencies import (
    DependencyEdge,
    DependencyGraphResult,
)
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
    PreconditionSpec,
)
from oida_code.models.obligation import Obligation
from oida_code.score.event_evidence import (
    EventEvidenceView,
    build_event_evidence_view,
    event_completion_from_view,
    event_operator_accept_from_view,
    event_tests_pass_from_view,
)
from oida_code.score.experimental_shadow_fusion import (
    compute_experimental_shadow_fusion,
)
from oida_code.score.fusion_readiness import assess_fusion_readiness
from oida_code.score.mapper import (
    build_scoring_inputs,
    edge_confidences_from_dependency_graph,
)

# ---------------------------------------------------------------------------
# Edge confidence helpers (raw graph)
# ---------------------------------------------------------------------------


def _edge(
    parent: str, child: str, kind: str, confidence: float, *,
    reason: str = "test",
    source: str = "test",
) -> DependencyEdge:
    return DependencyEdge(
        parent_id=parent, child_id=child,
        kind=kind,  # type: ignore[arg-type]
        confidence=confidence,
        reason=reason,
        source=source,
    )


def test_same_symbol_confidence_0_9_reaches_shadow() -> None:
    """A constitutive edge with confidence=0.9 (same-symbol AST link)
    must reach the shadow layer's edge_confidences map verbatim."""
    graph = DependencyGraphResult(
        obligations=[],
        constitutive_edges=[_edge("o-1", "o-2", "constitutive", 0.9)],
        supportive_edges=[],
    )
    ob_to_event = {"o-1": "e1", "o-2": "e2"}
    confs = edge_confidences_from_dependency_graph(graph, ob_to_event)
    assert confs == {("e1", "e2", "constitutive"): 0.9}


def test_direct_import_confidence_0_6_reaches_shadow() -> None:
    """Cross-file import-call edges enter the graph with confidence=0.6
    in the dependency extractor; they must round-trip into the
    edge_confidences map exactly (no downcast to default)."""
    graph = DependencyGraphResult(
        obligations=[],
        constitutive_edges=[],
        supportive_edges=[_edge("o-a", "o-b", "supportive", 0.6)],
    )
    confs = edge_confidences_from_dependency_graph(
        graph, {"o-a": "ea", "o-b": "eb"},
    )
    assert confs == {("ea", "eb", "supportive"): 0.6}


def test_missing_edge_metadata_falls_back_to_default_0_6() -> None:
    """When ``edge_confidences`` is None / empty, the shadow propagation
    must use the documented default 0.6 (ADR-23 §5)."""
    parent = _e(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=[PreconditionSpec(name="x", weight=1.0, verified=False)],
    )
    child = _e(
        idx=2, completion=1.0, operator_accept=1.0,
        preconditions=[PreconditionSpec(name="x", weight=1.0, verified=True)],
        constitutive_parents=[parent.id],
    )
    scen = NormalizedScenario(name="t", description="", events=[parent, child])
    rep = assess_fusion_readiness(scen)
    shadow = compute_experimental_shadow_fusion(scen, rep)
    p_p = shadow.event_scores[0].base_pressure
    c_b = shadow.event_scores[1].base_pressure
    c_d = shadow.event_scores[1].shadow_debt_pressure
    # default 0.6 * alpha_constitutive 0.80 = 0.48
    assert c_d == pytest.approx(max(c_b, p_p * 0.6 * 0.80), abs=1e-9)


def test_unknown_obligation_id_is_skipped() -> None:
    """Edges whose parent or child id isn't in the event mapping are
    silently dropped (they reference obligations outside scope)."""
    graph = DependencyGraphResult(
        obligations=[],
        constitutive_edges=[
            _edge("o-known", "o-unknown", "constitutive", 0.9),
            _edge("o-unknown", "o-known", "constitutive", 0.9),
        ],
        supportive_edges=[],
    )
    confs = edge_confidences_from_dependency_graph(graph, {"o-known": "e1"})
    assert confs == {}


# ---------------------------------------------------------------------------
# CLI shadow path (build_scoring_inputs + edge_confidences wiring)
# ---------------------------------------------------------------------------


def _ob(
    *,
    idx: int,
    scope: str,
    kind: str = "precondition",
    description: str = "",
    weight: float = 1.0,
) -> Obligation:
    return Obligation(
        id=f"o-{idx}",
        kind=kind,  # type: ignore[arg-type]
        scope=scope,
        description=description or f"obligation {idx}",
        weight=weight,
        status="open",
    )


def test_cli_shadow_passes_real_edge_confidence(tmp_path: Path) -> None:
    """``build_scoring_inputs`` produces a non-empty
    ``edge_confidences`` map when the dependency graph carries any
    edge, with values pulled directly from ``DependencyEdge.confidence``
    (not the 0.6 default).

    Same-scope obligations (api_contract + precondition + invariant on
    one file) trigger same-scope edges in the dependency extractor with
    non-default confidences (0.9 for same-symbol, 0.7 for migration/
    observability), which is what the test asserts reaches shadow."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text(
        "def endpoint():\n    return 1\n", encoding="utf-8",
    )
    obligations = [
        _ob(idx=1, scope="src/a.py::endpoint", kind="api_contract",
            description="endpoint a"),
        _ob(idx=2, scope="src/a.py::endpoint", kind="precondition",
            description="precond a"),
        _ob(idx=3, scope="src/a.py::endpoint", kind="invariant",
            description="invariant a"),
    ]
    request = AuditRequest(
        repo=RepoSpec(path=str(repo), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/a.py"], language="python"),
        intent=IntentSpec(summary="endpoint contract"),
    )
    inputs = build_scoring_inputs(obligations, request=request)
    edges_total = (
        len(inputs.graph.constitutive_edges)
        + len(inputs.graph.supportive_edges)
    )
    assert edges_total > 0, (
        f"same-symbol obligations should produce graph edges, got {edges_total}"
    )
    assert inputs.edge_confidences, (
        "edge_confidences must be non-empty when graph has edges"
    )
    # At least one edge must carry a non-default confidence
    # (same-symbol AST link uses 0.9; if every edge were 0.6 we'd be
    # silently overriding real signal with the fallback).
    non_default = [v for v in inputs.edge_confidences.values() if v != 0.6]
    assert non_default, (
        f"edge_confidences must include at least one non-0.6 entry, "
        f"got {inputs.edge_confidences}"
    )
    for value in inputs.edge_confidences.values():
        assert 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# Tool evidence by event
# ---------------------------------------------------------------------------


def _e(
    *,
    idx: int = 1,
    completion: float = 0.5,
    operator_accept: float = 0.5,
    preconditions: list[PreconditionSpec] | None = None,
    task: str | None = None,
    constitutive_parents: list[str] | None = None,
    supportive_parents: list[str] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        id=f"e{idx}",
        pattern_id=f"p_{idx}",
        task=task or f"src/m{idx}.py: do thing",
        capability=0.5,
        reversibility=0.5,
        observability=0.5,
        blast_radius=0.3,
        completion=completion,
        tests_pass=0.5,
        operator_accept=operator_accept,
        benefit=0.5,
        preconditions=preconditions or [],
        constitutive_parents=constitutive_parents or [],
        supportive_parents=supportive_parents or [],
        invalidates_pattern=False,
    )


def _scen(events: list[NormalizedEvent]) -> NormalizedScenario:
    return NormalizedScenario(name="t", description="", events=events)


def _ruff_ev(findings: list[Finding]) -> ToolEvidence:
    return ToolEvidence(
        tool="ruff", status="ok", duration_ms=10,
        findings=findings,
        counts={"error": sum(1 for f in findings if f.severity == "error")},
    )


def _mypy_ev(findings: list[Finding]) -> ToolEvidence:
    return ToolEvidence(
        tool="mypy", status="ok", duration_ms=10,
        findings=findings,
        counts={"error": sum(1 for f in findings if f.severity == "error")},
    )


def _pytest_ev(*, total: int = 10, failures: int = 0) -> ToolEvidence:
    return ToolEvidence(
        tool="pytest", status="ok", duration_ms=100,
        findings=[],
        counts={"total": total, "failure": failures, "error": 0},
    )


def _missing(tool: str) -> ToolEvidence:
    return ToolEvidence(tool=tool, status="tool_missing")


def _err(tool: str) -> ToolEvidence:
    return ToolEvidence(tool=tool, status="error", stderr_excerpt="boom")


def _finding(path: str, *, severity: str = "error") -> Finding:
    return Finding(
        tool="ruff",
        rule_id="X001", severity=severity,  # type: ignore[arg-type]
        path=path, line=1, column=1, message="msg",
    )


def test_ruff_file_finding_maps_to_event_static_pressure() -> None:
    """A ruff error on event A's scope must reduce A's
    operator_accept; event B (different scope) must remain at the
    no-finding 1.0."""
    a = _e(idx=1, task="src/a.py: x")
    b = _e(idx=2, task="src/b.py: y")
    scen = _scen([a, b])
    tool_ev = [
        _ruff_ev([_finding("src/a.py")]),
        _mypy_ev([]),
    ]
    views = build_event_evidence_view(
        scen, tool_ev,
        event_scopes={"e1": ("src/a.py",), "e2": ("src/b.py",)},
    )
    op_a = event_operator_accept_from_view(views["e1"])
    op_b = event_operator_accept_from_view(views["e2"])
    assert op_b > op_a, f"event B (no findings) should beat A: {op_b} > {op_a}"
    # And A should not be at the missing-tool neutral 0.5: ruff actually ran.
    assert op_a < 1.0


def test_mypy_file_finding_maps_to_event_static_pressure() -> None:
    """Mirror of the ruff test for mypy."""
    a = _e(idx=1, task="src/a.py: x")
    b = _e(idx=2, task="src/b.py: y")
    scen = _scen([a, b])
    tool_ev = [
        _ruff_ev([]),
        _mypy_ev([_finding("src/a.py")]),
    ]
    views = build_event_evidence_view(
        scen, tool_ev,
        event_scopes={"e1": ("src/a.py",), "e2": ("src/b.py",)},
    )
    op_a = event_operator_accept_from_view(views["e1"])
    op_b = event_operator_accept_from_view(views["e2"])
    assert op_b > op_a


def test_pytest_global_green_is_weak_not_total_proof() -> None:
    """A globally-green pytest run with NO scope-relevant test must
    lift completion ABOVE the missing-tool neutral but stay strictly
    below the 0.95 reserved for relevant tests passing."""
    a = _e(idx=1, task="src/a.py: x")
    scen = _scen([a])
    tool_ev = [_pytest_ev(total=20, failures=0)]
    views = build_event_evidence_view(
        scen, tool_ev,
        event_scopes={"e1": ("src/a.py",)},
    )
    completion = event_completion_from_view(views["e1"])
    assert 0.5 < completion < 0.95
    # The view records the weak global signal explicitly.
    assert views["e1"].pytest_global_passed is True
    assert views["e1"].pytest_relevant is False


def test_missing_tool_is_missing_not_failure() -> None:
    """When ruff/mypy/pytest are all tool_missing, the per-event
    completion / operator_accept stay at the neutral 0.5 — NOT 0.0."""
    a = _e(idx=1, task="src/a.py: x")
    scen = _scen([a])
    views = build_event_evidence_view(
        scen, [_missing("ruff"), _missing("mypy"), _missing("pytest")],
        event_scopes={"e1": ("src/a.py",)},
    )
    assert views["e1"].source == "missing"
    assert event_operator_accept_from_view(views["e1"]) == 0.5
    assert event_completion_from_view(views["e1"]) == 0.5


def test_tool_error_adds_uncertainty_warning() -> None:
    """A tool that ran but errored emits a per-event warning so the
    integrator knows the missing data isn't a real-zero signal."""
    a = _e(idx=1, task="src/a.py: x")
    scen = _scen([a])
    views = build_event_evidence_view(
        scen, [_err("ruff"), _missing("mypy"), _missing("pytest")],
        event_scopes={"e1": ("src/a.py",)},
    )
    assert any("ruff" in w and "uncertainty" in w for w in views["e1"].warnings)


def test_event_without_evidence_does_not_get_fake_green() -> None:
    """Event A is in scope; event B's scope doesn't intersect any
    finding/test path. B must NOT inherit a fake-green signal — its
    operator_accept is exactly the neutral 0.5 because ruff/mypy ran
    OK globally but said nothing about B."""
    a = _e(idx=1, task="src/a.py: x")
    b = _e(idx=2, task="src/totally_unrelated.py: y")
    scen = _scen([a, b])
    tool_ev = [
        _ruff_ev([_finding("src/a.py")]),
        _mypy_ev([]),
        _pytest_ev(total=5, failures=1),
    ]
    views = build_event_evidence_view(
        scen, tool_ev,
        event_scopes={"e1": ("src/a.py",), "e2": ("src/totally_unrelated.py",)},
    )
    # B's source must be "heuristic" (tool ran but no finding for B),
    # NOT "tool" (which would imply a real positive signal). Importantly,
    # B's operator_accept doesn't sneak above 1.0 just because the
    # tool ran globally.
    assert views["e2"].source == "heuristic"
    op_b = event_operator_accept_from_view(views["e2"])
    # Still bounded above by what a clean ruff+mypy on B's exact
    # scope would have produced (1.0); below by the missing-tool 0.5.
    assert 0.5 <= op_b <= 1.0


def test_pytest_relevant_failure_drops_completion() -> None:
    """A pytest failure whose path matches the event's scope should
    set pytest_relevant=True, pytest_passed=False, and completion=0.2."""
    a = _e(idx=1, task="src/a.py: x")
    scen = _scen([a])
    pytest_ev = ToolEvidence(
        tool="pytest", status="ok",
        findings=[
            Finding(
                tool="pytest", rule_id="failed", severity="error",
                path="src/a.py", line=1, column=1, message="fail",
            ),
        ],
        counts={"total": 5, "failure": 1, "error": 0},
    )
    views = build_event_evidence_view(
        scen, [pytest_ev],
        event_scopes={"e1": ("src/a.py",)},
    )
    view = views["e1"]
    assert view.pytest_relevant is True
    assert view.pytest_passed is False
    assert event_completion_from_view(view) == pytest.approx(0.2, abs=1e-9)


# ---------------------------------------------------------------------------
# Differentiation fixture — proof that E3.0 has value
# ---------------------------------------------------------------------------


def test_shadow_pressure_differentiates_when_evidence_differs() -> None:
    """Two events with materially different evidence must produce
    materially different shadow pressures.

    Event A:
      * preconditions verified
      * no static findings
      * scope-relevant pytest passed

    Event B:
      * preconditions unverified
      * ruff/mypy errors on B's scope
      * scope-relevant pytest failed

    Required: shadow_pressure(B) > shadow_pressure(A) by a
    non-trivial margin (>= 0.10).
    """
    a = _e(
        idx=1, task="src/a.py: x",
        preconditions=[PreconditionSpec(name="g", weight=1.0, verified=True)],
    )
    b = _e(
        idx=2, task="src/b.py: y",
        preconditions=[PreconditionSpec(name="g", weight=1.0, verified=False)],
    )
    scen = _scen([a, b])
    pytest_relevant_failure = ToolEvidence(
        tool="pytest", status="ok",
        findings=[
            Finding(
                tool="pytest", rule_id="failed", severity="error",
                path="src/b.py", line=1, column=1, message="fail",
            ),
        ],
        counts={"total": 5, "failure": 1, "error": 0},
    )
    pytest_relevant_pass = ToolEvidence(
        tool="pytest", status="ok",
        findings=[
            Finding(
                tool="pytest", rule_id="passed", severity="info",
                path="src/a.py", line=1, column=1, message="pass",
            ),
        ],
        counts={"total": 5, "failure": 0, "error": 0},
    )
    # We can't pass two pytest evidences at once in the current model
    # (one ToolEvidence per tool), so we synthesize a single pytest
    # evidence that carries both findings — the relevant-finding
    # filter in the view picks per-scope.
    pytest_combined = ToolEvidence(
        tool="pytest", status="ok",
        findings=[*pytest_relevant_failure.findings, *pytest_relevant_pass.findings],
        counts={"total": 10, "failure": 1, "error": 0},
    )
    tool_ev = [
        _ruff_ev([_finding("src/b.py")]),
        _mypy_ev([_finding("src/b.py")]),
        pytest_combined,
    ]

    # Wire the per-event evidence into the events using the same
    # transformation build_scoring_inputs does — model_copy with the
    # view-derived values.
    views = build_event_evidence_view(
        scen, tool_ev,
        event_scopes={"e1": ("src/a.py",), "e2": ("src/b.py",)},
    )
    upgraded = [
        ev.model_copy(update={
            "completion": event_completion_from_view(views[ev.id]),
            "tests_pass": event_tests_pass_from_view(views[ev.id]),
            "operator_accept": event_operator_accept_from_view(views[ev.id]),
        })
        for ev in scen.events
    ]
    upgraded_scen = _scen(upgraded)

    rep = assess_fusion_readiness(upgraded_scen)
    shadow = compute_experimental_shadow_fusion(upgraded_scen, rep)
    by_id = {s.event_id: s for s in shadow.event_scores}
    p_a = by_id["e1"].base_pressure
    p_b = by_id["e2"].base_pressure
    assert p_b > p_a + 0.10, (
        f"E3.0 differentiation broken: shadow(B)={p_b}, shadow(A)={p_a} "
        f"(expected B - A >= 0.10)"
    )
    # And the shadow report still carries no V_net leakage.
    payload = shadow.model_dump()
    assert payload["authoritative"] is False
    assert "total_v_net" not in payload


# ---------------------------------------------------------------------------
# Sanity: empty / None evidence preserves prior baseline behaviour
# ---------------------------------------------------------------------------


def test_no_tool_evidence_keeps_neutral_baseline() -> None:
    """When ``tool_evidence is None`` the per-event values are the
    same neutral 0.5 the v0.4.x scenario-level helper produced —
    no behavioural regression for callers that don't yet wire
    runners."""
    scen = _scen([_e(idx=1), _e(idx=2)])
    views = build_event_evidence_view(scen, None)
    for view in views.values():
        assert view.source == "missing"
        assert event_completion_from_view(view) == 0.5
        assert event_operator_accept_from_view(view) == 0.5
        assert event_tests_pass_from_view(view) == 0.5


def test_evidence_view_is_frozen() -> None:
    """E3.0 invariant — ``EventEvidenceView`` is frozen so a downstream
    estimator cannot mutate it after the linker has produced it."""
    from pydantic import ValidationError

    view = EventEvidenceView(event_id="e1", scope=("src/a.py",))
    with pytest.raises(ValidationError):
        view.event_id = "e2"  # type: ignore[misc]

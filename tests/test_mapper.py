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

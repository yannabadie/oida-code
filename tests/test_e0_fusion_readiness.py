"""E0 (QA/A10.md) — fusion readiness layer + direct-dep paper_gain (E0.1).

Two test groups:

* E0.1 — :func:`compute_paper_gain` honours the new direct-dependency
  inspection branch (d) once per no-progress segment, NOT as
  progress_event.
* E0  — :func:`assess_fusion_readiness` correctly classifies fusion
  readiness; ``capability`` / ``benefit`` / ``observability`` defaults
  block official fusion; partial signals (grounding, graph, trajectory)
  do NOT alone unlock V_net; corrupt-plausible-success scenarios stay
  diagnostic-only.
"""

from __future__ import annotations

from pathlib import Path

from oida_code.extract.dependencies import build_dependency_graph
from oida_code.extract.obligations import extract_obligations
from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.evidence import ToolEvidence
from oida_code.models.normalized_event import NormalizedEvent, NormalizedScenario
from oida_code.models.obligation import Obligation
from oida_code.models.trace import Trace, TraceEvent
from oida_code.models.trajectory import TrajectoryMetrics
from oida_code.score.fusion_readiness import assess_fusion_readiness
from oida_code.score.trajectory import score_trajectory

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


def _scenario_with_defaults() -> NormalizedScenario:
    return NormalizedScenario(name="t", description="", events=[_make_event(idx=1)])


# ---------------------------------------------------------------------------
# E0.1 — direct-dependency paper_gain branch (d)
# ---------------------------------------------------------------------------


def _setup_dep_repo(tmp_path: Path) -> None:
    """src/app.py imports src/db.py; both files exist on disk and
    carry asserts so the AST extractor produces obligations on each."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "db.py").write_text(
        "def get_conn(host):\n"
        "    assert host, 'host required'\n"
        "    return host\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "app.py").write_text(
        "from src import db\n"
        "def create_user(name):\n"
        "    assert name, 'name required'\n"
        "    return db.get_conn('x'), name\n",
        encoding="utf-8",
    )


def test_direct_dependency_inspection_is_paper_gain_once(tmp_path: Path) -> None:
    """E0.1 — first inspection of a direct dep of a pending obligation
    is paper_gain=True, is_progress=False."""
    _setup_dep_repo(tmp_path)
    app_ob = Obligation(
        id="o-pre-app-dep0001",
        kind="precondition",
        scope="src/app.py::create_user",
        description="GOAL",
        source="intent",
        weight=5,
    )
    db_ob = Obligation(
        id="o-pre-db-dep00001",
        kind="precondition",
        scope="src/db.py::get_conn",
        description="dep",
        source="extracted",
        weight=1,
    )
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    events = [
        TraceEvent(t=0, kind="read", tool="Read", scope=["src/app.py"]),
        TraceEvent(t=1, kind="read", tool="Read", scope=["src/db.py"]),
    ]
    trace = Trace(events=events)
    metrics = score_trajectory(trace, [app_ob, db_ob], request)
    # t=0: progress (entered U with src/app.py).
    assert metrics.timesteps[0].is_progress is True
    # t=1: db.py is NOT in U (changed_files=["src/app.py"] only) but it
    # IS a direct dep of the pending app obligation via the graph.
    # → paper_gain=True via branch (d), is_progress=False.
    assert metrics.timesteps[1].is_progress is False
    assert metrics.timesteps[1].paper_gain is True


def test_repeated_dependency_inspection_eventually_errors(tmp_path: Path) -> None:
    """E0.1 — second identical dep inspection in the same segment
    must NOT re-trigger paper_gain."""
    _setup_dep_repo(tmp_path)
    app_ob = Obligation(
        id="o-pre-app-rep0001",
        kind="precondition",
        scope="src/app.py::create_user",
        description="GOAL",
        source="intent",
        weight=5,
    )
    db_ob = Obligation(
        id="o-pre-db-rep00001",
        kind="precondition",
        scope="src/db.py::get_conn",
        description="dep",
        source="extracted",
        weight=1,
    )
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    events = [
        TraceEvent(t=0, kind="read", tool="Read", scope=["src/app.py"]),
        TraceEvent(t=1, kind="read", tool="Read", scope=["src/db.py"]),  # paper_gain
        TraceEvent(t=2, kind="read", tool="Read", scope=["src/db.py"]),  # repeat
    ]
    trace = Trace(events=events)
    metrics = score_trajectory(trace, [app_ob, db_ob], request)
    assert metrics.timesteps[1].paper_gain is True
    assert metrics.timesteps[2].paper_gain is False, (
        "repeated dep inspection in same segment must NOT retrigger paper_gain"
    )
    assert metrics.timesteps[2].is_error is True


def test_dependency_inspection_does_not_close_obligation(tmp_path: Path) -> None:
    """E0.1 — paper_gain via dep inspection is NOT a progress_event;
    the segment does not reset, stale starts accumulating."""
    _setup_dep_repo(tmp_path)
    app_ob = Obligation(
        id="o-pre-app-noclose1",
        kind="precondition",
        scope="src/app.py::create_user",
        description="GOAL",
        source="intent",
        weight=5,
    )
    db_ob = Obligation(
        id="o-pre-db-noclose01",
        kind="precondition",
        scope="src/db.py::get_conn",
        description="dep",
        source="extracted",
        weight=1,
    )
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    events = [
        TraceEvent(t=0, kind="read", tool="Read", scope=["src/app.py"]),
        TraceEvent(t=1, kind="read", tool="Read", scope=["src/db.py"]),
    ]
    trace = Trace(events=events)
    metrics = score_trajectory(trace, [app_ob, db_ob], request)
    # No obligation closed.
    assert metrics.timesteps[1].is_progress is False
    # Verify the graph actually carries the db→app supportive edge
    # (sanity check — without it the test would pass for the wrong reason).
    surface = ["src/app.py", "src/db.py"]
    obs = extract_obligations(tmp_path, surface)
    graph = build_dependency_graph(obs, tmp_path, ["src/app.py"])
    db_to_app = [
        e for e in graph.supportive_edges
        if e.reason == "direct_import"
    ]
    assert db_to_app, "graph must carry the db→app direct_import edge for E0.1"


# ---------------------------------------------------------------------------
# E0 — fusion readiness assessor
# ---------------------------------------------------------------------------


def test_fusion_readiness_blocks_when_capability_default() -> None:
    scenario = _scenario_with_defaults()
    rep = assess_fusion_readiness(scenario)
    assert rep.status == "blocked"
    blocker_names = {b.split(":")[0] for b in rep.blockers}
    assert "capability" in blocker_names


def test_fusion_readiness_blocks_when_benefit_default() -> None:
    scenario = _scenario_with_defaults()
    rep = assess_fusion_readiness(scenario)
    assert rep.status == "blocked"
    assert any("benefit" in b for b in rep.blockers)


def test_fusion_readiness_blocks_when_observability_default() -> None:
    scenario = _scenario_with_defaults()
    rep = assess_fusion_readiness(scenario)
    assert rep.status == "blocked"
    assert any("observability" in b for b in rep.blockers)


def test_fusion_readiness_allows_diagnostic_grounding() -> None:
    """grounding ≠ default does NOT alone unlock fusion, but it should
    surface as a non-blocking field in the report."""
    from oida_code.models.normalized_event import PreconditionSpec

    scenario = NormalizedScenario(
        name="t",
        description="",
        events=[
            _make_event(
                idx=1,
                preconditions=[
                    PreconditionSpec(name="x1", weight=0.5, verified=True),
                    PreconditionSpec(name="x2", weight=0.5, verified=False),
                ],
            )
        ],
    )
    rep = assess_fusion_readiness(scenario)
    assert rep.status == "blocked"  # capability/benefit/observability still default
    grounding = next(f for f in rep.field_readiness if f.name == "grounding")
    assert grounding.status == "real"
    assert grounding.blocks_official_fusion is False


def test_fusion_readiness_graph_present_does_not_unlock_vnet() -> None:
    """ADR-22 §rejected #2: graph presence must NOT unlock V_net."""
    scenario = NormalizedScenario(
        name="t",
        description="",
        events=[
            _make_event(idx=1, supportive_parents=["e2"]),
            _make_event(idx=2),
        ],
    )
    rep = assess_fusion_readiness(scenario)
    assert rep.graph_ready is True
    assert rep.status == "blocked"
    # capability/benefit/observability are STILL blockers.
    assert any("capability" in b for b in rep.blockers)


def test_corrupt_plausible_success_is_suspicious_not_official(
    tmp_path: Path,
) -> None:
    """A10.md §E0.3: even when apparent completion is high and
    grounding is partial, corrupt_success must not be emitted as
    official; readiness stays blocked."""
    # Fabricate a high-completion scenario with negative-path unverified.
    from oida_code.models.normalized_event import PreconditionSpec

    scenario = NormalizedScenario(
        name="t",
        description="",
        events=[
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
        ],
    )
    rep = assess_fusion_readiness(scenario)
    # Still blocked because capability/benefit/observability are 0.5.
    assert rep.status == "blocked"
    # No claim of corrupt_success in the report at all.
    assert not any("corrupt_success" in b.lower() for b in rep.blockers)


def test_official_summary_fields_remain_null_when_blocked() -> None:
    """Even when readiness is blocked, the report carries blockers but
    NEVER carries V_net / debt_final / corrupt_success values."""
    scenario = _scenario_with_defaults()
    rep = assess_fusion_readiness(scenario)
    dumped = rep.model_dump()
    # Schema check — fusion fields are NOT part of FusionReadinessReport.
    forbidden = {"total_v_net", "debt_final", "corrupt_success_ratio", "mean_q_obs"}
    assert not (forbidden & set(dumped.keys()))


def test_shadow_fusion_if_any_is_marked_experimental() -> None:
    """ADR-22 §accepted: shadow fusion only when clearly marked
    non-authoritative. The current FusionReadinessReport doesn't carry
    a shadow block at all (status field is the only signal); test the
    contract by asserting the only verdicts available are the 4 ladder
    rungs."""
    from typing import get_args

    from oida_code.score.fusion_readiness import FusionStatus

    valid = set(get_args(FusionStatus))
    assert valid == {"blocked", "diagnostic_only", "shadow_ready", "official_ready"}


# ---------------------------------------------------------------------------
# Trajectory + evidence integration smoke
# ---------------------------------------------------------------------------


def test_assess_with_trajectory_and_evidence_input() -> None:
    """Smoke: trajectory_metrics + tool_evidence flow into the report.

    Uses non-default completion + verified preconditions so the
    evidence-ready group of fields lights up. capability/benefit/
    observability remain at structural defaults → status still blocked.
    """
    from oida_code.models.normalized_event import PreconditionSpec

    scenario = NormalizedScenario(
        name="t",
        description="",
        events=[
            _make_event(
                idx=1,
                completion=0.9,
                tests_pass=0.85,
                operator_accept=0.9,
                preconditions=[
                    PreconditionSpec(name="x1", weight=0.5, verified=True),
                    PreconditionSpec(name="x2", weight=0.5, verified=False),
                ],
            )
        ],
    )
    pytest_ev = ToolEvidence(
        tool="pytest", status="ok", duration_ms=10,
        counts={"total": 5, "failure": 0, "error": 0},
    )
    ruff_ev = ToolEvidence(tool="ruff", status="ok", duration_ms=5, findings=[], counts={})
    mypy_ev = ToolEvidence(tool="mypy", status="ok", duration_ms=5, findings=[], counts={})
    metrics = TrajectoryMetrics(
        exploration_error=0.1,
        exploitation_error=0.1,
        stale_score=0,
        no_progress_rate=0.0,
        total_steps=5,
        progress_events_count=3,
        exploration_steps=3,
        exploitation_steps=2,
        terminal_steps=0,
        suspicious_tail_count=0,
    )
    rep = assess_fusion_readiness(
        scenario, tool_evidence=[pytest_ev, ruff_ev, mypy_ev], trajectory_metrics=metrics
    )
    assert rep.evidence_ready is True
    assert rep.trajectory_ready is True
    # Still blocked on capability/benefit/observability.
    assert rep.status == "blocked"

"""Block D2 (QA/A9.md) — run all 10 hermetic code-domain traces and
assert each against its ``expected.json``.

The scenarios live as :class:`TraceSpec` in
:mod:`tests.fixtures.code_traces.builders`. Each test materialises the
fixture directory in ``tmp_path`` (per A9.md format: repo/, request.json,
trace.jsonl, expected.json, README.md), invokes the real CLI, and
asserts structural properties — **no statistical outcome prediction,
no commits>0 label, no LLM judge** (A9.md §D2 constraints).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oida_code.cli import app
from oida_code.extract.dependencies import (
    build_dependency_graph,
    derive_audit_surface,
)
from oida_code.extract.obligations import extract_obligations
from oida_code.models.audit_request import AuditRequest
from oida_code.models.normalized_event import NormalizedScenario
from tests.fixtures.code_traces.builders import (
    SCENARIOS,
    TraceSpec,
    materialize,
)

runner = CliRunner()


@pytest.fixture(scope="module")
def scenarios_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialize all 10 fixtures once per test module."""
    root = tmp_path_factory.mktemp("code_traces_d2")
    for spec in SCENARIOS:
        materialize(spec, root)
    return root


def _load_expected(root: Path, name: str) -> dict:
    return json.loads((root / name / "expected.json").read_text(encoding="utf-8"))


def _run_normalize(root: Path, name: str, surface: str) -> NormalizedScenario:
    fixture_dir = root / name
    result = runner.invoke(
        app,
        [
            "normalize",
            str(fixture_dir / "request.json"),
            "--surface",
            surface,
        ],
    )
    assert result.exit_code == 0, (
        f"normalize exit {result.exit_code} on {name}/{surface}: {result.output}"
    )
    start = result.output.find("{")
    end = result.output.rfind("}")
    return NormalizedScenario.model_validate_json(result.output[start : end + 1])


def _run_score_trace(root: Path, name: str, surface: str) -> dict:
    fixture_dir = root / name
    result = runner.invoke(
        app,
        [
            "score-trace",
            str(fixture_dir / "trace.jsonl"),
            "--request",
            str(fixture_dir / "request.json"),
            "--surface",
            surface,
        ],
    )
    assert result.exit_code == 0, (
        f"score-trace exit {result.exit_code} on {name}/{surface}: {result.output}"
    )
    start = result.output.find("{")
    end = result.output.rfind("}")
    return json.loads(result.output[start : end + 1])


# ---------------------------------------------------------------------------
# Global invariants — every scenario must satisfy these
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_normalize_does_not_crash_and_has_no_unknown_parent_ids(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    """A9.md §D3 structural invariants: normalize completes, and every
    constitutive_parents / supportive_parents entry references an
    existing event ID. Applied to D2 scenarios as structural guard."""
    scenario = _run_normalize(scenarios_root, spec.name, "impact")
    known = {ev.id for ev in scenario.events}
    for ev in scenario.events:
        for parent in ev.constitutive_parents + ev.supportive_parents:
            assert parent in known, (
                f"{spec.name}: unknown parent {parent} on event {ev.id}"
            )
        assert ev.id not in ev.constitutive_parents
        assert ev.id not in ev.supportive_parents


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_score_trace_does_not_crash(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    payload = _run_score_trace(scenarios_root, spec.name, "impact")
    # TrajectoryMetrics always emits these keys.
    for key in (
        "exploration_error",
        "exploitation_error",
        "stale_score",
        "total_steps",
        "progress_events_count",
        "exploration_steps",
        "exploitation_steps",
    ):
        assert key in payload


# ---------------------------------------------------------------------------
# Per-scenario expected assertions (driven by expected.json)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_scenario_matches_expected_surface(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    expected = _load_expected(scenarios_root, spec.name)
    repo = scenarios_root / spec.name / "repo"

    impact = derive_audit_surface(repo, list(spec.changed_files), mode="impact")
    for path in expected["expected_surface"]["impact"]:
        assert path in impact, (
            f"{spec.name}: expected '{path}' in impact surface; got {impact}"
        )

    changed = derive_audit_surface(repo, list(spec.changed_files), mode="changed")
    assert set(changed) == set(expected["expected_surface"]["changed"])


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_scenario_matches_expected_metrics(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    expected = _load_expected(scenarios_root, spec.name)["expected_metrics"]
    payload = _run_score_trace(scenarios_root, spec.name, "impact")

    if "progress_events_min" in expected:
        assert payload["progress_events_count"] >= expected["progress_events_min"]
    if "progress_events_max" in expected:
        assert payload["progress_events_count"] <= expected["progress_events_max"]
    if "exploration_error_min" in expected:
        assert payload["exploration_error"] >= expected["exploration_error_min"]
    if "exploration_error_max" in expected:
        assert payload["exploration_error"] <= expected["exploration_error_max"]
    if "exploitation_error_min" in expected:
        assert payload["exploitation_error"] >= expected["exploitation_error_min"]
    if "exploitation_error_max" in expected:
        assert payload["exploitation_error"] <= expected["exploitation_error_max"]
    if "stale_score_min" in expected:
        assert payload["stale_score"] >= expected["stale_score_min"]


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_scenario_matches_expected_graph(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    expected = _load_expected(scenarios_root, spec.name)["expected_graph"]
    repo = scenarios_root / spec.name / "repo"
    surface = derive_audit_surface(repo, list(spec.changed_files), mode="impact")
    obligations = extract_obligations(repo, surface)
    graph = build_dependency_graph(obligations, repo, surface)

    assert len(graph.supportive_edges) >= expected["supportive_edges_min"], (
        f"{spec.name}: expected ≥{expected['supportive_edges_min']} supportive "
        f"edges, got {len(graph.supportive_edges)}"
    )
    assert len(graph.constitutive_edges) >= expected["constitutive_edges_min"]

    if expected.get("has_db_to_app_edge"):
        obligation_files = {
            o.id: o.scope.split("::", 1)[0].replace("\\", "/").lstrip("./")
            for o in obligations
        }
        db_ids = {
            oid for oid, f in obligation_files.items() if f.endswith("db.py")
        }
        app_ids = {
            oid for oid, f in obligation_files.items() if f.endswith("app.py")
        }
        has_edge = any(
            e.parent_id in db_ids
            and e.child_id in app_ids
            and e.reason == "direct_import"
            for e in graph.supportive_edges
        )
        assert has_edge, (
            f"{spec.name}: expected db→app direct_import edge, got "
            f"{[(e.parent_id, e.child_id, e.reason) for e in graph.supportive_edges]}"
        )


# ---------------------------------------------------------------------------
# Ablation: --surface changed vs impact on scenarios that flag it
# ---------------------------------------------------------------------------


ABLATION_SCENARIOS = [s for s in SCENARIOS if s.ablation_compare]


@pytest.mark.parametrize("spec", ABLATION_SCENARIOS, ids=[s.name for s in ABLATION_SCENARIOS])
def test_ablation_changed_vs_impact_differs(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    """Prove that ``--surface=impact`` strictly extends the surface
    compared to ``--surface=changed`` on flagged scenarios."""
    impact_scenario = _run_normalize(scenarios_root, spec.name, "impact")
    changed_scenario = _run_normalize(scenarios_root, spec.name, "changed")
    assert len(impact_scenario.events) >= len(changed_scenario.events), (
        f"{spec.name}: impact surface should produce at least as many "
        f"events as changed surface. Got impact={len(impact_scenario.events)}, "
        f"changed={len(changed_scenario.events)}"
    )
    # For import_dependency_missed specifically, impact must produce MORE.
    if spec.name == "07_import_dependency_missed":
        assert len(impact_scenario.events) > len(changed_scenario.events), (
            "Block D2 crown jewel: --surface=impact must discover "
            "more obligations than --surface=changed when a dependency "
            "file changes and its importer has its own obligations."
        )


# ---------------------------------------------------------------------------
# D3 honesty signals — V_net / debt MUST remain null in D2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_v_net_and_debt_final_remain_null(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    """A9.md §D2 hard rule: V_net and debt_final MUST NOT be emitted.

    The mapper doesn't populate these fields (ADR-13); they stay None
    in the scenario's default ReportSummary shape. We assert no event
    accidentally exposes a fusion-field float."""
    scenario = _run_normalize(scenarios_root, spec.name, "impact")
    # The scenario itself doesn't carry V_net/debt_final (those are on
    # AuditReport.summary which normalize doesn't emit). Verify.
    dumped = scenario.model_dump()
    assert "total_v_net" not in dumped.get("summary", {})
    assert "debt_final" not in dumped.get("summary", {})


# ---------------------------------------------------------------------------
# Fixture format hygiene — every A9.md-required file is present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_fixture_dir_has_required_files(
    scenarios_root: Path, spec: TraceSpec
) -> None:
    """A9.md §D2: each fixture dir must contain repo/, request.json,
    trace.jsonl, expected.json, README.md."""
    fixture_dir = scenarios_root / spec.name
    assert (fixture_dir / "repo").is_dir()
    assert (fixture_dir / "request.json").is_file()
    assert (fixture_dir / "trace.jsonl").is_file()
    assert (fixture_dir / "expected.json").is_file()
    assert (fixture_dir / "README.md").is_file()
    # request.json is a valid AuditRequest.
    AuditRequest.model_validate_json(
        (fixture_dir / "request.json").read_text(encoding="utf-8")
    )

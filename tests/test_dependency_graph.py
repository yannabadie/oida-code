"""Block C (ADR-21) — minimal dependency graph + impact cone + repair propagation.

Uses ``tmp_path`` to build mini-repos on the fly so each test is
hermetic. Every test references one of the 10+ items listed by the OIDA
author in QA/A6.md.
"""

from __future__ import annotations

from pathlib import Path

from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer
from oida_code.extract.dependencies import (
    build_dependency_graph,
    build_impact_cone,
)
from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.obligation import Obligation
from oida_code.score.mapper import (
    obligations_to_scenario,
    pydantic_to_vendored,
)

# ---------------------------------------------------------------------------
# Mini-repo fixture helpers
# ---------------------------------------------------------------------------


def _make_obligation(
    oid: str,
    kind: str,
    scope: str,
    *,
    source: str = "extracted",
    weight: int = 1,
) -> Obligation:
    return Obligation(
        id=oid,
        kind=kind,  # type: ignore[arg-type]
        scope=scope,
        description=f"{kind} on {scope}",
        source=source,  # type: ignore[arg-type]
        weight=weight,
    )


def _write_py(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


# ---------------------------------------------------------------------------
# Rule 1 — same-symbol constitutive edges
# ---------------------------------------------------------------------------


def test_same_symbol_precondition_is_constitutive_parent_of_api_contract(
    tmp_path: Path,
) -> None:
    """A precondition and an api_contract on the same file+symbol →
    precondition_id → api_contract_id is a CONSTITUTIVE edge."""
    pre = _make_obligation("o-pre-same001", "precondition",
                            "src/app.py::create_user")
    api = _make_obligation("o-api-same001", "api_contract",
                            "src/app.py::create_user")
    graph = build_dependency_graph([pre, api], tmp_path, [])
    assert len(graph.constitutive_edges) >= 1
    edge = next(
        e for e in graph.constitutive_edges
        if e.parent_id == pre.id and e.child_id == api.id
    )
    assert edge.kind == "constitutive"
    assert "precondition_supports_contract" in edge.reason
    assert edge.confidence > 0.0
    assert edge.source.startswith("rule1:")


# ---------------------------------------------------------------------------
# Rule 2 — direct imports
# ---------------------------------------------------------------------------


def test_direct_import_creates_supportive_edge_imported_to_importer(
    tmp_path: Path,
) -> None:
    """If ``src/service.py`` imports ``src/db.py``, and both have
    obligations, the edge is ``db_ob → service_ob``, supportive."""
    _write_py(tmp_path / "src" / "db.py", "def get_conn(): ...\n")
    _write_py(
        tmp_path / "src" / "service.py",
        "from src import db\n\ndef do(): db.get_conn()\n",
    )
    db_ob = _make_obligation("o-pre-dbimp001", "precondition", "src/db.py::get_conn")
    svc_ob = _make_obligation("o-pre-svcimp01", "precondition", "src/service.py::do")

    graph = build_dependency_graph(
        [db_ob, svc_ob], tmp_path, ["src/db.py", "src/service.py"]
    )
    edges = [
        e for e in graph.supportive_edges
        if e.parent_id == db_ob.id and e.child_id == svc_ob.id
    ]
    assert len(edges) == 1
    assert edges[0].reason == "direct_import"
    assert edges[0].source.startswith("rule2:import:")


def test_import_direction_is_dependency_to_dependent(tmp_path: Path) -> None:
    """Sanity of direction: the imported module is PARENT, the importer
    is CHILD. double_loop_repair on the parent reopens the child."""
    _write_py(tmp_path / "src" / "a.py", "VALUE = 1\n")
    _write_py(tmp_path / "src" / "b.py", "from src import a\nX = a.VALUE\n")
    a_ob = _make_obligation("o-pre-dirA0001", "precondition", "src/a.py::VALUE")
    b_ob = _make_obligation("o-pre-dirB0001", "precondition", "src/b.py::X")

    graph = build_dependency_graph(
        [a_ob, b_ob], tmp_path, ["src/a.py", "src/b.py"]
    )
    # The edge must go a → b (a is the dependency, b is the dependent).
    matching = [
        e for e in graph.supportive_edges
        if e.parent_id == a_ob.id and e.child_id == b_ob.id
    ]
    reversed_matching = [
        e for e in graph.supportive_edges
        if e.parent_id == b_ob.id and e.child_id == a_ob.id
    ]
    assert matching, "expected a_ob → b_ob edge"
    assert not reversed_matching, "edge must not be reversed"


def test_external_import_is_ignored_and_recorded_or_skipped(
    tmp_path: Path,
) -> None:
    """A stdlib or external import must produce NO edge but must not
    crash. Unresolved external imports go to ``unresolved_imports``."""
    _write_py(
        tmp_path / "src" / "a.py",
        "import os  # stdlib, filtered out\n"
        "import requests  # external, recorded\n",
    )
    a_ob = _make_obligation("o-pre-extA0001", "precondition", "src/a.py::func")
    graph = build_dependency_graph([a_ob], tmp_path, ["src/a.py"])
    # No import edges since only externals are imported.
    assert not any(
        e.reason == "direct_import" for e in graph.supportive_edges
    )
    # ``requests`` should be in unresolved_imports; ``os`` is stdlib
    # and silently filtered.
    assert any("requests" in entry for entry in graph.unresolved_imports)


# ---------------------------------------------------------------------------
# Rule 3 — related tests (supportive, not constitutive)
# ---------------------------------------------------------------------------


def test_test_file_creates_supportive_edge_not_constitutive(
    tmp_path: Path,
) -> None:
    """``tests/test_foo.py`` → ``src/foo.py`` must be SUPPORTIVE. A
    missing/failing test triggers audit, not automatic invalidation."""
    src_ob = _make_obligation("o-pre-testsrc1", "precondition", "src/foo.py::f")
    test_ob = _make_obligation(
        "o-pre-testtst1", "precondition", "tests/test_foo.py::test_f"
    )
    graph = build_dependency_graph([src_ob, test_ob], tmp_path, [])
    support = [
        e for e in graph.supportive_edges
        if e.parent_id == test_ob.id and e.child_id == src_ob.id
    ]
    constit = [
        e for e in graph.constitutive_edges
        if e.parent_id == test_ob.id and e.child_id == src_ob.id
    ]
    assert support, "test → source must be supportive"
    assert not constit, "test → source must NOT be constitutive"


# ---------------------------------------------------------------------------
# Hygiene — no unknown parents, no self-edges, deterministic
# ---------------------------------------------------------------------------


def test_no_unknown_parent_ids_in_normalized_scenario(tmp_path: Path) -> None:
    """After ``obligations_to_scenario``, every constitutive_parents /
    supportive_parents entry must resolve to a known event ID. The
    vendored analyzer's ``_validate_ids`` would otherwise raise."""
    pre = _make_obligation("o-pre-noun0001", "precondition",
                            "src/app.py::create_user")
    api = _make_obligation("o-api-noun0001", "api_contract",
                            "src/app.py::create_user")
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    scenario = obligations_to_scenario([pre, api], request=request)
    known_event_ids = {ev.id for ev in scenario.events}
    for ev in scenario.events:
        for parent in ev.constitutive_parents + ev.supportive_parents:
            assert parent in known_event_ids, (
                f"event {ev.id} references unknown parent {parent}"
            )


def test_no_self_edges(tmp_path: Path) -> None:
    """Self edges (a → a) must be dropped even if a rule would naively
    emit them."""
    api = _make_obligation("o-api-self0001", "api_contract",
                            "src/app.py::foo")
    # Single obligation that could match rule 1 trivially.
    graph = build_dependency_graph([api], tmp_path, [])
    for e in graph.constitutive_edges + graph.supportive_edges:
        assert e.parent_id != e.child_id


def test_graph_build_is_deterministic(tmp_path: Path) -> None:
    """Running ``build_dependency_graph`` twice on the same inputs
    must produce identical edge lists."""
    _write_py(tmp_path / "src" / "a.py", "X = 1\n")
    _write_py(tmp_path / "src" / "b.py", "from src import a\nY = a.X\n")
    obs = [
        _make_obligation("o-pre-detA0001", "precondition", "src/a.py::X"),
        _make_obligation("o-pre-detB0001", "precondition", "src/b.py::Y"),
    ]
    g1 = build_dependency_graph(obs, tmp_path, ["src/a.py", "src/b.py"])
    g2 = build_dependency_graph(obs, tmp_path, ["src/a.py", "src/b.py"])
    assert g1.constitutive_edges == g2.constitutive_edges
    assert g1.supportive_edges == g2.supportive_edges
    assert g1.unresolved_imports == g2.unresolved_imports


# ---------------------------------------------------------------------------
# double_loop_repair integration — the crown jewel test from A6.md
# ---------------------------------------------------------------------------


def test_double_loop_repair_reopens_constitutive_descendant(
    tmp_path: Path,
) -> None:
    """double_loop_repair(root = precondition_event) must list the
    api_contract_event in ``reopen`` (dominated by the precondition
    via the constitutive edge)."""
    pre = _make_obligation("o-pre-repr0001", "precondition",
                            "src/app.py::create_user")
    api = _make_obligation("o-api-repr0001", "api_contract",
                            "src/app.py::create_user")
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    scenario = obligations_to_scenario([pre, api], request=request)
    analyzer = OIDAAnalyzer(pydantic_to_vendored(scenario))
    pre_event = next(e for e in scenario.events if e.pattern_id.startswith("p_precondition_"))
    api_event = next(e for e in scenario.events if e.pattern_id.startswith("p_api_contract_"))
    result = analyzer.double_loop_repair(pre_event.id)
    assert api_event.id in result["reopen"], (
        f"expected {api_event.id} in reopen; got {result}"
    )


def test_double_loop_repair_audits_supportive_descendant(
    tmp_path: Path,
) -> None:
    """An observability obligation on the same scope as an api_contract
    is a SUPPORTIVE parent of the api_contract. double_loop_repair on
    the observability event should list the api_contract in AUDIT,
    not in REOPEN."""
    api = _make_obligation("o-api-audi0001", "api_contract",
                            "src/app.py::create_user")
    obs = _make_obligation("o-obs-audi0001", "observability",
                            "src/app.py::create_user")
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    scenario = obligations_to_scenario([api, obs], request=request)
    analyzer = OIDAAnalyzer(pydantic_to_vendored(scenario))
    obs_event = next(e for e in scenario.events if e.pattern_id.startswith("p_observability_"))
    api_event = next(e for e in scenario.events if e.pattern_id.startswith("p_api_contract_"))
    result = analyzer.double_loop_repair(obs_event.id)
    assert api_event.id in result["audit"], (
        f"expected {api_event.id} in audit; got {result}"
    )
    assert api_event.id not in result["reopen"], (
        "supportive parent must NOT force reopen"
    )


def test_repair_uses_constitutive_vs_supportive_edges(tmp_path: Path) -> None:
    """The canonical A6.md example: e1 precondition constitutive parent
    of e2 api_contract; e3 observability supportive parent of e2.
    double_loop_repair(e1) → reopen e2. double_loop_repair(e3) → audit e2."""
    e1 = _make_obligation("o-pre-canon001", "precondition",
                            "src/app.py::create_user")
    e2 = _make_obligation("o-api-canon001", "api_contract",
                            "src/app.py::create_user")
    e3 = _make_obligation("o-obs-canon001", "observability",
                            "src/app.py::create_user")
    request = AuditRequest(
        repo=RepoSpec(path=str(tmp_path), revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=["src/app.py"]),
    )
    scenario = obligations_to_scenario([e1, e2, e3], request=request)
    analyzer = OIDAAnalyzer(pydantic_to_vendored(scenario))
    # pattern_id is "p_<kind>_<slug>_<hash>" where <kind> may contain
    # underscores (api_contract). Match by prefix, not split.
    kinds = ("precondition", "api_contract", "migration", "invariant",
             "security_rule", "observability")
    by_pattern: dict[str, str] = {}
    for ev in scenario.events:
        for kind in kinds:
            if ev.pattern_id.startswith(f"p_{kind}_"):
                by_pattern[kind] = ev.id
                break

    reopen_from_e1 = analyzer.double_loop_repair(by_pattern["precondition"])
    audit_from_e3 = analyzer.double_loop_repair(by_pattern["observability"])

    assert by_pattern["api_contract"] in reopen_from_e1["reopen"]
    assert by_pattern["api_contract"] in audit_from_e3["audit"]
    assert by_pattern["api_contract"] not in audit_from_e3["reopen"]


# ---------------------------------------------------------------------------
# Impact cone
# ---------------------------------------------------------------------------


def test_impact_cone_tags_every_entry_with_a_reason(tmp_path: Path) -> None:
    """Every ``ImpactConeEntry`` must carry a reason from the fixed
    set (changed / imports_changed / imported_by_changed / related_test
    / config / migration)."""
    _write_py(tmp_path / "src" / "a.py", "X = 1\n")
    _write_py(tmp_path / "src" / "b.py", "from src import a\nY = a.X\n")
    _write_py(tmp_path / "tests" / "test_a.py", "def test_a(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n", encoding="utf-8"
    )
    cone = build_impact_cone(tmp_path, ["src/a.py", "src/b.py"])
    reasons = {entry.reason for entry in cone}
    # ``changed`` must appear, plus at least one of the neighbourhood tags.
    assert "changed" in reasons
    assert reasons - {"changed"}, f"expected neighbourhood entries, got {reasons}"
    for entry in cone:
        assert entry.reason in {
            "changed",
            "imports_changed",
            "imported_by_changed",
            "related_test",
            "config",
            "migration",
        }


def test_impact_cone_related_test_detected(tmp_path: Path) -> None:
    _write_py(tmp_path / "src" / "foo.py", "def f(): pass\n")
    _write_py(tmp_path / "tests" / "test_foo.py", "def test_f(): pass\n")
    cone = build_impact_cone(tmp_path, ["src/foo.py"])
    related = [e for e in cone if e.reason == "related_test"]
    assert any(e.path == "tests/test_foo.py" for e in related)


def test_impact_cone_is_bounded_by_max_files(tmp_path: Path) -> None:
    """max_files must cap the output even on large repos."""
    for i in range(20):
        _write_py(tmp_path / "src" / f"m{i}.py", "X = 1\n")
    cone = build_impact_cone(
        tmp_path, [f"src/m{i}.py" for i in range(20)], max_files=5
    )
    assert len(cone) == 5

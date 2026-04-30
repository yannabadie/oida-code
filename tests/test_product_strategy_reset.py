"""ADR-74 product-strategy reset guards."""

from __future__ import annotations

from tests.conftest import REPO_ROOT


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_product_strategy_is_active_compass() -> None:
    strategy = _read("docs/product_strategy.md")
    normalized = " ".join(strategy.split())
    assert "diagnostic second opinion for Python reviewers" in strategy
    assert "not a merge gate" in strategy
    assert "G-6d remains scientifically important" in strategy
    assert "ADR-75 records the dependency policy" in strategy
    assert "ADR-76 records the matching tranche policy" in strategy
    assert "exact clean +4" in strategy
    assert "Do not add requirements-file install support" in normalized
    assert "requirements/*.txt" in strategy
    assert "tox.ini" in strategy


def test_readme_points_to_strategy_before_phase_ledger() -> None:
    readme = _read("README.md")
    assert "## Current product strategy" in readme
    assert readme.index("## Current product strategy") < readme.index("## Status")
    assert "docs/product_strategy.md" in readme
    assert "phase ledger below is retained as evidence history" in readme


def test_plan_is_no_longer_active_source_of_truth() -> None:
    plan = _read("PLAN.md")
    assert "# OIDA Code Audit" in plan
    assert "Historical Plan" in plan
    assert "no longer the active source of truth" in plan
    assert "docs/product_strategy.md" in plan
    assert "Older statements in this file about GitHub App" in plan
    assert "wins on conflicts" not in plan


def test_agents_handoff_state_is_current_after_adr76() -> None:
    agents = _read("AGENTS.md")
    assert "9752f28" in agents
    assert "G-6a is CLOSED for the current archived load-bearing replay set" in agents
    assert "repo-product-vision-review" in agents
    assert "69f329be-0dd4-838f-8687-d68190f21e7d" in agents
    assert "autonomous-protocol-20260430" in agents
    assert "69f3ba6f-60f0-838b-8028-a8af734b2d72" in agents
    assert "G-6d remains OPEN toward N>=20" in agents
    assert "ADR-75" in agents
    assert "ADR-76" in agents
    assert "rejected or deferred" in agents
    assert "Evidence-Led Autonomous Block Protocol" in agents
    assert "exactly four clean candidates" in agents
    assert "next empirical priority is G-6a" not in agents


def test_codex_context_marks_old_capture_as_historical() -> None:
    context = _read("memory-bank/codexContext.md")
    assert "Current override (2026-04-30)" in context
    assert "9752f28" in context
    assert "ADR-75 chooses a policy-only response" in context
    assert "ADR-76 adds the exact-four rule" in context
    assert "Use `docs/product_strategy.md`" in context

"""Smoke test for the vendored OIDA core (blueprint §2 reuse clause).

Verifies the ``safe_online_migration`` scenario produces the signature pattern
documented in the working paper §7.1 (high Q_obs, high grounding, zero debt).
"""

from __future__ import annotations

from pathlib import Path

from oida_code.score import OIDAAnalyzer, load_scenario


def test_safe_online_migration_is_clean(vendored_examples_dir: Path) -> None:
    scenario = load_scenario(vendored_examples_dir / "safe_online_migration.json")
    analyzer = OIDAAnalyzer(scenario)
    report = analyzer.analyze()

    summary = report["summary"]
    # Paper §7.1.1: safe run ⇒ zero debt, positive net value.
    assert summary["event_count"] == 3
    assert summary["debt_final"] == 0.0
    assert summary["total_v_net"] > 0.0
    assert summary["corrupt_success_ratio"] == 0.0
    assert summary["bias_pattern_count"] == 0


def test_score_module_reexports_match_vendored() -> None:
    from oida_code._vendor.oida_framework.analyzer import (
        OIDAAnalyzer as _VendorAnalyzer,
    )
    from oida_code.score.analyzer import OIDAAnalyzer as _ReexportedAnalyzer

    assert _ReexportedAnalyzer is _VendorAnalyzer

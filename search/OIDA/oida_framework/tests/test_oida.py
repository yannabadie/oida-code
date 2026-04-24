from __future__ import annotations

import unittest
from pathlib import Path

from oida.analyzer import OIDAAnalyzer
from oida.io import load_scenario


ROOT = Path(__file__).resolve().parents[1]


class TestOIDAFramework(unittest.TestCase):
    def test_safe_scenario_has_zero_debt_and_positive_value(self) -> None:
        scenario = load_scenario(ROOT / "examples" / "safe_online_migration.json")
        report = OIDAAnalyzer(scenario).analyze()
        summary = report["summary"]
        self.assertEqual(summary["debt_final"], 0.0)
        self.assertGreater(summary["total_v_net"], 0.0)
        self.assertEqual(summary["bias_pattern_count"], 0)

    def test_destructive_scenario_has_positive_debt_and_negative_value(self) -> None:
        scenario = load_scenario(ROOT / "examples" / "destructive_db_recreate.json")
        report = OIDAAnalyzer(scenario).analyze()
        summary = report["summary"]
        self.assertGreater(summary["debt_final"], 1.0)
        self.assertLess(summary["total_v_net"], 0.0)
        self.assertGreaterEqual(summary["mean_q_obs"], 0.85)
        self.assertGreater(summary["bias_pattern_count"], 0)

    def test_repeated_low_grounding_scenario_accumulates_debt(self) -> None:
        scenario = load_scenario(ROOT / "examples" / "repeated_low_grounding_cost_optimization.json")
        report = OIDAAnalyzer(scenario).analyze()
        summary = report["summary"]
        self.assertGreater(summary["debt_final"], 0.0)
        self.assertGreater(summary["corrupt_success_ratio"], 0.0)

    def test_double_loop_repair_reopens_dominated_descendants(self) -> None:
        scenario = load_scenario(ROOT / "examples" / "destructive_db_recreate.json")
        analyzer = OIDAAnalyzer(scenario)
        analyzer.analyze()
        repair = analyzer.double_loop_repair("e1")
        self.assertEqual(repair["reopen"], ["e2", "e3"])
        self.assertEqual(repair["audit"], ["e4"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

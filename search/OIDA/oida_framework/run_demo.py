from __future__ import annotations

from pathlib import Path

from oida.analyzer import OIDAAnalyzer
from oida.io import load_scenario, save_report


def main() -> None:
    root = Path(__file__).resolve().parent
    examples = [
        root / "examples" / "safe_online_migration.json",
        root / "examples" / "destructive_db_recreate.json",
        root / "examples" / "repeated_low_grounding_cost_optimization.json",
    ]
    results_dir = root / "results"
    results_dir.mkdir(exist_ok=True)

    for path in examples:
        scenario = load_scenario(path)
        analyzer = OIDAAnalyzer(scenario)
        report = analyzer.analyze()
        out_path = results_dir / f"{path.stem}_report.json"
        save_report(report, out_path)
        print(f"[OK] analyzed {path.name} -> {out_path.name}")

    destructive = load_scenario(root / "examples" / "destructive_db_recreate.json")
    repair = OIDAAnalyzer(destructive)
    repair.analyze()
    repair_plan = repair.double_loop_repair("e1")
    save_report(repair_plan, results_dir / "destructive_db_recreate_repair_plan.json")
    print("[OK] repair plan -> destructive_db_recreate_repair_plan.json")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .analyzer import OIDAAnalyzer
from .io import load_scenario, save_report


def _print(data: Dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False))


def cmd_analyze(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    analyzer = OIDAAnalyzer(scenario)
    report = analyzer.analyze()
    if args.out:
        save_report(report, args.out)
    _print(report, pretty=args.pretty)
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    analyzer = OIDAAnalyzer(scenario)
    analyzer.analyze()
    repair = analyzer.double_loop_repair(args.root_event)
    if args.out:
        save_report(repair, args.out)
    _print(repair, pretty=args.pretty)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oida",
        description="Operational Integrity and Debt Analysis for tool-using AI agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze a scenario JSON file.")
    analyze.add_argument("scenario", type=Path, help="Path to scenario JSON.")
    analyze.add_argument("--out", type=Path, help="Optional output JSON path.")
    analyze.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    analyze.set_defaults(func=cmd_analyze)

    repair = sub.add_parser("repair", help="Generate a double-loop repair plan from a root event.")
    repair.add_argument("scenario", type=Path, help="Path to scenario JSON.")
    repair.add_argument("root_event", type=str, help="Root event ID to invalidate.")
    repair.add_argument("--out", type=Path, help="Optional output JSON path.")
    repair.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    repair.set_defaults(func=cmd_repair)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))

"""Phase 5.7 §5.7-E — operator soak aggregator runner.

Reads ``operator_soak_cases/<case_id>/{fiche,label,ux_score}.json``
sidecars, computes the QA/A34 §5.7-F recommendation, and writes:

* ``reports/operator_soak/aggregate.json``
* ``reports/operator_soak/aggregate.md``

Usage::

    python scripts/run_operator_soak_eval.py
    python scripts/run_operator_soak_eval.py --cases-root operator_soak_cases
    python scripts/run_operator_soak_eval.py --gateway-status diagnostic_only=2

The script never calls an external provider, never reads secrets, and
never writes a product verdict. ``contract_violation_count`` and
``official_field_leak_count`` come from the *operator*, not from any
LLM — the script accepts them as flags so the operator can record the
tally observed in the action artefacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oida_code.operator_soak.aggregate import (
    aggregate_cases,
    render_aggregate_markdown,
)


def _parse_distribution(raw: tuple[str, ...]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for entry in raw:
        if "=" not in entry:
            raise ValueError(
                f"--gateway-status entry {entry!r} must be 'status=count'",
            )
        status, count_str = entry.split("=", 1)
        status = status.strip()
        if not status:
            raise ValueError("empty status name in --gateway-status entry")
        distribution[status] = int(count_str)
    return distribution


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate operator-soak case sidecars and emit the "
            "Phase 5.7 recommendation. Diagnostic-only — no product "
            "verdict."
        ),
    )
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=Path("operator_soak_cases"),
        help="Directory containing case_<id>/ subdirectories.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/operator_soak"),
        help="Output directory for aggregate.json + aggregate.md.",
    )
    parser.add_argument(
        "--contract-violations",
        type=int,
        default=0,
        help="Operator-supplied tally of contract violations across runs.",
    )
    parser.add_argument(
        "--official-field-leaks",
        type=int,
        default=0,
        help="Operator-supplied tally of official-field leaks across runs.",
    )
    parser.add_argument(
        "--gateway-status",
        action="append",
        default=[],
        help=(
            "Repeatable 'status=count' (e.g. diagnostic_only=2). "
            "Status names should be one of the GatewayStatus literals."
        ),
    )
    args = parser.parse_args()

    distribution = _parse_distribution(tuple(args.gateway_status))

    report = aggregate_cases(
        args.cases_root,
        contract_violation_count=args.contract_violations,
        official_field_leak_count=args.official_field_leaks,
        gateway_status_distribution=distribution,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "aggregate.json"
    md_path = args.out_dir / "aggregate.md"
    json_path.write_text(
        json.dumps(report.model_dump(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_aggregate_markdown(report), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"recommendation: {report.recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

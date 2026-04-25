"""Phase 4.3-E (QA/A19.md, ADR-28) — calibration eval runner.

Loads the dataset manifest, dispatches each case to the right
family-specific evaluator, and emits :class:`CalibrationMetrics` JSON
plus a markdown summary. **No external API call.** **No predictive
claim.** ADR-28 §4.3-G forbids product threshold tuning here.

Usage::

    python scripts/run_calibration_eval.py
    python scripts/run_calibration_eval.py --dataset datasets/calibration_v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oida_code.calibration.metrics import CalibrationMetrics
from oida_code.calibration.runner import (
    CaseResult,
    aggregate,
    load_case,
    run_case,
)


def _format_markdown(
    metrics: CalibrationMetrics, results: list[CaseResult],
) -> str:
    lines = [
        "# Calibration v1 — pilot evaluation",
        "",
        f"- **cases_total**: {metrics.cases_total}",
        f"- **cases_evaluated**: {metrics.cases_evaluated}",
        f"- **excluded for contamination**: {metrics.cases_excluded_for_contamination}",
        f"- **excluded for flakiness**: {metrics.cases_excluded_for_flakiness}",
        f"- **official_field_leak_count**: {metrics.official_field_leak_count}",
        "",
        "## Claim metrics",
        "",
        f"- claim accuracy: {metrics.claim_accept_accuracy:.3f}",
        f"- claim macro-F1: {metrics.claim_accept_macro_f1:.3f}",
        f"- unsupported precision: {metrics.unsupported_precision:.3f}",
        f"- rejected precision: {metrics.rejected_precision:.3f}",
        f"- evidence-ref precision: {metrics.evidence_ref_precision:.3f}",
        f"- evidence-ref recall: {metrics.evidence_ref_recall:.3f}",
        f"- unknown-ref rejection rate: {metrics.unknown_ref_rejection_rate:.3f}",
        "",
        "## Tool metrics",
        "",
        f"- tool contradiction rejection rate: {metrics.tool_contradiction_rejection_rate:.3f}",
        f"- tool uncertainty preservation rate: {metrics.tool_uncertainty_preservation_rate:.3f}",
        f"- sandbox block rate (expected): {metrics.sandbox_block_rate_expected:.3f}",
        "",
        "## Shadow metrics",
        "",
        f"- bucket accuracy: {metrics.shadow_bucket_accuracy:.3f}",
        f"- pairwise-order accuracy: {metrics.shadow_pairwise_order_accuracy:.3f}",
        "",
        "## Code outcome (deferred to stability script)",
        "",
        f"- F2P pass-rate on expected-fixed: {metrics.f2p_pass_rate_on_expected_fixed:.3f}",
        f"- P2P preservation rate: {metrics.p2p_preservation_rate:.3f}",
        f"- flaky cases excluded: {metrics.flaky_case_count}",
        "",
        "## Safety",
        "",
        f"- block rate on adversarial cases: {metrics.safety_block_rate:.3f}",
        f"- fenced-injection rate: {metrics.fenced_injection_rate:.3f}",
        "",
        f"_{metrics.notes}_",
        "",
        "## Per-case status",
        "",
        "| case_id | family | leaks | notes |",
        "|---|---|---|---|",
    ]
    for r in results:
        notes = "; ".join(r.notes) if r.notes else ""
        lines.append(
            f"| {r.case_id} | {r.family} | {r.official_field_leaks} | "
            f"{notes[:120]} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", default="datasets/calibration_v1",
        help="dataset directory containing manifest.json + cases/",
    )
    parser.add_argument(
        "--out", default=".oida/calibration_v1",
        help="output directory for metrics.json + report.md",
    )
    args = parser.parse_args()

    dataset = Path(args.dataset)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases_dir = dataset / "cases"
    if not cases_dir.is_dir():
        print(f"no cases dir at {cases_dir}; run build_calibration_dataset.py first")
        return 2

    results: list[CaseResult] = []
    for case_dir in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        result = run_case(case, case_dir)
        results.append(result)

    metrics = aggregate(results)
    (out_dir / "metrics.json").write_text(
        metrics.model_dump_json(indent=2), encoding="utf-8",
    )
    (out_dir / "report.md").write_text(
        _format_markdown(metrics, results), encoding="utf-8",
    )
    # Per-case JSON for inspection.
    per_case = [
        {
            "case_id": r.case_id, "family": r.family,
            "contamination_risk": r.contamination_risk,
            "claim_confusion": r.claim_confusion,
            "shadow_bucket_actual": r.shadow_bucket_actual,
            "shadow_bucket_match": r.shadow_bucket_match,
            "official_field_leaks": r.official_field_leaks,
            "notes": r.notes,
        }
        for r in results
    ]
    (out_dir / "per_case.json").write_text(
        json.dumps(per_case, indent=2), encoding="utf-8",
    )
    print(f"wrote metrics + report to {out_dir}")
    print(f"cases_evaluated={metrics.cases_evaluated} "
          f"leaks={metrics.official_field_leak_count}")
    return 0 if metrics.official_field_leak_count == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase 5.7 aggregator — pure functions over the JSON sidecars.

The aggregator reads ``operator_soak_cases/<case_id>/{fiche,label,ux_score}.json``,
counts labels by bucket, computes the QA/A34 §5.7-F recommendation, and
returns an :class:`AggregateReport`. It is intentionally side-effect free:
``scripts/run_operator_soak_eval.py`` is the I/O wrapper.

Decision rule precedence (QA/A34 §5.7-F, tightened by QA/A35 §5.8-F):

1. ``official_field_leak_count > 0`` → ``fix_contract_leak`` (ADR-22 hard wall;
   must beat every other rule).
2. ``cases_completed < 3`` → ``continue_soak``.
3. ``false_negative_count >= 2`` → ``revise_gateway_policy_or_prompts``.
4. ``false_positive_count >= 2`` → ``revise_report_ux_or_labels``.
5. ``cases_completed >= 5`` and ``usefulness_rate >= 0.6`` →
   ``document_opt_in_path`` (rules 3 and 4 short-circuit before this rule
   fires, so reaching rule 5 implicitly requires
   ``false_positive_count < 2`` and ``false_negative_count < 2`` per
   QA/A35 §5.8-F).
6. otherwise → ``continue_soak``.

Even when (5) fires, ``enable-tool-gateway`` remains default ``false`` —
the recommendation is read by humans, never written into the action's
defaults.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from oida_code.operator_soak.models import (
    AggregateReport,
    OperatorLabelEntry,
    OperatorSoakFiche,
    OperatorUxScore,
    Recommendation,
    SoakCaseSummary,
)

USEFULNESS_THRESHOLD = 0.6
DOCUMENT_OPT_IN_MIN_CASES = 5
CONTINUE_SOAK_MIN_CASES = 3
FN_REVISE_THRESHOLD = 2
FP_REVISE_THRESHOLD = 2


def compute_recommendation(
    *,
    cases_completed: int,
    official_field_leak_count: int,
    false_negative_count: int,
    false_positive_count: int,
    useful_true_positive_count: int,
    useful_true_negative_count: int,
) -> Recommendation:
    """Map labelled counts to the canonical Recommendation Literal.

    See module docstring for the precedence rules. The function never
    returns a value outside the five-element ``Recommendation`` Literal,
    so forbidden product verdicts (``merge_safe``, ``production_safe``,
    etc.) are structurally unrepresentable.
    """
    if official_field_leak_count > 0:
        return "fix_contract_leak"
    if cases_completed < CONTINUE_SOAK_MIN_CASES:
        return "continue_soak"
    if false_negative_count >= FN_REVISE_THRESHOLD:
        return "revise_gateway_policy_or_prompts"
    if false_positive_count >= FP_REVISE_THRESHOLD:
        return "revise_report_ux_or_labels"
    if cases_completed >= DOCUMENT_OPT_IN_MIN_CASES:
        usefulness_rate = (
            useful_true_positive_count + useful_true_negative_count
        ) / cases_completed
        if usefulness_rate >= USEFULNESS_THRESHOLD:
            return "document_opt_in_path"
    return "continue_soak"


def _load_optional_json(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    payload: Mapping[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _read_case(
    case_dir: Path,
) -> tuple[
    OperatorSoakFiche,
    OperatorLabelEntry | None,
    OperatorUxScore | None,
]:
    """Read one case's three sidecars. ``fiche.json`` is required."""
    fiche_path = case_dir / "fiche.json"
    if not fiche_path.is_file():
        raise FileNotFoundError(f"missing fiche.json under {case_dir}")
    fiche_payload = json.loads(fiche_path.read_text(encoding="utf-8"))
    fiche = OperatorSoakFiche.model_validate(fiche_payload)

    label_payload = _load_optional_json(case_dir / "label.json")
    label = OperatorLabelEntry.model_validate(label_payload) if label_payload else None

    ux_payload = _load_optional_json(case_dir / "ux_score.json")
    ux = OperatorUxScore.model_validate(ux_payload) if ux_payload else None

    return fiche, label, ux


def _avg(values: tuple[int, ...]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def aggregate_cases(
    cases_root: Path,
    *,
    contract_violation_count: int = 0,
    official_field_leak_count: int = 0,
    gateway_status_distribution: Mapping[str, int] | None = None,
) -> AggregateReport:
    """Walk ``cases_root`` and produce an :class:`AggregateReport`.

    ``contract_violation_count``, ``official_field_leak_count``, and
    ``gateway_status_distribution`` are operator-supplied tallies of the
    *runs* (read from the action artefacts), not derivable from the
    sidecars alone. They default to zero / empty so the empty-cases path
    is testable without artefacts.

    Empty / missing ``cases_root`` is a valid state — the aggregator
    returns ``cases_total=0`` and ``recommendation=continue_soak`` per
    QA/A34 §5.7-F rule 1.
    """
    case_dirs: tuple[Path, ...] = ()
    if cases_root.is_dir():
        case_dirs = tuple(
            sorted(
                p
                for p in cases_root.iterdir()
                if p.is_dir() and (p / "fiche.json").is_file()
            ),
        )

    fiches: list[OperatorSoakFiche] = []
    labels: list[OperatorLabelEntry | None] = []
    ux_scores: list[OperatorUxScore | None] = []
    case_rows: list[SoakCaseSummary] = []

    for case_dir in case_dirs:
        fiche, label, ux = _read_case(case_dir)
        fiches.append(fiche)
        labels.append(label)
        ux_scores.append(ux)
        case_rows.append(
            SoakCaseSummary(
                case_id=fiche.case_id,
                status=fiche.status,
                expected_risk=fiche.expected_risk,
                operator_label=label.operator_label if label else None,
                workflow_run_id=fiche.workflow_run_id,
            ),
        )

    cases_total = len(fiches)
    cases_completed = sum(1 for f in fiches if f.status == "complete")

    label_counter: Counter[str] = Counter()
    for label in labels:
        if label is not None:
            label_counter[label.operator_label] += 1

    useful_true_positive_count = label_counter.get("useful_true_positive", 0)
    useful_true_negative_count = label_counter.get("useful_true_negative", 0)
    false_positive_count = label_counter.get("false_positive", 0)
    false_negative_count = label_counter.get("false_negative", 0)
    unclear_count = label_counter.get("unclear", 0)
    insufficient_fixture_count = label_counter.get("insufficient_fixture", 0)

    if cases_completed > 0:
        usefulness_rate = (
            useful_true_positive_count + useful_true_negative_count
        ) / cases_completed
    else:
        usefulness_rate = 0.0

    ux_present = tuple(u for u in ux_scores if u is not None)
    summary_readability_avg = _avg(tuple(u.summary_readability for u in ux_present))
    evidence_traceability_avg = _avg(tuple(u.evidence_traceability for u in ux_present))
    actionability_avg = _avg(tuple(u.actionability for u in ux_present))
    no_false_verdict_avg = _avg(tuple(u.no_false_verdict for u in ux_present))

    distribution_tuple = tuple(
        sorted((gateway_status_distribution or {}).items())
    )

    recommendation = compute_recommendation(
        cases_completed=cases_completed,
        official_field_leak_count=official_field_leak_count,
        false_negative_count=false_negative_count,
        false_positive_count=false_positive_count,
        useful_true_positive_count=useful_true_positive_count,
        useful_true_negative_count=useful_true_negative_count,
    )

    return AggregateReport(
        cases_total=cases_total,
        cases_completed=cases_completed,
        useful_true_positive_count=useful_true_positive_count,
        useful_true_negative_count=useful_true_negative_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        unclear_count=unclear_count,
        insufficient_fixture_count=insufficient_fixture_count,
        contract_violation_count=contract_violation_count,
        official_field_leak_count=official_field_leak_count,
        gateway_status_distribution=distribution_tuple,
        operator_usefulness_rate=usefulness_rate,
        summary_readability_avg=summary_readability_avg,
        evidence_traceability_avg=evidence_traceability_avg,
        actionability_avg=actionability_avg,
        no_false_verdict_avg=no_false_verdict_avg,
        cases=tuple(case_rows),
        recommendation=recommendation,
    )


def render_aggregate_markdown(report: AggregateReport) -> str:
    """Render the aggregate report as a stable Markdown string.

    Operators read this file to understand the soak state. The renderer
    is deterministic so test fixtures can pin exact strings.
    """
    lines: list[str] = []
    lines.append("# Phase 5.7 — Operator Soak Aggregate")
    lines.append("")
    lines.append(
        "_Soak metrics over the controlled cases under "
        "`operator_soak_cases/`. Diagnostic-only — no product "
        "verdict._",
    )
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- cases_total: {report.cases_total}")
    lines.append(f"- cases_completed: {report.cases_completed}")
    lines.append(
        f"- useful_true_positive_count: {report.useful_true_positive_count}",
    )
    lines.append(
        f"- useful_true_negative_count: {report.useful_true_negative_count}",
    )
    lines.append(f"- false_positive_count: {report.false_positive_count}")
    lines.append(f"- false_negative_count: {report.false_negative_count}")
    lines.append(f"- unclear_count: {report.unclear_count}")
    lines.append(
        f"- insufficient_fixture_count: {report.insufficient_fixture_count}",
    )
    lines.append(
        f"- contract_violation_count: {report.contract_violation_count}",
    )
    lines.append(
        f"- official_field_leak_count: {report.official_field_leak_count}",
    )
    lines.append("")
    lines.append("## Distribution")
    lines.append("")
    if report.gateway_status_distribution:
        for status, count in report.gateway_status_distribution:
            lines.append(f"- {status}: {count}")
    else:
        lines.append("_(no gateway runs recorded yet)_")
    lines.append("")
    lines.append("## Rates")
    lines.append("")
    lines.append(
        f"- operator_usefulness_rate: {report.operator_usefulness_rate:.3f}",
    )
    lines.append(
        f"- summary_readability_avg: {report.summary_readability_avg:.3f}",
    )
    lines.append(
        f"- evidence_traceability_avg: {report.evidence_traceability_avg:.3f}",
    )
    lines.append(f"- actionability_avg: {report.actionability_avg:.3f}")
    lines.append(f"- no_false_verdict_avg: {report.no_false_verdict_avg:.3f}")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    if report.cases:
        lines.append("| case_id | status | expected_risk | label | run_id |")
        lines.append("|---|---|---|---|---|")
        for c in report.cases:
            label_cell = c.operator_label or "_pending_"
            run_cell = c.workflow_run_id or "_pending_"
            lines.append(
                f"| {c.case_id} | {c.status} | {c.expected_risk} | "
                f"{label_cell} | {run_cell} |",
            )
    else:
        lines.append("_(no cases yet)_")
    lines.append("")
    lines.append(f"## Recommendation: `{report.recommendation}`")
    lines.append("")
    lines.append(
        "Even if the recommendation reaches `document_opt_in_path`, "
        "`enable-tool-gateway` remains **default false** in the "
        "composite Action.",
    )
    lines.append("")
    return "\n".join(lines)


# Re-export for type-checkers in callers that want the literal directly.
ContinueSoak = Literal["continue_soak"]


__all__ = (
    "CONTINUE_SOAK_MIN_CASES",
    "DOCUMENT_OPT_IN_MIN_CASES",
    "FN_REVISE_THRESHOLD",
    "FP_REVISE_THRESHOLD",
    "USEFULNESS_THRESHOLD",
    "ValidationError",
    "aggregate_cases",
    "compute_recommendation",
    "render_aggregate_markdown",
)

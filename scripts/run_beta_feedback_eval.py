"""Phase 6.0 — controlled-beta feedback aggregator.

Reads operator-submitted feedback forms (YAML or JSON) under a
configurable feedback root, computes the 17 Phase 6.0 metrics
specified in QA/A41 §6.0-E, and writes:

* ``reports/beta/beta_feedback_aggregate.json``
* ``reports/beta/beta_feedback_aggregate.md``

Usage::

    python scripts/run_beta_feedback_eval.py
    python scripts/run_beta_feedback_eval.py --feedback-root reports/beta
    python scripts/run_beta_feedback_eval.py --out-dir reports/beta

The script never calls an external provider, never reads secrets,
and never writes a product verdict. The metrics are diagnostic
only; they do not gate any production decision and they do not
flip the ``enable-tool-gateway`` Action input default.

The zero-feedback case is handled cleanly: when no form has been
submitted yet the script writes an aggregate that records
``beta_cases_total: 0`` and ``recommendation: continue_beta`` and
exits 0. The empty case is the expected initial state of Phase 6.0.

This script is intentionally self-contained — Phase 6.0 does not
introduce a new package module for beta aggregation. The single
script reads YAML / JSON, computes counts and means, writes the
two output files. The shape mirrors
``scripts/run_operator_soak_eval.py`` but the semantics are
beta-specific (no operator-soak fiche, no contract-violation
input).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_VALID_LABELS = (
    "useful_true_positive",
    "useful_true_negative",
    "false_positive",
    "false_negative",
    "unclear",
    "insufficient_fixture",
)
_SCORE_AXES = (
    "summary_readability",
    "evidence_traceability",
    "actionability",
    "no_false_verdict",
    "setup_friction",
)
_WOULD_USE_AGAIN = ("yes", "no", "maybe")
_FORBIDDEN_PHRASES = (
    "merge-safe",
    "production-safe",
    "bug-free",
    "security-verified",
    "total_v_net",
    "debt_final",
    "corrupt_success",
    "corrupt_success_ratio",
    "verdict",
)


@dataclass(frozen=True)
class FeedbackEntry:
    """One operator feedback submission."""

    beta_run_id: str
    beta_case_id: str
    beta_operator: str
    target_repo: str
    named_claim: str
    pytest_scope: str
    artifact_url: str | None
    scores: dict[str, int]
    would_use_again: str
    operator_label: str
    contract_violation_observed: bool
    official_field_leak_observed: bool


def _load_form(path: Path) -> dict[str, Any]:
    """Load a YAML or JSON feedback form.

    The file extension decides the parser; YAML is the canonical
    form per ``docs/beta/beta_feedback_form.md``. JSON is accepted
    for tooling that prefers it.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        loaded = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError(
            f"unrecognised feedback file extension: {path.suffix} "
            f"(expected .yaml / .yml / .json)",
        )
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    return loaded


def _validate_form(path: Path, raw: dict[str, Any]) -> FeedbackEntry:
    """Validate a single feedback form against the Phase 6.0 schema.

    The runner does not silently coerce missing fields; missing
    fields are surfaced as clear errors so the operator can fix
    the form rather than have the aggregator fabricate data.
    """
    beta_run = raw.get("beta_run")
    if not isinstance(beta_run, dict):
        raise ValueError(f"{path}: missing 'beta_run' mapping")
    scores = raw.get("scores")
    if not isinstance(scores, dict):
        raise ValueError(f"{path}: missing 'scores' mapping")

    for axis in _SCORE_AXES:
        value = scores.get(axis)
        if not isinstance(value, int) or value not in (0, 1, 2):
            raise ValueError(
                f"{path}: scores.{axis} must be 0|1|2, got {value!r}",
            )

    would_use_again = scores.get("would_use_again")
    if would_use_again not in _WOULD_USE_AGAIN:
        raise ValueError(
            f"{path}: scores.would_use_again must be one of "
            f"{_WOULD_USE_AGAIN}, got {would_use_again!r}",
        )

    operator_label = raw.get("operator_label")
    if operator_label not in _VALID_LABELS:
        raise ValueError(
            f"{path}: operator_label must be one of {_VALID_LABELS}, "
            f"got {operator_label!r}",
        )

    return FeedbackEntry(
        beta_run_id=str(beta_run.get("beta_run_id") or ""),
        beta_case_id=str(beta_run.get("beta_case_id") or ""),
        beta_operator=str(beta_run.get("beta_operator") or ""),
        target_repo=str(beta_run.get("target_repo") or ""),
        named_claim=str(beta_run.get("named_claim") or ""),
        pytest_scope=str(beta_run.get("pytest_scope") or ""),
        artifact_url=(
            str(beta_run["artifact_url"])
            if beta_run.get("artifact_url")
            else None
        ),
        scores={axis: int(scores[axis]) for axis in _SCORE_AXES},
        would_use_again=str(would_use_again),
        operator_label=str(operator_label),
        contract_violation_observed=bool(
            raw.get("contract_violation_observed", False),
        ),
        official_field_leak_observed=bool(
            raw.get("official_field_leak_observed", False),
        ),
    )


def _iter_feedback_files(root: Path) -> list[Path]:
    """Return all .yaml / .yml / .json files under ``root``.

    The aggregator filters out files that look like other Phase 6.0
    artefacts (``beta_cases.md`` is markdown so it never matches;
    ``beta_feedback_aggregate.json`` is the script's own output and
    is filtered by name).
    """
    if not root.exists():
        return []
    candidates: list[Path] = []
    for pattern in ("**/*.yaml", "**/*.yml", "**/*.json"):
        for path in root.rglob(pattern.split("/")[-1]):
            if path.name in (
                "beta_feedback_aggregate.json",
                "beta_feedback_aggregate.yaml",
            ):
                continue
            if "beta_feedback" not in path.name.lower():
                # Only files whose name contains "beta_feedback"
                # are treated as feedback forms. This prevents the
                # aggregator from ingesting unrelated YAML/JSON
                # operators may drop alongside cases.
                continue
            candidates.append(path)
    return sorted(set(candidates))


def _check_no_forbidden_phrases(entries: list[FeedbackEntry]) -> int:
    """Return the count of entries that quoted a forbidden phrase.

    The runner forbidden-phrase scan already rejects responses
    containing these tokens at the raw-bytes layer; this is a
    defensive aggregation check so the aggregate report can
    reflect the count without fabricating it.
    """
    leaks = 0
    for entry in entries:
        haystack = (
            f"{entry.named_claim} {entry.target_repo} {entry.pytest_scope}"
        ).lower()
        if any(phrase in haystack for phrase in _FORBIDDEN_PHRASES):
            leaks += 1
    return leaks


def _aggregate(entries: list[FeedbackEntry]) -> dict[str, Any]:
    """Compute the 17 Phase 6.0 metrics from a list of entries."""
    cases_total = len(entries)
    operators_total = len({e.beta_operator for e in entries if e.beta_operator})

    label_counts = {label: 0 for label in _VALID_LABELS}
    for entry in entries:
        label_counts[entry.operator_label] += 1

    useful_count = (
        label_counts["useful_true_positive"]
        + label_counts["useful_true_negative"]
    )
    operator_usefulness_rate = (
        useful_count / cases_total if cases_total else 0.0
    )

    score_means: dict[str, float] = {}
    for axis in _SCORE_AXES:
        if not entries:
            score_means[axis] = 0.0
        else:
            score_means[axis] = round(
                sum(e.scores[axis] for e in entries) / cases_total,
                3,
            )

    would_use_again_counts = {value: 0 for value in _WOULD_USE_AGAIN}
    for entry in entries:
        would_use_again_counts[entry.would_use_again] += 1

    contract_violations = sum(
        1 for e in entries if e.contract_violation_observed
    )
    operator_field_leaks = sum(
        1 for e in entries if e.official_field_leak_observed
    )
    forbidden_phrase_quotes = _check_no_forbidden_phrases(entries)
    official_field_leak_count = (
        operator_field_leaks + forbidden_phrase_quotes
    )

    if cases_total == 0:
        recommendation = "continue_beta"
        recommendation_reason = (
            "no feedback submitted yet — phase remains in beta_pack_only "
            "state per QA/A41 partial-completion authorization"
        )
    elif official_field_leak_count > 0:
        recommendation = "fix_contract_leak"
        recommendation_reason = (
            "official field leak observed in beta feedback; halt the "
            "controlled beta and fix the leak before continuing"
        )
    elif contract_violations > 0:
        recommendation = "revise_gateway_policy_or_prompts"
        recommendation_reason = (
            "operator-observed contract violation; revisit the gateway "
            "policy or the verifier prompts before continuing"
        )
    elif operator_usefulness_rate < 0.5:
        recommendation = "revise_report_ux_or_labels"
        recommendation_reason = (
            "operator usefulness rate below 0.5 across submitted "
            "feedback; revise the report UX or the operator labels"
        )
    elif cases_total < 2:
        recommendation = "continue_beta"
        recommendation_reason = (
            "fewer than 2 completed beta runs; continue the beta to "
            "reach the QA/A41 acceptance threshold"
        )
    else:
        recommendation = "consider_phase_6_1"
        recommendation_reason = (
            "controlled beta produced sufficient signal to evaluate "
            "Phase 6.1 scope (bundle generator vs UX simplification "
            "vs report redesign)"
        )

    return {
        "beta_cases_total": cases_total,
        "beta_cases_completed": cases_total,
        "operators_total": operators_total,
        "operator_usefulness_rate": round(operator_usefulness_rate, 3),
        "summary_readability_avg": score_means["summary_readability"],
        "evidence_traceability_avg": score_means["evidence_traceability"],
        "actionability_avg": score_means["actionability"],
        "no_false_verdict_avg": score_means["no_false_verdict"],
        "setup_friction_avg": score_means["setup_friction"],
        "would_use_again_yes_count": would_use_again_counts["yes"],
        "would_use_again_maybe_count": would_use_again_counts["maybe"],
        "would_use_again_no_count": would_use_again_counts["no"],
        "official_field_leak_count": official_field_leak_count,
        "false_positive_count": label_counts["false_positive"],
        "false_negative_count": label_counts["false_negative"],
        "unclear_count": label_counts["unclear"],
        "insufficient_fixture_count": label_counts["insufficient_fixture"],
        "useful_true_positive_count": label_counts["useful_true_positive"],
        "useful_true_negative_count": label_counts["useful_true_negative"],
        "contract_violation_count": contract_violations,
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "official_fields_emitted": False,
        "gateway_status": "diagnostic_only",
        "feedback_files_used": [],
    }


def _render_markdown(aggregate: dict[str, Any]) -> str:
    """Render the aggregate as a human-readable Markdown report.

    The Markdown is the operator-facing surface. It does not claim
    a product verdict; it lists counts, means, and the
    recommendation key.
    """
    used = aggregate["feedback_files_used"]
    lines: list[str] = []
    lines.append("# Phase 6.0 — beta feedback aggregate")
    lines.append("")
    lines.append(
        "**Status:** diagnostic only. This aggregate does not gate "
        "any production decision and does not flip the "
        "`enable-tool-gateway` Action input default.",
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"* `beta_cases_total: {aggregate['beta_cases_total']}`")
    lines.append(
        f"* `beta_cases_completed: {aggregate['beta_cases_completed']}`"
    )
    lines.append(f"* `operators_total: {aggregate['operators_total']}`")
    lines.append(
        f"* `operator_usefulness_rate: {aggregate['operator_usefulness_rate']}`"
    )
    lines.append(
        f"* `official_field_leak_count: {aggregate['official_field_leak_count']}`"
    )
    lines.append(
        f"* `gateway_status: {aggregate['gateway_status']}`"
    )
    lines.append(
        f"* `official_fields_emitted: {aggregate['official_fields_emitted']}`"
    )
    lines.append("")
    lines.append("## Score axes (0/1/2 means)")
    lines.append("")
    lines.append("| Axis | Mean |")
    lines.append("|---|---|")
    lines.append(
        f"| summary_readability | {aggregate['summary_readability_avg']} |"
    )
    lines.append(
        f"| evidence_traceability | {aggregate['evidence_traceability_avg']} |"
    )
    lines.append(f"| actionability | {aggregate['actionability_avg']} |")
    lines.append(
        f"| no_false_verdict | {aggregate['no_false_verdict_avg']} |"
    )
    lines.append(f"| setup_friction | {aggregate['setup_friction_avg']} |")
    lines.append("")
    lines.append("## Would use again")
    lines.append("")
    lines.append(f"* yes: {aggregate['would_use_again_yes_count']}")
    lines.append(f"* maybe: {aggregate['would_use_again_maybe_count']}")
    lines.append(f"* no: {aggregate['would_use_again_no_count']}")
    lines.append("")
    lines.append("## Operator labels")
    lines.append("")
    lines.append(
        f"* useful_true_positive: {aggregate['useful_true_positive_count']}"
    )
    lines.append(
        f"* useful_true_negative: {aggregate['useful_true_negative_count']}"
    )
    lines.append(f"* false_positive: {aggregate['false_positive_count']}")
    lines.append(f"* false_negative: {aggregate['false_negative_count']}")
    lines.append(f"* unclear: {aggregate['unclear_count']}")
    lines.append(
        f"* insufficient_fixture: {aggregate['insufficient_fixture_count']}"
    )
    lines.append(
        f"* contract_violation: {aggregate['contract_violation_count']}"
    )
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"* `{aggregate['recommendation']}`")
    lines.append("")
    lines.append(f"_{aggregate['recommendation_reason']}_")
    lines.append("")
    lines.append("The recommendation is a diagnostic key, not a product")
    lines.append("verdict. The `enable-tool-gateway` Action input default")
    lines.append("does not change in Phase 6.0 regardless of this value.")
    lines.append("")
    lines.append("## Feedback files used")
    lines.append("")
    if used:
        for relpath in used:
            lines.append(f"* `{relpath}`")
    else:
        lines.append("_No feedback submitted yet._ The Phase 6.0 controlled")
        lines.append("beta is in `beta_pack_only` state — the protocol is")
        lines.append("established but no operator has returned a feedback")
        lines.append("form. This is the expected initial state per QA/A41")
        lines.append("partial-completion authorization (criteria 7–10).")
    lines.append("")
    lines.append("## Honesty statement")
    lines.append("")
    lines.append(
        "Phase 6.0 runs a controlled beta of the opt-in "
        "gateway-grounded path with selected operators and "
        "controlled repos. It does not make the gateway default. "
        "It does not implement MCP. It does not enable provider "
        "tool-calling. It does not validate production predictive "
        "performance. It does not emit official `total_v_net`, "
        "`debt_final`, or `corrupt_success`. It does not modify "
        "the vendored OIDA core."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate Phase 6.0 beta feedback forms and emit the "
            "diagnostic recommendation. Zero-feedback case handled "
            "cleanly. No product verdict ever produced."
        ),
    )
    parser.add_argument(
        "--feedback-root",
        type=Path,
        default=Path("reports/beta"),
        help=(
            "Directory containing beta_feedback_*.yaml / .yml / "
            ".json forms. Searched recursively."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/beta"),
        help=(
            "Output directory for beta_feedback_aggregate.json + "
            "beta_feedback_aggregate.md."
        ),
    )
    args = parser.parse_args()

    files = _iter_feedback_files(args.feedback_root)
    entries: list[FeedbackEntry] = []
    used_relpaths: list[str] = []
    for path in files:
        raw = _load_form(path)
        entry = _validate_form(path, raw)
        entries.append(entry)
        try:
            used_relpaths.append(
                str(path.relative_to(args.feedback_root)).replace("\\", "/"),
            )
        except ValueError:
            used_relpaths.append(str(path).replace("\\", "/"))

    aggregate = _aggregate(entries)
    aggregate["feedback_files_used"] = used_relpaths

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "beta_feedback_aggregate.json"
    md_path = args.out_dir / "beta_feedback_aggregate.md"

    json_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(aggregate), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"recommendation: {aggregate['recommendation']}")
    print(f"beta_cases_total: {aggregate['beta_cases_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

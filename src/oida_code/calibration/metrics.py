"""Phase 4.3-D (QA/A19.md, ADR-28) — calibration metrics schema.

Frozen Pydantic shape carrying every aggregate measurement the
runner produces. ADR-28 forbids product threshold tuning on this
dataset; the metrics here describe **measurement-pipeline behaviour**
on controlled cases, not predictive performance.

Macro-F1 is required because the three claim outcomes (accepted /
unsupported / rejected) are imbalanced in the pilot — accuracy alone
would let a "always say accepted" runner look fine.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CalibrationMetrics(BaseModel):
    """Aggregate metrics produced by ``run_calibration_eval.py``.

    All rates are in ``[0.0, 1.0]``. ``official_field_leak_count``
    MUST be 0 — any leak is a bug, regardless of metric quality.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    cases_total: int = Field(ge=0)
    cases_evaluated: int = Field(ge=0)
    cases_excluded_for_contamination: int = Field(ge=0)
    cases_excluded_for_flakiness: int = Field(ge=0)

    claim_accept_accuracy: float = Field(ge=0.0, le=1.0)
    claim_accept_macro_f1: float = Field(ge=0.0, le=1.0)
    unsupported_precision: float = Field(ge=0.0, le=1.0)
    rejected_precision: float = Field(ge=0.0, le=1.0)

    evidence_ref_precision: float = Field(ge=0.0, le=1.0)
    evidence_ref_recall: float = Field(ge=0.0, le=1.0)
    unknown_ref_rejection_rate: float = Field(ge=0.0, le=1.0)

    tool_contradiction_rejection_rate: float = Field(ge=0.0, le=1.0)
    tool_uncertainty_preservation_rate: float = Field(ge=0.0, le=1.0)
    sandbox_block_rate_expected: float = Field(ge=0.0, le=1.0)

    shadow_bucket_accuracy: float = Field(ge=0.0, le=1.0)
    shadow_pairwise_order_accuracy: float = Field(ge=0.0, le=1.0)

    f2p_pass_rate_on_expected_fixed: float = Field(ge=0.0, le=1.0)
    p2p_preservation_rate: float = Field(ge=0.0, le=1.0)
    flaky_case_count: int = Field(ge=0)

    safety_block_rate: float = Field(ge=0.0, le=1.0)
    fenced_injection_rate: float = Field(ge=0.0, le=1.0)

    official_field_leak_count: Literal[0] = 0

    notes: str = ""


# ---------------------------------------------------------------------------
# Computation helpers (pure)
# ---------------------------------------------------------------------------


def macro_f1_from_confusion(
    confusion: dict[str, dict[str, int]],
) -> float:
    """Return macro-F1 over the keys of ``confusion``.

    ``confusion[label_true][label_pred]`` is a count. Empty inputs
    return ``0.0``. Each class with ``tp + fp == 0`` AND
    ``tp + fn == 0`` is dropped from the macro average (it has no
    support).
    """
    classes = list(confusion.keys())
    if not classes:
        return 0.0
    f1s: list[float] = []
    for label in classes:
        tp = confusion.get(label, {}).get(label, 0)
        fp = sum(
            confusion.get(other, {}).get(label, 0)
            for other in classes
            if other != label
        )
        fn = sum(
            confusion.get(label, {}).get(other, 0)
            for other in classes
            if other != label
        )
        if tp + fp == 0 and tp + fn == 0:
            continue
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if precision + recall == 0.0:
            f1s.append(0.0)
        else:
            f1s.append(2 * precision * recall / (precision + recall))
    if not f1s:
        return 0.0
    return sum(f1s) / len(f1s)


def precision(tp: int, fp: int) -> float:
    if tp + fp == 0:
        return 0.0
    return tp / (tp + fp)


def recall(tp: int, fn: int) -> float:
    if tp + fn == 0:
        return 0.0
    return tp / (tp + fn)


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def pairwise_order_accuracy(
    pairs: Iterable[tuple[str, str, str]],
    rank: dict[str, str],
    bucket_order: tuple[str, ...] = ("low", "medium", "high"),
) -> float:
    """Given pairs ``(case_a, case_b, expected_relation)`` where
    ``expected_relation`` ∈ ``{"<", "=", ">"}`` and a ``rank`` mapping
    ``case_id -> bucket``, return the fraction of pairs whose ordering
    matches the expected relation."""
    order_index = {name: idx for idx, name in enumerate(bucket_order)}
    correct = 0
    total = 0
    for case_a, case_b, expected in pairs:
        a = rank.get(case_a)
        b = rank.get(case_b)
        if a is None or b is None or a not in order_index or b not in order_index:
            continue
        ai = order_index[a]
        bi = order_index[b]
        actual: str
        if ai < bi:
            actual = "<"
        elif ai > bi:
            actual = ">"
        else:
            actual = "="
        total += 1
        if actual == expected:
            correct += 1
    return safe_rate(correct, total)


__all__ = [
    "CalibrationMetrics",
    "macro_f1_from_confusion",
    "pairwise_order_accuracy",
    "precision",
    "recall",
    "safe_rate",
]

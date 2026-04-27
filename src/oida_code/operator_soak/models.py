"""Phase 5.7 operator-soak schemas.

Pydantic v2 frozen models with ``extra="forbid"`` and Literal-pinned
enumerations for: case status, expected risk, operator label,
and aggregator recommendation. These models are the *only* surface
``scripts/run_operator_soak_eval.py`` parses; the README files in
``operator_soak_cases/`` are the human-readable view.

Hard-wall guards (ADR-22 / ADR-24 / ADR-25 / ADR-26) carry through here:

- ``operator_label`` is a six-bucket enum (``useful_true_positive``,
  ``useful_true_negative``, ``false_positive``, ``false_negative``,
  ``unclear``, ``insufficient_fixture``); product verdicts like
  ``merge_safe`` / ``production_safe`` / ``bug_free`` are
  STRUCTURALLY unrepresentable.
- ``recommendation`` is a five-value Literal (``continue_soak``,
  ``fix_contract_leak``, ``revise_gateway_policy_or_prompts``,
  ``revise_report_ux_or_labels``, ``document_opt_in_path``); per
  QA/A34 §5.7-F.
- ``AggregateReport`` exposes counts, distributions, and a
  recommendation, but never ``total_v_net``, ``debt_final``,
  ``corrupt_success``, ``corrupt_success_ratio``, or ``verdict``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Enumerations (Literal[...] to keep forbidden values structurally absent)
# ---------------------------------------------------------------------------

SoakCaseStatus = Literal[
    "awaiting_operator",
    "awaiting_run",
    "awaiting_label",
    "complete",
    "blocked",
]
SOAK_STATUS_VALUES: tuple[SoakCaseStatus, ...] = (
    "awaiting_operator",
    "awaiting_run",
    "awaiting_label",
    "complete",
    "blocked",
)

ExpectedRisk = Literal["low", "medium", "high", "unknown"]
EXPECTED_RISK_VALUES: tuple[ExpectedRisk, ...] = ("low", "medium", "high", "unknown")

OperatorLabel = Literal[
    "useful_true_positive",
    "useful_true_negative",
    "false_positive",
    "false_negative",
    "unclear",
    "insufficient_fixture",
]
OPERATOR_LABEL_VALUES: tuple[OperatorLabel, ...] = (
    "useful_true_positive",
    "useful_true_negative",
    "false_positive",
    "false_negative",
    "unclear",
    "insufficient_fixture",
)

Recommendation = Literal[
    "continue_soak",
    "fix_contract_leak",
    "revise_gateway_policy_or_prompts",
    "revise_report_ux_or_labels",
    "document_opt_in_path",
]
RECOMMENDATION_VALUES: tuple[Recommendation, ...] = (
    "continue_soak",
    "fix_contract_leak",
    "revise_gateway_policy_or_prompts",
    "revise_report_ux_or_labels",
    "document_opt_in_path",
)

# ---------------------------------------------------------------------------
# Per-case models
# ---------------------------------------------------------------------------


class OperatorSoakFiche(BaseModel):
    """Machine-readable case metadata authored by the operator.

    Lives at ``operator_soak_cases/<case_id>/fiche.json``. The README
    sibling carries the same metadata in plain prose for triage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    case_id: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    expected_risk: ExpectedRisk
    gateway_bundle: str = Field(min_length=1)
    workflow_run_id: str | None = None
    artifact_url: str | None = None
    notes: str = ""
    status: SoakCaseStatus


class OperatorLabelEntry(BaseModel):
    """Operator label for one case. NO LLM may write this file."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    operator_label: OperatorLabel
    operator_rationale: str = Field(min_length=1)
    labeled_by: str = Field(min_length=1)
    labeled_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def _rationale_line_count(self) -> OperatorLabelEntry:
        # QA/A34 §5.7-B requires 3-10 lines of rationale.
        line_count = len(self.operator_rationale.splitlines()) or 1
        if line_count < 3 or line_count > 10:
            raise ValueError(
                "operator_rationale must be between 3 and 10 lines "
                f"(got {line_count})",
            )
        return self


class OperatorUxScore(BaseModel):
    """UX qualitative scores per QA/A34 §5.7-G. NO LLM may write this file."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    summary_readability: int = Field(ge=0, le=2)
    evidence_traceability: int = Field(ge=0, le=2)
    actionability: int = Field(ge=0, le=2)
    no_false_verdict: int = Field(ge=0, le=2)
    scored_by: str = Field(min_length=1)
    scored_at: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------


class SoakCaseSummary(BaseModel):
    """Per-case row in the aggregate report."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    case_id: str
    status: SoakCaseStatus
    expected_risk: ExpectedRisk
    operator_label: OperatorLabel | None = None
    workflow_run_id: str | None = None


class AggregateReport(BaseModel):
    """Phase 5.7 aggregate metrics across all soak cases.

    Decision rules (QA/A34 §5.7-F) are encoded in
    :func:`compute_recommendation` (in ``aggregate.py``). This model
    only holds the resulting numbers + the chosen recommendation.

    The hard wall on official fusion fields is preserved: this model
    has no ``total_v_net`` / ``debt_final`` / ``corrupt_success`` /
    ``corrupt_success_ratio`` / ``verdict``, and the schema is frozen
    so post-construction injection is rejected.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    cases_total: int = Field(ge=0)
    cases_completed: int = Field(ge=0)
    useful_true_positive_count: int = Field(ge=0)
    useful_true_negative_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    unclear_count: int = Field(ge=0)
    insufficient_fixture_count: int = Field(ge=0)
    contract_violation_count: int = Field(ge=0)
    official_field_leak_count: int = Field(ge=0)
    gateway_status_distribution: tuple[tuple[str, int], ...] = ()
    operator_usefulness_rate: float = Field(ge=0.0, le=1.0)
    summary_readability_avg: float = Field(ge=0.0, le=2.0)
    evidence_traceability_avg: float = Field(ge=0.0, le=2.0)
    actionability_avg: float = Field(ge=0.0, le=2.0)
    no_false_verdict_avg: float = Field(ge=0.0, le=2.0)
    cases: tuple[SoakCaseSummary, ...] = ()
    recommendation: Recommendation
    is_authoritative: Literal[False] = False

    @model_validator(mode="after")
    def _completed_ge_labels(self) -> AggregateReport:
        labelled = (
            self.useful_true_positive_count
            + self.useful_true_negative_count
            + self.false_positive_count
            + self.false_negative_count
            + self.unclear_count
            + self.insufficient_fixture_count
        )
        if labelled > self.cases_completed:
            raise ValueError(
                f"sum of label counts ({labelled}) cannot exceed "
                f"cases_completed ({self.cases_completed})",
            )
        if self.cases_completed > self.cases_total:
            raise ValueError(
                f"cases_completed ({self.cases_completed}) cannot exceed "
                f"cases_total ({self.cases_total})",
            )
        return self


__all__ = (
    "EXPECTED_RISK_VALUES",
    "OPERATOR_LABEL_VALUES",
    "RECOMMENDATION_VALUES",
    "SOAK_STATUS_VALUES",
    "AggregateReport",
    "ExpectedRisk",
    "OperatorLabel",
    "OperatorLabelEntry",
    "OperatorSoakFiche",
    "OperatorUxScore",
    "Recommendation",
    "SoakCaseStatus",
    "SoakCaseSummary",
)

"""Phase 5.7 operator soak — schemas and aggregator.

Operator soak is a controlled-cases protocol for the opt-in
gateway-grounded action path (Phase 5.6 / ADR-41). Each case under
``operator_soak_cases/case_<id>_<slug>/`` carries three machine-readable
sidecars:

- ``fiche.json``    — case metadata authored by the operator
- ``label.json``    — operator label (NO LLM may write this)
- ``ux_score.json`` — operator UX scores (NO LLM may write this)

The aggregator (``scripts/run_operator_soak_eval.py``) reads only those JSON
files. The README files alongside each case are the human-readable view.

Every public model here is frozen, ``extra="forbid"``, and pins decision-rule
fields with ``Literal[...]`` so a forged label cannot widen the schema.

ADR-42 governs this package. The hard wall on the official fusion fields
(ADR-22 / ADR-24 / ADR-25 / ADR-26) is preserved end-to-end: the aggregate
report exposes counts and an explicit ``recommendation`` enum but never emits
``total_v_net``, ``debt_final``, ``corrupt_success``, ``corrupt_success_ratio``,
or ``verdict``.
"""

from oida_code.operator_soak.models import (
    EXPECTED_RISK_VALUES,
    OPERATOR_LABEL_VALUES,
    RECOMMENDATION_VALUES,
    SOAK_STATUS_VALUES,
    AggregateReport,
    ExpectedRisk,
    OperatorLabel,
    OperatorLabelEntry,
    OperatorSoakFiche,
    OperatorUxScore,
    Recommendation,
    SoakCaseStatus,
    SoakCaseSummary,
)

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

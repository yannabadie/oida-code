"""Phase 4.3 (QA/A19.md, ADR-28) — calibration dataset framework.

This package defines the schemas, metrics, and runner used to
evaluate estimator / verifier / tool-loop behaviour on a controlled
dataset. **It does not validate predictive performance.** ADR-22 +
ADR-28 keep the official OIDA fusion fields blocked at v0.4.x.

* :mod:`oida_code.calibration.models` — frozen Pydantic schemas
  (`CalibrationCase`, `ExpectedClaimLabel`, `ExpectedToolResultLabel`,
  `ExpectedCodeOutcome`, `CalibrationProvenance`,
  `CalibrationManifest`).
* :mod:`oida_code.calibration.metrics` — `CalibrationMetrics` schema
  + pure helpers (`macro_f1_from_confusion`, `precision`, `recall`,
  `safe_rate`, `pairwise_order_accuracy`).
* :mod:`oida_code.calibration.runner` — per-family evaluators +
  `aggregate(results)` → `CalibrationMetrics`.
"""

from oida_code.calibration.metrics import (
    CalibrationMetrics,
    macro_f1_from_confusion,
    pairwise_order_accuracy,
    precision,
    recall,
    safe_rate,
)
from oida_code.calibration.models import (
    CalibrationCase,
    CalibrationFamily,
    CalibrationManifest,
    CalibrationProvenance,
    ClaimExpected,
    ClaimReason,
    ContaminationRisk,
    ExpectedClaimLabel,
    ExpectedCodeOutcome,
    ExpectedRepairBehavior,
    ExpectedToolResultLabel,
    ShadowBucket,
    ToolResultExpected,
)
from oida_code.calibration.runner import (
    CaseResult,
    aggregate,
    load_case,
    run_case,
)

__all__ = [
    "CalibrationCase",
    "CalibrationFamily",
    "CalibrationManifest",
    "CalibrationMetrics",
    "CalibrationProvenance",
    "CaseResult",
    "ClaimExpected",
    "ClaimReason",
    "ContaminationRisk",
    "ExpectedClaimLabel",
    "ExpectedCodeOutcome",
    "ExpectedRepairBehavior",
    "ExpectedToolResultLabel",
    "ShadowBucket",
    "ToolResultExpected",
    "aggregate",
    "load_case",
    "macro_f1_from_confusion",
    "pairwise_order_accuracy",
    "precision",
    "recall",
    "run_case",
    "safe_rate",
]

"""E3 (QA/A14.md, ADR-24) — estimator contracts.

Sub-modules:

* :mod:`oida_code.estimators.contracts` — frozen Pydantic schemas
  ``SignalEstimate`` and ``EstimatorReport`` shared by all estimator
  implementations (deterministic, LLM-based, hybrid).
* :mod:`oida_code.estimators.deterministic` — pure deterministic
  baseline estimators for ``capability`` / ``benefit`` /
  ``observability`` derived from tool evidence + intent only.
* :mod:`oida_code.estimators.llm_contract` — input/output contracts
  for the future LLM estimator. **No LLM is called from this
  package.** ADR-24: contracts before implementation.
"""

from oida_code.estimators.contracts import (
    EstimateField,
    EstimateSource,
    EstimatorReport,
    EstimatorStatus,
    SignalEstimate,
)
from oida_code.estimators.deterministic import (
    estimate_all_for_event,
    estimate_benefit,
    estimate_capability,
    estimate_completion,
    estimate_observability,
    estimate_operator_accept,
    estimate_tests_pass,
)
from oida_code.estimators.llm_contract import (
    LLM_CONFIDENCE_CAP_HYBRID,
    LLM_CONFIDENCE_CAP_LLM_ONLY,
    LLMEstimatorInput,
    LLMEstimatorOutput,
)

__all__ = [
    "LLM_CONFIDENCE_CAP_HYBRID",
    "LLM_CONFIDENCE_CAP_LLM_ONLY",
    "EstimateField",
    "EstimateSource",
    "EstimatorReport",
    "EstimatorStatus",
    "LLMEstimatorInput",
    "LLMEstimatorOutput",
    "SignalEstimate",
    "estimate_all_for_event",
    "estimate_benefit",
    "estimate_capability",
    "estimate_completion",
    "estimate_observability",
    "estimate_operator_accept",
    "estimate_tests_pass",
]

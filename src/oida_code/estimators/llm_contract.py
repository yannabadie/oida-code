"""E3.3 (QA/A14.md, ADR-24) — LLM estimator contract.

**No LLM is called from this module.** This file defines the
input/output schemas any future LLM estimator MUST satisfy. The
production CLI does not import any LLM client at v0.4.x.

ADR-24 hard rules captured here:

* LLM output **must cite** ``cited_evidence_refs``. Any claim not
  backed by a cited reference is logged in ``unsupported_claims``.
* LLM-only estimates (``source="llm"``) **cannot** be authoritative —
  the schema validator on :class:`SignalEstimate` already rejects
  ``source="llm" + is_authoritative=True``. The contract here adds
  the reverse direction: a confidence cap at ``0.6`` for LLM-only
  estimates and ``0.8`` for hybrid (LLM + deterministic corroboration).
* LLM cannot emit official ``V_net`` / ``debt_final`` / ``corrupt_success``.
  This is enforced at :class:`SignalEstimate` (no such ``field``
  values exist) AND at :class:`EstimatorReport` (status
  ``official_ready_candidate`` requires every estimate to satisfy
  confidence >= 0.7, which the cap blocks for LLM-only).
* LLM cannot override tool failures: the consumer must compose the
  LLM output with deterministic estimates and pick the deterministic
  one when they disagree on a tool-grounded field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from oida_code.estimators.contracts import (
    EstimateField,
    SignalEstimate,
)
from oida_code.models.normalized_event import NormalizedEvent
from oida_code.score.event_evidence import EventEvidenceView

LLM_CONFIDENCE_CAP_LLM_ONLY = 0.6
LLM_CONFIDENCE_CAP_HYBRID = 0.8


class LLMEstimatorInput(BaseModel):
    """Inputs the LLM may consume.

    The shape mirrors :func:`compute_experimental_shadow_fusion`'s view
    so that the LLM gets exactly the same context as the deterministic
    layer — it cannot claim to have seen something the deterministic
    estimator didn't.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    intent: str
    event: NormalizedEvent
    evidence_view: EventEvidenceView
    neighboring_events: tuple[NormalizedEvent, ...] = ()
    allowed_fields: tuple[EstimateField, ...] = Field(
        default=("capability", "benefit", "observability"),
        description=(
            "Fields the LLM is allowed to estimate. Tool-grounded "
            "fields (operator_accept, tests_pass, completion) are "
            "deliberately NOT in the default — those should come from "
            "deterministic estimators except in hybrid corroboration "
            "scenarios."
        ),
    )


_DisallowedAuthoritative = Literal[False]


class LLMEstimatorOutput(BaseModel):
    """LLM estimator's response, frozen and validated.

    Each :class:`SignalEstimate` in ``estimates`` is independently
    validated by its own model. This wrapper adds two cross-cutting
    rules: confidence caps for LLM-only / hybrid sources, and a
    citation requirement.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    estimates: tuple[SignalEstimate, ...]
    cited_evidence_refs: tuple[str, ...]
    unsupported_claims: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _enforce_llm_caps_and_citation(self) -> LLMEstimatorOutput:
        for est in self.estimates:
            if est.source == "llm" and est.confidence > LLM_CONFIDENCE_CAP_LLM_ONLY:
                raise ValueError(
                    f"LLM-only estimate has confidence={est.confidence} > "
                    f"{LLM_CONFIDENCE_CAP_LLM_ONLY} (ADR-24 cap). "
                    f"Field={est.field}, event_id={est.event_id}."
                )
            if est.source == "hybrid" and est.confidence > LLM_CONFIDENCE_CAP_HYBRID:
                raise ValueError(
                    f"Hybrid estimate has confidence={est.confidence} > "
                    f"{LLM_CONFIDENCE_CAP_HYBRID} (ADR-24 cap). "
                    f"Field={est.field}, event_id={est.event_id}."
                )
        # Any LLM-sourced estimate that claims confidence > 0 MUST cite
        # at least one evidence_ref OR be in unsupported_claims.
        for est in self.estimates:
            if est.source not in ("llm", "hybrid"):
                continue
            if est.confidence == 0.0:
                continue
            if est.evidence_refs:
                continue
            ref = f"{est.field}@{est.event_id}"
            if ref not in self.unsupported_claims:
                raise ValueError(
                    f"LLM/hybrid estimate without evidence_refs must be "
                    f"listed in unsupported_claims (ADR-24): {ref}"
                )
        return self


__all__ = [
    "LLM_CONFIDENCE_CAP_HYBRID",
    "LLM_CONFIDENCE_CAP_LLM_ONLY",
    "LLMEstimatorInput",
    "LLMEstimatorOutput",
]

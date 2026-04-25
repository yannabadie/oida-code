"""E3.1 (QA/A14.md, ADR-24) — estimator contract schemas.

Defines the **frozen** Pydantic types every estimator must speak:

* :class:`SignalEstimate` — one estimated value for one
  ``(field, event_id)`` pair, with confidence + provenance.
* :class:`EstimatorReport` — the bundle of estimates for a scenario,
  carrying readiness ladder status separate from the official
  :class:`~oida_code.score.fusion_readiness.FusionReadinessReport`.

Hard rules (ADR-24):

* ``source="default"``  → ``confidence`` is forced to ``0.0`` and the
  estimate **blocks official fusion**.
* ``source="missing"``  → no value may be treated as real signal.
* ``source="llm"``      → never authoritative alone (capped confidence).
* ``is_authoritative=True`` is allowed **only** for tool-grounded
  deterministic estimates on narrow fields. Validators enforce this.

These rules are mechanical: they are checked by the model itself, not
by downstream consumers. The point is to prevent any future code path
from quietly promoting an LLM-only or default estimate to authoritative
just by setting a boolean.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EstimateField = Literal[
    "capability",
    "benefit",
    "observability",
    "completion",
    "tests_pass",
    "operator_accept",
    "edge_confidence",
]
"""Which OIDA event field this estimate populates.

``edge_confidence`` is event-pair scoped (the ``event_id`` is then the
child event's id; ``method_id`` carries the parent + kind in its name)
and is consumed by ``compute_experimental_shadow_fusion`` via its
``edge_confidences`` parameter (ADR-23 §5)."""


EstimateSource = Literal[
    "tool",
    "static_analysis",
    "test_result",
    "llm",
    "hybrid",
    "heuristic",
    "missing",
    "default",
]
"""Where the estimate's value came from.

Ordered (loosely) by trustworthiness:

* ``tool``           — directly from a deterministic tool's exit code /
                       counts / findings (ruff, mypy, pytest, semgrep,
                       codeql, hypothesis, mutmut).
* ``static_analysis`` — a deterministic static analyzer that did not
                       cross into LLM territory (e.g. AST coverage).
* ``test_result``    — pytest / hypothesis / mutmut result for a
                       specific event scope.
* ``hybrid``         — deterministic + LLM combined; LLM cannot make
                       the result authoritative on its own.
* ``llm``            — LLM only; confidence capped, never authoritative.
* ``heuristic``      — rule-based fallback that doesn't claim to measure.
* ``missing``        — no signal at all; field is unset for this event.
* ``default``        — placeholder structural default (e.g. 0.5);
                       blocks official fusion."""


EstimatorStatus = Literal[
    "blocked",
    "diagnostic_only",
    "shadow_ready",
    "official_ready_candidate",
]
"""Readiness ladder for the estimator report.

* ``blocked``                  — too many fields are default/missing;
                                 not safe to feed even shadow fusion.
* ``diagnostic_only``          — shadow can run but the report itself
                                 makes no claim about V_net.
* ``shadow_ready``             — every field has a non-default,
                                 non-missing estimate; shadow fusion
                                 can run on real signal.
* ``official_ready_candidate`` — confidence thresholds met across all
                                 load-bearing fields. **Reserved**:
                                 the production CLI must NOT emit
                                 official ``V_net`` even at this status
                                 unless a future ADR explicitly unlocks
                                 it (ADR-22 still holds today)."""


class SignalEstimate(BaseModel):
    """One estimated value for one ``(field, event_id)`` pair."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    field: EstimateField
    event_id: str | None = None

    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

    source: EstimateSource
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)

    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    is_default: bool = False
    is_authoritative: bool = False

    @model_validator(mode="after")
    def _enforce_source_invariants(self) -> SignalEstimate:
        """ADR-24 invariants: source / confidence / authoritative consistency."""
        # default → confidence = 0.0 (enforced) AND is_default=True.
        if self.source == "default":
            if self.confidence != 0.0:
                raise ValueError(
                    "SignalEstimate.source='default' requires confidence=0.0 "
                    "(ADR-24): default estimates contribute nothing to the "
                    "weighted fusion."
                )
            if not self.is_default:
                raise ValueError(
                    "SignalEstimate.source='default' must set is_default=True "
                    "(ADR-24): the consumer needs to identify default-origin "
                    "estimates without parsing source strings."
                )
            if self.is_authoritative:
                raise ValueError(
                    "SignalEstimate.source='default' cannot be authoritative "
                    "(ADR-22 + ADR-24): defaults block official fusion."
                )
        # missing → confidence MUST be 0.0; cannot be authoritative.
        if self.source == "missing":
            if self.confidence != 0.0:
                raise ValueError(
                    "SignalEstimate.source='missing' requires confidence=0.0 "
                    "(ADR-24): missing data must not contribute confidence."
                )
            if self.is_authoritative:
                raise ValueError(
                    "SignalEstimate.source='missing' cannot be authoritative "
                    "(ADR-24)."
                )
        # llm-only is never authoritative alone (Phase 4 contract).
        if self.source == "llm" and self.is_authoritative:
            raise ValueError(
                "SignalEstimate.source='llm' cannot set is_authoritative=True "
                "alone (ADR-24): LLM estimates require corroboration via "
                "source='hybrid' before any authoritative claim."
            )
        # heuristic is never authoritative either — they don't measure.
        if self.source == "heuristic" and self.is_authoritative:
            raise ValueError(
                "SignalEstimate.source='heuristic' cannot be authoritative "
                "(ADR-24): heuristics fill gaps, they don't measure."
            )
        return self


class EstimatorReport(BaseModel):
    """Full bundle of estimates for a scenario at one point in time."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    status: EstimatorStatus
    estimates: tuple[SignalEstimate, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommendation: str = ""

    @model_validator(mode="after")
    def _status_consistent_with_estimates(self) -> EstimatorReport:
        """``official_ready_candidate`` requires every estimate to be
        non-default, non-missing, and confidence >= 0.7. ``shadow_ready``
        requires every estimate to be non-default and non-missing.
        ``blocked`` is reachable from any state. The validator catches
        a ``status`` set inconsistently with the underlying estimates.
        """
        if self.status == "official_ready_candidate":
            for est in self.estimates:
                if est.is_default or est.source == "missing":
                    raise ValueError(
                        f"status='official_ready_candidate' requires every "
                        f"estimate to be non-default and non-missing; "
                        f"{est.field!r}@{est.event_id!r} is "
                        f"source={est.source!r}, is_default={est.is_default}."
                    )
                if est.confidence < 0.7:
                    raise ValueError(
                        f"status='official_ready_candidate' requires "
                        f"confidence >= 0.7; {est.field!r}@{est.event_id!r} "
                        f"has confidence={est.confidence}."
                    )
        elif self.status == "shadow_ready":
            for est in self.estimates:
                if est.is_default or est.source == "missing":
                    raise ValueError(
                        f"status='shadow_ready' requires every estimate to "
                        f"be non-default and non-missing; "
                        f"{est.field!r}@{est.event_id!r} is "
                        f"source={est.source!r}, is_default={est.is_default}."
                    )
        return self


__all__ = [
    "EstimateField",
    "EstimateSource",
    "EstimatorReport",
    "EstimatorStatus",
    "SignalEstimate",
]

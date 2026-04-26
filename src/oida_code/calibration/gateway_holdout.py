"""Phase 5.3 (QA/A30.md, ADR-38) — gateway holdout expected
labels.

Phase 4.3 already shipped :class:`CalibrationCase` for the
deterministic + LLM estimator surface. Phase 5.3 adds a parallel
"expected verifier outcome per mode" shape so the calibration
runner (`scripts/run_gateway_calibration.py`) can compare:

* ``baseline`` — :func:`run_verifier` with no gateway;
* ``gateway`` — :func:`run_gateway_grounded_verifier`.

The deliberate split — separate file, not extending
:mod:`oida_code.calibration.models` — is per the advisor's
recommendation: ``CalibrationCase``\\'s family-specific
invariants would interfere with this "two outcomes per case"
shape.

Hard rules (ADR-38, mirrored from QA/A30):

* No automatic label mutation — these labels are written ONCE
  by the operator and never bumped to make a particular
  measurement look better.
* No production thresholds — ``expected_delta`` is diagnostic
  only; a "improves" label means *we expect the gateway to
  improve this case*, not that the gateway is allowed to
  promote anything to official.
* No ``total_v_net`` / ``debt_final`` / ``corrupt_success``
  fields. The schema deliberately doesn't expose them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpectedVerifierOutcome(BaseModel):
    """Expected ``VerifierAggregationReport`` shape for one mode.

    Holdout labels carry only the FIELDS the calibration runner
    can deterministically check against an actual run:
    accepted/unsupported/rejected claim ids, plus
    expected blockers/warnings that the operator considers
    load-bearing for THIS case.

    The shape is intentionally tuple-based so the model is
    immutable from the runner's perspective (no field on this
    model can be flipped on the fly to hide a measurement).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    accepted_claim_ids: tuple[str, ...] = ()
    unsupported_claim_ids: tuple[str, ...] = ()
    rejected_claim_ids: tuple[str, ...] = ()
    blockers_expected: tuple[str, ...] = ()
    warnings_expected: tuple[str, ...] = ()


_ExpectedDelta = Literal[
    "improves",
    "same",
    "worse_expected",
    "not_applicable",
]
"""Operator-supplied expectation of how the gateway-grounded
loop should change the verdict on this case relative to the
no-gateway baseline.

* ``improves``        — gateway should yield a strictly better
                        outcome (more rejections of contradicted
                        claims, more unsupported demotions, etc).
* ``same``            — gateway should yield the SAME outcome as
                        baseline (the case isn't a discriminator).
* ``worse_expected``  — operator deliberately encoded a case where
                        the gateway's stricter rules will demote a
                        claim that baseline accepted. Important for
                        calibration: not every demotion is a bug.
* ``not_applicable``  — case not designed for this comparison
                        (e.g. baseline can't even run because the
                        case requires tool evidence to make sense).
"""


class GatewayHoldoutExpected(BaseModel):
    """Per-case expected verdicts for both modes.

    The runner pairs this with the actual baseline/gateway
    outcomes and records a per-case classification (no
    automatic label mutation).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    case_id: str = Field(min_length=1)
    expected_baseline: ExpectedVerifierOutcome
    expected_gateway: ExpectedVerifierOutcome
    expected_delta: _ExpectedDelta

    # If non-empty, the gateway run MUST cite at least one of
    # these tool evidence ids in its accepted_claims.
    required_tool_evidence_refs: tuple[str, ...] = ()

    # If non-empty, the gateway MUST NOT accept any claim whose
    # evidence_refs intersect with the listed reasons (e.g.
    # the operator wants to forbid claims that lean on
    # adversarial fence-close attempts).
    forbidden_acceptance_reasons: tuple[str, ...] = ()


__all__ = [
    "ExpectedVerifierOutcome",
    "GatewayHoldoutExpected",
]

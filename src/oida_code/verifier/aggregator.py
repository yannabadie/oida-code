"""Phase 4.1 (QA/A16.md, ADR-26) — verifier aggregation logic.

Combines forward + backward + deterministic-tool evidence into a
single :class:`VerifierAggregationReport`. The aggregator's job is to
say YES (claim accepted) only if **all** of the rules below hold:

1. Forward says supported.
2. Backward says necessary conditions met.
3. Every ``evidence_refs`` entry exists in the packet.
4. No deterministic-tool contradiction (if a tool-grounded estimate
   for the claim's event has source ``test_result`` /
   ``static_analysis`` / ``tool`` and value < 0.5, the LLM-style
   claim cannot say "supported" with positive confidence).
5. ``claim_type`` is in the allowed Literal (the schema enforces this
   already).
6. Confidence within the 0.6 LLM-only / 0.8 hybrid cap (best-effort —
   the contract is identical to E3's confidence policy).
7. The claim does not mention any forbidden official phrase
   (the schema validator rejects construction; the aggregator
   re-checks the cited evidence ids).

Failure of ANY rule produces:

* ``rejected_claims``     — claim is hard-rejected (cannot be cited
                            anywhere downstream).
* ``unsupported_claims``  — claim has signal but lacks corroboration;
                            useful for the integrator to inspect but
                            never authoritative.
* ``blockers``             — high-level reasons the report status is
                            ``blocked`` or ``diagnostic_only``.
"""

from __future__ import annotations

from oida_code.estimators.contracts import SignalEstimate
from oida_code.estimators.llm_prompt import LLMEvidencePacket
from oida_code.verifier.contracts import (
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierAggregationReport,
    VerifierClaim,
    VerifierStatus,
)


def _packet_evidence_ids(packet: LLMEvidencePacket) -> set[str]:
    return {item.id for item in packet.evidence_items}


def _tool_grounded_failure(
    deterministic_estimates: tuple[SignalEstimate, ...],
    event_id: str,
) -> bool:
    """True if a tool-grounded estimate on ``event_id`` reports failure
    (value < 0.5 with source in tool/static_analysis/test_result)."""
    for est in deterministic_estimates:
        if est.event_id != event_id:
            continue
        if est.source not in ("tool", "static_analysis", "test_result"):
            continue
        if est.value < 0.5 and est.confidence > 0.0:
            return True
    return False


def aggregate_verification(
    forward: ForwardVerificationResult,
    backward: tuple[BackwardVerificationResult, ...],
    packet: LLMEvidencePacket,
    deterministic_estimates: tuple[SignalEstimate, ...] | None = None,
) -> VerifierAggregationReport:
    """Run the aggregation rules. **Never raises**; failures become
    blockers/warnings on the resulting report.

    ``deterministic_estimates`` defaults to
    ``packet.deterministic_estimates`` so the aggregator picks up the
    tool-grounded signals embedded in the packet without the caller
    having to forward them explicitly.
    """
    if deterministic_estimates is None:
        deterministic_estimates = packet.deterministic_estimates
    accepted: list[VerifierClaim] = []
    rejected: list[VerifierClaim] = []
    unsupported: list[VerifierClaim] = []
    blockers: list[str] = []
    warnings: list[str] = []

    known_ids = _packet_evidence_ids(packet)
    # 4.1.1 — backward results must be filtered by event_id consistency.
    # A backward result whose event_id doesn't match the claim it refers
    # to is dropped (warning logged) so the aggregator can't be tricked
    # into accepting a cross-event vote.
    backward_by_claim: dict[str, BackwardVerificationResult] = {}
    for b in backward:
        if b.event_id != forward.event_id:
            warnings.append(
                f"backward result for claim {b.claim_id} has event_id "
                f"{b.event_id!r} != forward.event_id {forward.event_id!r}; "
                "ignoring"
            )
            continue
        backward_by_claim[b.claim_id] = b

    # Forward-rejected claims are recorded as such, never accepted.
    for claim in forward.rejected_claims:
        rejected.append(claim)

    for claim in forward.supported_claims:
        # 4.1.1 — claim.event_id must match the forward result's event_id.
        # Otherwise the claim was issued for a different event and should
        # never be aggregated under this forward.
        if claim.event_id != forward.event_id:
            warnings.append(
                f"claim {claim.claim_id} has event_id {claim.event_id!r} "
                f"!= forward.event_id {forward.event_id!r}; rejecting"
            )
            rejected.append(claim)
            continue

        # Rule 3 — evidence refs must exist
        unknown_refs = [r for r in claim.evidence_refs if r not in known_ids]
        if unknown_refs:
            warnings.append(
                f"claim {claim.claim_id} cites unknown evidence_refs "
                f"{unknown_refs}; rejecting"
            )
            rejected.append(claim)
            continue

        # Rule 2 — backward must say necessary conditions met
        b_result = backward_by_claim.get(claim.claim_id)
        if b_result is None:
            warnings.append(
                f"claim {claim.claim_id} has forward support but no "
                "backward verification; marking unsupported"
            )
            unsupported.append(claim)
            continue
        if not b_result.necessary_conditions_met:
            warnings.append(
                f"claim {claim.claim_id} backward says necessary conditions "
                f"not met (missing: {list(b_result.requirement.missing_requirements)})"
            )
            unsupported.append(claim)
            continue

        # Rule 4 — deterministic tool contradictions
        # 4.1.1 — check tool failure on the CLAIM's event_id, not the
        # forward's. Even if both currently match, this guards against
        # future per-event aggregation paths where forward could carry
        # a roll-up event_id while individual claims target sub-events.
        if (
            _tool_grounded_failure(deterministic_estimates, claim.event_id)
            and claim.confidence > 0.0
        ):
            warnings.append(
                f"claim {claim.claim_id} contradicts deterministic tool "
                f"failure on event {claim.event_id}; rejecting"
            )
            rejected.append(claim)
            continue

        # Rule 6 — confidence cap (LLM source caps at 0.6, hybrid at
        # 0.8). The schema didn't enforce this for VerifierClaim
        # because we don't know the source granularity at construction
        # time; we enforce it here for the LLM/replay sources.
        if claim.source in ("forward", "backward", "replay") and claim.confidence > 0.6:
            warnings.append(
                f"claim {claim.claim_id} confidence "
                f"{claim.confidence} exceeds 0.6 cap for LLM-style "
                "verifier sources; rejecting"
            )
            rejected.append(claim)
            continue

        accepted.append(claim)

    # Forward-side missing evidence and contradictions also flow into
    # the blockers/warnings set.
    if forward.missing_evidence_refs:
        warnings.append(
            f"forward reports missing evidence refs: "
            f"{list(forward.missing_evidence_refs)}"
        )
    for note in forward.contradictions:
        warnings.append(f"forward contradiction: {note}")

    # Status decision — diagnostic_only is the realistic ceiling at
    # Phase 4.1 because we have no real LLM and no tool execution.
    status: VerifierStatus
    if accepted:
        status = "verification_candidate" if not rejected else "diagnostic_only"
    elif unsupported:
        status = "diagnostic_only"
    else:
        status = "blocked"
        blockers.append(
            "no claim met all aggregation rules "
            "(forward + backward + evidence + tool non-contradiction)"
        )

    recommendation = _recommendation_for(
        status, len(accepted), len(rejected), len(unsupported),
    )

    return VerifierAggregationReport(
        status=status,
        accepted_claims=tuple(accepted),
        rejected_claims=tuple(rejected),
        unsupported_claims=tuple(unsupported),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        recommendation=recommendation,
    )


def _recommendation_for(
    status: VerifierStatus,
    accepted: int, rejected: int, unsupported: int,
) -> str:
    base = (
        f"verifier aggregation accepted={accepted} rejected={rejected} "
        f"unsupported={unsupported}"
    )
    if status == "verification_candidate":
        return (
            f"{base}. RESERVED: status='verification_candidate' is "
            "diagnostic only; ADR-22 still blocks official V_net at v0.4.x."
        )
    if status == "diagnostic_only":
        return f"{base}. some claims lack full corroboration; treat as diagnostic."
    return f"{base}. no claim was accepted; verifier output is blocked."


__all__ = ["aggregate_verification"]

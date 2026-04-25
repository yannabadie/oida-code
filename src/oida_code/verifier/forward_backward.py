"""Phase 4.1 (QA/A16.md, ADR-26) — forward/backward runner.

End-to-end driver that takes a packet, calls a forward provider, calls
a backward provider, and runs the aggregator. All failure modes
(invalid JSON, schema violations, forbidden phrases) become blockers
on the resulting :class:`VerifierAggregationReport`.

**Never raises.** Phase 4.1 is contract-only: the runner does NOT
execute any verifier-requested tool spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from oida_code.estimators.contracts import SignalEstimate
from oida_code.estimators.llm_prompt import (
    LLMEvidencePacket,
    has_forbidden_phrase,
    render_prompt,
)
from oida_code.verifier.aggregator import aggregate_verification
from oida_code.verifier.contracts import (
    BackwardVerificationResult,
    ForwardVerificationResult,
    VerifierAggregationReport,
)
from oida_code.verifier.replay import (
    VerifierProvider,
    VerifierProviderError,
)

_VERIFIER_TIMEOUT_S = 30


@dataclass(frozen=True)
class VerifierRun:
    """Bundled output of one forward/backward verifier dry-run."""

    report: VerifierAggregationReport
    forward_raw: str | None
    backward_raw: str | None


def run_verifier(
    packet: LLMEvidencePacket,
    forward_provider: VerifierProvider,
    backward_provider: VerifierProvider,
    *,
    deterministic_estimates: tuple[SignalEstimate, ...] | None = None,
    timeout_s: int = _VERIFIER_TIMEOUT_S,
) -> VerifierRun:
    """Drive the two providers with ``packet``'s prompt, validate, aggregate.

    Always returns a :class:`VerifierRun`. Failures (provider error,
    invalid JSON, schema violation, forbidden phrase in either reply)
    become blockers on the resulting
    :class:`VerifierAggregationReport`.

    ``deterministic_estimates`` defaults to
    ``packet.deterministic_estimates``; callers can override when the
    evidence packet was built without per-event tool evidence (e.g.
    score-trace at v0.4.x — see ADR-24 §10).
    """
    if deterministic_estimates is None:
        deterministic_estimates = packet.deterministic_estimates
    prompt = render_prompt(packet)

    forward_raw, forward_result, forward_blockers = _drive_provider(
        prompt,
        forward_provider,
        timeout_s,
        kind="forward",
        packet=packet,
        loader=ForwardVerificationResult,
    )
    backward_raw, backward_results, backward_blockers = _drive_backward(
        prompt,
        backward_provider,
        timeout_s,
        packet,
    )

    blockers = list(forward_blockers) + list(backward_blockers)

    if forward_result is None:
        report = VerifierAggregationReport(
            status="blocked",
            blockers=tuple(blockers),
            recommendation=(
                "forward verifier failed; aggregation skipped. See blockers."
            ),
        )
        return VerifierRun(
            report=report,
            forward_raw=forward_raw,
            backward_raw=backward_raw,
        )

    aggregation = aggregate_verification(
        forward_result,
        backward_results,
        packet,
        deterministic_estimates,
    )
    if blockers:
        aggregation = aggregation.model_copy(update={
            "blockers": tuple(list(aggregation.blockers) + blockers),
        })
    return VerifierRun(
        report=aggregation,
        forward_raw=forward_raw,
        backward_raw=backward_raw,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _drive_provider(
    prompt: str,
    provider: VerifierProvider,
    timeout_s: int,
    *,
    kind: str,
    packet: LLMEvidencePacket,
    loader: type[ForwardVerificationResult],
) -> tuple[str | None, ForwardVerificationResult | None, list[str]]:
    """Drive a forward provider end-to-end. Returns
    (raw_response, parsed, blockers)."""
    blockers: list[str] = []
    try:
        raw = provider.verify(prompt, timeout_s=timeout_s)
    except VerifierProviderError as exc:
        blockers.append(f"{kind} provider unavailable: {exc}")
        return None, None, blockers

    if not isinstance(raw, str):
        blockers.append(
            f"{kind} provider returned non-string payload "
            f"(type={type(raw).__name__})"
        )
        return None, None, blockers

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        blockers.append(
            f"{kind} response not valid JSON: {exc.msg} (offset {exc.pos})"
        )
        return raw, None, blockers

    if not isinstance(decoded, dict):
        blockers.append(
            f"{kind} response is not a JSON object "
            f"(type={type(decoded).__name__})"
        )
        return raw, None, blockers

    if has_forbidden_phrase(raw, packet):
        blockers.append(
            f"{kind} response references a forbidden official phrase; "
            "response rejected"
        )
        return raw, None, blockers

    decoded.setdefault("event_id", packet.event_id)
    try:
        parsed = loader.model_validate(decoded)
    except ValidationError as exc:
        blockers.append(
            f"{kind} response failed schema validation: "
            f"{exc.error_count()} errors"
        )
        return raw, None, blockers
    return raw, parsed, blockers


def _drive_backward(
    prompt: str,
    provider: VerifierProvider,
    timeout_s: int,
    packet: LLMEvidencePacket,
) -> tuple[str | None, tuple[BackwardVerificationResult, ...], list[str]]:
    """Backward provider returns a JSON list of BackwardVerificationResult.

    Empty list is allowed (no claims to validate); a non-list is a
    schema violation.
    """
    blockers: list[str] = []
    try:
        raw = provider.verify(prompt, timeout_s=timeout_s)
    except VerifierProviderError as exc:
        blockers.append(f"backward provider unavailable: {exc}")
        return None, (), blockers

    if not isinstance(raw, str):
        blockers.append(
            f"backward provider returned non-string payload "
            f"(type={type(raw).__name__})"
        )
        return None, (), blockers

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        blockers.append(
            f"backward response not valid JSON: {exc.msg} (offset {exc.pos})"
        )
        return raw, (), blockers

    if has_forbidden_phrase(raw, packet):
        blockers.append(
            "backward response references a forbidden official phrase; "
            "response rejected"
        )
        return raw, (), blockers

    if isinstance(decoded, dict) and "results" in decoded:
        items = decoded["results"]
    elif isinstance(decoded, list):
        items = decoded
    else:
        blockers.append(
            "backward response must be a JSON list or {results: [...]} "
            f"(got {type(decoded).__name__})"
        )
        return raw, (), blockers

    if not isinstance(items, list):
        blockers.append(
            "backward response 'results' must be a list "
            f"(got {type(items).__name__})"
        )
        return raw, (), blockers

    out: list[BackwardVerificationResult] = []
    for idx, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            blockers.append(
                f"backward result #{idx} is not a JSON object"
            )
            continue
        raw_item.setdefault("event_id", packet.event_id)
        try:
            out.append(BackwardVerificationResult.model_validate(raw_item))
        except ValidationError as exc:
            blockers.append(
                f"backward result #{idx} failed schema validation: "
                f"{exc.error_count()} errors"
            )
            continue
    return raw, tuple(out), blockers


__all__ = [
    "VerifierRun",
    "run_verifier",
]

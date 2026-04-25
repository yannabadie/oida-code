"""Phase 4.0-C (QA/A15.md, ADR-25) — LLM estimator runner.

End-to-end flow:

    packet -> render_prompt(packet) -> provider.estimate(prompt)
    -> json.loads(...) -> LLMEstimatorOutput.model_validate(...)
    -> merge with deterministic estimates -> EstimatorReport

Strict failure handling rules (QA/A15.md §Phase 4.0-C):

* invalid JSON               → no crash; estimate report adds a blocker
                               and returns the deterministic baseline
* schema violation           → no crash; reject the LLM batch entirely
* confidence above the cap   → reject (the LLMEstimatorOutput model
                               already enforces this; we surface a
                               readable warning when it triggers)
* missing evidence refs      → reject the offending estimate unless
                               ``unsupported_claims`` lists it
* forbidden phrase / V_net   → reject the entire response
* contradicts deterministic  → deterministic wins; LLM estimate is
                               downgraded to ``unsupported_claims``

The runner produces a fresh :class:`EstimatorReport` carrying the
union of deterministic + accepted-LLM estimates plus any blockers /
warnings the failure path raised.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from oida_code.estimators.contracts import (
    EstimatorReport,
    EstimatorStatus,
    SignalEstimate,
)
from oida_code.estimators.llm_contract import LLMEstimatorOutput
from oida_code.estimators.llm_prompt import (
    LLMEvidencePacket,
    evidence_ids,
    has_forbidden_phrase,
    render_prompt,
)
from oida_code.estimators.llm_provider import (
    LLMProvider,
    LLMProviderError,
)

_LLM_TIMEOUT_S = 30


@dataclass(frozen=True)
class LLMEstimatorRun:
    """Bundled result of one LLM estimator dry-run."""

    report: EstimatorReport
    raw_response: str | None
    accepted_count: int
    rejected_count: int


def run_llm_estimator(
    packet: LLMEvidencePacket,
    provider: LLMProvider,
    *,
    timeout_s: int = _LLM_TIMEOUT_S,
) -> LLMEstimatorRun:
    """Drive ``provider`` with ``packet``'s prompt, validate, merge.

    Always returns an :class:`LLMEstimatorRun`. **Never raises**; every
    failure becomes a blocker on the resulting :class:`EstimatorReport`.
    """
    prompt = render_prompt(packet)
    raw: str | None
    try:
        raw = provider.estimate(prompt, timeout_s=timeout_s)
    except LLMProviderError as exc:
        return _baseline_run(
            packet,
            blockers=[f"llm provider unavailable: {exc}"],
            warnings=[],
            raw_response=None,
        )

    if not isinstance(raw, str):
        return _baseline_run(
            packet,
            blockers=[
                "llm provider returned non-string payload "
                f"(type={type(raw).__name__})"
            ],
            warnings=[],
            raw_response=None,
        )

    # Parse JSON.
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _baseline_run(
            packet,
            blockers=[f"llm response is not valid JSON: {exc.msg} (offset {exc.pos})"],
            warnings=[],
            raw_response=raw,
        )

    if not isinstance(decoded, dict):
        return _baseline_run(
            packet,
            blockers=[
                f"llm response is not a JSON object (type={type(decoded).__name__})"
            ],
            warnings=[],
            raw_response=raw,
        )

    # Forbidden phrase check on the raw payload BEFORE schema validation.
    if has_forbidden_phrase(raw, packet):
        return _baseline_run(
            packet,
            blockers=[
                "llm response references a forbidden phrase "
                f"(any of {list(packet.forbidden_claims)}); response rejected"
            ],
            warnings=[],
            raw_response=raw,
        )

    # Validate the wrapper (caps + citation rules live in
    # LLMEstimatorOutput's model validators).
    try:
        validated = LLMEstimatorOutput.model_validate(decoded)
    except ValidationError as exc:
        return _baseline_run(
            packet,
            blockers=[f"llm output failed schema validation: {exc.error_count()} errors"],
            warnings=[],
            raw_response=raw,
        )

    # Cross-check evidence_refs against the packet's known IDs.
    known_ids = evidence_ids(packet)
    accepted: list[SignalEstimate] = []
    rejected_warnings: list[str] = []
    unsupported_lookup = set(validated.unsupported_claims)

    deterministic_by_field: dict[tuple[str, str | None], SignalEstimate] = {
        (est.field, est.event_id): est
        for est in packet.deterministic_estimates
    }

    for est in validated.estimates:
        # Disallowed fields (the LLM tried to emit a tool-grounded
        # field outside allowed_fields).
        if est.field not in packet.allowed_fields:
            rejected_warnings.append(
                f"llm tried to emit field {est.field!r} not in allowed_fields"
            )
            continue
        # Unknown evidence_refs → warning, but not auto-reject (the
        # Pydantic validator already required ≥1 ref OR
        # unsupported_claims membership for confidence > 0).
        unknown_refs = [r for r in est.evidence_refs if r not in known_ids]
        if unknown_refs:
            rejected_warnings.append(
                f"llm cited unknown evidence_refs {unknown_refs} on "
                f"{est.field}@{est.event_id}; estimate dropped"
            )
            continue
        # Contradicts deterministic tool failure?
        det = deterministic_by_field.get((est.field, est.event_id))
        if det is not None and _contradicts_tool_failure(det, est):
            rejected_warnings.append(
                f"llm contradicts deterministic tool signal on "
                f"{est.field}@{est.event_id}; deterministic estimate kept, "
                f"llm estimate marked unsupported"
            )
            unsupported_lookup.add(f"{est.field}@{est.event_id}")
            continue
        accepted.append(est)

    # Build the merged estimates list. We replace deterministic
    # capability/benefit/observability estimates with the LLM ones
    # when the LLM produced a non-default, non-missing replacement —
    # so the readiness ladder can lift past `blocked` on controlled
    # fixtures. Tool-grounded fields keep their deterministic value.
    accepted_keys = {(e.field, e.event_id) for e in accepted}
    merged: list[SignalEstimate] = []
    for det in packet.deterministic_estimates:
        if (det.field, det.event_id) in accepted_keys and det.field in (
            "capability", "benefit", "observability",
        ):
            # Replaced by LLM below.
            continue
        merged.append(det)
    merged.extend(accepted)

    status = _decide_status(merged)
    blockers: list[str] = []
    warnings: list[str] = list(rejected_warnings)
    if validated.unsupported_claims:
        warnings.append(
            f"llm reported {len(validated.unsupported_claims)} unsupported claim(s)"
        )
    recommendation = _recommendation_for(status, len(accepted), len(rejected_warnings))

    report = EstimatorReport(
        status=status,
        estimates=tuple(merged),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        recommendation=recommendation,
    )
    return LLMEstimatorRun(
        report=report,
        raw_response=raw,
        accepted_count=len(accepted),
        rejected_count=len(rejected_warnings),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _baseline_run(
    packet: LLMEvidencePacket,
    *,
    blockers: list[str],
    warnings: list[str],
    raw_response: str | None,
) -> LLMEstimatorRun:
    """Return the deterministic-only EstimatorReport when the LLM path
    failed for any reason. Adds ``blockers`` and ``warnings``."""
    status = _decide_status(list(packet.deterministic_estimates))
    report = EstimatorReport(
        status=status,
        estimates=packet.deterministic_estimates,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        recommendation=(
            "LLM dry-run failed; falling back to deterministic baseline. "
            "Status reflects deterministic estimates only."
        ),
    )
    return LLMEstimatorRun(
        report=report,
        raw_response=raw_response,
        accepted_count=0,
        rejected_count=0,
    )


def _contradicts_tool_failure(
    deterministic: SignalEstimate,
    llm: SignalEstimate,
) -> bool:
    """``deterministic wins`` rule.

    The deterministic estimate "fails" when its source is ``tool`` /
    ``static_analysis`` / ``test_result`` AND its value is < 0.5.
    The LLM contradicts that when it claims a value > 0.5 with positive
    confidence.
    """
    tool_grounded = deterministic.source in (
        "tool", "static_analysis", "test_result",
    )
    if not tool_grounded:
        return False
    if deterministic.value >= 0.5:
        return False
    return llm.value > 0.5 and llm.confidence > 0.0


def _decide_status(estimates: list[SignalEstimate]) -> EstimatorStatus:
    """Same rules as ``assess_estimator_readiness`` but inlined to
    avoid coupling the dry-run to a scenario object."""
    load_bearing = ("capability", "benefit", "observability")
    defaults_or_missing = 0
    minimum_confidence = 1.0
    found = 0
    for est in estimates:
        if est.field not in load_bearing:
            continue
        found += 1
        if est.is_default or est.source == "missing":
            defaults_or_missing += 1
        else:
            minimum_confidence = min(minimum_confidence, est.confidence)
    if found == 0:
        return "blocked"
    if defaults_or_missing >= found:
        return "blocked"
    if defaults_or_missing > 0:
        return "diagnostic_only"
    if minimum_confidence >= 0.7:
        return "official_ready_candidate"
    return "shadow_ready"


def _recommendation_for(
    status: EstimatorStatus, accepted: int, rejected: int,
) -> str:
    parts = [f"llm dry-run accepted={accepted} rejected={rejected}"]
    if status == "official_ready_candidate":
        parts.append(
            "RESERVED: official V_net stays null in production "
            "(ADR-22 + ADR-25 hold). Reachable only on controlled fixtures."
        )
    elif status == "shadow_ready":
        parts.append(
            "estimates pass schema; shadow fusion may run on real signal."
        )
    elif status == "diagnostic_only":
        parts.append(
            "some load-bearing fields still default/missing; report is "
            "diagnostic only."
        )
    else:
        parts.append("estimator blocked; no real-signal estimates.")
    return " ".join(parts)


__all__ = [
    "LLMEstimatorRun",
    "run_llm_estimator",
]

"""E3.4 (QA/A14.md, ADR-24) — estimator-driven readiness.

Bundles deterministic estimates into a single :class:`EstimatorReport`
and decides the readiness status. **Independent from**
:mod:`oida_code.score.fusion_readiness` — that module governs the
*official* fusion gate (ADR-22) and is unchanged. The estimator
readiness ladder is finer-grained and answers a different question:

    "Given the estimates we have for this scenario, can we run the
     shadow fusion on real signal? Or are we still on defaults?"

ADR-24 thresholds enforced here:

* ``official_ready_candidate``  — every load-bearing field has a
  non-default, non-missing estimate AND confidence >= 0.7. **Reserved
  status**: today, NO scenario should reach this in production at
  v0.4.x. The validator on :class:`EstimatorReport` rejects
  inconsistent constructions.
* ``shadow_ready``              — every load-bearing field has a
  non-default, non-missing estimate (any confidence > 0).
* ``diagnostic_only``           — at least one load-bearing default or
  missing estimate. The shadow can still run but the report MUST
  carry a "diagnostic only" disclaimer.
* ``blocked``                   — too many fields missing/default to
  trust even shadow output (e.g. no evidence at all).

Load-bearing fields are: ``capability``, ``benefit``,
``observability``. ``completion`` / ``tests_pass`` /
``operator_accept`` are derived signals — their per-event
defaults / missing reduce confidence but don't single-handedly
block the official gate (the deterministic signals can still feed
shadow).
"""

from __future__ import annotations

from oida_code.estimators.contracts import (
    EstimatorReport,
    EstimatorStatus,
    SignalEstimate,
)
from oida_code.estimators.deterministic import estimate_all_for_event
from oida_code.models.audit_request import AuditRequest
from oida_code.models.normalized_event import NormalizedScenario
from oida_code.score.event_evidence import EventEvidenceView

_LOAD_BEARING = ("capability", "benefit", "observability")
_THRESHOLD_OFFICIAL_CANDIDATE = 0.7


def assess_estimator_readiness(
    scenario: NormalizedScenario,
    evidence_view: dict[str, EventEvidenceView],
    request: AuditRequest | None = None,
) -> EstimatorReport:
    """Produce an :class:`EstimatorReport` from deterministic baselines.

    Walks every event in ``scenario``, calls :func:`estimate_all_for_event`,
    and decides the report status from the resulting per-event estimates.
    """
    estimates: list[SignalEstimate] = []
    for ev in scenario.events:
        view = evidence_view.get(ev.id)
        if view is None:
            continue
        estimates.extend(estimate_all_for_event(view, request))
    blockers: list[str] = []
    warnings: list[str] = []

    if not scenario.events:
        return EstimatorReport(
            status="blocked",
            estimates=(),
            blockers=("scenario has no events",),
            warnings=(),
            recommendation="provide a non-empty scenario before estimating",
        )

    if not evidence_view:
        return EstimatorReport(
            status="blocked",
            estimates=tuple(estimates),
            blockers=("no evidence view for any event",),
            warnings=(),
            recommendation=(
                "build_event_evidence_view returned an empty mapping; "
                "estimator cannot proceed"
            ),
        )

    # Tally per-field default/missing across load-bearing fields.
    load_bearing_defaults = 0
    load_bearing_missing = 0
    load_bearing_total = 0
    min_load_bearing_confidence = 1.0
    for est in estimates:
        if est.field not in _LOAD_BEARING:
            continue
        load_bearing_total += 1
        if est.is_default:
            load_bearing_defaults += 1
        elif est.source == "missing":
            load_bearing_missing += 1
        else:
            min_load_bearing_confidence = min(
                min_load_bearing_confidence, est.confidence,
            )

    if load_bearing_total == 0:
        return EstimatorReport(
            status="blocked",
            estimates=tuple(estimates),
            blockers=("no load-bearing estimates produced",),
            warnings=tuple(warnings),
            recommendation="check estimator wiring",
        )

    if load_bearing_defaults > 0:
        blockers.append(
            f"{load_bearing_defaults} load-bearing default estimate(s) — "
            "Phase 4 LLM intent estimator required to produce real signal"
        )
    if load_bearing_missing > 0:
        blockers.append(
            f"{load_bearing_missing} load-bearing missing estimate(s) — "
            "intent or evidence required"
        )

    status: EstimatorStatus
    if load_bearing_defaults + load_bearing_missing >= load_bearing_total:
        # All load-bearing fields are default/missing — every event is
        # blocked, not just diagnostic. Match the contract that
        # ``blocked`` means "not safe to feed even shadow fusion."
        status = "blocked"
    elif load_bearing_defaults > 0 or load_bearing_missing > 0:
        status = "diagnostic_only"
    else:
        # Every load-bearing estimate is real signal. Decide between
        # shadow_ready and official_ready_candidate by min confidence.
        if min_load_bearing_confidence >= _THRESHOLD_OFFICIAL_CANDIDATE:
            status = "official_ready_candidate"
        else:
            status = "shadow_ready"

    recommendation_lines = []
    if status == "blocked":
        recommendation_lines.append(
            "Estimator cannot produce real-signal estimates; the shadow "
            "fusion will be uniform/diagnostic only."
        )
    elif status == "diagnostic_only":
        recommendation_lines.append(
            "Some load-bearing fields are still default/missing. The "
            "shadow fusion will run but the integrator MUST treat its "
            "output as diagnostic; official V_net stays null."
        )
    elif status == "shadow_ready":
        recommendation_lines.append(
            "All load-bearing fields have real-signal estimates. The "
            "shadow fusion runs on differentiated inputs; official "
            "V_net stays null until ADR-22 is lifted."
        )
    else:  # official_ready_candidate
        recommendation_lines.append(
            "All load-bearing fields meet the confidence threshold. "
            "RESERVED: official V_net is still null in production "
            "(ADR-22 holds at v0.4.x)."
        )
    if warnings:
        recommendation_lines.append("Warnings: " + "; ".join(warnings))

    return EstimatorReport(
        status=status,
        estimates=tuple(estimates),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        recommendation=" ".join(recommendation_lines),
    )


__all__ = ["assess_estimator_readiness"]

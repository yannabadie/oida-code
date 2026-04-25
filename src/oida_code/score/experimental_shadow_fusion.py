"""Experimental shadow fusion (E1, ADR-22 / QA/A11.md).

**NON-AUTHORITATIVE.** Computes per-event "pressure" diagnostics from
the same inputs the official OIDA fusion would consume, and propagates
along Block-C edges using bounded `max()`. The output is structured to
make confusion with official `V_net` / `debt_final` / `corrupt_success`
impossible:

* The report carries ``authoritative: Literal[False]``.
* The metric names are ``shadow_debt_pressure`` /
  ``shadow_integrity_pressure`` / ``graph_propagation_pressure`` /
  ``trajectory_pressure``. **Never** ``shadow_v_net``.
* The CLI flag must contain the word ``experimental``.
* When :func:`assess_fusion_readiness` returns anything but
  ``official_ready`` (which is always in v0.4.x), the official summary
  fields stay ``null``. The shadow report sits in a separate output
  block.

Formula (verbatim from QA/A11.md §"Formule expérimentale minimale"):

    base_pressure(event) =
        0.40 * (1 - grounding)
      + 0.20 * static_failure_pressure
      + 0.25 * trajectory_pressure
      + 0.15 * (1 - completion)

    constitutive_pressure(child) = max(
        base_pressure(child),
        max(parent_pressure * edge.confidence * 0.80)
    )

    supportive_audit_pressure(child) = max(
        base_audit_pressure(child),
        max(parent_pressure * edge.confidence * 0.40)
    )

Bounded propagation (per A11.md):

* ``max iterations = min(10, n_events + 1)`` — guards against cycles.
* operator is ``max()`` — monotone + idempotent → no cumulative
  inflation from import/test cycles.
* values clipped to ``[0, 1]``.

What this module does NOT do:

* It does NOT compute ``V_net``. The vendored core's ``V_net`` is
  unchanged and the ``ReportSummary`` fusion fields remain ``null`` per
  ADR-13 and ADR-22.
* It does NOT predict outcome. The pressure values are diagnostic;
  treating them as predictions would re-create the Phase-3 length-
  confound trap (PHASE3_AUDIT_REPORT.md §3).
* It does NOT modify the vendored OIDA core (ADR-02 holds).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.models.normalized_event import NormalizedEvent
from oida_code.score.fusion_readiness import (
    FusionReadinessReport,
    FusionStatus,
)

if TYPE_CHECKING:
    from oida_code.models.evidence import ToolEvidence
    from oida_code.models.normalized_event import NormalizedScenario
    from oida_code.models.trajectory import TrajectoryMetrics


# ---------------------------------------------------------------------------
# Tunable formula coefficients (A11.md §weights)
# ---------------------------------------------------------------------------

_W_GROUNDING = 0.40
_W_STATIC = 0.20
_W_TRAJECTORY = 0.25
_W_COMPLETION = 0.15
_ALPHA_CONSTITUTIVE = 0.80
_ALPHA_SUPPORTIVE = 0.40
_DEFAULT_EDGE_CONFIDENCE = 0.6  # parents on NormalizedEvent carry no per-edge confidence

ShadowStatus = Literal[
    "experimental",
    "unsupported_input",
    "blocked_by_readiness",
]


# ---------------------------------------------------------------------------
# Public Pydantic shape
# ---------------------------------------------------------------------------


class ShadowEventScore(BaseModel):
    """Per-event diagnostic — never authoritative."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    base_pressure: float = Field(ge=0.0, le=1.0)
    shadow_debt_pressure: float = Field(ge=0.0, le=1.0)
    shadow_integrity_pressure: float = Field(ge=0.0, le=1.0)
    graph_propagation_pressure: float = Field(ge=0.0, le=1.0)


class ShadowGraphSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constitutive_edge_count: int = Field(ge=0)
    supportive_edge_count: int = Field(ge=0)
    propagation_iterations: int = Field(ge=0)
    propagation_converged: bool


class ShadowTrajectorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_steps: int = Field(ge=0)
    progress_events_count: int = Field(ge=0)
    no_progress_rate: float = Field(ge=0.0, le=1.0)
    derived_pressure: float = Field(ge=0.0, le=1.0)


class ShadowFusionReport(BaseModel):
    """Output of :func:`compute_experimental_shadow_fusion`.

    ``authoritative`` is ``False`` — pinned by the type annotation. The
    integrator MUST NOT copy any field from this report into
    ``AuditReport.summary.total_v_net``, ``debt_final``, or
    ``corrupt_success_ratio``.
    """

    model_config = ConfigDict(extra="forbid")

    authoritative: Literal[False] = False
    status: ShadowStatus
    readiness_status: FusionStatus
    event_scores: list[ShadowEventScore] = Field(default_factory=list)
    graph_summary: ShadowGraphSummary
    trajectory_summary: ShadowTrajectorySummary | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Per-event base pressure
# ---------------------------------------------------------------------------


def _grounding_for(event: NormalizedEvent) -> float:
    if not event.preconditions:
        return 0.0
    total = sum(p.weight for p in event.preconditions)
    if total <= 0:
        return 0.0
    verified = sum(p.weight for p in event.preconditions if p.verified)
    return min(1.0, max(0.0, float(verified) / float(total)))


def _static_failure_pressure(
    event: NormalizedEvent,
    tool_evidence: list[ToolEvidence] | None,
) -> float:
    """Crude inverse of :attr:`event.operator_accept` if no evidence,
    else fraction of static-tool error findings on the event's scope."""
    if tool_evidence is None:
        # Map operator_accept (∈[0,1]) → pressure 1 - operator_accept.
        return _clip(1.0 - event.operator_accept)
    # When evidence exists, assume the mapper already folded ruff/mypy
    # results into operator_accept — keep the same surface.
    return _clip(1.0 - event.operator_accept)


def _trajectory_pressure(
    metrics: TrajectoryMetrics | None,
) -> float:
    """Single derived scalar from TrajectoryMetrics. Conservative: take
    the **max** of exploration and exploitation errors; saturate at 1.0.
    Empty trajectory → 0.0."""
    if metrics is None or metrics.total_steps == 0:
        return 0.0
    return _clip(max(metrics.exploration_error, metrics.exploitation_error))


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _base_pressure(
    event: NormalizedEvent,
    tool_evidence: list[ToolEvidence] | None,
    trajectory_pressure: float,
) -> float:
    grounding = _grounding_for(event)
    static_p = _static_failure_pressure(event, tool_evidence)
    completion = event.completion
    pressure = (
        _W_GROUNDING * (1.0 - grounding)
        + _W_STATIC * static_p
        + _W_TRAJECTORY * trajectory_pressure
        + _W_COMPLETION * (1.0 - completion)
    )
    return _clip(pressure)


# ---------------------------------------------------------------------------
# Bounded graph propagation
# ---------------------------------------------------------------------------


def _propagate(
    events: list[NormalizedEvent],
    base_by_id: dict[str, float],
    parents_attr: str,
    alpha: float,
) -> tuple[dict[str, float], int, bool]:
    """Iteratively propagate pressure via ``max()`` over the named
    parents. Returns (final_pressure_by_id, iterations, converged).

    Cycle-safe by construction: ``max()`` is idempotent and the
    sequence is monotone non-decreasing in [0, 1] → at most
    ``n_events + 1`` iterations needed (per A11.md).
    """
    pressure = dict(base_by_id)
    n_events = len(events)
    max_iter = min(10, n_events + 1)
    converged = False
    iterations = 0
    for it in range(1, max_iter + 1):
        iterations = it
        changed = False
        for ev in events:
            parents = getattr(ev, parents_attr)
            if not parents:
                continue
            current = pressure[ev.id]
            best = current
            for parent_id in parents:
                if parent_id not in pressure:
                    continue
                contribution = pressure[parent_id] * _DEFAULT_EDGE_CONFIDENCE * alpha
                if contribution > best:
                    best = contribution
            best = _clip(best)
            if best > current + 1e-12:
                pressure[ev.id] = best
                changed = True
        if not changed:
            converged = True
            break
    return pressure, iterations, converged


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def compute_experimental_shadow_fusion(
    scenario: NormalizedScenario,
    readiness: FusionReadinessReport,
    *,
    tool_evidence: list[ToolEvidence] | None = None,
    trajectory_metrics: TrajectoryMetrics | None = None,
) -> ShadowFusionReport:
    """E1 entry point. NEVER authoritative.

    Honours the readiness verdict: if ``readiness.is_blocked()``, the
    shadow report still computes pressure values but the status is
    ``blocked_by_readiness`` and the integrator must keep official
    summary fields ``null``. The shadow report is opt-in by the CLI
    flag (``--experimental-shadow-fusion``); this function does no
    side effects beyond returning the report.
    """
    n_events = len(scenario.events)
    if n_events == 0:
        return ShadowFusionReport(
            status="unsupported_input",
            readiness_status=readiness.status,
            graph_summary=ShadowGraphSummary(
                constitutive_edge_count=0,
                supportive_edge_count=0,
                propagation_iterations=0,
                propagation_converged=True,
            ),
            blockers=["scenario has no events"],
            warnings=[],
            recommendation="provide a non-empty scenario",
        )

    traj_pressure = _trajectory_pressure(trajectory_metrics)
    base_by_id: dict[str, float] = {
        ev.id: _base_pressure(ev, tool_evidence, traj_pressure)
        for ev in scenario.events
    }

    # Constitutive propagation → shadow_debt_pressure
    debt_by_id, debt_iter, debt_converged = _propagate(
        scenario.events, base_by_id, "constitutive_parents", _ALPHA_CONSTITUTIVE,
    )
    # Supportive propagation → shadow_integrity_pressure (audit pressure)
    integrity_by_id, int_iter, int_converged = _propagate(
        scenario.events, base_by_id, "supportive_parents", _ALPHA_SUPPORTIVE,
    )

    constitutive_count = sum(
        len(ev.constitutive_parents) for ev in scenario.events
    )
    supportive_count = sum(len(ev.supportive_parents) for ev in scenario.events)

    event_scores = [
        ShadowEventScore(
            event_id=ev.id,
            base_pressure=base_by_id[ev.id],
            shadow_debt_pressure=debt_by_id[ev.id],
            shadow_integrity_pressure=integrity_by_id[ev.id],
            graph_propagation_pressure=_clip(
                max(
                    debt_by_id[ev.id] - base_by_id[ev.id],
                    integrity_by_id[ev.id] - base_by_id[ev.id],
                )
            ),
        )
        for ev in scenario.events
    ]

    graph_summary = ShadowGraphSummary(
        constitutive_edge_count=constitutive_count,
        supportive_edge_count=supportive_count,
        propagation_iterations=max(debt_iter, int_iter),
        propagation_converged=debt_converged and int_converged,
    )

    trajectory_summary: ShadowTrajectorySummary | None = None
    if trajectory_metrics is not None:
        trajectory_summary = ShadowTrajectorySummary(
            total_steps=trajectory_metrics.total_steps,
            progress_events_count=trajectory_metrics.progress_events_count,
            no_progress_rate=trajectory_metrics.no_progress_rate,
            derived_pressure=traj_pressure,
        )

    blockers = list(readiness.blockers)
    warnings: list[str] = []
    if not graph_summary.propagation_converged:
        warnings.append(
            "graph propagation did not converge within the iteration cap"
        )
    if constitutive_count == 0 and supportive_count == 0:
        warnings.append(
            "no graph edges; shadow scores degrade to local base pressure"
        )

    if readiness.status == "official_ready":
        # Reachable only in a future world where capability/benefit/
        # observability are no longer defaults. Even then, the shadow
        # layer's job is diagnostic — the integrator still chooses
        # whether to trust shadow vs vendored fusion.
        status: ShadowStatus = "experimental"
        recommendation = (
            "Readiness reports official_ready, but shadow remains "
            "non-authoritative by design (E1 contract). Compare with "
            "vendored fusion before promoting any number to a verdict."
        )
    elif readiness.is_blocked():
        status = "blocked_by_readiness"
        recommendation = (
            "Readiness is blocked. Shadow pressures are diagnostic only; "
            "official V_net / debt_final / corrupt_success MUST stay null."
        )
    else:
        status = "experimental"
        recommendation = (
            "Readiness is partial. Shadow pressures are diagnostic; "
            "do not promote to authoritative without further calibration."
        )

    return ShadowFusionReport(
        authoritative=False,
        status=status,
        readiness_status=readiness.status,
        event_scores=event_scores,
        graph_summary=graph_summary,
        trajectory_summary=trajectory_summary,
        blockers=blockers,
        warnings=warnings,
        recommendation=recommendation,
    )


__all__ = [
    "ShadowEventScore",
    "ShadowFusionReport",
    "ShadowGraphSummary",
    "ShadowStatus",
    "ShadowTrajectorySummary",
    "compute_experimental_shadow_fusion",
]

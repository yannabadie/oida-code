"""Fusion readiness layer (E0, ADR-22).

Sole responsibility: decide whether OIDA-code can emit *official*
``V_net`` / ``debt_final`` / ``corrupt_success`` for the current
:class:`NormalizedScenario`. The answer in v0.4.x is **no, blocked** for
every reasonable input — ``capability`` / ``benefit`` / ``observability``
remain structural defaults pending a Phase-4 LLM intent estimator
(ADR-22 §"Field readiness").

This module **does not** compute V_net. It does not modify the vendored
OIDA core. It only audits the inputs and emits a structured verdict.

Public surface:

* :class:`FusionStatus` — Literal verdict.
* :class:`FieldReadiness` — per-field audit row.
* :class:`FusionReadinessReport` — overall report.
* :func:`assess_fusion_readiness` — entry point.

Honesty principle (ADR-13 + ADR-22): the report's existence does not
unlock V_net emission. The integrator (CLI / `audit` command) is
responsible for **not** writing official summary fields when
``status != "official_ready"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from oida_code.models.evidence import ToolEvidence
    from oida_code.models.normalized_event import NormalizedScenario
    from oida_code.models.trajectory import TrajectoryMetrics


FusionStatus = Literal[
    "blocked",
    "diagnostic_only",
    "shadow_ready",
    "official_ready",
]
"""ADR-22 verdict ladder.

* ``blocked`` — at least one load-bearing field is a structural default;
  no V_net / debt_final / corrupt_success may be emitted, even as
  diagnostic.
* ``diagnostic_only`` — readiness layer can publish per-event
  diagnostics (grounding, trajectory metrics, repair signals) but the
  fusion summary stays ``null``.
* ``shadow_ready`` — an experimental shadow fusion may be computed,
  marked non-authoritative, in a separate output block. Never in
  ``summary.total_v_net``.
* ``official_ready`` — all load-bearing fields are real measurements
  with calibrated confidence. Phase-4+ unlocks this; not reachable
  in v0.4.x.
"""

FieldStatus = Literal["real", "heuristic", "default", "missing"]


class FieldReadiness(BaseModel):
    """One audited input to the OIDA fusion."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: FieldStatus
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    blocks_official_fusion: bool


class FusionReadinessReport(BaseModel):
    """Per-scenario audit of fusion inputs (ADR-22)."""

    model_config = ConfigDict(extra="forbid")

    status: FusionStatus
    blockers: list[str] = Field(default_factory=list)
    field_readiness: list[FieldReadiness] = Field(default_factory=list)
    graph_ready: bool = False
    trajectory_ready: bool = False
    evidence_ready: bool = False
    recommendation: str = ""

    def is_official(self) -> bool:
        return self.status == "official_ready"

    def is_blocked(self) -> bool:
        return self.status == "blocked"


# ---------------------------------------------------------------------------
# Per-field auditors
# ---------------------------------------------------------------------------


_DEFAULT_FLOAT = 0.5
_DEFAULT_TOLERANCE = 1e-9


def _is_default_05(value: float) -> bool:
    return abs(value - _DEFAULT_FLOAT) < _DEFAULT_TOLERANCE


def _audit_capability(scenario: NormalizedScenario) -> FieldReadiness:
    if not scenario.events:
        return FieldReadiness(
            name="capability",
            status="missing",
            source="no events",
            confidence=0.0,
            blocks_official_fusion=True,
        )
    all_default = all(_is_default_05(ev.capability) for ev in scenario.events)
    return FieldReadiness(
        name="capability",
        status="default" if all_default else "heuristic",
        source="default 0.5 (ADR-22 §field readiness)" if all_default
               else "non-default values present (Phase 4 LLM)",
        confidence=0.0 if all_default else 0.4,
        blocks_official_fusion=True,
    )


def _audit_benefit(scenario: NormalizedScenario) -> FieldReadiness:
    if not scenario.events:
        return FieldReadiness(
            name="benefit", status="missing", source="no events",
            confidence=0.0, blocks_official_fusion=True,
        )
    all_default = all(_is_default_05(ev.benefit) for ev in scenario.events)
    return FieldReadiness(
        name="benefit",
        status="default" if all_default else "heuristic",
        source="default 0.5 (ADR-22 §field readiness)" if all_default
               else "non-default values present",
        confidence=0.0 if all_default else 0.4,
        blocks_official_fusion=True,
    )


def _audit_observability(scenario: NormalizedScenario) -> FieldReadiness:
    if not scenario.events:
        return FieldReadiness(
            name="observability", status="missing", source="no events",
            confidence=0.0, blocks_official_fusion=True,
        )
    all_default = all(_is_default_05(ev.observability) for ev in scenario.events)
    return FieldReadiness(
        name="observability",
        status="default" if all_default else "heuristic",
        source="default 0.5 (test-presence detector pending)" if all_default
               else "non-default values present",
        confidence=0.0 if all_default else 0.3,
        blocks_official_fusion=True,
    )


def _audit_completion(
    scenario: NormalizedScenario, tool_evidence: list[ToolEvidence] | None,
) -> FieldReadiness:
    has_pytest = any(
        ev.tool == "pytest" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    if not scenario.events:
        return FieldReadiness(
            name="completion", status="missing", source="no events",
            confidence=0.0, blocks_official_fusion=False,
        )
    all_default = all(_is_default_05(ev.completion) for ev in scenario.events)
    if has_pytest and not all_default:
        return FieldReadiness(
            name="completion", status="real",
            source="pytest pass-ratio (mapper)",
            confidence=0.7, blocks_official_fusion=False,
        )
    if all_default:
        return FieldReadiness(
            name="completion", status="default",
            source="default 0.5 — no pytest evidence",
            confidence=0.0, blocks_official_fusion=False,
        )
    return FieldReadiness(
        name="completion", status="heuristic",
        source="partial pytest evidence",
        confidence=0.4, blocks_official_fusion=False,
    )


def _audit_tests_pass(
    scenario: NormalizedScenario, tool_evidence: list[ToolEvidence] | None,
) -> FieldReadiness:
    has_pytest = any(
        ev.tool == "pytest" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    has_property = any(
        ev.tool == "hypothesis" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    has_mutation = any(
        ev.tool == "mutmut" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    components = sum([has_pytest, has_property, has_mutation])
    return FieldReadiness(
        name="tests_pass",
        status="real" if components >= 2 else
               "heuristic" if components == 1 else "default",
        source=f"weighted blend ({components}/3 components real)",
        confidence=0.3 + 0.2 * components,
        blocks_official_fusion=False,
    )


def _audit_operator_accept(
    scenario: NormalizedScenario, tool_evidence: list[ToolEvidence] | None,
) -> FieldReadiness:
    ruff_ok = any(
        ev.tool == "ruff" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    mypy_ok = any(
        ev.tool == "mypy" and ev.status == "ok"
        for ev in (tool_evidence or [])
    )
    if ruff_ok and mypy_ok:
        return FieldReadiness(
            name="operator_accept", status="real",
            source="ruff + mypy ran ok",
            confidence=0.7, blocks_official_fusion=False,
        )
    if ruff_ok or mypy_ok:
        return FieldReadiness(
            name="operator_accept", status="heuristic",
            source="single static checker",
            confidence=0.4, blocks_official_fusion=False,
        )
    return FieldReadiness(
        name="operator_accept", status="default",
        source="default 0.5 — no static evidence",
        confidence=0.0, blocks_official_fusion=False,
    )


def _audit_grounding(scenario: NormalizedScenario) -> FieldReadiness:
    if not scenario.events:
        return FieldReadiness(
            name="grounding", status="missing", source="no events",
            confidence=0.0, blocks_official_fusion=False,
        )
    total_pre = sum(len(ev.preconditions) for ev in scenario.events)
    if total_pre == 0:
        return FieldReadiness(
            name="grounding", status="missing",
            source="no preconditions",
            confidence=0.0, blocks_official_fusion=False,
        )
    verified = sum(
        1
        for ev in scenario.events
        for p in ev.preconditions
        if p.verified
    )
    fraction = verified / total_pre
    return FieldReadiness(
        name="grounding",
        status="real" if fraction > 0.0 else "default",
        source=f"per-obligation ADR-20 children ({verified}/{total_pre} verified)",
        confidence=min(0.6, 0.2 + fraction * 0.6),
        blocks_official_fusion=False,
    )


def _audit_preconditions(scenario: NormalizedScenario) -> FieldReadiness:
    if not scenario.events:
        return FieldReadiness(
            name="preconditions", status="missing", source="no events",
            confidence=0.0, blocks_official_fusion=False,
        )
    total = sum(len(ev.preconditions) for ev in scenario.events)
    multi = sum(
        1 for ev in scenario.events if len(ev.preconditions) > 1
    )
    if total == 0:
        return FieldReadiness(
            name="preconditions", status="missing",
            source="no preconditions emitted",
            confidence=0.0, blocks_official_fusion=False,
        )
    return FieldReadiness(
        name="preconditions",
        status="real" if multi > 0 else "heuristic",
        source=f"ADR-20 1..N expansion ({multi}/{len(scenario.events)} events with N>1)",
        confidence=0.6 if multi > 0 else 0.3,
        blocks_official_fusion=False,
    )


def _audit_constitutive_edges(scenario: NormalizedScenario) -> FieldReadiness:
    total = sum(len(ev.constitutive_parents) for ev in scenario.events)
    return FieldReadiness(
        name="constitutive_edges",
        status="real" if total > 0 else "missing",
        source=f"ADR-21 same-symbol rule ({total} edges)",
        confidence=0.6 if total > 0 else 0.0,
        blocks_official_fusion=False,
    )


def _audit_supportive_edges(scenario: NormalizedScenario) -> FieldReadiness:
    total = sum(len(ev.supportive_parents) for ev in scenario.events)
    return FieldReadiness(
        name="supportive_edges",
        status="real" if total > 0 else "missing",
        source=f"ADR-21 imports/tests/migration ({total} edges)",
        confidence=0.6 if total > 0 else 0.0,
        blocks_official_fusion=False,
    )


def _audit_trajectory_metrics(
    trajectory_metrics: TrajectoryMetrics | None,
) -> FieldReadiness:
    if trajectory_metrics is None:
        return FieldReadiness(
            name="trajectory_metrics",
            status="missing",
            source="no TrajectoryMetrics provided",
            confidence=0.0,
            blocks_official_fusion=False,
        )
    if trajectory_metrics.total_steps == 0:
        return FieldReadiness(
            name="trajectory_metrics",
            status="missing",
            source="empty trace",
            confidence=0.0,
            blocks_official_fusion=False,
        )
    return FieldReadiness(
        name="trajectory_metrics",
        status="real",
        source=f"paper-adapted scorer ({trajectory_metrics.total_steps} steps)",
        confidence=0.7,
        blocks_official_fusion=False,
    )


def _audit_repair_signal(scenario: NormalizedScenario) -> FieldReadiness:
    has_constitutive = any(ev.constitutive_parents for ev in scenario.events)
    has_supportive = any(ev.supportive_parents for ev in scenario.events)
    if not (has_constitutive or has_supportive):
        return FieldReadiness(
            name="repair_signal", status="missing",
            source="no edges; double_loop_repair degenerates",
            confidence=0.0, blocks_official_fusion=False,
        )
    return FieldReadiness(
        name="repair_signal",
        status="real",
        source="double_loop_repair-ready (Block-C edges)",
        confidence=0.6 if has_constitutive else 0.4,
        blocks_official_fusion=False,
    )


# ---------------------------------------------------------------------------
# Public assessment
# ---------------------------------------------------------------------------


def assess_fusion_readiness(
    scenario: NormalizedScenario,
    *,
    tool_evidence: list[ToolEvidence] | None = None,
    trajectory_metrics: TrajectoryMetrics | None = None,
) -> FusionReadinessReport:
    """Audit ``scenario`` against the 12 fields ADR-22 lists.

    Returns a :class:`FusionReadinessReport` with a status verdict and
    a list of human-readable blockers. NEVER computes V_net.
    """
    fields: list[FieldReadiness] = [
        _audit_capability(scenario),
        _audit_benefit(scenario),
        _audit_observability(scenario),
        _audit_completion(scenario, tool_evidence),
        _audit_tests_pass(scenario, tool_evidence),
        _audit_operator_accept(scenario, tool_evidence),
        _audit_grounding(scenario),
        _audit_preconditions(scenario),
        _audit_constitutive_edges(scenario),
        _audit_supportive_edges(scenario),
        _audit_trajectory_metrics(trajectory_metrics),
        _audit_repair_signal(scenario),
    ]

    blockers = [
        f"{f.name}: {f.status} ({f.source})"
        for f in fields
        if f.blocks_official_fusion
    ]
    graph_ready = any(
        f.name == "constitutive_edges" and f.status == "real" for f in fields
    ) or any(
        f.name == "supportive_edges" and f.status == "real" for f in fields
    )
    trajectory_ready = any(
        f.name == "trajectory_metrics" and f.status == "real" for f in fields
    )
    evidence_ready = all(
        f.status in ("real", "heuristic")
        for f in fields
        if f.name in ("completion", "tests_pass", "operator_accept", "grounding")
    )

    # Verdict ladder.
    if blockers:
        status: FusionStatus = "blocked"
        recommendation = (
            "Phase-4 LLM intent estimator must replace capability/benefit/"
            "observability defaults before official V_net is safe to emit. "
            "Until then: diagnostic + repair only."
        )
    else:
        # No blockers: ladder by quality of supporting signals.
        if graph_ready and trajectory_ready and evidence_ready:
            status = "official_ready"
            recommendation = "All load-bearing fields validated. Official fusion may be emitted."
        elif graph_ready or trajectory_ready or evidence_ready:
            status = "shadow_ready"
            recommendation = (
                "No blockers, but partial signal; emit shadow fusion clearly "
                "marked non-authoritative."
            )
        else:
            status = "diagnostic_only"
            recommendation = "Diagnostics safe; shadow fusion not warranted."

    return FusionReadinessReport(
        status=status,
        blockers=blockers,
        field_readiness=fields,
        graph_ready=graph_ready,
        trajectory_ready=trajectory_ready,
        evidence_ready=evidence_ready,
        recommendation=recommendation,
    )


__all__ = [
    "FieldReadiness",
    "FieldStatus",
    "FusionReadinessReport",
    "FusionStatus",
    "assess_fusion_readiness",
]

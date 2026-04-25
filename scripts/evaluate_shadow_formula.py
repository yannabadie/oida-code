"""E2 (QA/A13.md, ADR-23) — shadow-formula sensitivity sweep + graph ablation.

Runs three structural experiments and emits machine-readable JSON +
markdown tables to ``.oida/e2/``:

1. **Sensitivity sweep** — varies one input at a time across
   ``[0.0, 0.25, 0.5, 0.75, 1.0]`` and records ``base_pressure``
   (or ``shadow_debt_pressure`` for ``edge_confidence``).
2. **Graph ablation** — runs the formula on 7 graph topologies
   (local_only / constitutive_only / supportive_only / mixed_graph /
   cycle_graph / dense_supportive_star / long_supportive_chain) and
   records iteration count, convergence, and channel-separation
   invariants.
3. **Variant comparison** — V1 (current E1.1) vs V2
   (dynamic-renormalized) vs V3 (conservative-missing). The script
   computes V1 directly from the production code; V2 and V3 are
   computed analytically because they are NOT implemented in
   production (ADR-23 keeps V1).

Honesty: this script emits NO official ``V_net`` / ``debt_final`` /
``corrupt_success`` numbers. It does NOT predict outcomes. The
output is purely structural and feeds
``reports/e2_shadow_formula_decision.md``.

Usage:

    python scripts/evaluate_shadow_formula.py
    python scripts/evaluate_shadow_formula.py --out .oida/e2
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oida_code.models.normalized_event import (
    NormalizedEvent,
    NormalizedScenario,
    PreconditionSpec,
)
from oida_code.models.trajectory import TrajectoryMetrics
from oida_code.score.experimental_shadow_fusion import (
    _ALPHA_CONSTITUTIVE,
    _DEFAULT_EDGE_CONFIDENCE,
    _W_COMPLETION,
    _W_GROUNDING,
    _W_STATIC,
    _W_TRAJECTORY,
    compute_experimental_shadow_fusion,
)
from oida_code.score.fusion_readiness import assess_fusion_readiness

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


SWEEP_GRID: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)


def _make_event(
    *,
    idx: int = 1,
    completion: float = 0.5,
    operator_accept: float = 0.5,
    preconditions: list[PreconditionSpec] | None = None,
    constitutive_parents: list[str] | None = None,
    supportive_parents: list[str] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        id=f"e{idx}",
        pattern_id=f"p_precondition_x_{idx}",
        task=f"task {idx}",
        capability=0.5,
        reversibility=0.5,
        observability=0.5,
        blast_radius=0.3,
        completion=completion,
        tests_pass=0.5,
        operator_accept=operator_accept,
        benefit=0.5,
        preconditions=preconditions or [],
        constitutive_parents=constitutive_parents or [],
        supportive_parents=supportive_parents or [],
        invalidates_pattern=False,
    )


def _scenario(events: list[NormalizedEvent]) -> NormalizedScenario:
    return NormalizedScenario(name="t", description="", events=events)


def _trajectory(error: float, total_steps: int = 10) -> TrajectoryMetrics:
    return TrajectoryMetrics(
        exploration_error=error,
        exploitation_error=error,
        stale_score=0,
        no_progress_rate=error,
        total_steps=total_steps,
        progress_events_count=max(0, total_steps - round(error * total_steps)),
        exploration_steps=total_steps // 2,
        exploitation_steps=total_steps - total_steps // 2,
    )


def _partial(n: int, verified_count: int) -> list[PreconditionSpec]:
    return [
        PreconditionSpec(name=f"p{i}", weight=1.0, verified=(i < verified_count))
        for i in range(n)
    ]


def _run(
    scenario: NormalizedScenario,
    *,
    trajectory: TrajectoryMetrics | None = None,
    edge_confidences: dict[tuple[str, str, str], float] | None = None,
) -> dict[str, Any]:
    readiness = assess_fusion_readiness(scenario)
    shadow = compute_experimental_shadow_fusion(
        scenario,
        readiness,
        trajectory_metrics=trajectory,
        edge_confidences=edge_confidences,
    )
    return shadow.model_dump()


# ---------------------------------------------------------------------------
# Sensitivity sweeps
# ---------------------------------------------------------------------------


@dataclass
class SweepRow:
    input: str
    value: float
    metric: str
    measured: float
    expected: float
    delta: float


def sweep_grounding() -> list[SweepRow]:
    """Vary verified-fraction over 4 preconditions; expected
    base_pressure = 0.40*(1-g) + 0.20*0.5 + 0.0 + 0.15*0.5 = 0.40*(1-g) + 0.175."""
    out: list[SweepRow] = []
    for v in (0, 1, 2, 3, 4):
        scen = _scenario([
            _make_event(
                idx=1, completion=0.5, operator_accept=0.5,
                preconditions=_partial(4, v),
            )
        ])
        score = _run(scen)["event_scores"][0]["base_pressure"]
        g = v / 4.0
        expected = (
            _W_GROUNDING * (1.0 - g)
            + _W_STATIC * 0.5
            + _W_TRAJECTORY * 0.0
            + _W_COMPLETION * 0.5
        )
        out.append(SweepRow(
            input="grounding",
            value=g,
            metric="base_pressure",
            measured=round(score, 6),
            expected=round(expected, 6),
            delta=round(score - expected, 6),
        ))
    return out


def sweep_completion() -> list[SweepRow]:
    """Expected = 0.40*(1-0.5) + 0.20*0.5 + 0.0 + 0.15*(1-c) = 0.30 + 0.15*(1-c)."""
    out: list[SweepRow] = []
    for c in SWEEP_GRID:
        scen = _scenario([
            _make_event(
                idx=1, completion=c, operator_accept=0.5,
                preconditions=_partial(2, 1),
            )
        ])
        score = _run(scen)["event_scores"][0]["base_pressure"]
        expected = (
            _W_GROUNDING * 0.5
            + _W_STATIC * 0.5
            + _W_TRAJECTORY * 0.0
            + _W_COMPLETION * (1.0 - c)
        )
        out.append(SweepRow(
            input="completion",
            value=c,
            metric="base_pressure",
            measured=round(score, 6),
            expected=round(expected, 6),
            delta=round(score - expected, 6),
        ))
    return out


def sweep_operator_accept() -> list[SweepRow]:
    out: list[SweepRow] = []
    for op in SWEEP_GRID:
        scen = _scenario([
            _make_event(
                idx=1, completion=0.5, operator_accept=op,
                preconditions=_partial(2, 1),
            )
        ])
        score = _run(scen)["event_scores"][0]["base_pressure"]
        expected = (
            _W_GROUNDING * 0.5
            + _W_STATIC * (1.0 - op)
            + _W_TRAJECTORY * 0.0
            + _W_COMPLETION * 0.5
        )
        out.append(SweepRow(
            input="operator_accept",
            value=op,
            metric="base_pressure",
            measured=round(score, 6),
            expected=round(expected, 6),
            delta=round(score - expected, 6),
        ))
    return out


def sweep_trajectory_pressure() -> list[SweepRow]:
    out: list[SweepRow] = []
    for t in SWEEP_GRID:
        scen = _scenario([
            _make_event(
                idx=1, completion=0.5, operator_accept=0.5,
                preconditions=_partial(2, 1),
            )
        ])
        traj = _trajectory(t)
        score = _run(scen, trajectory=traj)["event_scores"][0]["base_pressure"]
        expected = (
            _W_GROUNDING * 0.5
            + _W_STATIC * 0.5
            + _W_TRAJECTORY * t
            + _W_COMPLETION * 0.5
        )
        out.append(SweepRow(
            input="trajectory_pressure",
            value=t,
            metric="base_pressure",
            measured=round(score, 6),
            expected=round(expected, 6),
            delta=round(score - expected, 6),
        ))
    return out


def sweep_edge_confidence() -> list[SweepRow]:
    """2-event constitutive edge: parent fully unverified (high
    pressure), child fully verified (low base). Expected child debt =
    max(child_base, parent_p * conf * alpha_constitutive).

    Default behaviour (no override) is reported as ``conf=0.6``."""
    parent = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_partial(1, 0),
    )
    child = _make_event(
        idx=2, completion=1.0, operator_accept=1.0,
        preconditions=_partial(1, 1),
        constitutive_parents=[parent.id],
    )
    scen = _scenario([parent, child])
    out: list[SweepRow] = []
    for conf in (0.0, 0.2, 0.4, _DEFAULT_EDGE_CONFIDENCE, 0.8, 1.0):
        edge_confs = {
            (parent.id, child.id, "constitutive"): conf,
        }
        result = _run(scen, edge_confidences=edge_confs)
        parent_p = result["event_scores"][0]["base_pressure"]
        child_base = result["event_scores"][1]["base_pressure"]
        child_debt = result["event_scores"][1]["shadow_debt_pressure"]
        expected = max(child_base, parent_p * conf * _ALPHA_CONSTITUTIVE)
        out.append(SweepRow(
            input="edge_confidence",
            value=conf,
            metric="shadow_debt_pressure",
            measured=round(child_debt, 6),
            expected=round(expected, 6),
            delta=round(child_debt - expected, 6),
        ))
    return out


# ---------------------------------------------------------------------------
# Graph ablation
# ---------------------------------------------------------------------------


@dataclass
class AblationRow:
    topology: str
    n_events: int
    n_constitutive_edges: int
    n_supportive_edges: int
    iterations: int
    converged: bool
    max_debt_pressure: float
    max_integrity_pressure: float
    debt_above_base_count: int
    integrity_above_base_count: int
    invariant_supportive_isolates_debt: bool
    notes: str


def _ablate(name: str, events: list[NormalizedEvent], notes: str) -> AblationRow:
    scen = _scenario(events)
    payload = _run(scen)
    base_by_id = {s["event_id"]: s["base_pressure"] for s in payload["event_scores"]}
    debt_by_id = {s["event_id"]: s["shadow_debt_pressure"] for s in payload["event_scores"]}
    int_by_id = {s["event_id"]: s["shadow_integrity_pressure"] for s in payload["event_scores"]}
    cons_count = sum(len(ev.constitutive_parents) for ev in events)
    sup_count = sum(len(ev.supportive_parents) for ev in events)
    # Channel-separation invariant: for events whose ONLY parents are
    # supportive, debt MUST equal base (no constitutive contribution).
    only_sup_violations = 0
    for ev in events:
        if (
            ev.supportive_parents
            and not ev.constitutive_parents
            and abs(debt_by_id[ev.id] - base_by_id[ev.id]) > 1e-9
        ):
            only_sup_violations += 1
    return AblationRow(
        topology=name,
        n_events=len(events),
        n_constitutive_edges=cons_count,
        n_supportive_edges=sup_count,
        iterations=payload["graph_summary"]["propagation_iterations"],
        converged=payload["graph_summary"]["propagation_converged"],
        max_debt_pressure=round(max(debt_by_id.values()), 6),
        max_integrity_pressure=round(max(int_by_id.values()), 6),
        debt_above_base_count=sum(
            1 for ev in events
            if debt_by_id[ev.id] > base_by_id[ev.id] + 1e-9
        ),
        integrity_above_base_count=sum(
            1 for ev in events
            if int_by_id[ev.id] > base_by_id[ev.id] + 1e-9
        ),
        invariant_supportive_isolates_debt=(only_sup_violations == 0),
        notes=notes,
    )


def ablate_local_only() -> AblationRow:
    events = [_make_event(idx=i) for i in range(1, 4)]
    return _ablate(
        "local_only",
        events,
        "no edges; debt and integrity collapse to base; warning emitted",
    )


def ablate_constitutive_only() -> AblationRow:
    a = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_partial(1, 0),
    )
    b = _make_event(idx=2, completion=0.95, preconditions=_partial(1, 1),
                    constitutive_parents=[a.id])
    c = _make_event(idx=3, completion=0.95, preconditions=_partial(1, 1),
                    constitutive_parents=[b.id])
    return _ablate(
        "constitutive_only",
        [a, b, c],
        "linear constitutive chain; debt propagates with attenuation",
    )


def ablate_supportive_only() -> AblationRow:
    a = _make_event(
        idx=1, completion=0.0, operator_accept=0.0,
        preconditions=_partial(1, 0),
    )
    b = _make_event(idx=2, completion=0.95, preconditions=_partial(1, 1),
                    supportive_parents=[a.id])
    c = _make_event(idx=3, completion=0.95, preconditions=_partial(1, 1),
                    supportive_parents=[b.id])
    return _ablate(
        "supportive_only",
        [a, b, c],
        "linear supportive chain; integrity raised, debt unchanged",
    )


def ablate_mixed_graph() -> AblationRow:
    cons = _make_event(idx=1, completion=0.0, operator_accept=0.0,
                       preconditions=_partial(1, 0))
    sup = _make_event(idx=2, completion=0.0, operator_accept=0.0,
                      preconditions=_partial(1, 0))
    child = _make_event(idx=3, completion=0.95, preconditions=_partial(1, 1),
                        constitutive_parents=[cons.id],
                        supportive_parents=[sup.id])
    return _ablate(
        "mixed_graph",
        [cons, sup, child],
        "child has both kinds of parent; channels remain separate",
    )


def ablate_cycle_graph() -> AblationRow:
    a = _make_event(idx=1, completion=0.0, constitutive_parents=["e3"])
    b = _make_event(idx=2, completion=0.0, constitutive_parents=["e1"])
    c = _make_event(idx=3, completion=0.0, constitutive_parents=["e2"])
    return _ablate(
        "cycle_graph",
        [a, b, c],
        "3-event constitutive cycle; max() is idempotent → bounded",
    )


def ablate_dense_supportive_star() -> AblationRow:
    parents = [
        _make_event(idx=i + 1, completion=0.0, operator_accept=0.0,
                    preconditions=_partial(1, 0))
        for i in range(10)
    ]
    child = _make_event(
        idx=99, completion=0.5, operator_accept=0.5,
        preconditions=_partial(2, 1),
        supportive_parents=[p.id for p in parents],
    )
    return _ablate(
        "dense_supportive_star",
        [*parents, child],
        "10 supportive parents → 1 child; integrity bounded by max parent",
    )


def ablate_long_supportive_chain() -> AblationRow:
    chain: list[NormalizedEvent] = []
    for i in range(6):
        if i == 0:
            ev = _make_event(idx=i + 1, completion=0.0, operator_accept=0.0,
                             preconditions=_partial(1, 0))
        else:
            ev = _make_event(
                idx=i + 1, completion=0.95, operator_accept=0.95,
                preconditions=_partial(1, 1),
                supportive_parents=[chain[i - 1].id],
            )
        chain.append(ev)
    return _ablate(
        "long_supportive_chain",
        chain,
        "6-link supportive chain; integrity attenuates with depth",
    )


# ---------------------------------------------------------------------------
# Variant comparison (V1 vs V2 vs V3)
# ---------------------------------------------------------------------------


@dataclass
class VariantRow:
    case: str
    v1_pressure: float
    v2_pressure: float
    v3_pressure: float
    v1_warning: bool
    notes: str


def _v1_base_pressure(
    *, grounding_pressure: float, static_p: float,
    traj: float, completion: float,
) -> float:
    """Replicates the V1 (current E1.1) formula on raw inputs — no
    rescaling. Missing grounding is delivered as ``0.5`` upstream."""
    return (
        _W_GROUNDING * grounding_pressure
        + _W_STATIC * static_p
        + _W_TRAJECTORY * traj
        + _W_COMPLETION * (1.0 - completion)
    )


def _v2_renormalized_base_pressure(
    *, grounding_pressure: float | None, static_p: float | None,
    traj: float | None, completion: float | None,
) -> float:
    """V2 — exclude missing components and renormalize remaining
    weights so they sum to 1.0. ``None`` means missing."""
    pairs = [
        (_W_GROUNDING, grounding_pressure),
        (_W_STATIC, static_p),
        (_W_TRAJECTORY, traj),
        (_W_COMPLETION, None if completion is None else (1.0 - completion)),
    ]
    active = [(w, v) for w, v in pairs if v is not None]
    total_w = sum(w for w, _ in active)
    if total_w == 0:
        return 0.0
    return sum(w * v for w, v in active) / total_w


def _v3_conservative_missing_base_pressure(
    *, grounding_present: bool, grounding_pressure: float,
    static_p: float, traj: float, completion: float,
) -> float:
    """V3 — like V1 but adds a missing-grounding penalty: if the
    precondition model is missing the formula treats the grounding
    component as 0.5 (neutral), same as V1, BUT outputs a flag that
    downstream classifies the report as ``low_confidence``. Numerically
    identical to V1 here; the difference is reporting status."""
    return _v1_base_pressure(
        grounding_pressure=0.5 if not grounding_present else grounding_pressure,
        static_p=static_p,
        traj=traj,
        completion=completion,
    )


def variant_comparison() -> list[VariantRow]:
    """Compare three variants on four illustrative cases."""
    rows: list[VariantRow] = []

    # Case A: missing grounding model.
    rows.append(VariantRow(
        case="missing_grounding (no preconditions)",
        v1_pressure=round(
            _v1_base_pressure(grounding_pressure=0.5, static_p=0.5, traj=0.0, completion=0.5),
            6,
        ),
        v2_pressure=round(
            _v2_renormalized_base_pressure(
                grounding_pressure=None, static_p=0.5, traj=0.0, completion=0.5,
            ),
            6,
        ),
        v3_pressure=round(
            _v3_conservative_missing_base_pressure(
                grounding_present=False, grounding_pressure=0.0,
                static_p=0.5, traj=0.0, completion=0.5,
            ),
            6,
        ),
        v1_warning=True,
        notes="V1 = neutral 0.5 + warning; V2 renormalizes; V3 = V1 + downgraded confidence",
    ))

    # Case B: real-zero grounding (model present, all unverified).
    rows.append(VariantRow(
        case="real_zero_grounding",
        v1_pressure=round(
            _v1_base_pressure(grounding_pressure=1.0, static_p=0.5, traj=0.0, completion=0.5),
            6,
        ),
        v2_pressure=round(
            _v2_renormalized_base_pressure(
                grounding_pressure=1.0, static_p=0.5, traj=0.0, completion=0.5,
            ),
            6,
        ),
        v3_pressure=round(
            _v3_conservative_missing_base_pressure(
                grounding_present=True, grounding_pressure=1.0,
                static_p=0.5, traj=0.0, completion=0.5,
            ),
            6,
        ),
        v1_warning=False,
        notes="all variants agree: full grounding term contributes 0.40",
    ))

    # Case C: all components present, partial grounding.
    rows.append(VariantRow(
        case="partial_grounding_g=0.5",
        v1_pressure=round(
            _v1_base_pressure(grounding_pressure=0.5, static_p=0.5, traj=0.5, completion=0.5),
            6,
        ),
        v2_pressure=round(
            _v2_renormalized_base_pressure(
                grounding_pressure=0.5, static_p=0.5, traj=0.5, completion=0.5,
            ),
            6,
        ),
        v3_pressure=round(
            _v3_conservative_missing_base_pressure(
                grounding_present=True, grounding_pressure=0.5,
                static_p=0.5, traj=0.5, completion=0.5,
            ),
            6,
        ),
        v1_warning=False,
        notes="all variants agree when nothing is missing",
    ))

    # Case D: missing trajectory (no metrics passed) + present grounding.
    rows.append(VariantRow(
        case="missing_trajectory_metrics",
        v1_pressure=round(
            _v1_base_pressure(grounding_pressure=0.5, static_p=0.5, traj=0.0, completion=0.5),
            6,
        ),
        v2_pressure=round(
            _v2_renormalized_base_pressure(
                grounding_pressure=0.5, static_p=0.5, traj=None, completion=0.5,
            ),
            6,
        ),
        v3_pressure=round(
            _v3_conservative_missing_base_pressure(
                grounding_present=True, grounding_pressure=0.5,
                static_p=0.5, traj=0.0, completion=0.5,
            ),
            6,
        ),
        v1_warning=False,
        notes="V1/V3 treat missing trajectory as 0; V2 renormalizes weights",
    ))
    return rows


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def _sweep_to_table(rows: list[SweepRow]) -> str:
    return _md_table(
        ["input", "value", "metric", "measured", "expected", "delta"],
        [[r.input, r.value, r.metric, r.measured, r.expected, r.delta] for r in rows],
    )


def _ablation_to_table(rows: list[AblationRow]) -> str:
    return _md_table(
        [
            "topology", "n_events", "cons_edges", "sup_edges",
            "iter", "converged", "max_debt", "max_integrity",
            "debt>base", "int>base", "sup_isolates_debt",
        ],
        [
            [
                r.topology, r.n_events, r.n_constitutive_edges,
                r.n_supportive_edges, r.iterations, r.converged,
                r.max_debt_pressure, r.max_integrity_pressure,
                r.debt_above_base_count, r.integrity_above_base_count,
                r.invariant_supportive_isolates_debt,
            ]
            for r in rows
        ],
    )


def _variant_to_table(rows: list[VariantRow]) -> str:
    return _md_table(
        ["case", "V1 (E1.1)", "V2 (renormalized)", "V3 (conservative)", "warning?", "notes"],
        [
            [r.case, r.v1_pressure, r.v2_pressure, r.v3_pressure, r.v1_warning, r.notes]
            for r in rows
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=".oida/e2",
        help="output directory for sensitivity.json / ablation.json / sensitivity.md",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sweep_rows = (
        sweep_grounding()
        + sweep_completion()
        + sweep_operator_accept()
        + sweep_trajectory_pressure()
        + sweep_edge_confidence()
    )
    ablation_rows = [
        ablate_local_only(),
        ablate_constitutive_only(),
        ablate_supportive_only(),
        ablate_mixed_graph(),
        ablate_cycle_graph(),
        ablate_dense_supportive_star(),
        ablate_long_supportive_chain(),
    ]
    variant_rows = variant_comparison()

    sweep_payload = [r.__dict__ for r in sweep_rows]
    ablation_payload = [r.__dict__ for r in ablation_rows]
    variant_payload = [r.__dict__ for r in variant_rows]

    (out_dir / "sensitivity.json").write_text(
        json.dumps(sweep_payload, indent=2), encoding="utf-8",
    )
    (out_dir / "ablation.json").write_text(
        json.dumps(ablation_payload, indent=2), encoding="utf-8",
    )
    (out_dir / "variants.json").write_text(
        json.dumps(variant_payload, indent=2), encoding="utf-8",
    )

    sensitivity_md = "# Sensitivity sweep (E2)\n\n" + _sweep_to_table(sweep_rows) + "\n"
    ablation_md = "# Graph ablation (E2)\n\n" + _ablation_to_table(ablation_rows) + "\n"
    variants_md = "# Variant comparison (E2)\n\n" + _variant_to_table(variant_rows) + "\n"

    (out_dir / "sensitivity.md").write_text(sensitivity_md, encoding="utf-8")
    (out_dir / "ablation.md").write_text(ablation_md, encoding="utf-8")
    (out_dir / "variants.md").write_text(variants_md, encoding="utf-8")

    # Also emit a combined console summary so a CI run sees the result.
    print(sensitivity_md)
    print()
    print(ablation_md)
    print()
    print(variants_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

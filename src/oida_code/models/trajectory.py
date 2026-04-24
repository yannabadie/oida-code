"""Trajectory metrics schema (Phase 3, paper 2604.13151).

Shape of the per-trace output of :mod:`oida_code.score.trajectory`.
Separate from the evidence / obligation models because a trajectory is
about *what the agent did*, not *what the code is*.

Formulas live in ``score/trajectory.py``; this module only owns the
Pydantic wire shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oida_code.models.trace import NoProgressClassification

CaseLabel = Literal["exploration", "exploit_goal", "exploit_other", "either"]
"""Paper Table 1 case attribution for a single timestep.

Maps to the paper's four cases:

* ``exploration``     — Case 1 (U(t) non-empty, P(t) empty)
* ``exploit_goal``    — Case 2 (goal in P(t), |T|=1)
* ``exploit_other``   — Case 3 (P(t) non-empty, goal not in P, U(t) empty)
* ``either``          — Case 4 (P(t) non-empty, goal not in P, U(t) non-empty)
"""


class TimestepCase(BaseModel):
    """Per-timestep case assignment + error flag (debug/audit surface)."""

    model_config = ConfigDict(extra="forbid")

    t: int = Field(ge=0)
    case: CaseLabel
    is_error: bool
    is_progress: bool = False
    stale_score: int = Field(ge=0)
    gain: bool
    target_set_size: int = Field(ge=0)


class TrajectoryMetrics(BaseModel):
    """Scorer output for one :class:`~oida_code.models.trace.Trace`.

    Normalization follows paper §5 "Evaluation":

    * ``exploration_error`` = errors over Cases 1+4 / timesteps in Cases 1+4
    * ``exploitation_error`` = errors over Cases 2+3+4 / timesteps in Cases 2+3+4

    Both are in ``[0, 1]`` by construction (each timestep contributes at
    most 1 to numerator and exactly 1 to its denominator).
    """

    model_config = ConfigDict(extra="forbid")

    exploration_error: float = Field(ge=0.0, le=1.0)
    exploitation_error: float = Field(ge=0.0, le=1.0)
    stale_score: int = Field(ge=0, description="Max S_t across the trajectory.")
    no_progress_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of timesteps that belong to a no-progress segment.",
    )
    total_steps: int = Field(ge=0)
    progress_events_count: int = Field(ge=0)

    # Paper denominators kept visible so downstream readers can reason
    # about confidence (a low error rate on 2 timesteps is not the same
    # signal as on 200).
    exploration_steps: int = Field(ge=0, description="Steps in Cases 1+4.")
    exploitation_steps: int = Field(ge=0, description="Steps in Cases 2+3+4.")

    # Per-segment classification (Phase-2 shape filled in by Phase-3 scorer).
    segment_classifications: list[NoProgressClassification] = Field(
        default_factory=list,
        description="Classification of each NoProgressSegment in trace order.",
    )

    # Full per-timestep trace — useful for debugging / visualizations;
    # callers may skip this via model_dump(exclude={"timesteps"}).
    timesteps: list[TimestepCase] = Field(default_factory=list)


__all__ = [
    "CaseLabel",
    "TimestepCase",
    "TrajectoryMetrics",
]

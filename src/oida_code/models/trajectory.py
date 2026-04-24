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

CaseLabel = Literal[
    "exploration",
    "exploit_goal",
    "exploit_other",
    "either",
    "terminal",
]
"""Paper Table 1 case attribution for a single timestep, extended with a
terminal case for the post-goal tail that the paper does not model.

* ``exploration``     — Case 1 (U(t) non-empty, P(t) empty)
* ``exploit_goal``    — Case 2 (goal in P(t), |T|=1)
* ``exploit_other``   — Case 3 (P(t) non-empty, goal not in P, U(t) empty)
* ``either``          — Case 4 (P(t) non-empty, goal not in P, U(t) non-empty)
* ``terminal``        — ADR-19 A2.2: P(t) = ∅ ∧ U(t) = ∅ ∧ goal closed.
  Paper assumes the episode ends at the goal; real code sessions keep
  running (commit, report, cleanup). Terminal steps are excluded from
  both normalizers; a ``suspicious_tail`` flag on the metrics carries
  the post-terminal-code-edit signal separately.
"""


class TimestepCase(BaseModel):
    """Per-timestep case assignment + error flag (debug/audit surface)."""

    model_config = ConfigDict(extra="forbid")

    t: int = Field(ge=0)
    case: CaseLabel
    is_error: bool
    is_progress: bool = False
    candidate_gain: bool = False
    """ADR-19 A2.1 diagnostic: weaker, SEGMENT-UNBOUNDED signal. True on
    every action that touched a pending-obligation resource or ran a
    test while obligations pending, even if the same action was done
    earlier in the segment. NOT used by err(t); kept for the Phase-4
    verifier to inspect. See :attr:`paper_gain` for the predicate err
    actually uses."""
    paper_gain: bool = False
    """ADR-19 A2.4: the paper's ``Gain(t → t+1)``. Equals True iff the
    action is a progress event OR the **first occurrence in the current
    no-progress segment** of: (a) touching a pending-obligation
    resource, (b) running a relevant test, (c) inspecting a direct
    dependency (Block C). Repeating an action that was already
    paper_gain earlier in the segment is NOT paper_gain again — keeps
    the scorer honest about rerunning the same test 20 times."""
    stale_score: int = Field(ge=0)
    gain: bool
    """Deprecated alias for :attr:`paper_gain`. Same value; kept so
    existing JSON consumers don't break. New code should read
    :attr:`paper_gain`."""
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
    terminal_steps: int = Field(
        default=0,
        ge=0,
        description=(
            "Steps after goal closed AND U empty. "
            "Excluded from both normalizers (ADR-19 A2.2)."
        ),
    )
    suspicious_tail_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Code-editing actions observed in the terminal tail. Non-zero "
            "values mean the agent kept editing after the goal was closed — "
            "a regression-risk signal distinct from exploration/exploitation."
        ),
    )

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

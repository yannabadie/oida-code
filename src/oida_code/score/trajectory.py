"""Explore/Exploit error scorer — paper 2604.13151 §4 + ADR-18 + ADR-19.

This module implements Park et al. 2026 §4 formulas (`c_t`, `e_t`, `n_t`,
`S_t`, `err(t)`, Table 1 case attribution) adapted to code audit traces.

**Structural discipline (ADR-19):**

The scorer is written around three explicit types so the paper's
state-before / action / state-after distinction is impossible to
conflate by accident:

    state_before = TrajectoryState.build(events[:t], changed_files, obligations)
    action       = events[t]
    state_after  = state_before.apply(action, obligations)

The case attribution, target-set size, and progress/gain checks are all
derived from ``state_before``. Only the stale-score update and the
visited/closed deltas use ``state_after``.

**Formulas (paper §4, adapted via ADR-18; bounded `U(t)` per same ADR):**

    c_t = |E_np| - |V_np| + 1            (cyclomatic number of no-progress sub-walk)
    e_t = Σ_e max{m_np(e) - 2, 0}        (edge-reuse penalty, budget = 2)
    n_t = Σ_v max{m_np(v) - 2, 0}        (node-reuse penalty, budget = 2)
    S_t = c_t + e_t + n_t

    err(t) = 0 if t→t+1 is a progress event
           = 1 if Gain(t→t+1) = 0
           = 0 if |T(t)| = 1 and Gain(t→t+1) = 1
           = 1{S_t > S_{t-1}} if |T(t)| > 1 and Gain(t→t+1) = 1

Case attribution (Table 1, attributed to **state_before**):

    Case 1: U ≠ ∅, P = ∅                 → exploration step
    Case 2: goal ∈ P                     → exploitation step
    Case 3: P ≠ ∅, goal ∉ P, U = ∅       → exploitation step
    Case 4: P ≠ ∅, goal ∉ P, U ≠ ∅       → either step
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING

from oida_code.models.trace import (
    NoProgressClassification,
    NoProgressSegment,
    Trace,
    TraceEvent,
)
from oida_code.models.trajectory import CaseLabel, TimestepCase, TrajectoryMetrics

if TYPE_CHECKING:
    from oida_code.models.audit_request import AuditRequest
    from oida_code.models.obligation import Obligation


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


# ---------------------------------------------------------------------------
# TrajectoryState — explicit state-before / state-after discipline (ADR-19)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrajectoryState:
    """State of the audit-surface at a single tick, **before** some action.

    ``TrajectoryState.build(events[:t], ...)`` is the state *before* the
    agent takes action ``events[t]``. Do not pass ``events[:t+1]`` — that
    would be ``state_after``, which is a different object.
    """

    visited: frozenset[str]
    closed: frozenset[str]
    unobserved: frozenset[str]
    pending: frozenset[str]
    goal: str | None

    @staticmethod
    def build(
        prefix: list[TraceEvent],
        changed_files: list[str],
        obligations: list[Obligation],
        *,
        goal: str | None,
    ) -> TrajectoryState:
        visited = _collect_visited(prefix)
        closed = _collect_closed(prefix)
        unobserved = frozenset(_normalize_path(f) for f in changed_files) - visited
        pending = _pending_set(obligations, closed, visited)
        return TrajectoryState(
            visited=visited,
            closed=closed,
            unobserved=unobserved,
            pending=pending,
            goal=goal,
        )


# ---------------------------------------------------------------------------
# State construction primitives — operate on a prefix of events, never events[t]
# ---------------------------------------------------------------------------


def _collect_visited(prefix: list[TraceEvent]) -> frozenset[str]:
    """Paths read / grep'd / globbed up to (but not including) the current action."""
    return frozenset(
        _normalize_path(p)
        for ev in prefix
        if ev.kind in {"read", "grep", "tool_call"}
        for p in ev.scope
    )


def _collect_closed(prefix: list[TraceEvent]) -> frozenset[str]:
    """Obligation IDs closed by any event in the prefix."""
    return frozenset(oid for ev in prefix for oid in ev.closed_obligations)


def _pending_set(
    obligations: list[Obligation],
    closed_ids: frozenset[str],
    visited_paths: frozenset[str],
) -> frozenset[str]:
    """Obligations with status=open ∧ scope visited.

    ADR-18 notes this is a coarse proxy for "prerequisites satisfied"; the
    dependency-graph-aware version lands in Phase 3.5 Block C.
    """
    out: set[str] = set()
    for o in obligations:
        if o.id in closed_ids:
            continue
        if o.status != "open":
            continue
        scope_path = _normalize_path(o.scope.split("::", 1)[0])
        if not scope_path or scope_path in visited_paths:
            out.add(o.id)
    return frozenset(out)


def _pick_goal(obligations: list[Obligation]) -> str | None:
    """``source = "intent"`` wins; else heaviest weight; ties by id."""
    if not obligations:
        return None
    intent = [o for o in obligations if o.source == "intent"]
    if intent:
        return sorted(intent, key=lambda o: o.id)[0].id
    return sorted(obligations, key=lambda o: (-o.weight, o.id))[0].id


# ---------------------------------------------------------------------------
# Case attribution (Table 1) — operates on state_before ONLY
# ---------------------------------------------------------------------------


def classify_case(state_before: TrajectoryState) -> CaseLabel:
    """Paper Table 1 case attribution, on state **before** the action."""
    u_empty = not state_before.unobserved
    p_empty = not state_before.pending
    goal_pending = (
        state_before.goal is not None and state_before.goal in state_before.pending
    )

    if p_empty and not u_empty:
        return "exploration"                       # Case 1
    if goal_pending:
        return "exploit_goal"                      # Case 2
    if not p_empty and not goal_pending and u_empty:
        return "exploit_other"                     # Case 3
    if not p_empty and not goal_pending and not u_empty:
        return "either"                            # Case 4
    # P = ∅ ∧ U = ∅: the trace has nothing left to do. Paper is silent;
    # we classify it as exploit_goal with |T| = 0 so err(t) falls to the
    # Gain = 0 → err = 1 branch whenever a further action is taken.
    return "exploit_goal"


def target_set_size(case: CaseLabel, state_before: TrajectoryState) -> int:
    """|T(t)| from Table 1. Always computed on state_before."""
    if case == "exploration":
        return len(state_before.unobserved)
    if case == "exploit_goal":
        return 1
    if case == "exploit_other":
        return len(state_before.pending)
    # "either" — paper: T = U union {l(u) : u in P}
    return len(state_before.unobserved) + len(state_before.pending)


# ---------------------------------------------------------------------------
# Gain + progress — operate on state_before + action (+ state_after for close)
# ---------------------------------------------------------------------------


def compute_gain(
    state_before: TrajectoryState,
    action: TraceEvent,
    state_after: TrajectoryState,
) -> bool:
    """ADR-18 gain: entered unobserved-changed-file OR closed an obligation.

    Phase 3.5 Block-A contract: narrow set-membership gain. Evidence-based
    richer variants (discovery/evidence/obligation/risk/counterexample) are
    Phase 3.5 Block-B carry-over.
    """
    action_paths = {_normalize_path(p) for p in action.scope}
    if action_paths & state_before.unobserved:
        return True
    newly_closed = state_after.closed - state_before.closed
    return bool(newly_closed)


def is_progress_step(
    state_before: TrajectoryState,
    action: TraceEvent,
    state_after: TrajectoryState,
) -> bool:
    """Paper §4 progress event: entered unobserved cell OR closed a task.

    Progress is computed from the *delta* between state_before and
    state_after, keyed to the bounded-U(t) surface (ADR-18). Re-reading a
    file already in ``state_before.visited`` is not progress even if the
    tool returned fresh text.
    """
    action_paths = {_normalize_path(p) for p in action.scope}
    if action_paths & state_before.unobserved:
        return True
    newly_closed = state_after.closed - state_before.closed
    return bool(newly_closed)


# ---------------------------------------------------------------------------
# Stale-score counters (c_t, e_t, n_t)
# ---------------------------------------------------------------------------


def _stale_counters(
    events: list[TraceEvent], segment_start: int, segment_end: int
) -> tuple[int, int, int]:
    """Compute (c, e, n) for the no-progress window ``events[segment_start:segment_end]``.

    Nodes are ``(kind, scope[0] or '_none')``. The richer
    resource-id-based nodes that treat ``Read foo.py`` and ``Edit foo.py``
    as the same territory are Phase 3.5 Block-A carry-over per author's
    item 7.
    """
    window = events[segment_start : segment_end + 1]
    if len(window) < 2:
        return 0, 0, 0

    def _node(ev: TraceEvent) -> tuple[str, str]:
        primary = _normalize_path(ev.scope[0]) if ev.scope else "_none"
        return ev.kind, primary

    node_visits: Counter[tuple[str, str]] = Counter()
    edge_visits: Counter[tuple[tuple[str, str], tuple[str, str]]] = Counter()
    nodes = [_node(ev) for ev in window]
    for n in nodes:
        node_visits[n] += 1
    for a, b in pairwise(nodes):
        edge_visits[(a, b)] += 1

    e_over = sum(max(m - 2, 0) for m in edge_visits.values())
    n_over = sum(max(m - 2, 0) for m in node_visits.values())
    cyclomatic = len(edge_visits) - len(node_visits) + 1
    cyclomatic = max(cyclomatic, 0)
    return cyclomatic, e_over, n_over


# ---------------------------------------------------------------------------
# Segment classification
# ---------------------------------------------------------------------------


def _classify_segment(
    timesteps: list[TimestepCase], seg: NoProgressSegment
) -> NoProgressClassification:
    window = [
        ts for ts in timesteps if seg.start_t <= ts.t <= seg.end_t and ts.is_error
    ]
    if not window:
        return "stale"
    exploration = sum(1 for ts in window if ts.case in ("exploration", "either"))
    exploitation = sum(
        1 for ts in window if ts.case in ("exploit_goal", "exploit_other", "either")
    )
    if exploration == 0 and exploitation == 0:
        return "stale"
    if exploration >= exploitation:
        return "exploration_error"
    return "exploitation_error"


def _derive_segments(timesteps: list[TimestepCase]) -> list[NoProgressSegment]:
    segments: list[NoProgressSegment] = []
    start: int | None = None
    for ts in timesteps:
        in_np = ts.is_error or ts.stale_score > 0
        if in_np and start is None:
            start = ts.t
        elif not in_np and start is not None:
            segments.append(
                NoProgressSegment(
                    start_t=start,
                    end_t=ts.t - 1,
                    cycle_count=0,
                    edge_reuse=0,
                    node_reuse=0,
                )
            )
            start = None
    if start is not None:
        segments.append(
            NoProgressSegment(
                start_t=start,
                end_t=timesteps[-1].t,
                cycle_count=0,
                edge_reuse=0,
                node_reuse=0,
            )
        )
    return segments


# ---------------------------------------------------------------------------
# Main scoring loop — explicit state_before / action / state_after
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _ScoringLoop:
    """Mutable bookkeeping for the main loop; kept out of module state."""

    events: list[TraceEvent] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    goal: str | None = None
    timesteps: list[TimestepCase] = field(default_factory=list)
    max_stale: int = 0
    prev_stale: int = 0
    last_progress_t: int = -1

    def run(self) -> list[TimestepCase]:
        for t in range(len(self.events)):
            self._score_step(t)
        return self.timesteps

    def _score_step(self, t: int) -> None:
        # --- state_before, action, state_after (ADR-19 discipline) ---
        state_before = TrajectoryState.build(
            self.events[:t],
            self.changed_files,
            self.obligations,
            goal=self.goal,
        )
        action = self.events[t]
        state_after = TrajectoryState.build(
            self.events[: t + 1],
            self.changed_files,
            self.obligations,
            goal=self.goal,
        )

        # --- attribution uses state_before ONLY ---
        case = classify_case(state_before)
        t_size = target_set_size(case, state_before)
        progress = is_progress_step(state_before, action, state_after)

        if progress:
            self._emit_progress(t, case, t_size)
            return

        gain = compute_gain(state_before, action, state_after)
        stale = self._stale_score_at(t)
        self.max_stale = max(self.max_stale, stale)

        if not gain:
            is_error = True
        elif t_size <= 1:
            is_error = False
        else:
            is_error = stale > self.prev_stale

        self.prev_stale = stale

        self.timesteps.append(
            TimestepCase(
                t=t,
                case=case,
                is_error=is_error,
                is_progress=False,
                stale_score=stale,
                gain=gain,
                target_set_size=t_size,
            )
        )

    def _emit_progress(self, t: int, case: CaseLabel, t_size: int) -> None:
        self.last_progress_t = t
        self.prev_stale = 0
        self.timesteps.append(
            TimestepCase(
                t=t,
                case=case,
                is_error=False,
                is_progress=True,
                stale_score=0,
                gain=True,
                target_set_size=t_size,
            )
        )

    def _stale_score_at(self, t: int) -> int:
        c, e_over, n_over = _stale_counters(
            self.events, max(self.last_progress_t + 1, 0), t
        )
        return c + e_over + n_over


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def score_trajectory(
    trace: Trace,
    obligations: list[Obligation] | None = None,
    request: AuditRequest | None = None,
) -> TrajectoryMetrics:
    """Score a trace end-to-end and produce :class:`TrajectoryMetrics`.

    Deterministic, pure, no I/O. A zero-event trace returns a zeroed
    metrics object.
    """
    obligations = list(obligations or [])
    events = list(trace.events)

    if not events:
        return TrajectoryMetrics(
            exploration_error=0.0,
            exploitation_error=0.0,
            stale_score=0,
            no_progress_rate=0.0,
            total_steps=0,
            progress_events_count=0,
            exploration_steps=0,
            exploitation_steps=0,
            segment_classifications=[],
            timesteps=[],
        )

    changed_files = list(request.scope.changed_files) if request else []
    goal = _pick_goal(obligations)

    loop = _ScoringLoop(
        events=events,
        changed_files=changed_files,
        obligations=obligations,
        goal=goal,
    )
    timesteps = loop.run()

    # Normalizers per paper §5 Evaluation.
    exploration_steps = sum(
        1 for ts in timesteps if ts.case in ("exploration", "either")
    )
    exploitation_steps = sum(
        1 for ts in timesteps if ts.case in ("exploit_goal", "exploit_other", "either")
    )
    exploration_errors = sum(
        1 for ts in timesteps if ts.is_error and ts.case in ("exploration", "either")
    )
    exploitation_errors = sum(
        1
        for ts in timesteps
        if ts.is_error
        and ts.case in ("exploit_goal", "exploit_other", "either")
    )

    exploration_error = (
        exploration_errors / exploration_steps if exploration_steps > 0 else 0.0
    )
    exploitation_error = (
        exploitation_errors / exploitation_steps if exploitation_steps > 0 else 0.0
    )

    segments = list(trace.no_progress_segments)
    if not segments:
        segments = _derive_segments(timesteps)

    in_segment = sum(
        1
        for ts in timesteps
        if any(seg.start_t <= ts.t <= seg.end_t for seg in segments)
    )
    no_progress_rate = in_segment / len(timesteps) if timesteps else 0.0

    classifications = [_classify_segment(timesteps, seg) for seg in segments]

    progress_events_count = sum(1 for ts in timesteps if ts.is_progress)

    return TrajectoryMetrics(
        exploration_error=round(exploration_error, 6),
        exploitation_error=round(exploitation_error, 6),
        stale_score=loop.max_stale,
        no_progress_rate=round(no_progress_rate, 6),
        total_steps=len(events),
        progress_events_count=progress_events_count,
        exploration_steps=exploration_steps,
        exploitation_steps=exploitation_steps,
        segment_classifications=classifications,
        timesteps=timesteps,
    )


__all__ = [
    "TrajectoryState",
    "classify_case",
    "compute_gain",
    "is_progress_step",
    "score_trajectory",
    "target_set_size",
]

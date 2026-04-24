"""Explore/Exploit error scorer — paper 2604.13151 §4 + ADR-18.

Inputs:
    * :class:`~oida_code.models.trace.Trace`
    * :class:`~oida_code.models.obligation.Obligation` list (goal + pending set)
    * optional :class:`~oida_code.models.audit_request.AuditRequest` to scope
      U(t) to ``changed_files``

Output:
    :class:`~oida_code.models.trajectory.TrajectoryMetrics`

Formulas (paper §4, adapted via ADR-18):

    c_t = |E_np| - |V_np| + 1            (cyclomatic number of no-progress sub-walk)
    e_t = Σ_e max{m_np(e) - 2, 0}        (edge-reuse penalty, budget 2)
    n_t = Σ_v max{m_np(v) - 2, 0}        (node-reuse penalty, budget 2)
    S_t = c_t + e_t + n_t

    err(t) = 0 if t→t+1 is a progress event
           = 1 if Gain(t→t+1) = 0
           = 0 if |T(t)| = 1 and Gain = 1
           = 1{S_t > S_{t-1}} if |T(t)| > 1 and Gain = 1

Case attribution (Table 1):

    Case 1: U ≠ ∅, P = ∅                 → exploration step
    Case 2: goal ∈ P                     → exploitation step
    Case 3: P ≠ ∅, goal ∉ P, U = ∅       → exploitation step
    Case 4: P ≠ ∅, goal ∉ P, U ≠ ∅       → either step

    exploration_error = errors_in_cases_1_and_4 / steps_in_cases_1_and_4
    exploitation_error = errors_in_cases_2_3_and_4 / steps_in_cases_2_3_and_4

ADR-18 grid→code mapping: U(t) = changed_files unread; P(t) = open
obligations whose scope is visited + deps closed; Gain = set-membership
on unread files OR newly-closed obligations.
"""

from __future__ import annotations

from collections import Counter
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


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _visited_paths_up_to(events: list[TraceEvent], t: int) -> set[str]:
    """Paths read / grep'd / globbed before timestep ``t`` (inclusive)."""
    visited: set[str] = set()
    for ev in events[: t + 1]:
        if ev.kind in {"read", "grep", "tool_call"}:
            for p in ev.scope:
                visited.add(_normalize_path(p))
    return visited


def _closed_obligations_up_to(events: list[TraceEvent], t: int) -> set[str]:
    closed: set[str] = set()
    for ev in events[: t + 1]:
        for oid in ev.closed_obligations:
            closed.add(oid)
    return closed


def _pick_goal(obligations: list[Obligation]) -> str | None:
    """Return the id of the obligation considered the "goal" for attribution.

    ADR-18 policy: ``source = "intent"`` wins; otherwise the heaviest
    weight; ties broken by lexicographic id for determinism.
    """
    if not obligations:
        return None
    intent = [o for o in obligations if o.source == "intent"]
    if intent:
        return sorted(intent, key=lambda o: o.id)[0].id
    return sorted(obligations, key=lambda o: (-o.weight, o.id))[0].id


def _pending_set(
    obligations: list[Obligation],
    closed_ids: set[str],
    visited_paths: set[str],
) -> set[str]:
    """Obligations with status=open ∧ scope visited.

    Phase-3 Phase-1 approximation: we treat ``scope visited`` as a proxy
    for "prerequisites satisfied" — a richer dependency model is the
    Phase-3 carry-over (ADR-15 acknowledges the empty graph for P2).
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
    return out


def _unobserved_changed(changed_files: list[str], visited: set[str]) -> set[str]:
    """``U(t) = changed_files \\ visited`` — the bounded-U(t) of ADR-18."""
    return {_normalize_path(f) for f in changed_files} - visited


def _attribute_case(
    unobserved: set[str], pending: set[str], goal: str | None
) -> CaseLabel:
    u_empty = len(unobserved) == 0
    p_empty = len(pending) == 0
    goal_pending = goal is not None and goal in pending

    # Table 1 branches.
    if p_empty and not u_empty:
        return "exploration"
    if goal_pending:
        return "exploit_goal"
    if not p_empty and not goal_pending and u_empty:
        return "exploit_other"
    if not p_empty and not goal_pending and not u_empty:
        return "either"
    # P = ∅ and U = ∅: the trace is effectively done; treat as exploit_goal
    # (|T| = 0 is a degenerate case the paper doesn't define — we score
    #  it as a pure exploitation step with Gain=0 if nothing closes).
    return "exploit_goal"


def _is_progress(event: TraceEvent) -> bool:
    return bool(event.new_facts or event.closed_obligations)


def _gain(
    prev_unobserved: set[str],
    prev_closed: set[str],
    next_event: TraceEvent,
    new_closed: set[str],
) -> bool:
    """Set-membership Gain (ADR-18): entered U or closed a new obligation."""
    paths = {_normalize_path(p) for p in next_event.scope}
    if paths & prev_unobserved:
        return True
    return bool(new_closed - prev_closed)


def _target_set_size(
    case: CaseLabel, unobserved: set[str], pending: set[str]
) -> int:
    """|T(t)| from Table 1. Used by the stale-score branch of err(t)."""
    if case == "exploration":
        return len(unobserved)
    if case == "exploit_goal":
        return 1
    if case == "exploit_other":
        return len(pending)
    # "either" — paper: T = U union {l(u) : u in P}
    return len(unobserved) + len(pending)


def _stale_counters(
    events: list[TraceEvent], segment_start: int, segment_end: int
) -> tuple[int, int, int]:
    """Compute (c, e, n) for the no-progress window ``events[segment_start:segment_end]``.

    Nodes are ``(kind, scope[0] or '_none')`` per ADR-18.
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


def _classify_segment(
    timesteps: list[TimestepCase], seg: NoProgressSegment
) -> NoProgressClassification:
    """Majority case over the segment's error timesteps.

    Tie-break: exploration beats exploitation (the paper's Figure 1a shows
    exploration error is the stronger predictor of failure).
    """
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


def score_trajectory(
    trace: Trace,
    obligations: list[Obligation] | None = None,
    request: AuditRequest | None = None,
) -> TrajectoryMetrics:
    """Score a trace end-to-end and produce :class:`TrajectoryMetrics`.

    Phase-3 contract: deterministic, no I/O, no external services. A
    zero-event trace returns a zeroed metrics object (not an error) so
    callers can uniformly handle "session had no tool calls".
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

    timesteps: list[TimestepCase] = []
    max_stale = 0
    prev_stale = 0
    # Track the start of the current no-progress window.
    last_progress_t = -1

    for t in range(len(events)):
        visited = _visited_paths_up_to(events, t)
        closed_before = _closed_obligations_up_to(events, max(t - 1, 0))
        closed_now = _closed_obligations_up_to(events, t)
        unobserved = _unobserved_changed(changed_files, visited)
        pending = _pending_set(obligations, closed_now, visited)
        case = _attribute_case(unobserved, pending, goal)
        t_size = _target_set_size(case, unobserved, pending)

        # Progress event — reset stale counters; err(t) is 0 per paper.
        if _is_progress(events[t]):
            last_progress_t = t
            prev_stale = 0
            timesteps.append(
                TimestepCase(
                    t=t,
                    case=case,
                    is_error=False,
                    stale_score=0,
                    gain=True,
                    target_set_size=t_size,
                )
            )
            continue

        # Gain(t-1 → t): we compare to the *prior* unobserved/closed sets.
        if t == 0:
            gain = True  # no prior state to compare; paper undefined, treat as gain
        else:
            prev_visited = _visited_paths_up_to(events, t - 1)
            prev_unobserved = _unobserved_changed(changed_files, prev_visited)
            gain = _gain(prev_unobserved, closed_before, events[t], closed_now)

        # Stale score for the current no-progress window.
        c, e_over, n_over = _stale_counters(
            events, max(last_progress_t + 1, 0), t
        )
        stale = c + e_over + n_over
        max_stale = max(max_stale, stale)

        # err(t) per equation (1).
        if not gain:
            is_error = True
        elif t_size <= 1:
            is_error = False
        else:
            is_error = stale > prev_stale

        prev_stale = stale

        timesteps.append(
            TimestepCase(
                t=t,
                case=case,
                is_error=is_error,
                stale_score=stale,
                gain=gain,
                target_set_size=t_size,
            )
        )

    # Normalization: Cases 1+4 denominator and Cases 2+3+4 denominator.
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

    # no_progress_rate — fraction of timesteps inside a declared segment.
    # Fall back to derived segments if the trace didn't pre-populate them.
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

    progress_events_count = sum(1 for ev in events if _is_progress(ev))

    return TrajectoryMetrics(
        exploration_error=round(exploration_error, 6),
        exploitation_error=round(exploitation_error, 6),
        stale_score=max_stale,
        no_progress_rate=round(no_progress_rate, 6),
        total_steps=len(events),
        progress_events_count=progress_events_count,
        exploration_steps=exploration_steps,
        exploitation_steps=exploitation_steps,
        segment_classifications=classifications,
        timesteps=timesteps,
    )


def _derive_segments(timesteps: list[TimestepCase]) -> list[NoProgressSegment]:
    """Synthesize NoProgressSegments from error timesteps when the trace
    didn't pre-populate ``trace.no_progress_segments``. A segment spans
    every contiguous run of non-progress steps (where is_error = True OR
    stale_score > 0)."""
    segments: list[NoProgressSegment] = []
    start: int | None = None
    for ts in timesteps:
        in_np = ts.is_error or ts.stale_score > 0
        if in_np and start is None:
            start = ts.t
        elif not in_np and start is not None:
            end = ts.t - 1
            segments.append(
                NoProgressSegment(
                    start_t=start,
                    end_t=end,
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


__all__ = ["score_trajectory"]

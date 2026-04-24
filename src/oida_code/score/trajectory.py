"""Explore/Exploit error scorer — paper 2604.13151 §4 + ADR-18 + ADR-19.

Implements Park et al. 2026 §4 formulas (`c_t`, `e_t`, `n_t`, `S_t`,
`err(t)`, Table 1 case attribution) adapted to code audit traces.

**Structural discipline (ADR-19 A/A2):**

Three explicit types carry the state-before / action / state-after
distinction so the paper's semantics cannot be conflated by an index
slip:

    state_before = TrajectoryState.build(events[:t], changed_files, obligations)
    action       = events[t]
    state_after  = state_before.apply(action, obligations)

The case attribution, target-set size, and progress/gain checks are all
derived from ``state_before``. Only the visited/closed deltas use
``state_after``.

**A2.1 split** (2026-04-24 author directive):

* ``progress_event`` — strong signal that resets the no-progress
  segment: newly observed in-surface resource OR newly closed
  obligation.
* ``candidate_gain`` — weaker signal that a step moved *toward* a
  target without yet producing real progress: progress_event OR
  touched-a-pending-obligation-resource OR ran-relevant-test OR
  inspected-direct-dependency. Exposed on ``TimestepCase.candidate_gain``.
* ``err(t)`` is keyed on the narrow ``gain`` (paper-faithful:
  membership in the next target set) not the broader candidate_gain;
  the latter is a diagnostic the Phase-4 verifier will consume.

**A2.2 terminal case** (2026-04-24 author directive):

``P(t) = ∅ ∧ U(t) = ∅ ∧ goal-in-closed`` is an explicit ``terminal``
case. Post-terminal steps do not contribute to exploration or
exploitation denominators; code-editing actions in the terminal tail
count into a separate ``suspicious_tail_count`` diagnostic.

**A2.3 resource_id stale nodes + undirected edges** (2026-04-24):

Stale-graph nodes are the resource identity of the scope (file path or
symbol), not ``(kind, scope)``. ``Read src/a.py``, ``Edit src/a.py``,
``Grep src/a.py`` are the same node. Edges are *unordered* pairs of
resources — a probe-and-return walk (A→B→A) registers 2 traversals of
the single undirected edge {A, B}, not 2 distinct directed edges. This
matches the paper's ``NoProgressSegment._edge_key(a, b) = (min, max)``
semantics and makes D1 tests 1/2/7 pass.
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


_CODE_EDIT_KINDS: frozenset[str] = frozenset({"edit", "write"})
_OBSERVATION_KINDS: frozenset[str] = frozenset({"read", "grep", "tool_call"})
"""ADR-19 A2.5: kinds that actually *observe* a resource.

`read` and `grep` / `glob` (mapped to ``grep`` by our parser) are
unambiguous observations. ``tool_call`` is admitted because the parser
uses it as a fallback for Bash/PowerShell invocations that may be
read-like (``cat``, ``ls``, ``rg``). An edit/write scope-entry does NOT
count — the agent changed the file but has not proven they understood
it. This is the semantic the OIDA author requires in Answer4.md so a
blind edit cannot silently close U(t) without a prior read.
"""


# ---------------------------------------------------------------------------
# Path + resource-id normalization (A2.3)
# ---------------------------------------------------------------------------


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _resource_id(scope_entry: str) -> str:
    """Canonical resource identifier for stale-graph nodes.

    File paths normalize via ``_normalize_path``. Scope entries in
    ``file::symbol`` form keep the symbol so two distinct symbols in the
    same file are still distinct resources — but all Read/Edit/Grep on
    the same symbol share node identity.
    """
    norm = scope_entry.replace("\\", "/").lstrip("./")
    return norm


def _event_resource(ev: TraceEvent) -> str:
    """Primary resource_id for a trace event. Empty scope → ``_none``."""
    if not ev.scope:
        return "_none"
    return _resource_id(ev.scope[0])


# ---------------------------------------------------------------------------
# TrajectoryState — ADR-19 explicit state-before / state-after discipline
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrajectoryState:
    """State of the audit-surface at a single tick, **before** some action.

    ``TrajectoryState.build(events[:t], ...)`` is state *before* the
    agent takes action ``events[t]``. Do not pass ``events[:t+1]``.
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
# State construction primitives
# ---------------------------------------------------------------------------


def _collect_visited(prefix: list[TraceEvent]) -> frozenset[str]:
    return frozenset(
        _normalize_path(p)
        for ev in prefix
        if ev.kind in {"read", "grep", "tool_call"}
        for p in ev.scope
    )


def _collect_closed(prefix: list[TraceEvent]) -> frozenset[str]:
    return frozenset(oid for ev in prefix for oid in ev.closed_obligations)


def _pending_set(
    obligations: list[Obligation],
    closed_ids: frozenset[str],
    visited_paths: frozenset[str],
) -> frozenset[str]:
    """Obligations with status=open ∧ scope visited."""
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
    if not obligations:
        return None
    intent = [o for o in obligations if o.source == "intent"]
    if intent:
        return sorted(intent, key=lambda o: o.id)[0].id
    return sorted(obligations, key=lambda o: (-o.weight, o.id))[0].id


# ---------------------------------------------------------------------------
# Case attribution (Table 1 + terminal) — on state_before ONLY
# ---------------------------------------------------------------------------


def classify_case(state_before: TrajectoryState) -> CaseLabel:
    """Paper Table 1 + ADR-19 A2.2 terminal extension.

    Terminal fires when P=∅, U=∅, AND the goal has been closed. If the
    goal exists but is not yet closed, we still land in the degenerate
    exploit_goal branch (paper's |T|=0 case, rare in practice).
    """
    u_empty = not state_before.unobserved
    p_empty = not state_before.pending
    goal_pending = (
        state_before.goal is not None and state_before.goal in state_before.pending
    )
    goal_closed = (
        state_before.goal is not None and state_before.goal in state_before.closed
    )

    if p_empty and not u_empty:
        return "exploration"                       # Case 1
    if goal_pending:
        return "exploit_goal"                      # Case 2
    if not p_empty and not goal_pending and u_empty:
        return "exploit_other"                     # Case 3
    if not p_empty and not goal_pending and not u_empty:
        return "either"                            # Case 4
    # P = ∅ ∧ U = ∅.
    if goal_closed or state_before.goal is None:
        return "terminal"                          # ADR-19 A2.2
    return "exploit_goal"                          # |T|=0 degenerate


def target_set_size(case: CaseLabel, state_before: TrajectoryState) -> int:
    if case == "exploration":
        return len(state_before.unobserved)
    if case == "exploit_goal":
        return 1
    if case == "exploit_other":
        return len(state_before.pending)
    if case == "either":
        return len(state_before.unobserved) + len(state_before.pending)
    # terminal
    return 0


# ---------------------------------------------------------------------------
# Progress + gain (A2.1 split)
# ---------------------------------------------------------------------------


def is_observation_action(action: TraceEvent) -> bool:
    """ADR-19 A2.5: True iff the action actually observed a resource.

    Observation kinds (``read``, ``grep``, ``tool_call``) are the only
    actions that can move a file *out* of ``U(t)``. Edits and writes
    modify without observing — they count as paper_gain when they
    first-touch a pending obligation, but they do NOT shrink U(t) and
    do NOT fire progress_event on their own.
    """
    return action.kind in _OBSERVATION_KINDS


def is_progress_event(
    state_before: TrajectoryState,
    action: TraceEvent,
    state_after: TrajectoryState,
) -> bool:
    """Paper §4 progress event: entered unobserved cell OR closed a task.

    Resets the no-progress segment. STRICTLY STRONGER than paper Gain —
    progress_event implies paper_gain but not vice versa.

    A2.5 tightening: "entered unobserved" requires the action to be an
    :func:`is_observation_action`. A blind Edit on an unread file is no
    longer considered entering U — the file remains unobserved until a
    Read/Grep/Glob actually inspects it.
    """
    action_paths = {_normalize_path(p) for p in action.scope}
    if is_observation_action(action) and action_paths & state_before.unobserved:
        return True
    newly_closed = state_after.closed - state_before.closed
    return bool(newly_closed)


def _pending_obligation_scopes(
    state_before: TrajectoryState,
    obligations: list[Obligation],
) -> set[str]:
    """Path halves of the scopes of currently-pending obligations."""
    out: set[str] = set()
    for o in obligations:
        if o.id in state_before.pending:
            path_half = _normalize_path(o.scope.split("::", 1)[0])
            if path_half:
                out.add(path_half)
    return out


def compute_paper_gain(
    state_before: TrajectoryState,
    action: TraceEvent,
    state_after: TrajectoryState,
    obligations: list[Obligation],
    segment_events_before: list[TraceEvent],
) -> bool:
    """ADR-19 A2.4: the paper's ``Gain(t → t+1)``, the predicate err(t)
    uses. Broader than ``is_progress_event`` but **bounded per no-
    progress segment**: repeating a helpful move does not re-trigger.

    ``paper_gain = True`` iff any of:

    * ``is_progress_event`` (entered U or closed obligation)
    * action touches a pending-obligation resource AND that resource
      was not already touched earlier in the current no-progress
      segment
    * action is ``kind="test_run"``, obligations are pending, AND no
      test_run occurred earlier in the current segment

    (Direct-dependency inspection — scientist's 4th sub-rule — is
    Block C work, bound on the dependency graph.)

    Keeping paper_gain bounded per segment is the specific correction
    the OIDA author requested in Answer3.md: "sinon un agent peut
    relancer le même test 20 fois sans jamais être pénalisé".
    """
    if is_progress_event(state_before, action, state_after):
        return True

    pending_scopes = _pending_obligation_scopes(state_before, obligations)
    if not pending_scopes:
        return False

    action_paths = {_normalize_path(p) for p in action.scope}
    if not action_paths and action.kind != "test_run":
        return False

    already_touched_in_segment: set[str] = set()
    segment_had_test_run = False
    for ev in segment_events_before:
        for p in ev.scope:
            already_touched_in_segment.add(_normalize_path(p))
        if ev.kind == "test_run":
            segment_had_test_run = True

    # (b) first touch of a pending-obligation resource in this segment.
    first_pending_touches = (action_paths & pending_scopes) - already_touched_in_segment
    if first_pending_touches:
        return True

    # (c) first relevant test_run in this segment.
    return action.kind == "test_run" and not segment_had_test_run


def compute_candidate_gain(
    state_before: TrajectoryState,
    action: TraceEvent,
    state_after: TrajectoryState,
    obligations: list[Obligation],
) -> bool:
    """A2.1 diagnostic (segment-UNBOUNDED). NOT used by err(t).

    Paper_gain is the predicate err uses; candidate_gain is kept as a
    broader diagnostic signal the Phase-4 verifier can consume.
    Candidate fires on every action that could conceivably help —
    repetitions included. The scientist (Answer3.md) explicitly said
    this is fine, as long as candidate is not confused with paper Gain.
    """
    if is_progress_event(state_before, action, state_after):
        return True

    action_paths = {_normalize_path(p) for p in action.scope}
    if not action_paths:
        return False

    pending_scopes = _pending_obligation_scopes(state_before, obligations)
    if action_paths & pending_scopes:
        return True
    return action.kind == "test_run" and bool(pending_scopes)


# ---------------------------------------------------------------------------
# Stale-score counters (A2.3 resource_id nodes + undirected edges)
# ---------------------------------------------------------------------------


def _stale_counters(
    events: list[TraceEvent], segment_start: int, segment_end: int
) -> tuple[int, int, int]:
    """Compute (c_t, e_t, n_t) for ``events[segment_start : segment_end+1]``.

    Nodes = ``_event_resource(ev)`` — same resource_id regardless of
    action kind (A2.3). Edges = unordered pairs of consecutive node
    identities (A2.3). Budgets = 2 per paper.
    """
    window = events[segment_start : segment_end + 1]
    if len(window) < 2:
        return 0, 0, 0

    nodes = [_event_resource(ev) for ev in window]
    node_visits: Counter[str] = Counter()
    edge_visits: Counter[tuple[str, str]] = Counter()
    for n in nodes:
        node_visits[n] += 1
    for a, b in pairwise(nodes):
        lo, hi = (a, b) if a <= b else (b, a)
        edge_visits[(lo, hi)] += 1  # undirected

    e_over = sum(max(m - 2, 0) for m in edge_visits.values())
    n_over = sum(max(m - 2, 0) for m in node_visits.values())
    cyclomatic = len(edge_visits) - len(node_visits) + 1
    cyclomatic = max(cyclomatic, 0)
    return cyclomatic, e_over, n_over


# ---------------------------------------------------------------------------
# Segment classification + derivation
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
# Main scoring loop
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _ScoringLoop:
    events: list[TraceEvent] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    goal: str | None = None
    timesteps: list[TimestepCase] = field(default_factory=list)
    max_stale: int = 0
    prev_stale: int = 0
    last_progress_t: int = -1
    suspicious_tail: int = 0

    def run(self) -> list[TimestepCase]:
        for t in range(len(self.events)):
            self._score_step(t)
        return self.timesteps

    def _score_step(self, t: int) -> None:
        state_before = TrajectoryState.build(
            self.events[:t], self.changed_files, self.obligations, goal=self.goal
        )
        action = self.events[t]
        state_after = TrajectoryState.build(
            self.events[: t + 1], self.changed_files, self.obligations, goal=self.goal
        )

        case = classify_case(state_before)
        t_size = target_set_size(case, state_before)
        progress = is_progress_event(state_before, action, state_after)
        candidate = compute_candidate_gain(
            state_before, action, state_after, self.obligations
        )

        # Terminal case: never flagged as error, tracks suspicious_tail.
        if case == "terminal":
            if action.kind in _CODE_EDIT_KINDS:
                self.suspicious_tail += 1
            self.timesteps.append(
                TimestepCase(
                    t=t,
                    case=case,
                    is_error=False,
                    is_progress=False,
                    candidate_gain=candidate,
                    paper_gain=False,
                    stale_score=0,
                    gain=False,
                    target_set_size=t_size,
                )
            )
            return

        if progress:
            self._emit_progress(t, case, t_size, candidate)
            return

        # A2.4: err(t) uses paper_gain, bounded per no-progress segment.
        segment_start = self.last_progress_t + 1
        segment_events_before = self.events[segment_start:t]
        paper_gain = compute_paper_gain(
            state_before,
            action,
            state_after,
            self.obligations,
            segment_events_before,
        )

        stale = self._stale_score_at(t)
        self.max_stale = max(self.max_stale, stale)

        if not paper_gain:
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
                candidate_gain=candidate,
                paper_gain=paper_gain,
                stale_score=stale,
                gain=paper_gain,  # deprecated alias, same value as paper_gain
                target_set_size=t_size,
            )
        )

    def _emit_progress(
        self, t: int, case: CaseLabel, t_size: int, candidate: bool
    ) -> None:
        self.last_progress_t = t
        self.prev_stale = 0
        self.timesteps.append(
            TimestepCase(
                t=t,
                case=case,
                is_error=False,
                is_progress=True,
                candidate_gain=candidate,
                paper_gain=True,  # progress_event implies paper_gain
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
    """Score a trace end-to-end. Deterministic, pure, no I/O."""
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
            terminal_steps=0,
            suspicious_tail_count=0,
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

    exploration_steps = sum(
        1 for ts in timesteps if ts.case in ("exploration", "either")
    )
    exploitation_steps = sum(
        1 for ts in timesteps if ts.case in ("exploit_goal", "exploit_other", "either")
    )
    terminal_steps = sum(1 for ts in timesteps if ts.case == "terminal")
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
        terminal_steps=terminal_steps,
        suspicious_tail_count=loop.suspicious_tail,
        segment_classifications=classifications,
        timesteps=timesteps,
    )


__all__ = [
    "TrajectoryState",
    "classify_case",
    "compute_candidate_gain",
    "compute_paper_gain",
    "is_observation_action",
    "is_progress_event",
    "score_trajectory",
    "target_set_size",
]

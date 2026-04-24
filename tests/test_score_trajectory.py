"""Tests for :mod:`oida_code.score.trajectory` (Phase 3).

Fixtures in ``tests/fixtures/traces/*.json`` carry a ``label`` field that
is the ground truth the scorer must reproduce for the Phase-3 synthetic
gate. The file-level docstring of each fixture explains the expected
failure mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.obligation import Obligation
from oida_code.models.trace import Trace
from oida_code.score.trajectory import score_trajectory

FIXTURES = Path(__file__).parent / "fixtures" / "traces"


def _load(name: str) -> tuple[Trace, list[Obligation], AuditRequest, str]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    trace = Trace.model_validate(data["trace"])
    obligations = [Obligation.model_validate(o) for o in data["obligations"]]
    request = AuditRequest(
        repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=data["changed_files"]),
    )
    return trace, obligations, request, data["label"]


def test_empty_trace_returns_zeros() -> None:
    metrics = score_trajectory(Trace(events=[]), obligations=[])
    assert metrics.exploration_error == 0.0
    assert metrics.exploitation_error == 0.0
    assert metrics.stale_score == 0
    assert metrics.total_steps == 0


def test_clean_success_has_low_errors() -> None:
    trace, oblig, req, _ = _load("clean_success.json")
    m = score_trajectory(trace, oblig, req)
    # Post ADR-19 state-before-action fix: exploration stays at 0 (every
    # Read targeted a changed file). Exploitation can go up to ~0.6 on
    # this fixture — the two pre-close Edits + the post-close git commit
    # don't themselves close an obligation or enter a new file, so the
    # paper's err-when-Gain=0 branch flags them. That's signal, not a
    # bug: a truly optimal trace would skip the redundant edit/commit.
    assert m.exploration_error <= 0.4, m.exploration_error
    assert m.exploitation_error <= 0.65, m.exploitation_error
    # 3 progress events (read-target, read-tests, close-by-test-run).
    assert m.progress_events_count >= 3


def test_exploration_dominated_fixture_has_high_exploration_error() -> None:
    trace, oblig, req, label = _load("exploration_dominated.json")
    assert label == "exploration_error"
    m = score_trajectory(trace, oblig, req)
    assert m.exploration_error >= 0.5, m.exploration_error
    # Every step is Case 1 or 4, so exploitation_steps should be <= exploration_steps.
    assert m.exploration_steps >= m.exploitation_steps


def test_exploitation_dominated_fixture_has_high_exploitation_error() -> None:
    trace, oblig, req, label = _load("exploitation_dominated.json")
    assert label == "exploitation_error"
    m = score_trajectory(trace, oblig, req)
    # After t=0 reads the file, U is empty and the goal is pending →
    # Case 2 steps. Subsequent edits without closing the obligation
    # have Gain=False ⇒ all errors.
    assert m.exploitation_error >= 0.5, m.exploitation_error


def test_stale_cycling_fixture_raises_stale_score() -> None:
    trace, oblig, req, label = _load("stale_cycling.json")
    assert label == "stale"
    m = score_trajectory(trace, oblig, req)
    # Stale score grows via node + edge reuse beyond budget 2.
    assert m.stale_score >= 1, m.stale_score


def test_mixed_progress_fixture_makes_some_progress() -> None:
    trace, oblig, req, _ = _load("mixed_progress.json")
    m = score_trajectory(trace, oblig, req)
    # One obligation closed → at least one progress event.
    assert m.progress_events_count >= 1
    # Post-progress wandering keeps exploration_error non-trivial.
    assert m.exploration_error > 0.0


@pytest.mark.parametrize(
    "fixture,expected_dominant",
    [
        ("exploration_dominated.json", "exploration"),
        ("exploitation_dominated.json", "exploitation"),
        ("clean_success.json", "neither"),
    ],
)
def test_classification_matches_fixture_label(
    fixture: str, expected_dominant: str
) -> None:
    """Phase-3 exit gate: classification precision ≥ 2/3 on synthetic set.

    Parametrized on the three clearly-labeled fixtures; ``stale_cycling``
    and ``mixed_progress`` are measured by the dedicated tests above.
    """
    trace, oblig, req, _ = _load(fixture)
    m = score_trajectory(trace, oblig, req)
    if expected_dominant == "exploration":
        assert m.exploration_error >= m.exploitation_error
    elif expected_dominant == "exploitation":
        assert m.exploitation_error >= m.exploration_error
    else:
        # "Clean success" produces some exploitation err via the post-close
        # commit step (see test_clean_success_has_low_errors for details).
        assert max(m.exploration_error, m.exploitation_error) <= 0.65


# ---------------------------------------------------------------------------
# ADR-19 — state-before-action + t=0 edge cases + Case reachability proofs
# ---------------------------------------------------------------------------


def test_t0_obligation_close_counts_as_progress() -> None:
    """ADR-19 item 2: a first-action (t=0) obligation close must register
    as a progress event. Before the fix, closed_before for t=0 silently
    included event[0].closed_obligations → progress never fired."""
    trace, oblig, req, _ = _load("t0_obligation_close.json")
    m = score_trajectory(trace, oblig, req)
    assert m.total_steps == 1
    assert m.progress_events_count == 1, (
        "t=0 obligation close must count as progress; got "
        f"{m.progress_events_count}"
    )
    assert m.timesteps[0].is_progress is True


def test_t0_case_attributed_to_empty_state() -> None:
    """ADR-19 item 1: at t=0, state_before.visited must be empty, so a
    trace with at least one file in changed_files must have Case 1
    (exploration) at t=0 when no obligation is pending at start."""
    trace, oblig, req, _ = _load("exploration_dominated.json")
    m = score_trajectory(trace, oblig, req)
    assert m.timesteps[0].case == "exploration", (
        f"t=0 with empty state must be exploration, got {m.timesteps[0].case}"
    )


def test_case_3_is_reachable_on_purpose_built_fixture() -> None:
    """ADR-19 item 5 + author Q1.2: prove Case 3 (exploit_other) can fire
    when U empties while P still has non-goal obligations."""
    trace, oblig, req, _ = _load("case3_exploit_other_reachable.json")
    m = score_trajectory(trace, oblig, req)
    cases = {ts.case for ts in m.timesteps}
    assert "exploit_other" in cases, (
        f"Case 3 not reached on purpose-built fixture; observed {cases}"
    )


def test_state_before_action_state_after_are_distinct() -> None:
    """ADR-19 discipline: TrajectoryState.build(events[:t]) and
    TrajectoryState.build(events[:t+1]) must not share identity and must
    differ for any action that touches scope OR closes an obligation."""
    from oida_code.models.trace import TraceEvent
    from oida_code.score.trajectory import TrajectoryState

    events = [
        TraceEvent(t=0, kind="read", tool="Read", scope=["src/a.py"], intent="read a"),
        TraceEvent(
            t=1,
            kind="edit",
            tool="Edit",
            scope=["src/a.py"],
            closed_obligations=["o-pre-test000001"],
            intent="close",
        ),
    ]
    before_t1 = TrajectoryState.build(events[:1], ["src/a.py"], [], goal=None)
    after_t1 = TrajectoryState.build(events[:2], ["src/a.py"], [], goal=None)
    # `before` has closed = ∅, `after` has closed = {the obligation id}.
    assert before_t1.closed == frozenset()
    assert after_t1.closed == frozenset({"o-pre-test000001"})
    # Unobserved: t=0 read put src/a.py into visited.
    assert before_t1.visited == frozenset({"src/a.py"})
    assert before_t1.unobserved == frozenset()


# ---------------------------------------------------------------------------
# ADR-19 A2 — split gain/progress, terminal case, resource_id nodes
# ---------------------------------------------------------------------------


def test_candidate_gain_can_fire_without_progress_event() -> None:
    """ADR-19 A2.1: prove the paper's 'gain without progress' branch is
    structurally reachable after the split. Pre-A2.1, compute_gain and
    is_progress_event were identical, so this combination was impossible."""
    trace, oblig, req, _ = _load("gain_without_progress.json")
    m = score_trajectory(trace, oblig, req)
    # t=0 is a progress event (entered U with src/a.py).
    # t=1 is a test_run on tests/test_a.py while an obligation is pending
    #    on src/a.py::f → candidate_gain fires (ran relevant test) but
    #    progress_event does NOT (no new path in U, no obligation closed).
    assert m.timesteps[0].is_progress is True
    assert m.timesteps[1].is_progress is False
    assert m.timesteps[1].candidate_gain is True, (
        "A2.1 branch unreachable: candidate_gain should fire on "
        "relevant-test-run step even without closing an obligation"
    )


def test_post_terminal_tail_does_not_inflate_exploitation_error() -> None:
    """ADR-19 A2.2: after goal closed AND U empty, subsequent steps are
    terminal and must not count in either normalizer. Code edits in the
    tail count into a separate suspicious_tail_count diagnostic."""
    trace, oblig, req, _ = _load("post_terminal_tail.json")
    m = score_trajectory(trace, oblig, req)
    # t=0 exploration (entered src/a.py), t=1 exploit_goal progress (close),
    # t=2 commit on visited file with goal closed → terminal
    # t=3 tool_call → terminal
    # t=4 edit → terminal + suspicious_tail
    terminal_events = [ts for ts in m.timesteps if ts.case == "terminal"]
    assert len(terminal_events) >= 2, (
        f"expected ≥ 2 terminal steps, got {len(terminal_events)}"
    )
    # No terminal step should be an error.
    assert all(not ts.is_error for ts in terminal_events)
    # Suspicious tail fires for t=4 edit.
    assert m.suspicious_tail_count >= 1
    # Terminal steps don't land in either denominator.
    assert m.terminal_steps >= 2
    # Exploitation_error normaliser excludes terminal → stays moderate.
    assert m.exploitation_error <= 0.5


def test_same_file_different_tools_share_stale_node() -> None:
    """ADR-19 A2.3: Read / Edit / Grep on src/a.py must share node
    identity so the no-progress graph treats them as the same territory."""
    trace, oblig, req, _ = _load("same_resource_different_tools.json")
    m = score_trajectory(trace, oblig, req)
    # t=0 progress (enters U). t=1-3 all on src/a.py, no obligation
    # closure, no new paths → no_progress segment starts at t=1.
    # Pre-A2.3, node_visits had 3 distinct keys (read, grep, edit all
    # carrying their kind) so n_t never crossed the budget.
    # Post-A2.3, node_visits['src/a.py'] = 3 (grep + edit + re-read),
    # over the budget of 2 → n_t = 1 at the final step.
    assert m.stale_score >= 1, (
        f"A2.3 broken: same-file node_visits should exceed budget, "
        f"got stale_score={m.stale_score}"
    )


# ---------------------------------------------------------------------------
# ADR-19 A2.4 — paper_gain vs progress: err(t) uses paper_gain
# ---------------------------------------------------------------------------


def test_paper_gain_can_fire_without_progress_event_and_no_error() -> None:
    """A2.4: paper_gain=True AND is_progress=False AND stale not rising
    → is_error=False. Proves err(t) uses paper_gain (segment-first
    relevant-test-run) not progress_gain (strict progress)."""
    trace, oblig, req, _ = _load("paper_gain_first_test_run.json")
    m = score_trajectory(trace, oblig, req)
    assert m.timesteps[0].is_progress is True  # t=0 reads src/a.py (in U)
    t1 = m.timesteps[1]
    assert t1.is_progress is False, "t=1 must not be a progress event"
    assert t1.paper_gain is True, (
        "A2.4 broken: first test_run while obligation pending should be "
        "paper_gain=True even without a progress event"
    )
    assert t1.is_error is False, (
        "paper_gain=True and |T|=1 (exploit_goal) must yield is_error=False"
    )


def test_repeated_test_run_eventually_errors() -> None:
    """A2.4 repetition bound: paper_gain is segment-first, not segment-any.
    Rerunning the same test without evidence delta must eventually trip
    err=True. Answer3.md: without this, an agent could rerun a test 20
    times with |T|≤1 and never be penalized."""
    trace, oblig, req, _ = _load("paper_gain_repeated_action.json")
    m = score_trajectory(trace, oblig, req)
    # t=0 progress, t=1 first test_run → paper_gain=True, no err
    assert m.timesteps[1].paper_gain is True
    assert m.timesteps[1].is_error is False
    # t=2 and t=3 repeat the same test_run → paper_gain=False → err=True
    for t in (2, 3):
        ts = m.timesteps[t]
        assert ts.paper_gain is False, (
            f"t={t}: repeated test_run must NOT re-trigger paper_gain; "
            f"got paper_gain={ts.paper_gain}"
        )
        assert ts.is_error is True, (
            f"t={t}: repeated test_run without evidence delta must be "
            f"flagged as error; got is_error={ts.is_error}"
        )
    # candidate_gain stays True on repeats (diagnostic, segment-unbounded).
    assert m.timesteps[2].candidate_gain is True
    assert m.timesteps[3].candidate_gain is True


def test_paper_gain_is_true_whenever_progress_event_is_true() -> None:
    """Structural invariant: progress_event ⊆ paper_gain.

    Every existing fixture where is_progress=True must also have
    paper_gain=True on the same step. Prevents a future refactor from
    accidentally making paper_gain narrower than progress."""
    import json

    fixtures_dir = Path(__file__).parent / "fixtures" / "traces"
    violations: list[tuple[str, int]] = []
    for fixture_path in sorted(fixtures_dir.glob("*.json")):
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        trace = Trace.model_validate(data["trace"])
        obs = [Obligation.model_validate(o) for o in data["obligations"]]
        req = AuditRequest(
            repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
            scope=ScopeSpec(changed_files=data["changed_files"]),
        )
        m = score_trajectory(trace, obs, req)
        for ts in m.timesteps:
            if ts.is_progress and not ts.paper_gain:
                violations.append((fixture_path.name, ts.t))
    assert not violations, (
        f"progress_event must imply paper_gain; violations: {violations}"
    )


# ---------------------------------------------------------------------------
# ADR-19 A2.5 — observation semantics: edit/write cannot close U(t) alone
# ---------------------------------------------------------------------------


def test_blind_edit_does_not_consume_unobserved_surface() -> None:
    """A2.5 — an Edit on an unread file is NOT a progress_event. The
    file remains in U(t) until a Read/Grep observes it.

    Pre-A2.5, the scope-intersects-unobserved check fired progress on
    any action whose scope overlapped U — so a blind edit "consumed"
    the unobserved surface without the agent having actually inspected
    the file."""
    trace, oblig, req, _ = _load("blind_edit_no_read.json")
    m = score_trajectory(trace, oblig, req)
    t0 = m.timesteps[0]
    assert t0.is_progress is False, (
        "A2.5 broken: blind edit on unread file must not be a progress event"
    )
    # paper_gain may still fire (first-touch of pending-obligation
    # resource), but progress must not.


def test_repeated_edit_on_same_changed_file_errors_eventually() -> None:
    """A2.5 regression: first edit of a pending-obligation file after
    read = paper_gain (first-touch in segment). Second identical edit
    without closing anything must NOT re-trigger paper_gain.

    Without this bound, the scorer would happily watch an agent edit
    the same file 20 times as long as an obligation stays pending."""
    trace, oblig, req, _ = _load("repeated_edit_same_file.json")
    m = score_trajectory(trace, oblig, req)
    # t=0 read enters U → progress
    assert m.timesteps[0].is_progress is True
    # t=1 first edit of pending-obligation resource → paper_gain=True,
    # not progress (no close), |T|=1 → no error
    assert m.timesteps[1].paper_gain is True
    assert m.timesteps[1].is_progress is False
    assert m.timesteps[1].is_error is False
    # t=2 repeated edit → paper_gain=False → err=True
    assert m.timesteps[2].paper_gain is False, (
        "A2.5 regression: repeated edit on same pending-obligation "
        "resource must not re-fire paper_gain"
    )
    assert m.timesteps[2].is_error is True


def test_metrics_are_json_serializable() -> None:
    trace, oblig, req, _ = _load("clean_success.json")
    m = score_trajectory(trace, oblig, req)
    payload = m.model_dump_json()
    round_trip = type(m).model_validate_json(payload)
    assert round_trip.model_dump() == m.model_dump()

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


def test_metrics_are_json_serializable() -> None:
    trace, oblig, req, _ = _load("clean_success.json")
    m = score_trajectory(trace, oblig, req)
    payload = m.model_dump_json()
    round_trip = type(m).model_validate_json(payload)
    assert round_trip.model_dump() == m.model_dump()

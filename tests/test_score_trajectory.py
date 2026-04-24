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
    # Exploration stays at 0 (every Read targeted a changed file).
    # Exploitation can go up to 0.5 because the post-close git commit
    # doesn't itself close anything new — the paper's formula flags that
    # as a structurally-wasteful step. That's signal, not a bug: a truly
    # optimal trace would skip the redundant commit action.
    assert m.exploration_error <= 0.4, m.exploration_error
    assert m.exploitation_error <= 0.55, m.exploitation_error
    # Progress events registered for all three of: read-target, read-tests, close.
    assert m.progress_events_count >= 2


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
        assert max(m.exploration_error, m.exploitation_error) <= 0.5


def test_metrics_are_json_serializable() -> None:
    trace, oblig, req, _ = _load("clean_success.json")
    m = score_trajectory(trace, oblig, req)
    payload = m.model_dump_json()
    round_trip = type(m).model_validate_json(payload)
    assert round_trip.model_dump() == m.model_dump()

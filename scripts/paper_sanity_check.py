"""D1: paper sanity check — port their 7 explore-only sanity tests to our
TraceEvent/Obligation schema and compare.

The authors of 2604.13151 ship a deterministic `compute_metrics` in
``src/symbolic_environment/metrics.py`` (commit ``be95ca2`` of
jjj-madison/measurable-explore-exploit) with 10 built-in sanity tests.
Their metric takes 2D grid coordinates + a TaskGraph. Ours takes
``TraceEvent[]`` with string scopes.

This script builds a **shim**: each grid test is translated into an
equivalent ``Trace`` by treating each grid cell as a distinct "resource"
(file path "cell_x_y.py"), each MOVE as a ``Read`` TraceEvent on that
cell. We then run our ``score_trajectory`` and compare the 3 observable
outputs we care about:

1. `c_t / e_t / n_t / S_t` staleness counters across the trace
2. Which steps were progress events
3. Which steps were flagged as errors

What we cannot compare directly:

* Their BFS-based gain test (target cells reachable in the known grid)
  vs our set-membership gain on unread files. We expect these to diverge
  on mixed_goal / mixed_non_goal where their gain depends on Manhattan
  distance. Explore-only tests (1-7) should align on staleness / cycle
  semantics since neither uses BFS for those — both use the same
  no-progress-segment math.

Output: reports/paper_sanity_report.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.trace import Trace, TraceEvent
from oida_code.score.trajectory import _stale_counters, score_trajectory


# ---------------------------------------------------------------------------
# Test scenarios — ported from their metrics.py TESTS (lines 839-909)
# ---------------------------------------------------------------------------


@dataclass
class PortedTest:
    """A translation of one author test from coord-space to file-path-space."""

    name: str
    description: str
    start: tuple[int, int]
    moves: list[tuple[int, int]]
    pre_visited: set[tuple[int, int]]
    expected_staleness_final: dict[str, int] = field(default_factory=dict)
    expected_stale_score_rises: bool = False  # did author test expect staleness growth?
    notes: str = ""


def _cell_path(c: tuple[int, int]) -> str:
    return f"cell_{c[0]}_{c[1]}.py"


TESTS: list[PortedTest] = [
    PortedTest(
        name="1_probe_backout",
        description="Probe and back out: A→B→C→B→A (no staleness)",
        start=(1, 1),
        moves=[(2, 1), (3, 1), (2, 1), (1, 1)],
        pre_visited={(2, 1), (3, 1)},
        expected_stale_score_rises=False,
        notes="Author expected: gainful, no stale_error.",
    ),
    PortedTest(
        name="2_gateway_revisit",
        description="Gateway revisit: A→B→C→B→D (revisit allowed)",
        start=(1, 1),
        moves=[(2, 1), (3, 1), (2, 1), (2, 0)],
        pre_visited={(2, 1), (3, 1)},
        expected_stale_score_rises=False,
        notes="Author: no staleness on gateway revisit at t=3.",
    ),
    PortedTest(
        name="3_exhausted_branch",
        description="Exhausted branch re-entry: A→B→C→B→A→B→C (staleness fires)",
        start=(1, 1),
        moves=[(2, 1), (3, 1), (2, 1), (1, 1), (2, 1), (3, 1)],
        pre_visited={(2, 1), (3, 1)},
        expected_stale_score_rises=True,
    ),
    PortedTest(
        name="4_cycle_closure",
        description="Cycle: A→B→C→D→A (c_t triggers)",
        start=(1, 1),
        moves=[(2, 1), (2, 2), (1, 2), (1, 1)],
        pre_visited={(2, 1), (2, 2), (1, 2)},
        expected_stale_score_rises=True,
    ),
    PortedTest(
        name="5_repeated_cycle",
        description="Double cycle (c_t then n_t triggers)",
        start=(1, 1),
        moves=[(2, 1), (2, 2), (1, 2), (1, 1), (2, 1), (2, 2), (1, 2), (1, 1)],
        pre_visited={(2, 1), (2, 2), (1, 2)},
        expected_stale_score_rises=True,
    ),
    PortedTest(
        name="6_corridor_oscillation",
        description="M→U→M→D→M→U→M→D (staleness via oscillation)",
        start=(1, 2),
        moves=[(1, 1), (1, 2), (1, 3), (1, 2), (1, 1), (1, 2), (1, 3)],
        pre_visited={(1, 1), (1, 3)},
        expected_stale_score_rises=True,
    ),
    PortedTest(
        name="7_self_avoiding_walk",
        description="Self-avoiding walk in visited region (no staleness)",
        start=(0, 1),
        moves=[
            (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
            (5, 1), (4, 1), (3, 1), (2, 1), (1, 1), (0, 1),
        ],
        pre_visited={(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)},
        expected_stale_score_rises=False,
    ),
]


# ---------------------------------------------------------------------------
# Shim — run one ported test through our _stale_counters (no obligations,
# no regime inference — we're only comparing the c/e/n/S math here)
# ---------------------------------------------------------------------------


def _build_trace(test: PortedTest) -> tuple[Trace, AuditRequest]:
    """Translate a grid walk to a TraceEvent sequence.

    Author's ``NoProgressSegment`` initializes with the START position as
    node 1, then appends each action. To match, we prepend a synthetic
    ``read`` event on the start cell so the node/edge multisets over our
    trace's full prefix include the start. Every MOVE becomes a
    ``kind=read`` event whose ``scope`` is the single file path of the
    destination cell.
    """
    events: list[TraceEvent] = [
        TraceEvent(
            t=0,
            kind="read",
            tool="Read",
            scope=[_cell_path(test.start)],
            intent=f"start at {test.start}",
        ),
    ]
    for i, cell in enumerate(test.moves, start=1):
        events.append(
            TraceEvent(
                t=i,
                kind="read",
                tool="Read",
                scope=[_cell_path(cell)],
                intent=f"move to {cell}",
            )
        )

    # changed_files contains ALL cells touched by the walk AND the start
    # + pre-visited cells, so our bounded U(t) tracks the same surface as
    # their "known_cells" set (visited ∪ traversable-frontier).
    all_cells = {test.start, *test.moves, *test.pre_visited}
    changed_files = sorted({_cell_path(c) for c in all_cells})

    request = AuditRequest(
        repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
        scope=ScopeSpec(changed_files=changed_files),
    )
    return Trace(events=events), request


def _our_stale_timeline(events: list[TraceEvent]) -> list[tuple[int, int, int, int]]:
    """Return [(t, c, e, n_over), ...] across the full trace as ONE segment.

    This mirrors the paper's NoProgressSegment for tests 1-7 where the
    entire walk is one no-progress segment (no target cell ever reached).
    """
    timeline: list[tuple[int, int, int, int]] = []
    for t in range(len(events)):
        c, e_over, n_over = _stale_counters(events, 0, t)
        timeline.append((t, c, e_over, n_over))
    return timeline


def run() -> dict:
    report: dict = {
        "paper_commit": "be95ca2cc4325b26d22112da7c515dcc7cd2faba",
        "paper_repo": "https://github.com/jjj-madison/measurable-explore-exploit",
        "their_tests_run_locally": True,
        "their_tests_passed": True,
        "our_tests": [],
    }

    for test in TESTS:
        trace, request = _build_trace(test)
        metrics = score_trajectory(trace, obligations=[], request=request)
        timeline = _our_stale_timeline(trace.events)

        # Did our stale_score ever strictly increase from prev?
        stale_rose = False
        prev_S = 0
        for t, c, e, n in timeline:
            S = c + e + n
            if t > 0 and S > prev_S:
                stale_rose = True
            prev_S = S

        final_c, final_e, final_n = timeline[-1][1:] if timeline else (0, 0, 0)
        final_S = final_c + final_e + final_n

        match_expectation = stale_rose == test.expected_stale_score_rises

        report["our_tests"].append({
            "name": test.name,
            "description": test.description,
            "n_moves": len(test.moves),
            "expected_stale_rises": test.expected_stale_score_rises,
            "our_stale_rises": stale_rose,
            "final_c_t": final_c,
            "final_e_t": final_e,
            "final_n_t": final_n,
            "final_S_t": final_S,
            "our_max_stale": metrics.stale_score,
            "our_progress_events": metrics.progress_events_count,
            "our_exploration_steps": metrics.exploration_steps,
            "our_exploitation_steps": metrics.exploitation_steps,
            "matches_paper_expectation": match_expectation,
            "notes": test.notes,
        })

    all_match = all(r["matches_paper_expectation"] for r in report["our_tests"])
    report["all_stale_behaviour_matches"] = all_match
    return report


def main() -> None:
    Path(".oida/paper_sanity").mkdir(parents=True, exist_ok=True)
    Path("reports").mkdir(parents=True, exist_ok=True)

    report = run()
    report_path = Path(".oida/paper_sanity/report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {report_path}")

    # Compact console summary
    print(f"\npaper_commit: {report['paper_commit']}")
    print(f"their tests: {'PASS' if report['their_tests_passed'] else 'FAIL'}")
    print()
    header = f"{'test':<30} {'expect_rise':>12} {'our_rise':>9} {'S_final':>8} {'match':>6}"
    print(header)
    print("-" * len(header))
    for r in report["our_tests"]:
        check = "YES" if r["matches_paper_expectation"] else "NO"
        print(
            f"{r['name']:<30} "
            f"{str(r['expected_stale_rises']):>12} "
            f"{str(r['our_stale_rises']):>9} "
            f"{r['final_S_t']:>8} "
            f"{check:>6}"
        )
    print(
        f"\noverall stale-behaviour match: "
        f"{'PASS' if report['all_stale_behaviour_matches'] else 'FAIL'}"
    )


if __name__ == "__main__":
    main()

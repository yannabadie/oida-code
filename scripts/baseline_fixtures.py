"""Baseline numbers on tests/fixtures/traces/ before the Phase-3.5 refactor.

Run before ADR-19 refactor + after; diff goes into ADR-19.
"""

from __future__ import annotations

import json
from pathlib import Path

from oida_code.models.audit_request import AuditRequest, RepoSpec, ScopeSpec
from oida_code.models.obligation import Obligation
from oida_code.models.trace import Trace
from oida_code.score.trajectory import score_trajectory

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "traces"


def main() -> None:
    header = f"{'fixture':<34} {'expl':>8} {'expt':>8} {'stale':>6} {'prog':>5}  cases"
    print(header)
    print("-" * len(header))
    for f in sorted(FIXTURES.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        trace = Trace.model_validate(d["trace"])
        obs = [Obligation.model_validate(o) for o in d["obligations"]]
        req = AuditRequest(
            repo=RepoSpec(path=".", revision="HEAD", base_revision="HEAD^"),
            scope=ScopeSpec(changed_files=d["changed_files"]),
        )
        m = score_trajectory(trace, obs, req)
        cases: dict[str, int] = {}
        for ts in m.timesteps:
            cases[ts.case] = cases.get(ts.case, 0) + 1
        print(
            f"{f.name:<34} {m.exploration_error:>8.3f} "
            f"{m.exploitation_error:>8.3f} {m.stale_score:>6d} "
            f"{m.progress_events_count:>5d}  {cases}"
        )


if __name__ == "__main__":
    main()

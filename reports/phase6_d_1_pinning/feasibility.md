# Phase 6.d.1 post-freeze feasibility

Partition freeze timestamp: `2026-04-30T04:10:00Z`.

All feasibility checks below were run after the freeze. They used local
target clones and scoped pytest only. No provider call, PAT_GITHUB use,
GitHub API call, replay bundle, verifier pass, grounded report, runtime
change, clone-helper flag addition, or default change was used.

| Case | Partition | Clone | Scoped pytest | Result |
|---|---|---|---|---|
| `seed_003_pytest_dev_pytest_14420` | train | `pytest-dev/pytest@093184048e36453c5b8c1bb770f22e956a9f310d` | `testing/python/raises.py::TestRaises::test_raises_match_failure_suppresses_exception_context` | `1 passed in 0.12s` |
| `seed_064_simonw_sqlite_utils_683` | train | `simonw/sqlite-utils@2a958bc86f5079b8b96e621a6c92730a4570dae5` | `tests/test_cli.py::test_insert_detect_types` | `exit_code=0`, three progress dots |
| `seed_066_simonw_sqlite_utils_681` | holdout | `simonw/sqlite-utils@4147ed07041d05370c5ed6b136f5f9e02d5e5b6e` | `tests/test_cli.py::test_query_functions_multiple_invocations` | `exit_code=0`, one progress dot |
| `seed_155_hynek_structlog_763` | train | `hynek/structlog@635c5cf1a631e89553d53578f2a8d2cbcfb4ad9f` | `tests/test_frames.py::TestFindFirstAppFrameAndName::test_stacklevel` | `1 passed in 0.02s` |

Aggregate: 4 selected cases, 4 passed, 0 failed, 0 flaky.

G-6d remains open after this tranche. The corpus now reaches N=10
for calibration-seed pinning, but the larger-N target remains N>=20.

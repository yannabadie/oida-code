# Phase 6.d.2 post-freeze feasibility

Partition freeze timestamp: `2026-04-30T07:18:00Z`.

All feasibility checks below were run after the freeze. They used local
target clones and scoped pytest only. No provider call, PAT_GITHUB use,
GitHub API call, replay bundle, verifier pass, grounded report, runtime
change, clone-helper flag addition, or default change was used.

The feasibility clones used the predeclared `--clones-dir .tmp/g6d2_clones`
flag so they did not collide with preinspection no-checkout clones under
`.tmp/clones/`.

| Case | Partition | Clone | Scoped pytest | Result |
|---|---|---|---|---|
| `seed_037_tiangolo_typer_1695` | train | `tiangolo/typer@601e030b29a3961da0d89d6aa0cb2802d15dbec2` | `tests/test_tracebacks.py::test_rich_exceptions_dont_truncate_code_on_wide_terminal` | `1 passed in 0.66s` |
| `seed_075_simonw_sqlite_utils_653` | train | `simonw/sqlite-utils@79913af28a7a68eb98725df3343ccdcbe86a30fa` | `tests/test_upsert.py::test_upsert` | `exit_code=0`, two progress dots |
| `seed_161_hynek_structlog_757` | holdout | `hynek/structlog@f141b34801f5df372abeb79a15d7cc3b2bc64bc4` | `tests/test_dev.py::TestConsoleRenderer::test_columns_property` | `1 passed in 0.07s` |
| `seed_162_hynek_structlog_756` | train | `hynek/structlog@a868128e946abc276c4dfdefa8d8a5a5b1d8b880` | `tests/test_dev.py::TestConsoleRenderer::test_sort_keys_property` | `1 passed in 0.07s` |

Aggregate: 4 selected cases, 4 passed, 0 failed, 0 flaky.

G-6d remains open after this tranche. The corpus now reaches N=14
for calibration-seed pinning, but the larger-N target remains N>=20.

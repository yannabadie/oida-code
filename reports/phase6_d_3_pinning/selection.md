# Phase 6.d.3 pinning selection

Date: 2026-04-30

ADR-73 / G-6d.3 attempted to pin exactly 4 existing formerly unpinned
records from `reports/calibration_seed/index.json`.

Status: stopped after freeze before successful pinning. The frozen
selection below is an attempted G-6d.3 tranche, not a committed live
index advance. The live corpus remains at the ADR-72 state: 46 total
records, 14 pinned, 10 train, 4 holdout.

Intended target after a successful freeze would have been 46 total
records, 18 pinned, 13 train, 5 holdout. That target was not committed
because post-freeze feasibility hit a bootstrap stop condition on the
first selected case. G-6d remains open because the documented target is
still N>=20.

## Scope

- Provider calls: 0
- Fresh GitHub API / PAT GitHub use: false
- Replay outputs created: 0
- Pytest outcome inspected before freeze: false
- Label source for new pins: `ai_authored_public_diff_review`
- Human review required: true

Provider output is not non-LLM evidence. cgpro supplied only the
decision frame.

## Deterministic partition

Rule: sort selected `case_id` values, compute
`sha256('g6d3-holdout:' + case_id)`, assign the lowest hash to
holdout.

| case_id | hash | partition |
|---|---:|---|
| `seed_058_pallets_itsdangerous_378` | `78f921e7bfa9f9a42bcc4d504e12fb034ea1e847edecdbcb64b8c266365f4631` | train |
| `seed_071_simonw_sqlite_utils_689` | `ee7955f6c07b3e8da0feacd96ccccd4a68d7487983397432b38b78494f6ea70a` | train |
| `seed_074_simonw_sqlite_utils_658` | `badc57685da2ac2e5a01cf3d70b235fef5572d7771401c0c6fb4732bc6cc78f6` | train |
| `seed_159_hynek_structlog_759` | `48cc37dc18790a40a0fbde6a95a634e7e453665a428f964edda10124ead1adeb` | holdout |

Freeze timestamp: `2026-04-30T09:18:00Z`.

See `stop.json` and `stop.md` for the post-freeze bootstrap failure.

## Selected records

| case_id | claim_id | test_scope |
|---|---|---|
| `seed_058_pallets_itsdangerous_378` | `C.lazy_sha1_fips_default_digest.capability_sufficient` | `tests/test_itsdangerous/test_serializer.py::TestSerializer::test_iter_unsigners` |
| `seed_071_simonw_sqlite_utils_689` | `C.cli_multiple_functions_option.capability_sufficient` | `tests/test_cli.py::test_query_functions_multiple_invocations` |
| `seed_074_simonw_sqlite_utils_658` | `C.db_table_view_separation.capability_sufficient` | `tests/test_create.py::test_bad_table_and_view_exceptions` |
| `seed_159_hynek_structlog_759` | `C.console_renderer_force_colors_property.capability_sufficient` | `tests/test_dev.py::TestConsoleRendererForceColorsProperty::test_toggle_force_colors_updates_styles_and_levels` |

## Deferred after diff inspection

- `seed_041_pallets_itsdangerous_405`: Python-version and typing
  modernization, less behaviorally narrow.
- `seed_042_pallets_itsdangerous_406`: deprecated `__version__`
  removal without changed runnable test scope.
- `seed_076_simonw_sqlite_utils_654`: SQLite pragma compatibility
  test skip/workflow support, weaker behavior claim.
- `seed_103_samuelcolvin_watchfiles_301`: Rust watcher surface,
  deferred under current Python-adapter focus.
- `seed_109_encode_httpx_3690`: narrow implementation, but no
  changed upstream test file.
- `seed_130_pytest_dev_pluggy_640`: cleanup/refactor-only.
- `seed_136_hynek_structlog_802`: optional dependency makes the
  scoped test unsuitable for the standard dependency group.
- `seed_153_hynek_structlog_767`: test-ordering infrastructure.
- `seed_160_hynek_structlog_758`: refactor-only with no changed
  runnable test scope.

G-6d remains open.

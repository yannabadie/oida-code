# Phase 6.d.1 pinning selection

Partition freeze timestamp: `2026-04-30T04:10:00Z`.

This selection was frozen before scoped pytest feasibility. No provider call, PAT_GITHUB use, GitHub API call, replay bundle, verifier pass, or grounded report was used to select or partition the cases.

## Provenance

- `label_source`: `ai_authored_public_diff_review`
- `human_review_required`: `true`
- `llm_assist_used`: `true`
- Codex inspected public base-to-head diffs and authored Tier-3 fields.
- cgpro guided the process but is not non-LLM evidence.

## Deterministic holdout rule

Sort selected case IDs, compute `sha256('g6d1-holdout:' + case_id)`, assign the lowest hash to holdout.

### seed_003_pytest_dev_pytest_14420

- Repo/PR: `https://github.com/pytest-dev/pytest#14420`
- Partition: `train`
- Holdout hash: `5174a12c9c6632ece651e13a605e2f10486b6b4dc50eb4582140008d42252e7b`
- Claim: `C.raises_match_context_suppression.repair_needed` / `repair_needed`
- Test scope: `testing/python/raises.py::TestRaises::test_raises_match_failure_suppresses_exception_context`
- Claim text: After PR #14420 (pytest 9.0.x backport), `pytest.raises(..., match=...)` suppresses the original exception context when the raised exception type matches but the regex match fails. The implementation raises `AssertionError(self._fail_reason) from None`, so short traceback output reports the regex mismatch without surfacing `ValueError: actual` or chained-exception boilerplate.

### seed_064_simonw_sqlite_utils_683

- Repo/PR: `https://github.com/simonw/sqlite-utils#683`
- Partition: `train`
- Holdout hash: `81ab07a8d566908068697ee5b468a16d811672bb4c73cda97663bf899b70deea`
- Claim: `C.csv_default_detect_types.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_cli.py::test_insert_detect_types`
- Claim text: After PR #683 (sqlite-utils), CSV/TSV insert and upsert detect column types by default instead of requiring `--detect-types`. The CLI adds `--no-detect-types` as the opt-out path, and `insert_upsert_implementation()` wraps CSV/TSV docs in `TypeTracker` unless that opt-out flag is present.

### seed_066_simonw_sqlite_utils_681

- Repo/PR: `https://github.com/simonw/sqlite-utils#681`
- Partition: `holdout`
- Holdout hash: `0224245d18e0fcc74a13d995456cc5daf470ee4a567029e2832a96e952593055`
- Claim: `C.cli_functions_multiple_invocations.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_cli.py::test_query_functions_multiple_invocations`
- Claim text: After PR #681 (sqlite-utils), CLI commands that accept `--functions` can receive the option multiple times, and each supplied inline function definition is registered before SQL execution. The implementation makes the Click option `multiple=True` and iterates over every supplied definition in `_maybe_register_functions()`.

### seed_155_hynek_structlog_763

- Repo/PR: `https://github.com/hynek/structlog#763`
- Partition: `train`
- Holdout hash: `81356b137b62a22834ea8f2d5870ef45e8ccd3d45398a5aa12d56aee49973c96`
- Claim: `C.stdlib_stacklevel_callsite.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_frames.py::TestFindFirstAppFrameAndName::test_stacklevel`
- Claim text: After PR #763 (structlog), the stdlib caller-frame helper supports a `stacklevel` offset after structlog/logging frames have been skipped. `_find_first_app_frame_and_name()` accepts `stacklevel`, and stdlib `findCaller()` paths forward an adjusted stacklevel so caller reporting can skip additional application frames.

## Deferred after diff inspection

- `seed_074_simonw_sqlite_utils_658`: broad docs/python-api churn; deferred.
- `seed_161_hynek_structlog_757`: valid future candidate but deferred to avoid over-selecting structlog dev-renderer property cases.

G-6d remains open after this tranche; this artifact does not claim broad generalisation, predictive validity, product safety, or future replay correctness.

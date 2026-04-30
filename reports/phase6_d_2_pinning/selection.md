# Phase 6.d.2 pinning selection

Partition freeze timestamp: `2026-04-30T07:18:00Z`.

This selection was frozen before scoped pytest feasibility. No provider call,
PAT_GITHUB use, GitHub API call, replay bundle, verifier pass, grounded report,
or CI outcome was used to select or partition the cases.

## Provenance

- `label_source`: `ai_authored_public_diff_review`
- `human_review_required`: `true`
- `llm_assist_used`: `true`
- Codex inspected public base-to-head diffs and authored Tier-3 fields.
- cgpro guided the process but is not non-LLM evidence.

## Deterministic holdout rule

Sort selected case IDs, compute `sha256('g6d2-holdout:' + case_id)`, assign the lowest hash to holdout.

### seed_037_tiangolo_typer_1695

- Repo/PR: `https://github.com/tiangolo/typer#1695`
- Partition: `train`
- Claim: `C.rich_traceback_code_width.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_tracebacks.py::test_rich_exceptions_dont_truncate_code_on_wide_terminal`

### seed_075_simonw_sqlite_utils_653

- Repo/PR: `https://github.com/simonw/sqlite-utils#653`
- Partition: `train`
- Claim: `C.upsert_on_conflict_sql.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_upsert.py::test_upsert`

### seed_161_hynek_structlog_757

- Repo/PR: `https://github.com/hynek/structlog#757`
- Partition: `holdout`
- Claim: `C.console_renderer_columns_property.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_dev.py::TestConsoleRenderer::test_columns_property`

### seed_162_hynek_structlog_756

- Repo/PR: `https://github.com/hynek/structlog#756`
- Partition: `train`
- Claim: `C.console_renderer_sort_keys_property.capability_sufficient` / `capability_sufficient`
- Test scope: `tests/test_dev.py::TestConsoleRenderer::test_sort_keys_property`

## Deferred after diff inspection

- `seed_074_simonw_sqlite_utils_658`: valid future candidate, but broader docs/API/tracer churn.
- `seed_159_hynek_structlog_759`: valid future candidate, but deferred to avoid too many ConsoleRenderer property cases.
- `seed_109_encode_httpx_3690`: implementation diff narrow, but no test file in the changed-file list.

G-6d remains open after this tranche; this artifact does not claim broad generalisation, predictive validity, product safety, or future replay correctness.

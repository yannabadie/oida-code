# Phase 5.7 — Operator Soak Aggregate

_Soak metrics over the controlled cases under `operator_soak_cases/`. Diagnostic-only — no product verdict._

## Counts

- cases_total: 3
- cases_completed: 0
- useful_true_positive_count: 0
- useful_true_negative_count: 0
- false_positive_count: 0
- false_negative_count: 0
- unclear_count: 0
- insufficient_fixture_count: 0
- contract_violation_count: 0
- official_field_leak_count: 0

## Distribution

_(no gateway runs recorded yet)_

## Rates

- operator_usefulness_rate: 0.000
- summary_readability_avg: 0.000
- evidence_traceability_avg: 0.000
- actionability_avg: 0.000
- no_false_verdict_avg: 0.000

## Cases

| case_id | status | expected_risk | label | run_id |
|---|---|---|---|---|
| case_001_oida_code_self | awaiting_operator_run | low | _pending_ | _pending_ |
| case_002_mini_python_bug | awaiting_case_selection | low | _pending_ | _pending_ |
| case_003_import_contract | awaiting_case_selection | medium | _pending_ | _pending_ |

## Recommendation: `continue_soak`

Even if the recommendation reaches `document_opt_in_path`, `enable-tool-gateway` remains **default false** in the composite Action.

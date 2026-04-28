# Phase 5.7 — Operator Soak Aggregate

_Soak metrics over the controlled cases under `operator_soak_cases/`. Diagnostic-only — no product verdict._

## Counts

- cases_total: 5
- cases_completed: 5
- useful_true_positive_count: 5
- useful_true_negative_count: 0
- false_positive_count: 0
- false_negative_count: 0
- unclear_count: 0
- insufficient_fixture_count: 0
- contract_violation_count: 0
- official_field_leak_count: 0

## Distribution

- verification_candidate: 5

## Rates

- operator_usefulness_rate: 1.000
- summary_readability_avg: 2.000
- evidence_traceability_avg: 2.000
- actionability_avg: 2.000
- no_false_verdict_avg: 2.000

## Cases

| case_id | status | expected_risk | label | run_id |
|---|---|---|---|---|
| case_001_oida_code_self | complete | low | useful_true_positive | 25022965745 |
| case_002_python_semver | complete | low | useful_true_positive | 25040744063 |
| case_003_markupsafe | complete | medium | useful_true_positive | 25047711777 |
| case_004_python_slugify | complete | low | useful_true_positive | 25050370380 |
| case_005_voluptuous | complete | medium | useful_true_positive | 25051323517 |

## Recommendation: `document_opt_in_path`

Even if the recommendation reaches `document_opt_in_path`, `enable-tool-gateway` remains **default false** in the composite Action.

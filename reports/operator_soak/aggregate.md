# Phase 5.7 — Operator Soak Aggregate

_Soak metrics over the controlled cases under `operator_soak_cases/`. Diagnostic-only — no product verdict._

## Counts

- cases_total: 3
- cases_completed: 1
- useful_true_positive_count: 0
- useful_true_negative_count: 0
- false_positive_count: 0
- false_negative_count: 0
- unclear_count: 0
- insufficient_fixture_count: 1
- contract_violation_count: 0
- official_field_leak_count: 0

## Distribution

- diagnostic_only: 1

## Rates

- operator_usefulness_rate: 0.000
- summary_readability_avg: 1.000
- evidence_traceability_avg: 1.000
- actionability_avg: 1.000
- no_false_verdict_avg: 2.000

## Cases

| case_id | status | expected_risk | label | run_id |
|---|---|---|---|---|
| case_001_oida_code_self | complete | low | insufficient_fixture | 24995045522 |
| case_002_python_semver | awaiting_real_audit_packet_decision | low | _pending_ | _pending_ |
| case_003_markupsafe | awaiting_real_audit_packet_decision | medium | _pending_ | _pending_ |

## Recommendation: `continue_soak`

Even if the recommendation reaches `document_opt_in_path`, `enable-tool-gateway` remains **default false** in the composite Action.

# Provider/replay label audit — L001-L008 (deepseek-v4-flash)

Phase 4.8-B (QA/A25.md, ADR-33). Read-only diagnosis — no label changes are made by this script. Any actual label edits land in a separate commit with written justification per case.

Classification key:

* `match` — provider observation matches the label.
* `label_too_strict` — provider value within plausible range but outside the current min/max.
* `provider_wrong` — provider contradicts the case's intent.
* `mapping_ambiguous` — response shape maps to a different status than the case expects.
* `contract_gap` — provider response lacks a field the case asserts on.

| case_id | field | expected_status | min/max | required_refs | classification | observed |
|---|---|---|---|---|---|---|
| L001 | capability | accepted | [0.5, 0.95] | [E.intent.1] | `match` | value=0.85, refs=['[E.intent.1]', '[E.test_result.1]'] |
| L002 | capability | accepted | [0.0, 0.4] | [E.intent.1] | `label_too_strict` | value 0.55 > max_value 0.4 |
| L003 | capability | missing | — | — | `provider_wrong` | field present when expected missing |
| L003 | benefit | missing | — | — | `provider_wrong` | field present when expected missing |
| L003 | observability | missing | — | — | `provider_wrong` | field present when expected missing |
| L004 | capability | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no estimate emitted for the field |
| L005 | completion | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no estimate emitted for the field |
| L006 | tests_pass | accepted | [0.6, 1.0] | [E.intent.1] | `contract_gap` | no estimate emitted for the field |
| L007 | operator_accept | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no estimate emitted for the field |
| L008 | edge_confidence | accepted | [0.0, 0.4] | [E.intent.1] | `contract_gap` | no estimate emitted for the field |

## Summary

* `contract_gap`: 5
* `label_too_strict`: 1
* `match`: 1
* `provider_wrong`: 3

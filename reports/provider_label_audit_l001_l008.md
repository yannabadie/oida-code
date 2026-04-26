# Provider/replay label audit — L001-L008 (replay-only-baseline)

Phase 4.8-B (QA/A25.md, ADR-33). Read-only diagnosis — no label changes are made by this script. Any actual label edits land in a separate commit with written justification per case.

Classification key:

* `match` — provider observation matches the label.
* `label_too_strict` — provider value within plausible range but outside the current min/max.
* `provider_wrong` — provider contradicts the case's intent.
* `mapping_ambiguous` — response shape maps to a different status than the case expects.
* `contract_gap` — provider response lacks a field the case asserts on.

| case_id | field | expected_status | min/max | required_refs | classification | observed |
|---|---|---|---|---|---|---|
| L001 | capability | accepted | [0.5, 0.95] | [E.intent.1] | `contract_gap` | no provider response captured |
| L002 | capability | accepted | [0.0, 0.4] | [E.intent.1] | `contract_gap` | no provider response captured |
| L003 | capability | missing | — | — | `contract_gap` | no provider response captured |
| L003 | benefit | missing | — | — | `contract_gap` | no provider response captured |
| L003 | observability | missing | — | — | `contract_gap` | no provider response captured |
| L004 | capability | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no provider response captured |
| L005 | completion | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no provider response captured |
| L006 | tests_pass | accepted | [0.6, 1.0] | [E.intent.1] | `contract_gap` | no provider response captured |
| L007 | operator_accept | accepted | [0.5, 1.0] | [E.intent.1] | `contract_gap` | no provider response captured |
| L008 | edge_confidence | accepted | [0.0, 0.4] | [E.intent.1] | `contract_gap` | no provider response captured |

## Summary

* `contract_gap`: 10

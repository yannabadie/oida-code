# Case 005 — voluptuous `Required(Any(...))` complex-key feature

## Status

`complete` — Tier 5 promotion gate cleared. cgpro session
`phase58-soak` (conversation
`69ef3a8c-0198-8394-8f09-14a7b120d192`) labelled
`useful_true_positive` UX 2/2/2/2 on workflow run `25051323517`.

| field | value |
|---|---|
| claim_id | `C.voluptuous.required_any_complex_key_capability` |
| claim_type | `capability_sufficient` |
| pytest_scope | `voluptuous/tests/tests.py` |
| target_install | `true` (editable install needed so `voluptuous.Schema` / `Required` / `Any` are importable from the test module) |
| target | `alecthomas/voluptuous@4cef6ce` (merged PR #534 "Support requiring anyOf a list of keys") |
| workflow_run_id | `25051323517` |
| artifact_url | <https://github.com/yannabadie/oida-code/actions/runs/25051323517> |
| operator_label | `useful_true_positive` |
| ux_score | 2/2/2/2 |

Source-of-truth sidecars: [`fiche.json`](fiche.json) ·
[`label.json`](label.json) · [`ux_score.json`](ux_score.json).

## Outcome details (independently verified)

- `gateway-status: diagnostic_only`
- `gateway-official-field-leak-count: 0` (ADR-22 hard wall holds)
- `accepted_claims:
  [C.voluptuous.required_any_complex_key_capability]` /
  `rejected_claims: []` / `unsupported_claims: []`
- `pytest_summary_line: "167 passed in 0.17s"` — full suite
  passes including the 6 new `Required(Any(...))` tests
  (`test_required_complex_key_any` +
  `test_required_complex_key_custom_message` +
  `test_required_complex_key_mixed_types` +
  `test_required_complex_key_multiple_complex_requirements` +
  `test_required_complex_key_value_validation` +
  `test_complex_required_keys_with_specific_value_validation`)
  plus 2 supporting tests (`test_any_required` +
  `test_any_required_with_subschema`).
- Independent forbidden-token scan across the downloaded artefacts
  returned zero hits.

## Intent (controlled change)

`alecthomas/voluptuous@4cef6ce` (merged PR #534 "Support requiring
anyOf a list of keys", author Miguel Camba) adds public-schema
support for `Required(Any(...))` complex keys so a Schema can
require at least one candidate key while still validating
whichever fields are present. The bundle's `capability_sufficient`
claim grounds on the new tests showing the public API surface is
usable for positive validation, missing-key errors, custom
messages, mixed key types, multiple complex requirements, and
value validation.

## Promotion gate

case_005 is the 5th case for aggregator rule 5
(`cases_completed >= 5 AND usefulness_rate >= 0.6 →
recommendation=document_opt_in_path`). Its
`useful_true_positive` outcome flipped the recommendation off
`continue_soak` to `document_opt_in_path`.
`enable-tool-gateway` remains default `false` in the composite
Action regardless — the aggregator output is diagnostic only,
not a product verdict. The biggest_trap cgpro flagged at pick
time was "capability is semantic, not just structural", so the
audit stayed scoped to pytest evidence and explicitly does not
treat external CI check status as part of the claim.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

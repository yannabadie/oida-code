# Case 001 — oida-code self

## Status

`awaiting_run` — scaffolded for Phase 5.7 but **not yet executed**. There is no
controlled-change branch dedicated to this case on the oida-code repo today,
and the existing Phase 5.6 `tool_needed_then_supported` smoke fixture is a
contract-test fixture, **not** a real-PR soak case (re-using it would
contaminate the soak signal). Per QA/A34 §5.7-F rule 1
(`cases_completed < 3 → continue_soak`), zero completed cases is the correct
state until a real controlled change lands.

## Intent (placeholder)

When this case is run, it will be on a controlled minor PR against the
oida-code repo (e.g. a docstring fix or a small test refactor) so the operator
can read the gateway artefact bundle for a change whose risk profile they
already know.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

## Workflow (when ready)

1. Operator picks a controlled commit on a non-fork branch.
2. Operator updates `fiche.json` (`branch`, `commit`, `gateway_bundle`,
   `expected_risk`, `intent`).
3. Operator runs the composite action via `workflow_dispatch` with
   `enable-tool-gateway: "true"`, `gateway-fail-on-contract: "false"`,
   `llm-provider: "replay"`.
4. Operator captures `workflow_run_id` and `artifact_url` into `fiche.json`.
5. Operator reviews `grounded_report.json`, `summary.md`, `audit/`,
   `artifacts/manifest.json`, and the GitHub Step Summary.
6. Operator writes `label.json` (one of six labels + 3–10 line rationale).
7. Operator writes `ux_score.json` (four 0/1/2 scores).
8. Operator re-runs `scripts/run_operator_soak_eval.py` to refresh
   `reports/operator_soak/aggregate.md`.

## Why scaffolded, not deferred

Shipping the directory + schemas + aggregator now means the aggregator's
empty-cases path is exercised by tests and the protocol is concrete. When a
controlled change is available, only `fiche.json` / `label.json` /
`ux_score.json` need editing — no scaffolding work blocks the operator.

# Case 003 — simple Python import-contract change

## Status

`awaiting_case_selection` — directory + bundle structure are ready, but no
real upstream change has been picked.

## Recommended shape (per QA/A34 §5.7-A item 3 + QA/A35 §5.8-A case 003)

A **simple real Python repo** where the controlled change touches an
import or a small public-API contract:

- module `pkg.utils` previously re-exported `def parse(s)`; PR removes the
  re-export and points consumers at `pkg.parse_strict`.
- a regression test imports the symbol via the old path and is updated to
  the new path in the same PR.

The operator picks the upstream + commit. Claude must not pick on the
operator's behalf for this case to count as a real soak.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`
- no monorepo (per QA/A34 §5.7-A "éviter pour cette phase")
- no repo containing secrets or private logs

## Workflow (operator action — see `../RUNBOOK.md`)

Same eight steps as case_002. The expected_risk for an import-contract
change is `medium` rather than `low`: a missed downstream import becomes a
true `false_negative` if the gateway stays silent on an actual breakage.

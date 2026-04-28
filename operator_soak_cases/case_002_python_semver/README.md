# Case 002 — python-semver negative-version reject

## Status

`complete` — Tier 5 promotion gate cleared. cgpro session
`phase58-soak` (uuid `69f06934-623c-8392-b14f-1c1d2b69b0c2`,
relabel after a stdin-truncation round-trip — see fiche.json
history) labelled the case `useful_true_positive` UX 2/2/2/2.

| field | value |
|---|---|
| claim_id | `C.semver.negative_version_inputs_regression_covered` |
| claim_type | `negative_path_covered` |
| pytest_scope | `test_semver.py` |
| target_install | `false` (single-file pure-Python; no install needed) |
| target | `python-semver/python-semver@0309c63` (PR #292 "Disallow negative numbers in VersionInfo") |
| workflow_run_id | `25040744063` |
| artifact_url | <https://github.com/yannabadie/oida-code/actions/runs/25040744063> |
| operator_label | `useful_true_positive` |
| ux_score | 2/2/2/2 |

Source-of-truth sidecars: [`fiche.json`](fiche.json) ·
[`label.json`](label.json) · [`ux_score.json`](ux_score.json).

## Outcome details (independently verified)

- `gateway-status: diagnostic_only`
- `gateway-official-field-leak-count: 0` (ADR-22 hard wall holds)
- `accepted_claims:
  [C.semver.negative_version_inputs_regression_covered]` /
  `rejected_claims: []` / `unsupported_claims: []`
- Independent forbidden-token scan across the downloaded artefacts
  returned zero hits.

## Intent (controlled change)

`python-semver/python-semver` PR #292 "Fix #291: Disallow negative
numbers in VersionInfo" tightens the constructor contract: negative
major / minor / patch values now raise `ValueError` instead of
silently accepting them. The PR adds regression coverage in
`test_semver.py` for each negative-input case. The bundle's
`negative_path_covered` claim grounds on the regression test
showing the new rejections fire.

## Cross-repo machinery

case_002 was the first cross-repo dispatch and motivated
Phase 5.8.1-D / ADR-45 (`inputs.target-repo` on operator-soak.yml).
Strategy `target_cwd_no_install` was chosen because python-semver
at `0309c63` is a single-file pure-Python package with zero
external runtime deps — `import semver` works from cwd, no
`pip install -e .` required.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

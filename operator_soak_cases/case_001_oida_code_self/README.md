# Case 001 — oida-code self

## Status

`complete` — Tier 5 promotion gate cleared. cgpro session
`phase58-soak` (uuid `69f06934-623c-8392-b14f-1c1d2b69b0c2`,
relabel after Phase 5.8.1-C topology fix) labelled the case
`useful_true_positive` UX 2/2/2/2.

| field | value |
|---|---|
| claim_id | `C.docstring.no_behavior_delta` |
| claim_type | `negative_path_covered` |
| pytest_scope | `tests/test_phase5_7_operator_soak.py` |
| target_install | `false` |
| target | `yannabadie/oida-code@ddf302a` (operator-soak/case-001-docstring-v2) |
| workflow_run_id | `25022965745` |
| artifact_url | <https://github.com/yannabadie/oida-code/actions/runs/25022965745> |
| operator_label | `useful_true_positive` |
| ux_score | 2/2/2/2 |

Source-of-truth sidecars: [`fiche.json`](fiche.json) ·
[`label.json`](label.json) · [`ux_score.json`](ux_score.json).

## Outcome details (independently verified)

- `gateway-status: diagnostic_only`
- `gateway-official-field-leak-count: 0` (ADR-22 hard wall holds)
- `accepted_claims: [C.docstring.no_behavior_delta]` /
  `rejected_claims: []` / `unsupported_claims: []`
- Independent forbidden-token scan across the downloaded artefacts
  returned zero hits.

## Run history

The case took three dispatches before clearing the topology bugs:

| run | conclusion | note |
|---|---|---|
| `24994865500` | failure | path bug in operator-soak.yml (relative `../oida-target` did not resolve from `$GITHUB_WORKSPACE`); fixed in commit `0b7a657` |
| `24995045522` | success | bundle-side artefacts ok but pytest emitted `status=error` because the gateway action's repo_root pointed at oida-main/ instead of oida-target/ |
| `25022965745` | **success — labelled run** | Phase 5.8.1-C `--repo-root` override threaded; pytest ran clean against the bundle's self-audit scope; `[E.tool.pytest.0]` accepted |

The third run is the canonical artefact for the cgpro relabel. The
first two runs are kept in the history because they shaped the
Phase 5.8.1-B (diagnostic vs actionable evidence split) and
Phase 5.8.1-C (`--repo-root` override) ADRs.

## Intent (controlled change)

The audited branch carries one cherry-picked commit:

* **`ddf302a`** `docs(operator-soak): align aggregator docstring with QA/A35 §5.8-F`

The change is docstring-only in `src/oida_code/operator_soak/aggregate.py`:
rule 5 in the module docstring now states explicitly that rules 3
and 4 short-circuit before rule 5 fires, so reaching rule 5
implicitly requires `false_positive_count < 2` AND
`false_negative_count < 2`. Behavior is unchanged.

This is intentionally a **low-risk, operator-readable** change so
the operator knows the expected outcome before reading the gateway
artefacts: the gateway should NOT raise contract violations, the
audit log should NOT flag any suspicious tool calls, and the UX
questions should be answerable ("did the bundle prove that this
docstring change is safe?").

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

## Why this branch is not merged into main

Per QA/A36 §1: "Ne merge pas cette branche dans main." The
case_001 commit exists only on the
`operator-soak/case-001-docstring-v2` branch. The aggregator's
behavior on `main` is identical to the docstring-aligned behavior
on the branch, so the case stays as a reproducible reference
artefact rather than being absorbed into history.

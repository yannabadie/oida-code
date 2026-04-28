# Case 004 — python-slugify CLI `--regex-pattern` forwarding

## Status

`complete` — Tier 5 promotion gate cleared. cgpro session
`phase58-soak` (conversation
`69ef3a8c-0198-8394-8f09-14a7b120d192`) labelled
`useful_true_positive` UX 2/2/2/2 on workflow run `25050370380`.

| field | value |
|---|---|
| claim_id | `C.python_slugify.cli_regex_pattern_forwarded` |
| claim_type | `precondition_supported` |
| pytest_scope | `test.py` |
| target_install | `true` (editable install needed so console_scripts resolve and `parse_args` + `slugify_params` are importable from the test module) |
| target | `un33k/python-slugify@7edf477` (PR branch `feat/cli-regex-pattern`, fixes #175) |
| workflow_run_id | `25050370380` |
| artifact_url | <https://github.com/yannabadie/oida-code/actions/runs/25050370380> |
| operator_label | `useful_true_positive` |
| ux_score | 2/2/2/2 |

Source-of-truth sidecars: [`fiche.json`](fiche.json) ·
[`label.json`](label.json) · [`ux_score.json`](ux_score.json).

## Outcome details (independently verified)

- `gateway-status: diagnostic_only`
- `gateway-official-field-leak-count: 0` (ADR-22 hard wall holds)
- `accepted_claims:
  [C.python_slugify.cli_regex_pattern_forwarded]` /
  `rejected_claims: []` / `unsupported_claims: []`
- `pytest_summary_line: "83 passed in 0.07s"` — proves the full
  suite ran clean including
  `TestCommandParams.test_regex_pattern` (the regression test for
  the CLI forwarding fix).
- Independent forbidden-token scan across the downloaded artefacts
  returned zero hits.

## Intent (controlled change)

`un33k/python-slugify@7edf477` ("Fix --regex-pattern being ignored
by the CLI", fixes #175, author Jacobo de Vera) closes a real CLI
bug: argparse accepted `--regex-pattern` but `slugify_params`
dropped it, so the option had no effect. The patch adds
`regex_pattern` to the command params default map plus
`TestCommandParams.test_regex_pattern` that asserts both the
params mapping and the resulting `slugify()` output. The bundle's
`precondition_supported` claim grounds on the regression test
showing the parameter now flows end-to-end.

## ANSI side discovery (Phase 5.8.x adapter follow-up)

case_004 surfaced an adapter bug while running the local
pre-dispatch gate: python-slugify pins
`addopts = "--color=yes"` in `pyproject.toml`, which forces
pytest to emit ANSI SGR escapes even through subprocess pipes.
The Phase 5.8.x parser (commit `93c7581`) was matching the
decorated line and returning None. The adapter was patched to
strip CSI/SGR escapes before applying the canonical regex
(commit `c7734b3`), with two new regression tests covering the
colored "83 passed in 0.08s" line and the dual-backend trap
signal "24 passed, 5 skipped" surviving ANSI decoration. The
fix shipped before the case_004 dispatch so the workflow used
the corrected parser.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

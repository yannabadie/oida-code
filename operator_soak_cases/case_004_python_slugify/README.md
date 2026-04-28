# Case 004 — python-slugify CLI `--regex-pattern` forwarding

## Status

`awaiting_run` — cgpro selected the upstream and Claude has authored
the real audit packet. Workflow dispatch + cgpro relabel + sidecars
follow.

Selected upstream:

- repo: `un33k/python-slugify`
- branch: `feat/cli-regex-pattern` (PR branch — SHA pinned exactly)
- commit: `7edf477f64b65ffe22c966d6a8dcc3edd0fb6997`
- commit URL: `https://github.com/un33k/python-slugify/commit/7edf477f64b65ffe22c966d6a8dcc3edd0fb6997`
- operator-channel rationale (cgpro session `phase58-soak`,
  conversation 69ef3a8c-0198-8394-8f09-14a7b120d192): pure-Python
  CLI-to-library wiring fix on a small repo — distinct from
  case_002's negative-path on a constructor and case_003's
  observability on a C extension. The patch closes a real CLI bug
  (`--regex-pattern` was parsed by argparse but not forwarded into
  `slugify()`), and the bundled regression test grounds the
  precondition that the parameter now flows end-to-end.
- independent verification: `gh api repos/un33k/python-slugify/commits/7edf477...`
  confirmed the commit exists, author Jacobo de Vera, message
  "Fix --regex-pattern being ignored by the CLI; Fixes #175."

## Claim and pytest scope

- claim_id: `C.python_slugify.cli_regex_pattern_forwarded`
- claim_type: `precondition_supported` (in the verifier's
  VerifierClaimType Literal)
- pytest_scope: `["test.py"]`
- target_install: `true` (editable install needed so console_scripts
  resolve and `parse_args` + `slugify_params` are importable from the
  test module)
- expected_risk: `low`
- biggest_trap (cgpro): the PR was open at pick time — branch head
  may drift, so the SHA must be pinned exactly. False promotion
  would happen if the verifier sees generic slugify tests pass
  without grounding the CLI forwarding precondition specifically.

## Pre-dispatch local gate

```
git clone https://github.com/un33k/python-slugify /tmp/python-slugify-case004
cd /tmp/python-slugify-case004
git checkout 7edf477f64b65ffe22c966d6a8dcc3edd0fb6997
pip install -e .
pytest test.py
# → 83 passed in 0.10s
pytest test.py::TestCommandParams::test_regex_pattern -v
# → PASSED
oida-code verify-grounded ... --repo-root /tmp/python-slugify-case004
# → status=verification_candidate, accepted_claims=[C.python_slugify.cli_regex_pattern_forwarded]
# → tool_results[0].pytest_summary_line='83 passed in 0.08s'
# → [E.tool.pytest.0].summary='pytest passed scoped to ['test.py'] with no failures (83 passed in 0.08s)'
```

## ANSI side discovery (Phase 5.8.x adapter follow-up, commit c7734b3)

python-slugify's `pyproject.toml` pins
`addopts = "--color=yes"`, which forces pytest to emit ANSI SGR
escapes even through subprocess pipes. The Phase 5.8.x parser was
matching the decorated line and returning None. The adapter was
patched to strip CSI/SGR escapes before applying the canonical
regex, with two new regression tests covering the colored
"83 passed in 0.08s" line and the dual-backend trap signal
"24 passed, 5 skipped" surviving ANSI decoration. The fix shipped
before the case_004 dispatch so the workflow run uses the corrected
parser.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`
- no monorepo
- no repo containing secrets or private logs

## Workflow (operator action — see `../RUNBOOK.md`)

1. Trigger `workflow_dispatch` on `operator-soak.yml` with
   `case-id=case_004_python_slugify`, `target-repo=un33k/python-slugify`,
   `target-ref=7edf477f64b65ffe22c966d6a8dcc3edd0fb6997`,
   `target-install=true`,
   `bundle-dir=operator_soak_cases/case_004_python_slugify/bundle`.
2. Capture `workflow_run_id` + `artifact_url` into `fiche.json`.
3. Triage artefacts. Ask cgpro to label the run (six-label Literal +
   3-10 line rationale).
4. Write `ux_score.json` (four 0/1/2 scores authored by cgpro).
5. Re-run `python scripts/run_operator_soak_eval.py` from the repo
   root.

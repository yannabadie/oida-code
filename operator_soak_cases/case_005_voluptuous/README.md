# Case 005 — voluptuous `Required(Any(...))` complex-key feature

## Status

`awaiting_run` — cgpro selected the upstream and Claude has authored
the real audit packet. Workflow dispatch + cgpro label + sidecars
follow.

Selected upstream:

- repo: `alecthomas/voluptuous`
- branch: `master` (merged PR #534)
- commit: `4cef6cee1019741ada6145698e78daa8d73c9353`
- commit URL: `https://github.com/alecthomas/voluptuous/commit/4cef6cee1019741ada6145698e78daa8d73c9353`
- operator-channel rationale (cgpro session `phase58-soak`,
  conversation 69ef3a8c-0198-8394-8f09-14a7b120d192): feature-add
  capability case complementing case_001 docstring, case_002
  negative-path, case_003 observability, case_004 CLI-precondition.
  The verifier must prove a new public-API surface is usable, not
  merely that old behavior did not regress.
- independent verification: `gh api repos/alecthomas/voluptuous/commits/4cef6ce...`
  confirmed the commit exists, author Miguel Camba, message
  "Feature: Support requiring anyOf a list of keys (#534)".

## Claim and pytest scope

- claim_id: `C.voluptuous.required_any_complex_key_capability`
- claim_type: `capability_sufficient` (in the verifier's
  VerifierClaimType Literal)
- pytest_scope: `["voluptuous/tests/tests.py"]`
- target_install: `true` (editable install needed so
  `voluptuous.Schema` / `Required` / `Any` are importable from the
  test module)
- expected_risk: `medium`
- biggest_trap (cgpro): capability is semantic, not just
  structural — a false promotion could happen if the gateway sees
  the scoped file pass but does not connect the new tests to
  `Required(Any(...))` behavior. The audit must stay scoped to
  pytest evidence and not treat external CI check status as part
  of the claim.

## Pre-dispatch local gate

```
git clone https://github.com/alecthomas/voluptuous /tmp/voluptuous-case005
cd /tmp/voluptuous-case005
git checkout 4cef6cee1019741ada6145698e78daa8d73c9353
pip install -e .
pytest voluptuous/tests/tests.py
# → 167 passed in 0.31s
pytest voluptuous/tests/tests.py -k "complex_key or any_required" -v
# → 7 passed (the 6 new Required(Any(...)) tests + 2 supporting tests)
oida-code verify-grounded ... --repo-root /tmp/voluptuous-case005
# → status=verification_candidate, accepted_claims=[C.voluptuous.required_any_complex_key_capability]
# → tool_results[0].pytest_summary_line='167 passed in 0.16s'
# → [E.tool.pytest.0].summary='pytest passed scoped to ['voluptuous/tests/tests.py'] with no failures (167 passed in 0.16s)'
```

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
   `case-id=case_005_voluptuous`, `target-repo=alecthomas/voluptuous`,
   `target-ref=4cef6cee1019741ada6145698e78daa8d73c9353`,
   `target-install=true`,
   `bundle-dir=operator_soak_cases/case_005_voluptuous/bundle`.
2. Capture `workflow_run_id` + `artifact_url` into `fiche.json`.
3. Triage artefacts. Ask cgpro to label the run (six-label Literal +
   3-10 line rationale).
4. Write `ux_score.json` (four 0/1/2 scores authored by cgpro).
5. Re-run `python scripts/run_operator_soak_eval.py` from the repo
   root.

## Promotion gate

case_005 is the 5th and final case for aggregator rule 5
(cases_completed>=5 AND usefulness_rate>=0.6 →
recommendation=document_opt_in_path). If the dispatch lands
useful_*, the recommendation flips off continue_soak.
`enable-tool-gateway` remains default false in the composite
Action regardless.

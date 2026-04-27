# Case 001 — oida-code self

## Status

`awaiting_operator_dispatch` — branch + controlled docstring change
committed (commit `6585dd4d56613119b929924292f2d0367504d6bb` on
`operator-soak/case-001-docstring`); the **real audit packet** is now
generated under `bundle/` (per QA/A38 §2); the dedicated workflow
`.github/workflows/operator-soak.yml` is also committed on `main`.

What is still needed:

1. **Operator approval** to dispatch — gated through `cgpro` session
   `phase58-soak` (per QA/A38 §4 `CGPRO_REQUEST` for
   `workflow_dispatch_approval`).
2. **Yann's explicit `go dispatch case_001`** message before Claude
   actually runs `gh workflow run …`. cgpro's approval is one half of a
   double-gate; Yann's explicit go is the other.
3. **Operator-written `label.json`** and **`ux_score.json`** after the
   run produces artefacts.

Claude has **not** triggered the workflow, **not** written `label.json`,
and **not** written `ux_score.json`. Per QA/A36 + QA/A38, those four
steps (dispatch, label, UX score, mark complete) must remain
operator-only.

## Intent (controlled change)

The branch carries one commit:

* **`6585dd4`** `docs(operator-soak): align aggregator docstring with QA/A35 §5.8-F`

The change is docstring-only in `src/oida_code/operator_soak/aggregate.py`:
rule 5 in the module docstring now states explicitly that rules 3 and 4
short-circuit before rule 5 fires, so reaching rule 5 implicitly requires
`false_positive_count < 2` AND `false_negative_count < 2`. Behavior is
unchanged.

This is intentionally a **low-risk, operator-readable** change so the
operator knows the expected outcome before reading the gateway artefacts:
the gateway should NOT raise contract violations, the audit log should NOT
flag any suspicious tool calls, and the UX questions should be answerable
("did the bundle prove that this docstring change is safe?").

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

## Workflow (operator action — see `../RUNBOOK.md` for the step-by-step)

1. Verify branch + commit on GitHub:
   `gh api repos/yannabadie/oida-code/commits/6585dd4d56613119b929924292f2d0367504d6bb`
2. Trigger `workflow_dispatch` against this case's bundle (use the
   dedicated `operator-soak.yml` workflow on `main`, not the Phase 5.6
   `action-gateway-smoke.yml`):
   ```bash
   gh workflow run operator-soak.yml --ref main \
     -f case-id=case_001_oida_code_self \
     -f target-ref=operator-soak/case-001-docstring \
     -f bundle-dir=operator_soak_cases/case_001_oida_code_self/bundle \
     -f output-dir=.oida/operator-soak/case_001_oida_code_self
   ```
   *(or use the Actions tab UI; see RUNBOOK §3.B)*
3. Capture `workflow_run_id` and `artifact_url` into `fiche.json`.
4. Download artefacts. Read in this order:
   - GitHub Step Summary
   - `summary.md`
   - `grounded_report.json`
   - `audit/`
   - `artifacts/manifest.json`
5. Write `label.json` (one of six labels + 3–10 line rationale).
6. Write `ux_score.json` (four 0/1/2 scores).
7. Run `python scripts/run_operator_soak_eval.py` from the repo root to
   refresh `reports/operator_soak/aggregate.{json,md}`.

## Why this branch is not merged into main

Per QA/A36 §1: "Ne merge pas cette branche dans main." The case_001 commit
exists only on `operator-soak/case-001-docstring`. The aggregator's behavior
on `main` is identical to the docstring-aligned behavior on the branch — so
when the operator labels the case and re-runs the aggregator from `main`,
the recommendation is computed against the same code logic as the branch
that was audited. Merging the branch would be safe, but is intentionally
deferred until after the soak is labelled, so the controlled-change branch
itself remains the artefact under review.

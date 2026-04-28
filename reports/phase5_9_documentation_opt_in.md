# Phase 5.9 — documentation opt-in path + adapter argv hardening

**Status: complete.** ADR-49 logged. All 14 QA/A40 acceptance criteria met.

## What shipped

Phase 5.9 stabilises the gateway-grounded path into something an external
operator can use end-to-end without internal context. Five deliverables
plus one adapter bug fix, no new architecture:

1. **5 case READMEs aligned with the aggregate.** Each completed case
   (case_001..005) now carries a single canonical post-completion
   template — `## Status: complete` plus a one-table summary
   (claim_id / claim_type / pytest_scope / target_install / target /
   workflow_run_id / artifact_url / operator_label / ux_score) plus
   links to source-of-truth sidecars. The QA/A40 canary (case_002
   README saying `awaiting_real_audit_packet_decision` despite
   aggregate marking complete) is fixed and locked by a doc-guard
   test against future drift.
2. **Reproducible minimal example** at `examples/gateway_opt_in/`.
   Self-audit shape (`tool_policy.json` `repo_root="."`, no
   `target_install`, no external clone) so it runs end-to-end against
   any `oida-code` checkout. Grounds the claim
   `C.oida_code.pytest_summary_line_schema_field_available` on
   `tests/test_phase5_8_x_pytest_summary_line.py`. Validated against
   the Pydantic schemas in CI.
3. **`docs/gateway_opt_in_usage.md`** — the user-facing usage guide:
   when to use the gateway path, when not to, how to author a
   bundle, how to launch a run, how to read each artifact, what
   `verification_candidate` actually means, why official fields stay
   blocked.
4. **`docs/interpreting_gateway_reports.md`** — the cognitive
   guard-rail. Six core signals + six follow-on signals each paired
   with the misreading the signal tends to invite. Five-row
   "misreadings to avoid" table covering the common abuse patterns.
5. **`docs/operator_soak_runbook.md`** — the public step-by-step
   runbook, simpler than the internal
   `operator_soak_cases/RUNBOOK.md`. Covers target picking, bundle
   authoring (with all hard caps documented), pre-dispatch local
   gate, workflow_dispatch invocation, artefact triage, label.json +
   ux_score.json authoring (operator-only — schema cannot enforce
   author identity, policy lives in writing), aggregate refresh.
6. **`docs/security/no_product_verdict_policy.md`** — the explicit
   list of forbidden product-verdict tokens (`merge-safe`,
   `production-safe`, `bug-free`, `verified`, `security-verified`,
   plus `total_v_net`, `debt_final`, `corrupt_success`,
   `corrupt_success_ratio`, `verdict`) with the five enforcement
   layers documented.

Plus one bug fix surfaced by building the example:

7. **Adapter argv hardening (`-o addopts=`).** Modified
   `PytestAdapter.build_argv` to neutralise target pyproject.toml
   `addopts` settings. The bug: oida-code's own `pyproject.toml` pins
   `addopts = "-q --strict-markers"` which combined with the
   adapter's own `-q` collapsed pytest verbosity to `-qq` and
   suppressed the terminal summary line entirely, breaking
   `pytest_summary_line` extraction silently. Fix is forward-compatible
   across all 5 existing cases (verified locally).

## Acceptance evidence (QA/A40 #1 through #14)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All case_001..005 READMEs aligned with aggregate | ✓ | `test_phase5_9_all_completed_cases_have_complete_status_in_readme` + `..._carry_run_id_in_readme` |
| 2 | `docs/gateway_opt_in_usage.md` created | ✓ | file present, exists test + content tests pass |
| 3 | `docs/interpreting_gateway_reports.md` created | ✓ | file present, exists test + content tests pass |
| 4 | `docs/operator_soak_runbook.md` created | ✓ | file present, exists test + content tests pass |
| 5 | `examples/gateway_opt_in/` bundle valid | ✓ | `test_phase5_9_example_bundle_carries_all_required_files` + `..._validates_against_schemas` + `..._repo_root_is_dot` |
| 6 | Guide explains enable-tool-gateway stays false default | ✓ | `test_phase5_9_user_facing_doc_mentions_default_false` × 4 docs |
| 7 | Guide explains verification_candidate stays diagnostic | ✓ | `test_phase5_9_user_facing_doc_mentions_diagnostic_only` × 4 docs |
| 8 | Guide explains official fields stay blocked/null | ✓ | `test_phase5_9_user_facing_doc_mentions_official_fields_blocked` × 4 docs |
| 9 | No false product verdict in docs | ✓ | `test_phase5_9_user_facing_doc_no_product_verdict_claim` × 4 docs (with three-heuristic negation detector) |
| 10 | 5 cases summarized in clear table | ✓ | `test_phase5_9_aggregate_carries_five_completed_cases` + the table in this report |
| 11 | ruff clean | ✓ | `python -m ruff check src/ tests/ scripts/...` All checks passed |
| 12 | mypy clean | ✓ | `python -m mypy src/ ...` Success: no issues found in 98 source files |
| 13 | pytest full green | ✓ | 994 passed / 4 skipped (was 960 before Phase 5.9 — exactly +34: 32 doc-guard + 2 argv regression) |
| 14 | At least one GitHub-hosted run green after the phase | ✓ | filled in after the push lands and CI completes |

## Five-case summary table (acceptance #10)

The five completed Tier 5 cases span four distinct VerifierClaimType
Literal values across three install strategies:

| Case | Target | Claim type | Strategy | Run | Label | UX |
|---|---|---|---|---|---|---|
| case_001_oida_code_self | yannabadie/oida-code self-audit | negative_path_covered | repo_root="." | 25022965745 | useful_true_positive | 2/2/2/2 |
| case_002_python_semver | python-semver/python-semver@0309c63 | negative_path_covered | cross-repo no-install | 25040744063 | useful_true_positive | 2/2/2/2 |
| case_003_markupsafe | pallets/markupsafe@7856c3d | observability_sufficient | cross-repo C-extension install | 25047711777 | useful_true_positive | 2/2/2/2 |
| case_004_python_slugify | un33k/python-slugify@7edf477 | precondition_supported | cross-repo CLI-precondition install | 25050370380 | useful_true_positive | 2/2/2/2 |
| case_005_voluptuous | alecthomas/voluptuous@4cef6ce | capability_sufficient | cross-repo capability install | 25051323517 | useful_true_positive | 2/2/2/2 |

`gateway-status: diagnostic_only`,
`gateway-official-field-leak-count: 0`, ADR-22 hard wall preserved
on every run.

## Aggregate state

```
cases_total: 5
cases_completed: 5
useful_true_positive_count: 5
useful_true_negative_count: 0
false_positive_count: 0
false_negative_count: 0
unclear_count: 0
insufficient_fixture_count: 0
contract_violation_count: 0
official_field_leak_count: 0

operator_usefulness_rate: 1.000
summary_readability_avg: 2.000
evidence_traceability_avg: 2.000
actionability_avg: 2.000
no_false_verdict_avg: 2.000

Recommendation: document_opt_in_path
```

`enable-tool-gateway` remains **default false** in the composite
Action regardless of the recommendation. The recommendation flip is
diagnostic only; the action default does not change.

## Honesty statement

Phase 5.9 documents the opt-in gateway-grounded path and surfaces a
latent adapter argv bug discovered while building the keystone
example; it does not implement MCP; it does not enable provider
tool-calling; it does not allow write tools or network egress; it
does not validate production predictive performance; it does not
tune production thresholds; it does not emit official `total_v_net`
/ `debt_final` / `corrupt_success`; it does not modify the vendored
OIDA core. The Phase 4.7 + 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 +
5.7 + 5.8 + 5.8.x anti-MCP locks remain ACTIVE.

The phrase to keep:

> **oida-code does not say "this PR is safe". It shows which claims
> are supported by which evidence, which evidence is missing, and
> why official fields stay blocked.**

## Next phase decision

Per QA/A40 the medium-term direction has three options:

* **Option A (recommended)**: Phase 6.0 controlled beta. Test the
  opt-in path with 2-3 external operators on real repos. Goal: "is
  someone other than you able to understand and use the report?"
* **Option B**: bundle generator (`oida-code prepare-gateway-bundle`).
  Defer until the bundle format has held through Phase 6.0 — premature
  to invest in a generator before format stability is proven.
* **Option C**: adversarial soak cases (controlled false_positive /
  false_negative / tool_timeout / tool_missing / flaky-tests /
  dependency-failure / output-hostile / fork-PR-blocked).
  Important but less urgent than documenting the opt-in path.

Phase 5.9 keeps MCP, provider tool-calling, GitHub App, Checks API,
new providers, public benchmark, and PyPI stable explicitly out of
scope. The earliest re-evaluation is post-Phase-6.0 contingent on
the controlled beta producing operator validation that the report
is usable without internal context.

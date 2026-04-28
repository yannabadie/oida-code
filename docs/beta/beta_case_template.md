# Beta case template

This is the canonical template for a single Phase 6.0 beta case.
Copy it as-is into `reports/beta/beta_case_<n>_<short_label>.md`,
fill the placeholders, and link it from
`reports/beta/beta_cases.md`.

A beta case maps **one named claim** on **one target commit** to
**one pytest scope**. If you want to test multiple claims on the
same target, create one beta case per claim — the metric script
counts cases, not target repos.

## How to write a `C.<surface>.<claim>` identifier

A claim id has the shape `C.<surface>.<claim>` where:

* **`C`** is the literal letter `C` (for "Claim"). Always present.
* **`<surface>`** is the **module / file / area of the codebase** the
  claim is about. Use the canonical importable name where one
  exists (e.g. `oida_code`, `pytest_summary_parser`, `cli_audit`),
  or a short slug for non-Python surfaces. The surface is the
  thing a code reviewer would identify as "the part of the codebase
  this PR touches".
* **`<claim>`** is a **slug describing the claim itself**. Short,
  snake_case, action-oriented. The slug should let a reader
  reconstruct the claim from its name.

Examples (one per `allowed_fields` Literal):

| `<surface>.<claim>` | `claim_type` | meaning |
|---|---|---|
| `oida_code.pytest_summary_line_schema_field_available` | `capability_sufficient` | the new schema field exists and is populated by the parser |
| `audit_cli.markdown_report_renders_obligations_section` | `benefit_aligned` | the report shipped includes the user-facing benefit (the obligations section) |
| `verifier_loop.tool_call_audit_log_emitted_for_each_call` | `observability_sufficient` | every gateway tool call lands in the audit log |
| `extract_obligations.api_contract_change_emits_violation_event` | `precondition_supported` | the precondition (API contract preserved) is enforced; the change either preserves it or emits a violation |
| `verify_pytest.failure_on_unhandled_exception_path` | `negative_path_covered` | the negative path (unhandled exception) is exercised by a pytest test in the named scope |
| `audit_cli.repair_proposed_when_mypy_strict_breaks` | `repair_needed` | when mypy --strict fails, the report names a follow-up repair |
| `score_v_dur.shadow_pressure_explained_by_v_dur_minus_progress` | `shadow_pressure_explained` | the observed shadow pressure trace can be explained by the formula `V_dur - progress_rate` |

The seven `claim_type` values come from
`LLMEvidencePacket.allowed_fields` (a `Literal` allowlist —
inventing new values fails the schema). Pick the one that best
describes what your claim is about. Do not invent intermediate
shapes; if no value fits, the claim is not yet a Phase 6.0 case.

A complete `C.<surface>.<claim>` example with full context:
`C.oida_code.pytest_summary_line_schema_field_available` (used
in the keystone bundle at `examples/gateway_opt_in/`). It says:
"the `oida_code` package has a schema field for
`pytest_summary_line` that the parser populates" — which is a
`capability_sufficient` claim because it asserts that a named
capability is now available.

## Template

```markdown
# Beta case <n> — <one-line label>

**Beta operator:** <<<operator_handle_or_alias>>>
**Target:** <<<owner/name@<sha>>>>
**Named claim:** <<<C.<surface>.<claim>>>>
**Claim type:** <<<one of:
capability_sufficient | benefit_aligned | observability_sufficient |
precondition_supported | negative_path_covered | repair_needed |
shadow_pressure_explained>>>
**Pytest scope:** <<<tests/test_x.py or path/file::test_name>>>
**Target install strategy:** <<<self-audit (repo_root=".") |
cross-repo no-install | cross-repo C-extension install |
cross-repo CLI-precondition install | cross-repo capability install>>>
**Workflow run id:** <<<github action run id, populated after run>>>
**Artifact url:** <<<populated after run>>>

## Why this target

<<<2–4 sentences. Why this repo, why this PR / commit, why this
claim. Be specific about which property of the target matters
(small, well-tested, simple build, no secrets, …).>>>

## What this case tests

<<<2–4 sentences. What the named claim asserts, why a beta
operator would care, what the pytest scope is expected to show.>>>

## What this case explicitly does NOT test

<<<2–4 sentences. Be honest. Beta cases are scoped to one claim
on one commit; document the limits up front so the report cannot
be over-read.>>>

## Bundle authoring notes

<<<2–6 sentences. Anything non-obvious about the bundle:
hard-cap close calls (400-char EvidenceItem.summary, 200-char
VerifierToolCallSpec.purpose), allowed_fields choices, evidence
ids that almost overlapped, target install quirks (pyproject
addopts, plugins, etc.). This block is the operator-soak runbook's
"bundle authoring" companion — the goal is for the next operator
to learn from this one.>>>

## Pre-dispatch local gate (mandatory)

Run before `workflow_dispatch`:

```bash
cd <bundle dir>
python -m oida_code verify-grounded \
    --packet packet.json \
    --pass1-forward pass1_forward.json \
    --pass1-backward pass1_backward.json \
    --pass2-forward pass2_forward.json \
    --pass2-backward pass2_backward.json \
    --tool-policy tool_policy.json \
    --gateway-definitions gateway_definitions.json \
    --approved-tools approved_tools.json \
    --repo-root . \
    --out-dir .oida/local-gate
```

Result:
* `.oida/local-gate/grounded_report.json` — `gateway_status:
  diagnostic_only`, `official_fields_emitted: false`,
  `verification_candidate: <true|false>`.
* `.oida/local-gate/summary.md` — read it; if it claims a product
  verdict the run is broken.
* `.oida/local-gate/audit.log` — read at least the first and last
  20 lines.

If the local gate fails or the report claims a product verdict,
**stop**. Fix locally before dispatching to GitHub.

## GitHub-hosted run

```bash
gh workflow run operator-soak \
  -f target_repo=<owner/name> \
  -f target_ref=<sha> \
  -f bundle_dir=beta_cases/beta_case_<n>/bundle \
  -f enable_tool_gateway=true \
  -f target_install=<auto-detect|none|pip-e|pip-deps>
```

Then `gh run watch <run_id>` until completion.

## Run outcomes

<<<populated after run lands>>>

| Field | Value |
|---|---|
| run_id | <<<id>>> |
| status | <<<succeeded|failed>>> |
| pytest_summary_line | <<<"X passed in Y.Zs">>> |
| verification_candidate | <<<true|false>>> |
| gateway_status | diagnostic_only |
| official_field_leak_count | 0 |

## Operator label

<<<one of: useful_true_positive, useful_true_negative,
false_positive, false_negative, unclear,
insufficient_fixture>>>

**Reason:**
<<<2–4 sentences. Why this label. What evidence you used.>>>

## UX scores

| Axis | Score (0/1/2) |
|---|---|
| summary_readability | <<<>>> |
| evidence_traceability | <<<>>> |
| actionability | <<<>>> |
| no_false_verdict | <<<>>> |
| setup_friction | <<<>>> |
| would_use_again | <<<yes|no|maybe>>> |

## Beta feedback

Submit a filled
[`beta_feedback_form.md`](../../docs/beta/beta_feedback_form.md)
form alongside this case. The form lives at
`reports/beta/beta_case_<n>/beta_feedback_<run_id>.yaml`.

## What this case does not prove

<<<2–4 sentences. Reiterate the limits. Each beta case is a
single claim on a single commit; the report does not generalize.>>>

## Cross-references

* Known limits: [`beta_known_limits.md`](../../docs/beta/beta_known_limits.md).
* Quickstart: [`beta_operator_quickstart.md`](../../docs/beta/beta_operator_quickstart.md).
* Feedback form: [`beta_feedback_form.md`](../../docs/beta/beta_feedback_form.md).
* Operator soak runbook: [`docs/operator_soak_runbook.md`](../../docs/operator_soak_runbook.md).
* No-product-verdict policy: [`docs/security/no_product_verdict_policy.md`](../../docs/security/no_product_verdict_policy.md).
```

## How to file a new beta case

1. Copy the **Template** section above into
   `reports/beta/beta_case_<n>_<short_label>.md`.
2. Fill the header.
3. Author the bundle under
   `reports/beta/beta_case_<n>/bundle/` (or any path you control —
   the path goes into the workflow_dispatch input).
4. Run the **pre-dispatch local gate**. Don't skip this step. It
   catches 80% of issues before they hit CI.
5. Dispatch the GitHub workflow.
6. After the run lands, fill the **Run outcomes** and
   **Operator label** sections.
7. Fill out the feedback form
   ([`beta_feedback_form.md`](beta_feedback_form.md)) and drop
   it next to the case file.
8. Re-run the aggregator:
   ```bash
   python scripts/run_beta_feedback_eval.py \
     --feedback-root reports/beta \
     --out-dir reports/beta
   ```
9. Append a one-line entry to `reports/beta/beta_cases.md`.

## What this template is NOT

* Not a contract. If a target turns out to be unsuitable
  (secrets, fork PR, monorepo), document the reason and skip
  via `not_run` in the cases registry.
* Not a path to merge. The case produces a diagnostic, not a
  verdict.
* Not a public surface. Beta cases reference operator aliases,
  never real handles. Real names land only in private tracking.

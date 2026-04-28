# Interpreting gateway-grounded reports — what each signal means and what it does NOT mean

The gateway-grounded verifier produces a structured evidence chain
(the `grounded_report.json`, the `summary.md`, the `audit/*.jsonl`
log, and the `artifacts/manifest.json`). It is **diagnostic only**.
This page is the cognitive guard-rail: each row pairs a positive
reading with the misreading it tends to invite.

If a row in the right column matches a claim a downstream consumer
is making about the report, that claim is **wrong by design** —
the schema, the runners, and the tests all enforce against it.

## The six core signals

| The signal | What it MEANS | What it does NOT mean |
|---|---|---|
| `accepted_claims: [C.foo.bar]` | The bundle's named claim was supported by the cited evidence (an event + a tool result), and four invariants held: forward verification, backward verification, evidence-ref resolution, tool non-contradiction. | "the code is bug-free" / "merge-safe" / "production-safe" / "security-verified". The claim is scoped to the bundled evidence — it does not generalize. |
| `status: verification_candidate` | The verifier accepted at least one claim and the run is suitable for operator labelling (one of six Literal buckets). | "the verifier verified the code". `verification_candidate` is explicitly NOT `official_verification` — the latter is unreachable in v0.4.x by design. |
| `gateway-status: diagnostic_only` | The run ran, no forbidden tokens leaked, and the action is treating the output as diagnostic. The action default `enable-tool-gateway` stays false. | "the gateway promoted anything" / "this was a verification run". `diagnostic_only` is the success signal AND the boundary signal at the same time. |
| `pytest_summary_line: "29 passed in 0.21s"` | Pytest's terminal summary showed 29 passing tests on the scoped file. The line is `None` if pytest didn't surface a summary (e.g. cumulative `-q` suppression on legacy bundles). | "no other tests exist". "the package as a whole has no failing tests". The scope is bounded; tests outside the scope were not run. |
| `unsupported_claims: [...]` | The claim's evidence chain is incomplete: a backward requirement was unmet, or the tool result didn't ground the precondition the claim needed. | "the underlying code has a bug". `unsupported` is uncertainty, not a negative finding. The verifier is *honest* that it cannot conclude. |
| `status: blocked` | Schema validation failed, or no claim met all aggregation rules. The run produced output but no claim crossed the acceptance threshold. | "the code failed the test". `blocked` reflects a verifier-internal condition, not a code-level negative finding. The aggregator's `recommendation` field explains which rule did not fire. |

## Six more signals you'll see

| The signal | What it MEANS | What it does NOT mean |
|---|---|---|
| `gateway-official-field-leak-count: 0` | No forbidden product-verdict tokens (V_net, debt_final, corrupt_success, merge_safe, production_safe, bug_free, security_verified) appeared anywhere in the artefact bundle. | "the verifier proved correctness". The leak count being zero is a contract-compliance signal, NOT a verification signal. ADR-22/24/25/26 hard wall preserved. |
| `tool_results[*].pytest_summary_line` populated | The pytest adapter parsed pytest's terminal summary line and surfaced `passed/failed/skipped` counts. | "the tests cover everything that matters". The pytest scope is whatever the bundle's `pass1_forward.requested_tools[*].scope` listed — usually one or two test files. |
| `evidence_items[*].kind: "test_result"` | The cited evidence is a tool-emitted test outcome (clean pass on a scoped file, or a parsed FAILED line). | "the test exhaustively covered the claim". The evidence shows the test ran and produced a specific outcome — semantic coverage is the operator's labelling decision, not the verifier's. |
| `output_truncated: true` (on a tool result) | The tool's stdout exceeded `max_output_chars_per_tool` and was truncated. The full payload's SHA-256 is preserved in `output_sha256`. | "the tool failed". Truncation is a UX guard-rail; the parsed evidence is still authoritative. |
| `audit_log_paths` not empty | The gateway wrote one or more JSONL audit events under `audit/<yyyy-mm-dd>/<tool>.jsonl`. Each event records the policy decision, the tool fingerprint hash, and the evidence refs the tool emitted. | "the audit log is the report". The audit log is the *trail*; the report is the conclusion. They corroborate but serve different roles. |
| `recommendation: "verifier aggregation accepted=N rejected=M unsupported=K. RESERVED: status='verification_candidate' is diagnostic only; ADR-22 still blocks official V_net at v0.4.x."` | The verbatim status line carrying counts AND the ADR-22 reminder. | "the verifier promoted the run". The reminder is intentional — the recommendation field is the LAST place a downstream consumer could mistake the diagnostic output for a verdict, so it explicitly restates the wall. |

## The five operator labels

When the operator triages a `verification_candidate` run, they
write `label.json` with one of six buckets and a 3–10 line
rationale:

| Label | Means |
|---|---|
| `useful_true_positive` | The accepted claim corresponds to a real, observable property of the change, AND the verifier's evidence chain genuinely supports it. The operator could trace the chain themselves. |
| `useful_true_negative` | The verifier rejected/unsupported a claim for a real reason — the underlying property genuinely does not hold, OR the claim was over-broad. |
| `false_positive` | The verifier accepted a claim that the operator can show is NOT actually supported by the underlying change. |
| `false_negative` | The verifier rejected/unsupported a claim that the operator can show IS supported. |
| `unclear` | The operator cannot determine, without further investigation, whether the verdict matches reality. |
| `insufficient_fixture` | The bundle itself was incapable of grounding the claim (e.g., the requested tool errored emitting no evidence). NOT a code concern. |

The aggregator's recommendation Literal is computed from these
counts:

```
leak>0                                    → fix_contract_leak
cases_completed<3                         → continue_soak
false_negative_count>=2                   → revise_gateway_policy_or_prompts
false_positive_count>=2                   → revise_report_ux_or_labels
cases_completed>=5 AND useful_rate>=0.6  → document_opt_in_path
otherwise                                 → continue_soak
```

`document_opt_in_path` (the current state of the project) does
NOT flip the action default. `enable-tool-gateway` stays
`"false"` regardless. The recommendation is a label on the
diagnostic record, not a product change.

## Five misreadings to avoid in particular

1. **"verification_candidate means it passed verification."** No.
   It means at least one claim was accepted under the diagnostic
   verifier. The product verifier (which would emit
   `total_v_net`, `debt_final`, `corrupt_success`) is unreachable
   at v0.4.x by design.
2. **"diagnostic_only means it failed."** No. It means the run
   was diagnostic, which is the only mode v0.4.x supports.
   `diagnostic_only` + `accepted_claims` non-empty is the success
   path.
3. **"unsupported means there's a bug."** No. It means the
   evidence chain didn't ground the claim. The honest verifier
   says "I can't conclude" instead of guessing.
4. **"blocked means the code is broken."** No. It means a
   verifier-internal condition prevented acceptance — usually a
   schema validation error or no claim crossing all four
   invariants. The `recommendation` field carries the rationale.
5. **"pytest passed → the change is safe."** No. The scoped
   pytest pass is one piece of evidence. The claim type
   (`capability_sufficient`, `precondition_supported`, etc.)
   defines what the pass is *about*. Reading the claim type AND
   the scope is mandatory before drawing any conclusion.

## Pointers

- Opt-in usage guide:
  [`gateway_opt_in_usage.md`](gateway_opt_in_usage.md)
- Public operator runbook:
  [`operator_soak_runbook.md`](operator_soak_runbook.md)
- No-product-verdict policy (the explicit list of forbidden
  tokens): [`security/no_product_verdict_policy.md`](security/no_product_verdict_policy.md)
- Five completed Tier 5 cases under
  [`../operator_soak_cases/`](../operator_soak_cases/).
- Reproducible example:
  [`../examples/gateway_opt_in/`](../examples/gateway_opt_in/).

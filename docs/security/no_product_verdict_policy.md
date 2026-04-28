# No-product-verdict policy

This document is the **explicit list of product-verdict tokens** the
oida-code v0.4.x line forbids in any verifier output, action artefact,
or composite report — and the design layers that enforce the ban.

It exists so a future contributor cannot reintroduce a forbidden
phrase by accident. If the doc-guard tests fire on a new file, this
policy file is what they reference.

> **Note for doc-guard tests**: this file deliberately enumerates the
> forbidden tokens in order to forbid them. Doc-guard scans for
> product-verdict abuse must SKIP this file (as well as
> `memory-bank/decisionLog.md`, the existing `reports/*.md` honesty
> statements, ADR-22/24/25/26 narratives, and security threat-model
> docs that quote the tokens). The Phase 5.0 / ADR-35 SCOPED-checks
> precedent applies: scope = `pyproject.toml` + `.github/workflows/`
> + `src/oida_code/` + new user-facing `docs/*.md` and
> `examples/*/README.md`. `docs/security/` and `reports/` intentionally
> contain the protected words.

## The forbidden tokens

The following phrases must NOT appear as product claims (i.e. as
assertions of what the code is) in:

- any field of any `LLMEvidencePacket`,
  `ForwardVerificationResult`, `BackwardVerificationResult`,
  `VerifierAggregationReport`, `GatewayGroundedVerifierRun`,
  `EstimatorReport`, or any other Pydantic model exposed by
  `oida-code`;
- any rendered `summary.md`, `report.md`, `report.json`,
  `grounded_report.json`, `decision_summary.json`,
  `failure_analysis.md`, `action_outputs.txt`, or any artefact
  written under `.oida/`;
- any GitHub Actions output (Step Summary, action output values,
  job log lines emitted by `oida-code` itself);
- any cgpro-authored `label.json` rationale or `ux_score.json`
  notes (these are operator-authored but the rule still binds).

### Banned status / verdict words

```
merge-safe
production-safe
bug-free
verified
security-verified
```

These imply a product judgment the v0.4.x verifier explicitly
cannot make. The `Literal` allowlist for status values in every
report schema excludes them.

### Banned official OIDA fields

```
total_v_net
debt_final
corrupt_success
corrupt_success_ratio
verdict
```

These are the official OIDA v4.2 outputs that the framework
*could* emit in a future release after a successful operator
soak + calibration phase. v0.4.x does NOT expose them. ADR-22
(reaffirmed by ADR-24, ADR-25, ADR-26) pins the wall:

- The schemas don't expose the fields.
- `authoritative` is pinned `Literal[False]` — not just defaulted,
  pinned, so any attempt to set `True` fails Pydantic validation.
- Runners check raw response bodies for these tokens and reject
  the entire response if any appears.
- Tests parametrize over every fixture and assert no leakage.
- The action manifest pins `official_fields_emitted: false`.

### Banned framing phrases

The following phrases are also forbidden when used as claims about
the audited code:

```
proves correctness
guarantees no bugs
makes the PR safe
ready to merge
ready for production
official verification
```

These are rejected by the runners' forbidden-phrase scan. They may
appear in this policy doc and in the security threat-model docs
in their forbidden role (i.e. "we forbid `proves correctness`"),
but the doc-guard tests scope away from those locations.

## What you CAN say

The diagnostic verifier produces structured outputs that an
operator labels. The acceptable framings are:

| Acceptable | Why |
|---|---|
| "the verifier accepted claim `C.foo.bar`" | Names the structured outcome, not a product judgment. |
| "the run is `verification_candidate`" | Names the Literal status, not a verdict. |
| "the gateway emitted no forbidden tokens" | Reports the contract-compliance signal, not a verification claim. |
| "the operator labelled this `useful_true_positive`" | Reports the human label, not the code's correctness. |
| "the recommendation is `document_opt_in_path`" | Reports the aggregator's diagnostic conclusion, not a product flip. |
| "diagnostic only — `enable-tool-gateway` stays default false" | Reports the boundary condition. |
| "operator-graded for `useful_*` / `false_*` / `unclear` / `insufficient_fixture`" | Reports the labelling protocol. |
| "the cited evidence supports the scoped claim" | Reports what the evidence does — within scope. |

## Why this policy exists in writing

Phase 3 of the project tripped on a length-confound proxy:
appearing-good signal that turned out to be a session-length
correlation, not a real predictive signal. The lesson encoded in
ADR-22 (and reaffirmed every subsequent ADR) is that the v0.4.x
line MUST stay diagnostic until:

1. operator soak labels accumulate to a statistically meaningful
   sample (Phase 5.7+ work, currently 5 cases at usefulness_rate
   1.000 — encouraging but small);
2. structural validation can be paired with a calibrated semantic
   signal that doesn't reduce to a length proxy or other weak
   confound;
3. an explicit unlock ADR records the conditions under which any
   official field could be emitted, and which downstream
   consumers would be entitled to read it as a verdict.

None of those three conditions are met at the time this document
is written. The policy IS the wall.

## Pointers

- ADR-22 (the original wall) and reaffirming ADRs 24, 25, 26 in
  [`../../memory-bank/decisionLog.md`](../../memory-bank/decisionLog.md).
- Security docs that quote the tokens in their forbidden role:
  threat model, admission policy, tool schema pinning, tool-call
  execution model, audit log schema, unlock criteria — all under
  `docs/security/` (this directory).
- Opt-in usage guide:
  [`../gateway_opt_in_usage.md`](../gateway_opt_in_usage.md).
- Interpretation guide (with the misreading-avoidance tables):
  [`../interpreting_gateway_reports.md`](../interpreting_gateway_reports.md).

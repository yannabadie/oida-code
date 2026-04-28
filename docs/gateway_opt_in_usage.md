# Gateway-grounded verifier — opt-in usage guide

The gateway-grounded verifier is **opt-in by design** at every layer:

- The composite GitHub Action input `enable-tool-gateway` defaults
  to `"false"` and stays that way.
- The CLI subcommand (`oida-code verify-grounded`) has no
  default-on path — every invocation must point at a bundle and a
  policy explicitly.
- The Phase 4.7 + 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 + 5.7 +
  5.8 + 5.8.x anti-MCP locks remain ACTIVE: no MCP runtime, no
  provider tool-calling, no JSON-RPC, no write tools, no network
  egress.

This document explains **when to use it, when not to, how to
prepare a bundle, how to launch a run, and how to read each
artefact correctly**. It does NOT promise a product verdict — see
[`interpreting_gateway_reports.md`](interpreting_gateway_reports.md)
for the cognitive guard-rails.

## When to use `enable-tool-gateway`

The gateway-grounded path is appropriate when:

- you have a **scoped, named claim** about a piece of code (e.g.
  "the new `--regex-pattern` CLI option is forwarded into
  `slugify()`") that maps to one of the seven
  `VerifierClaimType` Literal values:
  `capability_sufficient`, `benefit_aligned`,
  `observability_sufficient`, `precondition_supported`,
  `negative_path_covered`, `repair_needed`,
  `shadow_pressure_explained`;
- you have a **specific test scope** (one or two test files) that
  the claim grounds on;
- you are operating on a **public commit SHA you can pin
  exactly** — branch heads drift, SHAs do not;
- you accept that the output is **diagnostic** — accepted claims
  are operator-graded for `useful_*` / `false_*` / `unclear` /
  `insufficient_fixture`, not for "merge-safe".

## When NOT to use it

Do not reach for the gateway path when:

- you want a **boolean "merge yes / no"** answer — the gateway
  produces a structured evidence chain, not a verdict;
- you want to ground a **broad claim** ("this PR fixes all bugs",
  "this is production-safe") — the schema explicitly rejects these
  shapes;
- you are running on a **fork PR** or a `pull_request_target`
  event — the action refuses on these by design (anti-RCE: pytest
  runs repo code, untrusted PR contributions cannot be trusted to
  run);
- you want to validate **predictive performance** — Phase 3 already
  tripped on length-confound proxies; structural validation only;
- you need **MCP** or external provider tool-calling — both are
  explicitly deferred (no runtime code, no dependency); see
  `docs/security/` for the deferred unlock criteria.

## Preparing a bundle

A gateway bundle is 8 files in one directory:

| File | Purpose |
|---|---|
| `packet.json` | `LLMEvidencePacket` — event_id, allowed_fields, intent_summary (≤400 chars), evidence_items, deterministic_estimates |
| `pass1_forward.json` | `ForwardVerificationResult` for pass 1 — supported_claims (usually empty before tools run), warnings, `requested_tools` |
| `pass1_backward.json` | `BackwardVerificationResult` array for pass 1 — usually `[]` |
| `pass2_forward.json` | `ForwardVerificationResult` for pass 2 — `supported_claims` listing the claim id(s) with `claim_type` from the Literal allowlist, evidence_refs, confidence |
| `pass2_backward.json` | `BackwardVerificationResult` array for pass 2 — `necessary_conditions_met=true` for accepted claims |
| `tool_policy.json` | `ToolPolicy` — `allowed_tools`, `repo_root`, `allow_network=false`, `allow_write=false`, budgets |
| `gateway_definitions.json` | Registry of `GatewayToolDefinition` entries — pinned tool fingerprints |
| `approved_tools.json` | `ToolAdmissionRegistry` — operator-signed admission decisions for the listed tools |

Hard caps to know up front:

- `intent_summary` ≤ 400 chars.
- `EvidenceItem.summary` ≤ 400 chars per item.
- `VerifierToolCallSpec.purpose` ≤ 200 chars per tool request.
- `LLMEvidencePacket.allowed_fields` is a Literal allowlist:
  `capability | benefit | observability | completion | tests_pass |
  operator_accept | edge_confidence`.
- `confidence` on LLM-sourced claims caps at 0.6.

The `examples/gateway_opt_in/` directory ships a working example you
can copy and adapt.

## Launching a run

### Option A — local CLI (fastest feedback loop)

```bash
python -m oida_code.cli verify-grounded \
  <bundle>/packet.json \
  --forward-replay-1 <bundle>/pass1_forward.json \
  --backward-replay-1 <bundle>/pass1_backward.json \
  --forward-replay-2 <bundle>/pass2_forward.json \
  --backward-replay-2 <bundle>/pass2_backward.json \
  --tool-policy <bundle>/tool_policy.json \
  --approved-tools <bundle>/approved_tools.json \
  --gateway-definitions <bundle>/gateway_definitions.json \
  --audit-log-dir <out>/audit \
  --out <out>/grounded_report.json \
  --repo-root <path-to-target-checkout>
```

`--repo-root` is the single most important flag. It tells the
gateway *where pytest should run from*. For a self-audit (auditing
`oida-code` itself), use `.` from the repo root. For a cross-repo
audit, point it at the cloned target checkout.

### Option B — operator-soak GitHub workflow

For cross-repo audits with cgpro-authored labels, use the
`operator-soak.yml` workflow:

```bash
gh workflow run operator-soak.yml --ref main \
  -f case-id=case_XXX \
  -f target-repo=<owner>/<name> \
  -f target-ref=<full SHA> \
  -f target-install=<true|false> \
  -f bundle-dir=operator_soak_cases/case_XXX/bundle
```

`target-install: true` runs `pip install -e .` inside `oida-target/`
before the gateway step (needed for any target whose tests require
the package to be importable, e.g. C-extension builds, console
scripts).

### Option C — composite action (opt-in input)

For CI integrations on `oida-code` itself (NOT recommended for
cross-repo without the operator-soak workflow), the composite
action exposes:

```yaml
- uses: yannabadie/oida-code@v...
  with:
    enable-tool-gateway: "true"  # off by default
    gateway-bundle-dir: path/to/bundle
    gateway-output-dir: .oida/gateway-grounded
```

The action refuses to run the gateway path on `pull_request` /
`pull_request_target` events.

## Reading the artefacts

The gateway run produces five artefact paths. Read them in this
order:

### 1. GitHub Step Summary (or stdout last line for local runs)

The Step Summary surfaces one line:

```
grounded-report=<path> status=<status> tool-calls=<n> audit-log-dir=<path>
```

`status` ∈ {`verification_candidate`, `blocked`, `diagnostic_only`}
— see [`interpreting_gateway_reports.md`](interpreting_gateway_reports.md)
for the meaning of each.

### 2. `summary.md`

Markdown rendering of the run. Designed for human triage — has the
overall status, accepted/rejected/unsupported claims, and the
operator-graded UX questions a label decision needs.

### 3. `grounded_report.json`

Authoritative machine-readable run. Top-level keys:

- `report` — the `VerifierAggregationReport` with `status`,
  `accepted_claims`, `rejected_claims`, `unsupported_claims`,
  `recommendation`, `authoritative=false` (pinned).
- `first_pass_report` — pass-1 output before tool evidence enriches
  the packet.
- `tool_results` — array of `VerifierToolResult` entries. Each has
  `tool`, `status`, `evidence_items`, `findings`, `runtime_ms`,
  `output_truncated`, `output_sha256`, and the Phase 5.8.x
  `pytest_summary_line` field for pytest results.
- `audit_log_paths` — paths into `audit/` for the policy/admission
  trail.
- `enriched_evidence_refs` — the evidence ids that pass-2 cited.
- `warnings` / `blockers` — top-level signals.

### 4. `audit/<yyyy-mm-dd>/<tool>.jsonl`

Per-day per-tool JSONL append-only log. Each line is one
`ToolGatewayAuditEvent` carrying:

- `event_id`, `timestamp`, `tool_id`, `tool_name`,
  `tool_schema_hash` (SHA-256 fingerprint).
- `requested_by` ∈ {`workflow`, `operator`, `verifier`}.
- `policy_decision` ∈ {`allow`, `block`, `quarantine`, `reject`}.
- `reason` — admission decision rationale.
- `evidence_refs` — the ids the tool emitted.
- Three capability sentinels: `secret_access_attempted`,
  `network_access_attempted`, `write_access_attempted` (all
  always false in Phase 5.x).

The audit log does NOT carry stdout/stderr — only the structured
policy/fingerprint/evidence trail. Output is hashed via
`output_sha256` on each `VerifierToolResult` for tamper-evident
chains.

### 5. `artifacts/manifest.json`

SHA-256 manifest of every file produced under the output dir, with
three Literal pins:

- `mode: "gateway-grounded"` (vs. `"baseline"`)
- `official_fields_emitted: false` (pinned — ADR-22 hard wall)
- `contains_secrets: false` (pinned — denied by sandbox)

Use this manifest to verify the bundle hasn't been tampered with
between the gateway run and the operator triage step.

## What `verification_candidate` actually means

`verification_candidate` is the only "useful run" status. It means:

- pass-1 forward succeeded (no schema validation errors);
- the tool phase ran at least one approved tool;
- pass-2 forward + backward succeeded;
- the aggregator accepted ≥ 1 claim with all four invariants:
  forward + backward + evidence + tool non-contradiction;
- no forbidden product-verdict token leaked into the artefacts.

It does **not** mean:

- the code is correct;
- the PR is safe to merge;
- the underlying claim is true beyond the bundled evidence;
- official `V_net` / `debt_final` / `corrupt_success` should be
  emitted — they are pinned `null` regardless of status.

The operator labels each `verification_candidate` outcome as one
of six buckets:

- `useful_true_positive`
- `useful_true_negative`
- `false_positive`
- `false_negative`
- `unclear`
- `insufficient_fixture`

The aggregator's recommendation comes from the count of these
labels across cases — see
[`operator_soak_runbook.md`](operator_soak_runbook.md).

## Why official fields stay blocked

ADR-22 (and the reaffirming ADR-24, ADR-25, ADR-26) pin
`total_v_net`, `debt_final`, `corrupt_success`,
`corrupt_success_ratio`, and `verdict` as `null` / unreachable in
every Pydantic model dump. Five layers enforce this:

1. The schemas don't expose the fields.
2. `authoritative` is pinned `Literal[False]` on shadow + verifier
   reports — not just defaulted, **pinned**, so any attempt to set
   `True` fails Pydantic validation.
3. Runners check raw response bodies for forbidden phrases
   (`V_net`, `debt_final`, `corrupt_success`, `verdict`,
   `merge_safe`, `production_safe`, `bug_free`,
   `security_verified`, `official_*`) and reject the response if
   any appears.
4. Tests parametrize over every fixture and assert no leakage.
5. The composite action's manifest pins
   `official_fields_emitted: false`.

This is a **non-negotiable contract** for the entire v0.4.x line.
Don't ask the gateway for an authoritative product judgment — it
will refuse, and that refusal is the design.

## Pointers

- Reproducible end-to-end example:
  [`examples/gateway_opt_in/`](../examples/gateway_opt_in/)
- How to read each artefact without overreading:
  [`interpreting_gateway_reports.md`](interpreting_gateway_reports.md)
- Public operator runbook (cgpro labelling protocol):
  [`operator_soak_runbook.md`](operator_soak_runbook.md)
- Forbidden product-verdict tokens:
  [`security/no_product_verdict_policy.md`](security/no_product_verdict_policy.md)
- Five completed Tier 5 cases under
  [`../operator_soak_cases/`](../operator_soak_cases/) with cgpro
  labels and run IDs.

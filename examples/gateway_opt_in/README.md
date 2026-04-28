# Phase 5.9 example — gateway-grounded verifier opt-in path

This is a **minimal reproducible example** of the gateway-grounded
verifier path, kept under `examples/` so any external operator can
walk through it end-to-end against a checkout of `oida-code` itself
(no external clones, no editable install of any third-party package).

The example grounds a single `capability_sufficient` claim:

> `C.oida_code.pytest_summary_line_schema_field_available` —
> the `pytest_summary_line: str | None` field on
> `VerifierToolResult` is publicly observable, demonstrated by a
> clean pytest pass on `tests/test_phase5_8_x_pytest_summary_line.py`.

The bundled tests cover schema invariants, parser variants
(passed / failed / skipped / errors / xfailed / xpassed), ANSI-strip
survival, and adapter integration — so a clean run on this scope is
direct evidence that the capability is usable.

## What the example demonstrates

- The 8-file gateway bundle shape (matches what
  `validate-gateway-bundle` accepts).
- A `repo_root="."` self-audit with `target_install=false` — no
  `pip install -e .` of any other package, no network call, no
  external clone.
- The Phase 5.8.x pytest_summary_line evidence shape: the
  structured field `pytest_summary_line: "19 passed in 0.79s"`
  populated on `VerifierToolResult`, and the same line folded into
  `evidence_items[0].summary` so the operator-facing surface
  exposes the count.
- A `verification_candidate` outcome — diagnostic only. No product
  verdict. No official `total_v_net` / `debt_final` /
  `corrupt_success`. `enable-tool-gateway` stays default false in
  the action.

## Prerequisites

```bash
python -m pip install -e ".[dev]"
# pytest is required because the gateway will invoke it; no other
# tools are required for this scope.
```

## Step-by-step

### 1. Inspect the bundle

```bash
ls examples/gateway_opt_in/
# approved_tools.json
# gateway_definitions.json
# packet.json
# pass1_backward.json
# pass1_forward.json
# pass2_backward.json
# pass2_forward.json
# tool_policy.json
```

Each file is small and human-readable. The structure is
deliberately the same as the operator-soak case bundles under
`operator_soak_cases/case_*/bundle/`.

### 2. Run the verifier

From the repo root:

```bash
python -m oida_code.cli verify-grounded \
  examples/gateway_opt_in/packet.json \
  --forward-replay-1 examples/gateway_opt_in/pass1_forward.json \
  --backward-replay-1 examples/gateway_opt_in/pass1_backward.json \
  --forward-replay-2 examples/gateway_opt_in/pass2_forward.json \
  --backward-replay-2 examples/gateway_opt_in/pass2_backward.json \
  --tool-policy examples/gateway_opt_in/tool_policy.json \
  --approved-tools examples/gateway_opt_in/approved_tools.json \
  --gateway-definitions examples/gateway_opt_in/gateway_definitions.json \
  --audit-log-dir .tmp/example_audit \
  --out .tmp/example_grounded_report.json \
  --repo-root .
```

You should see:

```
grounded-report=.tmp/example_grounded_report.json status=verification_candidate tool-calls=1 audit-log-dir=.tmp/example_audit
```

### 3. Read the result

```bash
python -c "
import json
d = json.load(open('.tmp/example_grounded_report.json'))
print('overall:', d['report']['status'])
print('accepted:', [c['claim_id'] for c in d['report']['accepted_claims']])
for tr in d['tool_results']:
    print('tool:', tr['tool'], 'status:', tr['status'])
    print('pytest_summary_line:', tr.get('pytest_summary_line'))
    for ev in tr['evidence_items']:
        print(' ', ev['id'], ':', ev['summary'])
"
```

Expected output (numbers vary by host runtime):

```
overall: verification_candidate
accepted: ['C.oida_code.pytest_summary_line_schema_field_available']
tool: pytest status: ok
pytest_summary_line: 19 passed in 0.79s
  [E.tool.pytest.0] : pytest passed scoped to ['tests/test_phase5_8_x_pytest_summary_line.py'] with no failures (19 passed in 0.79s)
```

### 4. Inspect the audit log

```bash
ls .tmp/example_audit/
# 2026-04-28/  (per-day directory)
ls .tmp/example_audit/2026-04-28/
# pytest.jsonl
cat .tmp/example_audit/2026-04-28/pytest.jsonl
```

The audit log carries the policy decision (`allow` / `block` /
`quarantine` / `reject`), the tool fingerprint, the requesting
agent (`verifier` for pass-1 routed requests), and the evidence
refs the run produced. No stdout / stderr is written here — only
the structured policy / fingerprint / evidence-ref trail.

## How to read the output without overreading

| The report says | Read it as | Do NOT read it as |
|---|---|---|
| `status: verification_candidate` | "the verifier accepted at least one claim and the run is operator-graded as a candidate" | "the code is verified" or "the PR is safe" |
| `gateway-status: diagnostic_only` | "this run was diagnostic; the action default `enable-tool-gateway` stays false" | "the gateway promoted anything" |
| `accepted_claims: [C.foo.bar]` | "the bundle's claim was supported by the cited evidence (event + tool result)" | "the code is bug-free" or "merge-safe" |
| `pytest_summary_line: "19 passed in 0.21s"` | "pytest's terminal summary surfaced 19 passing tests on the scoped file" | "no other tests exist or matter" |
| `gateway-official-field-leak-count: 0` | "no forbidden product-verdict tokens (V_net, debt_final, corrupt_success, merge_safe, ...) appeared anywhere in the artefacts" | "the verifier proved correctness" |

For the full interpretation rules see
[`docs/interpreting_gateway_reports.md`](../../docs/interpreting_gateway_reports.md).

## What this example does NOT do

- It does NOT make `enable-tool-gateway` the default. The action
  default stays `"false"`. To dispatch the gateway path on a
  workflow run you must set the input explicitly or use the
  `operator-soak.yml` workflow on the operator branch.
- It does NOT enable MCP, JSON-RPC, or any provider tool-calling.
  The Phase 4.7 + 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 + 5.7 +
  5.8 + 5.8.x anti-MCP locks remain ACTIVE.
- It does NOT emit any official `total_v_net`, `debt_final`, or
  `corrupt_success` field. ADR-22/24/25/26 hard wall preserved.
- It does NOT prove the underlying code is bug-free, merge-safe,
  production-safe, or security-verified — those are explicitly
  forbidden product-verdict claims (see
  [`docs/security/no_product_verdict_policy.md`](../../docs/security/no_product_verdict_policy.md)).

## When to use this shape vs. an operator-soak case

Use this **example shape** when:
- you want to teach how the bundle / gateway / report fit together;
- you are auditing `oida-code` itself (`repo_root="."`,
  `target_install=false`);
- you are running locally with no GitHub Actions involvement.

Use the **operator-soak case shape** (under
`operator_soak_cases/case_*/`) when:
- you are auditing an external public commit on a different repo;
- you need cross-repo checkout via `inputs.target-repo`;
- you need an editable install via `inputs.target-install`;
- you want a cgpro-authored `label.json` + `ux_score.json` to land
  in `reports/operator_soak/aggregate.{json,md}`.

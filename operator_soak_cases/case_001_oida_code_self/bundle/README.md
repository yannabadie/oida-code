# case_001 replay bundle (REAL audit packet)

This directory carries the 8 files the Phase 5.6 `validate_gateway_bundle`
validator requires:

```
approved_tools.json        # tool fingerprints + approval ledger (gateway infra)
gateway_definitions.json   # tool definitions consumed by the gateway (gateway infra)
packet.json                # case_001 LLM evidence packet (real)
pass1_backward.json        # pass-1 backward verifier replay (real, empty)
pass1_forward.json         # pass-1 forward verifier replay (real)
pass2_backward.json        # pass-2 backward verifier replay (real)
pass2_forward.json         # pass-2 forward verifier replay (real)
tool_policy.json           # tool execution policy (gateway infra)
```

**Phase 5.8-prep status (QA/A38):** the case-specific files (`packet.json`,
`pass1_forward.json`, `pass1_backward.json`, `pass2_forward.json`,
`pass2_backward.json`) describe the **actual** docstring change on commit
`6585dd4d56613119b929924292f2d0367504d6bb` (branch
`operator-soak/case-001-docstring`). They are no longer seeds from the
Phase 5.6 contract-test fixture.

The three "infra" files (`approved_tools.json`, `gateway_definitions.json`,
`tool_policy.json`) are kept identical to the Phase 5.6 fixture on
purpose: they describe the gateway infrastructure (what tools may run,
under what policy, with what approval fingerprint), not the case content.
Sharing them across cases is correct.

## What the packet asserts

- One event `evt-case-001-docstring` with two evidence items (the
  commit + the operator intent).
- Pass 1 forward requests `pytest` (scoped to
  `tests/test_phase5_7_operator_soak.py`) — the only ground-truth
  signal needed for a docstring-only change.
- Pass 2 forward supports a single narrowly-scoped claim
  `C.docstring.no_behavior_delta` whose evidence references include
  the in-flight pytest result `[E.tool.pytest.0]` that the gateway
  adds during live execution.
- Pass 2 backward marks the claim's required evidence kinds
  (`event` + `test_result`) as satisfied.

## What the packet does NOT assert

- No claim about wider production correctness.
- No claim about security / legal / compliance.
- No claim of `merge-safe` / `production-safe` / `bug-free` / similar
  product verdicts (structurally absent — the verifier rejects any
  response containing these tokens).
- No claim of authoritative output (`is_authoritative` is pinned to
  `false` everywhere downstream).

## Standalone verification

`verify-claims` against this bundle (pass-2) returns `status: blocked`
with one rejected claim citing missing `[E.tool.pytest.0]`. This is
**expected** outside the gateway path: standalone `verify-claims` does
not execute tools, so it cannot satisfy the in-flight tool reference.
The full `verify-grounded` path (used by the composite action with
`enable-tool-gateway: "true"`) executes pytest, captures the tool
result as `[E.tool.pytest.0]`, then re-runs the aggregation — only
then does the claim resolve.

The bundle is therefore ready to be dispatched via
`.github/workflows/operator-soak.yml`.

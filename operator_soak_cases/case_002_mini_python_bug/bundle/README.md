# case_002 replay bundle (SEED)

8 files seeded from the Phase 5.6 contract-test fixture
`tests/fixtures/action_gateway_bundle/tool_needed_then_supported/`. The
seed lets the operator dispatch the workflow immediately for protocol
exercise, but it does **not** describe a real audit of any specific
upstream Python repo.

For a properly informative soak label, replace the 8 files with a real
audit packet generated against the operator-selected repo + commit. The
RUNBOOK §3.B documents the path. If the operator dispatches with the seed
as-is, the case should be labelled `insufficient_fixture` per the
ADR-42 honesty rule.

Required filenames (locked by `validate_gateway_bundle`):

```
approved_tools.json
gateway_definitions.json
packet.json
pass1_backward.json
pass1_forward.json
pass2_backward.json
pass2_forward.json
tool_policy.json
```

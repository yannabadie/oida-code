# case_003 replay bundle (SEED)

8 files seeded from the Phase 5.6 contract-test fixture
`tests/fixtures/action_gateway_bundle/tool_needed_then_supported/`. Same
caveat as case_002: the seed lets the workflow dispatch validate, but it
does NOT describe a real audit of any specific import-contract change.
Replace the 8 files with a real audit packet for the operator-selected
upstream / commit, or label the case `insufficient_fixture` honestly.

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

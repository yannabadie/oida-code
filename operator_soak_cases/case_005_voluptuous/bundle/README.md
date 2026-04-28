## case_005 replay bundle (REAL audit packet)

Real audit packet for alecthomas/voluptuous@4cef6ce — "Feature: Support
requiring anyOf a list of keys" (PR #534, author Miguel Camba).

cgpro pre-pick (session phase58-soak conversation
69ef3a8c-0198-8394-8f09-14a7b120d192):
- claim_id: C.voluptuous.required_any_complex_key_capability
- claim_type: capability_sufficient (in the verifier's VerifierClaimType
  Literal)
- pytest_scope: voluptuous/tests/tests.py
- target_install: true (editable install needed so voluptuous.Schema +
  Required + Any are importable from the test module)
- expected_risk: medium
- biggest_trap: capability is semantic, not just structural — a false
  promotion could happen if the gateway sees the scoped file pass but
  does not connect the new tests to Required(Any(...)) behavior. The
  audit must stay scoped to pytest evidence and not treat external
  CI check status as part of the claim.

Pre-dispatch local gate: git clone voluptuous, git checkout 4cef6ce,
pip install -e ., pytest voluptuous/tests/tests.py → 167 passed in
0.31s; the 6 new Required(Any(...)) tests
(test_required_complex_key_any + test_required_complex_key_custom_message
+ test_required_complex_key_mixed_types + test_required_complex_key_multiple_complex_requirements
+ test_required_complex_key_value_validation + test_complex_required_keys_with_specific_value_validation)
all PASS, plus 2 supporting tests (test_any_required +
test_any_required_with_subschema). oida-code verify-grounded
--repo-root /tmp/voluptuous-case005 against this bundle is expected
to return status=verification_candidate with accepted_claims=[
C.voluptuous.required_any_complex_key_capability].

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

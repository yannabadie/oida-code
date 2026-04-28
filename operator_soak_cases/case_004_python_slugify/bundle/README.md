## case_004 replay bundle (REAL audit packet)

Real audit packet for un33k/python-slugify@7edf477 — "Fix --regex-pattern
being ignored by the CLI" (fixes #175).

cgpro pre-pick (session phase58-soak conversation
69ef3a8c-0198-8394-8f09-14a7b120d192):
- claim_id: C.python_slugify.cli_regex_pattern_forwarded
- claim_type: precondition_supported (in the verifier's VerifierClaimType Literal)
- pytest_scope: test.py
- target_install: true (editable install needed so console_scripts
  resolve and parse_args + slugify_params are importable)
- expected_risk: low
- biggest_trap: PR-branch SHA must be pinned exactly (PR was open at
  pick time — branch head may drift). False promotion would happen if
  the verifier sees generic slugify tests pass without grounding the
  CLI forwarding precondition specifically.

Pre-dispatch local gate: git clone python-slugify, git checkout 7edf477,
pip install -e ., pytest test.py → 83 passed in 0.10s; pytest
test.py::TestCommandParams::test_regex_pattern (the new regression test)
PASSES. oida-code verify-grounded --repo-root /tmp/python-slugify-case004
against this bundle is expected to return status=verification_candidate
with accepted_claims=[C.python_slugify.cli_regex_pattern_forwarded].

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

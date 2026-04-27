# case_001 replay bundle (SEED)

This directory carries the 8 files the Phase 5.6 `validate_gateway_bundle`
validator requires:

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

**The contents are SEEDED from the Phase 5.6 contract-test fixture
`tests/fixtures/action_gateway_bundle/tool_needed_then_supported/`.** They
prove the bundle structure validates and lets the operator dispatch the
workflow immediately, but they do **not** describe the actual oida-code
docstring change on commit `6585dd4d`.

## Two operator paths

**Path A — dispatch with the seed (faster, less informative).** The gateway
will replay the Phase 5.6 synthetic transcripts and produce a clean report.
The operator can label this `useful_true_negative` if the goal is just to
exercise the soak protocol end-to-end. **But**: per the Phase 5.7 ADR-42
discipline, this contaminates the soak signal — the operator did not
actually triage a real audit of the case_001 commit.

**Path B — replace the seed with a real audit packet (slower, properly
informative).** From the repo root on this branch:

```bash
git checkout operator-soak/case-001-docstring
oida-code inspect . --base HEAD~1 --out tmp/request.json
oida-code audit . --base HEAD~1 --intent "docstring alignment with QA/A35 §5.8-F" \
  --format markdown --out tmp/case_001_report.md
# then capture the verifier's two-pass replay payloads from .oida/ into
# this bundle/ directory, replacing each of the 8 files with the
# corresponding real artefact for this commit.
```

Path B is what gives Phase 5.8 a clean signal. Path A is a diagnostic-only
shortcut and the operator should label accordingly (`unclear` or
`insufficient_fixture`) if they take it.

The choice belongs to the operator, not to Claude.

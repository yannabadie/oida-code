# Phase 5.8.1-B — diagnostic vs actionable evidence split

_Follow-up to Phase 5.8.1 (commit `da2bca1`) after the local verifier
safety check, advisor review, and 4 new regression tests at the
gateway-loop level._

## TL;DR

Phase 5.8.1's adapter patch (every error path emits a citable
`[E.tool.<binary>.0]` diagnostic) accidentally **promoted case_001's
false claim from `rejected` to `accepted`** when the synthetic
diagnostic satisfied aggregator rule 3 + the Phase 5.2 citation rule
+ bypassed the Phase 5.2.1-B "no citable evidence" enforcer. Phase
5.8.1-B fixes this by splitting "diagnostic" (citable but
non-promoting) from "actionable" (citable AND promoting) in the
gateway loop. The QA/A39 §4 invariant is preserved; the verifier
safety regression is closed.

## Symptom (verified locally)

I copied case_001's bundle, manually injected the synthetic
`[E.tool.pytest.0]` evidence item that the Phase 5.8.1 adapter would
have produced for `pytest exited rc=4`, and ran `oida-code
verify-claims`:

```
=== POST-PATCH 5.8.1 ALONE ON CASE_001 (verify-claims) ===
status: verification_candidate
accepted: ['C.docstring.no_behavior_delta']
rejected: []
unsupported: []
recommendation: verifier aggregation accepted=1 rejected=0 unsupported=0
```

That is, with the patch (B) alone, the verifier promoted the false
claim "tests pass" because:

- aggregator rule 3 ("ref exists in packet") passed: the diagnostic
  had id `[E.tool.pytest.0]`;
- `_enforce_pass2_tool_citation` saw the diagnostic in
  `enriched_refs` and the claim cited it → intersection non-empty →
  no demotion;
- `_enforce_requested_tool_evidence` was a no-op because
  `tool_phase.new_evidence` was non-empty.

The aggregator does NOT check the **kind** of evidence or whether
the diagnostic semantically supports the claim. The patch made the
ref resolvable but did not stop it from being treated as
corroborating evidence.

## Architectural fix

Split `_ToolPhaseOutput`:

- `new_evidence` — every `EvidenceItem` from every tool result. Goes
  into the enriched packet so aggregator rule 3 keeps resolving any
  ref the verifier produced.
- `actionable_evidence` — strict subset whose source result has
  `status in {"ok", "failed"}` (i.e. the tool actually executed and
  reported a meaningful signal). Items synthesised on
  `error` / `timeout` / `tool_missing` / `blocked` paths are
  diagnostic only and do NOT enter this set.

Two enforcer call sites updated:

- `_enforce_requested_tool_evidence`: NO-OP guard switched from
  `new_evidence` to `actionable_evidence`. When only diagnostic
  items exist, the enforcer fires, demotes accepted claims to
  `unsupported`, and surfaces a Phase 5.8.1-B blocker explaining
  the diagnostic-only path.
- `_enforce_pass2_tool_citation`: `enriched_refs` is built from
  `actionable_evidence` only. A claim that cites only diagnostic
  refs cannot satisfy the citation rule.

## Verified safe outcome (post-fix)

Re-running the same case_001 reproduction at the gateway-loop level
(via `run_gateway_grounded_verifier` + the case_001 bundle's actual
forward/backward replays + an executor that returns
`returncode=4, stdout=""` to mimic the real workflow):

```
=== POST-FIX 5.8.1-B ON CASE_001 (gateway-loop) ===
status: diagnostic_only
accepted: []
unsupported: ['C.docstring.no_behavior_delta']
rejected: []
blockers:
  - requested tool produced only diagnostic evidence (adapter status
    in error/timeout/tool_missing); cannot promote pass-2 claims
    (Phase 5.8.1-B)
enriched_evidence_refs: ()
```

The claim is properly demoted to `unsupported` (uncertainty
preserved), the status stays `diagnostic_only` (no false promotion),
and an explicit Phase 5.8.1-B blocker explains why. Compare:

| Phase | status | accepted | rejected | unsupported | safety |
|---|---|---|---|---|---|
| pre-5.8.1 | diagnostic_only | 0 | 1 | 0 | safe-fragile (silent rule-3 reject) |
| 5.8.1 alone | verification_candidate | 1 | 0 | 0 | **UNSAFE** (false promotion) |
| 5.8.1-B (this fix) | diagnostic_only | 0 | 0 | 1 | safe + properly demoted |

## Phase 5.5 anchor restoration (advisor-flagged)

The Phase 5.5 holdout calibration's `tool_missing_uncertainty` and
`tool_timeout_uncertainty` rows had drifted from
`status=diagnostic_only` to `status=verification_candidate` between
5.8.1 and 5.8.1-B. The advisor predicted this shift was downstream
of the same bug. Confirmed: post-fix, both rows revert to
`status=diagnostic_only`. The tests restore the original strict
anchor (`status=diagnostic_only` AND `accepted=0` AND
`unsupported=1`) in the same commit.

## Test additions (regression guards)

Four new tests in
`tests/test_phase5_8_1_pytest_evidence_invariant.py`:

1. `test_case001_pytest_error_does_not_promote_claim_post_patch` —
   verifier-level reproduction of the case_001 bundle with a
   pytest executor returning `rc=4`. Asserts the claim is demoted
   to `unsupported`, status is NOT `verification_candidate`, and a
   Phase 5.8.1-B blocker is surfaced.
2. `test_case001_pytest_clean_pass_still_promotes_claim` —
   happy-path regression guard. With pytest returning `5 passed`,
   the claim must still be accepted (the split must not break the
   success path).
3. `test_run_tool_phase_splits_diagnostic_from_actionable` —
   direct unit test for the `_run_tool_phase` split. With pytest
   `rc=4`, the diagnostic is in `new_evidence` but NOT in
   `actionable_evidence`.
4. `test_run_tool_phase_clean_pass_evidence_is_actionable` —
   direct unit test for the success-path split. With pytest
   `rc=0`, every item in `new_evidence` is also in
   `actionable_evidence`.

## Out-of-scope (still deferred)

- **Workflow topology bug (A)** — pytest still fails at the wrong
  cwd in `operator-soak.yml`. Phase 5.8.1-B does not fix this. The
  next case_001 dispatch will still see pytest emit a diagnostic
  for "file not found"; the loop will correctly demote the claim
  to `unsupported` instead of either silently rejecting (pre-5.8.1)
  or falsely accepting (5.8.1 alone).
- **Aggregator-alone safety** — `oida-code verify-claims` (no
  gateway loop) on a packet with a hand-injected diagnostic will
  still over-accept. The contract is "raw verify-claims trusts the
  packet"; production grounding goes through
  `run_gateway_grounded_verifier`, which IS safe. If we want
  aggregator-alone safety we need a separate ADR — not in scope
  here.

## Hard-rule guards (unchanged)

- ADR-22 forbidden tokens: still none. Local grep across
  `src/`, `tests/`, `reports/operator_soak/` confirms no
  `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` / `merge_safe` / etc.
- ADR-37: no MCP, no JSON-RPC, no provider tool-calling, no write
  or network egress. The fix is a 30-line refactor inside the
  existing gateway loop.
- `enable-tool-gateway` default: still `"false"`.
- Vendored core: untouched.

## Quality gates

- `python -m ruff check src/ tests/ scripts/...` → all checks
  passed.
- `python -m mypy src/ scripts/...` → no issues found in 98 files.
- `python -m pytest` → **940 passed, 4 skipped** (unchanged total).
- The 4 new regression tests pass; the original 12 Phase 5.8.1
  invariant tests still pass; the 2 Phase 5.5 anchor tests are
  restored to the strict form.

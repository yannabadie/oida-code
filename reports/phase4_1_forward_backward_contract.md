# Phase 4.1 — Forward/backward verifier contract

**Date**: 2026-04-25.
**Scope**: QA/A16.md — define and test the verifier contract before
implementing the tool-grounded loop.
**Authority**: ADR-26 (Forward/backward verifier contract before
tool-grounded loop).
**Reproduce**:

```bash
python -m pytest tests/test_phase4_0_llm_estimator_dryrun.py tests/test_phase4_1_verifier_contract.py -q
oida-code verify-claims tests/fixtures/verifier_forward_backward/forward_supported_backward_supported/packet.json \
    --forward-replay tests/fixtures/verifier_forward_backward/forward_supported_backward_supported/forward_response.json \
    --backward-replay tests/fixtures/verifier_forward_backward/forward_supported_backward_supported/backward_response.json
```

**Verdict (TL;DR)**: structural complete. The forward/backward
verifier contract is enforced end-to-end on 8 hermetic fixtures
including a prompt-injection attempt and a tool-vs-LLM contradiction.
**No external API call. No tool execution.** ADR-22 + ADR-25 + ADR-26
all hold; production CLI emits no `V_net` / `debt_final` /
`corrupt_success`. The named-fence hardening from 4.0.1 is paired
with this commit.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-26 — Forward/backward verifier contract | +85 |
| `src/oida_code/estimators/llm_prompt.py` | 4.0.1 named OIDA_EVIDENCE fences + neutralise inner-close attempts | +50 |
| `src/oida_code/verifier/__init__.py` | sub-package re-exports | ~60 |
| `src/oida_code/verifier/contracts.py` | VerifierClaim + Forward/Backward + VerifierAggregationReport + VerifierToolCallSpec | ~210 |
| `src/oida_code/verifier/aggregator.py` | aggregate_verification (7 rules) | ~190 |
| `src/oida_code/verifier/forward_backward.py` | run_verifier driver, never raises | ~260 |
| `src/oida_code/verifier/replay.py` | Fake / FileReplay / OptionalExternalVerifierProvider | ~150 |
| `src/oida_code/cli.py` | `oida-code verify-claims` subcommand | +75 |
| `reports/phase4_0_llm_estimator_dryrun.md` | §5.1 fence hardening section + replaced EVIDENCE_BLOB → OIDA_EVIDENCE | +30 / -10 |
| `tests/fixtures/verifier_forward_backward/` | 8 hermetic fixtures × 4 files | ~640 |
| `tests/test_phase4_0_llm_estimator_dryrun.py` | 5 new 4.0.1 fence tests | +130 |
| `tests/test_phase4_1_verifier_contract.py` | 31 new tests (schema + aggregation + fixtures) | ~470 |
| `reports/phase4_1_forward_backward_contract.md` | this report | — |

**Gates**: ruff clean, mypy clean (68 src files, +5 verifier modules),
**400 passed + 3 skipped** (V2 placeholder + 2 Phase-4 observability
markers).

---

## 2. ADR-26 excerpt

> **Decision (Phase 4.1 protocol)**: define frozen schemas
> `VerifierClaim` / `ForwardVerificationResult` /
> `BackwardRequirement` / `BackwardVerificationResult` /
> `VerifierAggregationReport` / `VerifierToolCallSpec`. Aggregator
> requires forward AND backward support, evidence existence, tool
> non-contradiction, claim-type allowlist, confidence cap, and
> forbidden-phrase rejection. Replay-only providers; no tool
> execution; ToolCallSpec is description not execution.
>
> **Accepted**: claim schema with citable refs, forward/backward
> schemas with explicit `necessary_conditions_met`, aggregation
> requiring both directions, fake/replay providers, deterministic
> tools winning conflicts.
>
> **Rejected**: direct official V_net from verifier, LLM-only proof
> claims, verifier inventing evidence, verifier executing tools in
> Phase 4.1, external API calls by default, modifying vendored core.

Full text: `memory-bank/decisionLog.md` `[2026-04-25 21:00:00]`.

---

## 3. Contract schemas

```python
VerifierClaimType = Literal[
    "capability_sufficient",
    "benefit_aligned",
    "observability_sufficient",
    "precondition_supported",
    "negative_path_covered",
    "repair_needed",
    "shadow_pressure_explained",
]

class VerifierClaim(BaseModel):  # frozen, extra=forbid
    claim_id: str
    event_id: str
    claim_type: VerifierClaimType
    statement: str  # max_length=400, validator rejects forbidden phrases
    confidence: float
    evidence_refs: tuple[str, ...]
    source: Literal["forward","backward","aggregator","tool","replay"]
    is_authoritative: Literal[False] = False  # pinned

class ForwardVerificationResult(BaseModel):  # frozen
    event_id: str
    supported_claims: tuple[VerifierClaim, ...]
    rejected_claims: tuple[VerifierClaim, ...]
    missing_evidence_refs: tuple[str, ...]
    contradictions: tuple[str, ...]
    warnings: tuple[str, ...]

class BackwardRequirement(BaseModel):  # frozen
    claim_id: str
    required_evidence_kinds: tuple[Literal[8 evidence kinds], ...]
    satisfied_evidence_refs: tuple[str, ...]
    missing_requirements: tuple[str, ...]

class BackwardVerificationResult(BaseModel):  # frozen
    event_id: str
    claim_id: str
    requirement: BackwardRequirement
    necessary_conditions_met: bool

class VerifierAggregationReport(BaseModel):  # frozen
    status: Literal["blocked","diagnostic_only","verification_candidate"]
    accepted_claims: tuple[VerifierClaim, ...]
    rejected_claims: tuple[VerifierClaim, ...]
    unsupported_claims: tuple[VerifierClaim, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    recommendation: str
    authoritative: Literal[False] = False  # pinned

class VerifierToolCallSpec(BaseModel):  # frozen, NOT executed in 4.1
    tool: Literal["ruff","mypy","pytest","semgrep","codeql"]
    purpose: str
    expected_evidence_kind: <8 evidence kinds>
    scope: tuple[str, ...]
```

ADR-26 invariants enforced at the model level:

* `VerifierClaim.statement` validator rejects forbidden phrases
  (V_net / debt_final / corrupt_success / verdict / merge_safe /
  production_safe / bug_free / security_verified / official_*).
* `VerifierClaim.claim_type` is a strict 7-element Literal.
* `VerifierClaim.is_authoritative` and
  `VerifierAggregationReport.authoritative` are both
  `Literal[False]` — not just defaulted-False, but **pinned** so any
  attempt to set True fails validation.

---

## 4. Forward verifier semantics

The forward verifier answers:

> Given these premises, which conclusions can I support?

It emits `supported_claims` + `rejected_claims` + the lists of
missing refs / contradictions / warnings. It MUST cite known
evidence ids; refs that do not appear in the packet's `evidence_items`
are dropped by the aggregator (rule 3).

The forward verifier **cannot invent** a conclusion that's not tied
to an evidence ref. The schema doesn't enforce "evidence_refs ≥ 1"
(some claim_types could legitimately have empty refs in a future
non-corroborated mode), but the aggregator's combination of
forward + backward + ref-existence makes it impossible for an
unsupported claim to reach `accepted_claims`.

---

## 5. Backward verifier semantics

The backward verifier answers:

> For this claim, which evidence kinds are necessary, and are they
> all present?

Concretely:

```
Claim: observability_sufficient
Required: at least one test_result OR logging/error-surface evidence
          + negative-path evidence if failure mode is user-visible
If absent: necessary_conditions_met = False
```

This is the layer that prevents an LLM from saying "observability
high" just because it sees a global pytest pass. The aggregator
treats `necessary_conditions_met=False` as "claim becomes unsupported"
— it stays in the report for inspection, but it never moves into
`accepted_claims`.

---

## 6. Aggregation policy

`aggregate_verification(forward, backward, packet, deterministic)`
runs 7 rules:

| # | rule | failure mode |
|---|---|---|
| 1 | forward says supported | claim is in `forward.rejected_claims` → goes to report's `rejected_claims` |
| 2 | backward says necessary conditions met | unsupported |
| 3 | every `evidence_refs` entry exists in packet | rejected, warning logged |
| 4 | no deterministic-tool contradiction | rejected, warning logged |
| 5 | claim_type ∈ allowlist | schema-level rejection at construction |
| 6 | confidence ≤ 0.6 for LLM-style sources (forward/backward/replay) | rejected, warning logged |
| 7 | no forbidden phrase | schema-level rejection at construction; runner catches forbidden phrases in raw response too |

When all 7 hold, the claim joins `accepted_claims`. When some fail,
the report status drops:

* `verification_candidate` — at least one accepted, no rejection
* `diagnostic_only` — at least one accepted OR unsupported, with rejections OR backward gaps
* `blocked` — no accepted claim, no unsupported

---

## 7. Replay provider design

Mirrors Phase 4.0's LLM provider abstraction:

| provider | role |
|---|---|
| `FakeVerifierProvider` | deterministic empty-result echo for unit tests |
| `FileReplayVerifierProvider(fixture_path)` | reads recorded JSON from disk; the CLI's only realistic path at v0.4.x |
| `OptionalExternalVerifierProvider` | opt-in stub. `verify()` raises `VerifierProviderUnavailable` whether `OIDA_VERIFIER_API_KEY` is set or not (Phase 4.2 vendor binding pending) |

Security checks (both unit-tested):

* `test_no_external_provider_called_by_default`
* `test_external_provider_does_not_leak_secrets` — env var value
  never appears in the exception message, stdout, or stderr.

---

## 8. Hermetic fixtures

Each fixture lives under
`tests/fixtures/verifier_forward_backward/<name>/` with four files:
`packet.json`, `forward_response.json`, `backward_response.json`,
`expected.json`.

| Fixture | Status | Behaviour |
|---|---|---|
| `forward_supported_backward_supported` | `verification_candidate` | All checks pass; `c-cap-1` accepted. |
| `forward_supported_backward_missing_negative_path` | `diagnostic_only` | Backward says negative-path test required → `c-obs-1` becomes unsupported. |
| `forward_overclaims_capability` | `blocked` | Forward cites `[E.imaginary.999]` (unknown) → rejected; backward also says necessary conditions not met. |
| `backward_requires_missing_intent` | `diagnostic_only` | Forward supports `c-benefit-1`; backward requires intent (none in packet) → unsupported. |
| `tool_failure_contradicts_claim` | `blocked` | Deterministic test_result has value 0.2 (failure) on the same event; the LLM-style claim is rejected — deterministic wins. |
| `unknown_evidence_ref` | `blocked` | Forward cites `[E.does_not_exist.42]` → rejected. |
| `prompt_injection_claim_payload` | `blocked` | Hostile comment in evidence summary; forward correctly emits no claim; render places injection inside named `<<<OIDA_EVIDENCE id="..." kind="...">>>` ... `<<<END_OIDA_EVIDENCE id="...">>>` fences. |
| `repair_needed_supported` | `verification_candidate` | Repair claim accepted (forward + backward + evidence ok), `authoritative=False` ensures it cannot promote to official. |

Plus dedicated tests:

* `test_prompt_injection_claim_payload_is_data` — checks
  `<<<OIDA_EVIDENCE id="..." kind="...">>>` ...
  `<<<END_OIDA_EVIDENCE id="...">>>` bracketing on the rendered prompt.
* `test_repair_needed_claim_is_diagnostic_only` — verifies
  `authoritative` stays `False` even when status is
  `verification_candidate`.

---

## 9. Prompt-injection handling

The named-fence hardening from 4.0.1 carries through unchanged:
hostile content in `evidence_items[*].summary` is wrapped in
`<<<OIDA_EVIDENCE id="..." kind="...">>>` ...
`<<<END_OIDA_EVIDENCE id="...">>>`. Any literal closing-fence
sequence in user text is neutralised with a zero-width space.

For the verifier specifically, even if a hostile prompt successfully
manipulated a (future) live model into emitting `capability=1.0`,
the runner additionally:

* rejects the entire response if the raw payload contains any
  forbidden phrase (V_net / etc.);
* rejects claims whose `evidence_refs` aren't in the packet;
* rejects claims contradicting deterministic tool failures.

The fence is one defence layer; the schema + aggregator are the
others. ADR-26 does not trust any single layer.

---

## 10. Tool-call specs are not executed

`VerifierToolCallSpec` exists in the schema so a forward verifier
can declare "I would re-run pytest scoped to src/app.py" without
actually running pytest. Phase 4.1 explicitly forbids tool execution
at the verifier layer; the `oida_code.verifier` package does NOT
import any tool runner at module load and does not expose any
`execute()` / `run_tool_call_spec()` method.

`test_tool_call_specs_are_not_executed_in_phase4_1` is the canary:
it constructs a `VerifierToolCallSpec` and asserts that neither the
spec object nor the verifier module exposes an execute method. If
Phase 4.2 ever adds tool execution, the test will break — which is
intentional: a Phase 4.2 follow-up ADR must explicitly authorise it
and update the test.

---

## 11. Official fields remain absent

`test_verifier_report_has_no_vnet_debt_corrupt_success` asserts that
the `VerifierAggregationReport.model_dump()` payload contains NONE
of:

* `total_v_net`
* `v_net`
* `debt_final`
* `corrupt_success`, `corrupt_success_ratio`,
  `corrupt_success_verdict`
* `verdict`

`authoritative` is `Literal[False]` so the schema literally cannot
carry `authoritative=True`. ADR-22 + ADR-25 + ADR-26 all hold: the
verifier output is **diagnostic only**, regardless of how confident
the forward + backward agree.

---

## 12. Known limitations

1. **Phase 4.1 is contractual.** The runner exercises the schema +
   aggregator + replay providers. There is no real LLM call and no
   tool execution. Phase 4.2 will introduce the tool-grounded loop
   under a follow-up ADR.
2. **Replay fixtures are operator-captured.** A real LLM response
   for the verifier path doesn't exist yet; the fixtures are
   hand-written to exercise each rule. A real backward verifier
   would need a calibrated requirement registry (which evidence
   kinds are required for which claim types) — that's Phase 4.2+
   work.
3. **Confidence cap is best-effort.** The aggregator caps LLM-style
   sources (forward / backward / replay) at 0.6, matching the E3
   policy. If a future verifier source is added, the cap must be
   reviewed alongside.
4. **Backward provider returns a list, not a dict.** The runner
   accepts either `[result, ...]` or `{"results": [...]}` for
   ergonomics. If the forward provider's wrapper schema ever
   changes, the backward parser will need a similar update.

---

## 13. Recommendation for Phase 4.2

Per QA/A16.md §"Après Phase 4.1":

* **Phase 4.2 — tool-grounded verifier loop.** Allow the verifier to
  CALL tools (ruff, mypy, pytest, semgrep, codeql) and feed their
  outputs back into the aggregator. Mandatory:
  * external provider gets a real binding under explicit
    `--provider external` + env var
  * token / cost / latency budgets enforced before any call
  * tool outputs go through the deterministic adapters from E3.0;
    LLM never sees raw stdout
  * aggregator keeps the last word — it can override any LLM
    "supported" with a tool-grounded "rejected"
* **OWASP ASVS** for agentic systems should be reviewed: external
  data treated as untrusted, instruction/data separation (we have
  this via fences), pattern filtering for known attacks, monitoring
  of tool calls, explicit confirmation for any sensitive tool
  (delete files, modify CI, write to secrets, etc.).

---

## 14. Honesty statement

Phase 4.1 defines and tests the forward/backward verifier contract.

It does **NOT** implement the full tool-grounded verifier loop.

It does **NOT** call external LLM APIs by default.

It does **NOT** execute verifier-requested tools.

It does **NOT** validate predictive real-world performance.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-25 + ADR-26 all hold.

It does **NOT** modify the vendored OIDA core (ADR-02 holds).

The 4.0.1 fence hardening is the security companion to this commit —
named per-item fences with neutralised inner closes are the explicit
data-vs-instruction boundary.

---

## 15. Gates

| gate | status |
|---|---|
| `python -m ruff check src/ tests/ scripts/...` | clean |
| `python -m mypy src/ scripts/...` | 68 src files, no issues |
| `python -m pytest -q` | **400 passed, 3 skipped** |
| `oida-code verify-claims <packet> --forward-replay <r> --backward-replay <r>` | emits valid `VerifierAggregationReport`; `authoritative=False`; no V_net leakage |
| repo + history scan for committed keys | clean |

---

## 16. Acceptance checklist (QA/A16.md §"Critères d'acceptation Phase 4.1")

| # | criterion | status |
|---|---|---|
| 1 | 4.0.1 fence hardening shipped or explicitly rejected with reason | **shipped** (named OIDA_EVIDENCE fences + neutralisation; report updated) |
| 2 | ADR-26 written | DONE (`memory-bank/decisionLog.md`) |
| 3 | VerifierClaim schema added | DONE (`verifier/contracts.py`) |
| 4 | ForwardVerificationResult schema added | DONE |
| 5 | BackwardRequirement / BackwardVerificationResult schemas added | DONE |
| 6 | VerifierAggregationReport schema added | DONE |
| 7 | Aggregator requires both forward and backward support | PASS (`test_forward_only_is_not_enough`) |
| 8 | Missing evidence rejects or marks unsupported | PASS (`test_backward_missing_requirement_rejects_claim`) |
| 9 | Unknown evidence refs rejected | PASS (`test_unknown_evidence_ref_rejects_claim`) |
| 10 | Tool-grounded contradictions reject LLM claims | PASS (`test_tool_failure_contradicts_claim`) |
| 11 | Forbidden official fields reject batch | PASS (`test_forbidden_official_field_rejects_batch`) |
| 12 | No report contains V_net / debt_final / corrupt_success / verdict | PASS (`test_verifier_report_has_no_vnet_debt_corrupt_success`) |
| 13 | Replay/fake provider only; external provider stub remains no-call | PASS (`test_no_external_provider_called_by_default`) |
| 14 | ToolCallSpec may exist but is not executed | PASS (`test_tool_call_specs_are_not_executed_in_phase4_1`) |
| 15 | At least 8 hermetic fixtures pass | PASS (8 fixtures × `test_phase4_1_fixture`) |
| 16 | Prompt-injection fixture included | PASS (`prompt_injection_claim_payload` + dedicated test) |
| 17 | CLI `verify-claims` works on replay fixtures | PASS (CLI smoke ran from this report's reproduction block) |
| 18 | reports/phase4_1_forward_backward_contract.md produced | DONE (this file) |
| 19 | ruff clean | PASS |
| 20 | mypy clean | PASS |
| 21 | pytest full green, skips documented | PASS (400 + 3 documented skips) |

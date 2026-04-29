# Phase 6.1'd — LLM-author replays + verify-grounded round-trip

**Status:** delivered (commit pending).
**Phase block:** 6.1'd (per QA/A44 §"Phase 6.1' option choice"
sub-block ordering).
**Predecessor:** Phase 6.1'c (commit `1def23a`) — corpus
expansion + partition discipline.
**Acceptance criterion:** verify-grounded runs end-to-end on
the 3 pinned cases and produces an honest classification.

## What this block delivers

1. **Three Phase 6.1'b generator-shape bug fixes** caught by
   the round-trip:
   * `approved_tools.json` — was `["pytest"]`, now a
     `ToolAdmissionRegistry` with a fingerprinted decision.
   * `pass*_backward.json` — was a single object, now a JSON
     LIST (matching keystone shape).
   * Inlined SHA256 fingerprint helpers so the
     `gateway_definitions.json` and `approved_tools.json`
     fingerprint stay drift-free.
2. **`scripts/llm_author_replays.py`** (NEW, ~290 lines) —
   manual-lane LLM-author helper. Reads a seed record + bundle,
   calls DeepSeek to author the four `pass*_*.json` replays,
   validates Pydantic, archives the skeleton stubs, overwrites
   the bundle with LLM output. `MANUAL_EGRESS_SCRIPT = True`
   marker per ADR-53. SSL `VERIFY_X509_STRICT` relaxed for
   Python 3.13 + DeepSeek cert-chain compatibility.
3. **End-to-end round-trip on 3 pinned cases** — all 3 produce
   `status=diagnostic_only` with `tool_calls=1`. Evidence
   archived under `reports/phase6_1_d/round_trip_outputs/`.
4. **+5 tests:** 4 new in
   `tests/test_phase6_1_d_llm_author_replays.py`, 1 new in
   `tests/test_phase6_1_b_bundle_generator.py`. Existing
   pass-stub test updated for list-shape backward replays.
5. **ADR-57** documenting the round-trip outcome and the
   ADR-55 retraction (skeleton was file-presence-valid but not
   runtime-Pydantic-valid until the 3 fixes).

## Round-trip results

| case_id | partition | LLM call (s) | tool_calls | status | unsupported_claims |
|---|---|---:|---:|---|---|
| seed_008_pytest_dev_pytest_14407 | train | 8.2 | 1 | diagnostic_only | C.cli_version_flag.repair_needed |
| seed_065_simonw_sqlite_utils_680 | holdout | 8.1 | 1 | diagnostic_only | C.column_type_mapping.repair_needed |
| seed_157_hynek_structlog_761 | holdout | 8.9 | 1 | diagnostic_only | C.callsite_qual_name.capability_sufficient |

All three converge to the same honest behavior:

1. Bundle is well-formed; verifier accepts it.
2. Gateway invokes pytest with the bundle's policy.
3. pytest reports the test scope is not in `--repo-root .`
   (the test scope lives in the target repo, not the local
   oida-code checkout).
4. Verifier classifies as `diagnostic_only` and demotes the
   claim to `unsupported`.
5. `tool_calls: 1` confirms the gateway actually ran pytest;
   no theatre.

To get `verification_candidate` (the success outcome) requires
a real target checkout (clone pytest-dev/pytest at the head_sha
and pass `--repo-root <clone>`). That is Phase 6.1'e or later
work, deferred explicitly.

## Three generator-shape bugs caught

The Phase 6.1'd round-trip surfaced what `validate_gateway_bundle`
did not catch — three shape mismatches between what the
generator produced and what the runtime Pydantic loaders expect:

### Bug 1: `approved_tools.json` was a JSON array

```json
// Phase 6.1'b emitted:
["pytest"]

// Phase 6.1'd-fixed emits (matches keystone):
{
  "approved": [
    {
      "tool_id": "oida-code/pytest",
      "status": "approved_read_only",
      "reason": "phase6.1.b auto-emitted approval...",
      "fingerprint": {
        "tool_id": "oida-code/pytest",
        "tool_name": "pytest",
        "adapter_version": "0.4.0",
        "description_sha256": "<64-char hex>",
        "input_schema_sha256": "<64-char hex>",
        "output_schema_sha256": "<64-char hex>",
        "combined_sha256": "<64-char hex>"
      }
    }
  ],
  "quarantined": [],
  "rejected": []
}
```

### Bug 2: `pass*_backward.json` was a single object

```json
// Phase 6.1'b emitted:
{ "event_id": "...", "claim_id": "...", "requirement": {...}, ... }

// Phase 6.1'd-fixed emits (matches keystone):
// pass1_backward.json
[]

// pass2_backward.json
[
  { "event_id": "...", "claim_id": "...", "requirement": {...}, ... }
]
```

### Bug 3: Hashes computed inline, drift-prone

The `gateway_definitions.json` content was duplicated inline in
the writer functions, with no shared source of truth between the
definition body and the fingerprint computation. Fix: factor out
`_pytest_definition()` and `_pytest_fingerprint()` so the four
SHA256 hashes match by construction.

## Why the validator missed these

`validate_gateway_bundle` (Phase 5.6 / QA/A33 §5.6-B) performs:

1. File-presence check (8 required files exist)
2. Path-traversal check (no symlinks pointing out)
3. Filename-pattern check (no secret / provider / MCP shapes)

It does NOT load the file contents through the Pydantic
contracts. That's a separate runtime-loading step performed by
`verify-grounded`. The structural validator + runtime loader
form a layered acceptance — **Phase 6.1'b's "structural ok"
was not a guarantee of "runtime ok"**, and Phase 6.1'd is what
catches the gap.

ADR-57 retracts the strict-reading of ADR-55's "skeleton is
structurally valid" claim: the skeleton WAS structurally valid
against the file-presence + filename-pattern check, but NOT
against the Pydantic-loader runtime check. The staged-acceptance
design surfaced the bugs at the right time.

## Discipline preserved (ADR-56 holdout)

The three generator fixes were caught using **seed_008** (the
train case) AND fix non-claim-specific structural bugs (registry
shape, backward-replay list shape, fingerprint hashing). The
fixes were applied BEFORE running on holdout cases (seed_065 +
seed_157). The holdouts ran THROUGH the unchanged generator and
produced the same `diagnostic_only` outcome.

The generator was NOT modified in response to anything specific
to the holdout cases. ADR-56's "no tuning against holdout
contents" is honored.

## SSL workaround (Python 3.13 / Windows / DeepSeek)

Python 3.13 enabled `VERIFY_X509_STRICT` by default, which
rejects certs whose CA chain lacks the Authority Key Identifier
extension. DeepSeek's cert chain triggers this. The
`scripts/llm_author_replays.py` SSL context relaxes this single
flag while keeping hostname verification + cert-chain validation
otherwise enabled. Symptom: `SSL: CERTIFICATE_VERIFY_FAILED —
Missing Authority Key Identifier`.

## Provider call summary

* Provider: DeepSeek (chat-completions endpoint with
  `response_format={"type":"json_object"}`)
* Model: deepseek-chat
* Per-call latency: 8-9 seconds
* Per-call cost: ~$0.001
* Total for the 3 cases: ~$0.003
* Failure modes encountered:
  * SSL cert chain (fixed via `VERIFY_X509_STRICT` relaxation)
  * Pydantic field omissions (fixed via tighter system prompt)
  * Confidence > 0.6 cap (fixed via system-prompt confidence
    guidance)
* Final success: 3/3 cases produced 4-replay JSON objects that
  validated against the Pydantic contracts on the first try
  after the prompt fixes.

## Test count

**1097 → 1102 (+5).** The 5 new/updated tests:

- `test_pass_stubs_pydantic_valid_with_skeleton_warning` —
  updated for list-shape backward replays
- `test_approved_tools_is_admission_registry` (NEW)
- `test_llm_author_replays_carries_egress_marker` (NEW)
- `test_llm_author_replays_refuses_without_egress_ok` (NEW)
- `test_no_manual_egress_script_referenced_in_workflows` (NEW —
  generalizes Phase 6.1'a-pre's indexer-only check to all
  marker-carrying scripts via dynamic discovery)
- `test_marker_set_includes_indexer_and_llm_author` (NEW)

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — system prompt explicitly forbids these
  in the LLM output. None observed across the 3 round-trips.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in **runtime path** (`src/oida_code/`)
  — none. The provider call lives in `scripts/llm_author_replays.py`
  (manual lane).

## Lane separation preserved

The four-lane structural separation continues to hold. The
manual data acquisition lane gains a SECOND member
(`scripts/llm_author_replays.py`); the existing
`scripts/build_calibration_seed_index.py` is unchanged. Both
carry the `MANUAL_EGRESS_SCRIPT = True` marker; both are
discoverable by the new dynamic test in
`tests/test_phase6_1_d_llm_author_replays.py`.

## What this block does NOT deliver

* `verification_candidate` outcome on any pinned case. Requires
  a real target checkout. Deferred to Phase 6.1'e or later.
* Multi-provider replay triangulation (DeepSeek + Grok +
  MiniMax + Kimi). Phase 6.1'e (AI-tier re-run) may use this
  pattern.
* Yann-solo dogfood pass on the 3 pinned cases. That is also
  Phase 6.1'e.
* AI-tier cold-reader critique re-run after the corpus
  expansion. Also Phase 6.1'e.

## What's next

**Phase 6.1'e** — final block of the 6.1' chain:

1. Re-run `scripts/run_ai_adversarial_review.py` on the new
   `docs/beta/` + `reports/calibration_seed/` surface (3-5
   provider panel) per QA/A44 §"Multi-provider panel sizing".
2. Yann-solo dogfood: run a real `verify-grounded` against a
   target checkout (clone `pytest-dev/pytest@480809ae` and
   point `--repo-root <clone>`), expecting
   `verification_candidate` on seed_008.
3. (Optional) extend the LLM-author script to a panel of 3-5
   providers and capture cross-model agreement on the same
   bundles.

## Cross-references

* ADR-57 (this block): `memory-bank/decisionLog.md`
* ADR-56 (Phase 6.1'c): `memory-bank/decisionLog.md`
* ADR-55 (Phase 6.1'b): `memory-bank/decisionLog.md`
* ADR-54 (Phase 6.1'a): `memory-bank/decisionLog.md`
* QA/A44: `QA/A44.md`
* Bundle generator: `src/oida_code/bundle/generator.py`
* LLM-author script: `scripts/llm_author_replays.py`
* Round-trip evidence: `reports/phase6_1_d/round_trip_outputs/`
* Tests: `tests/test_phase6_1_d_llm_author_replays.py`
* Project status: `docs/project_status.md`

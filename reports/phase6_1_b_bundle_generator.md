# Phase 6.1'b — `prepare-gateway-bundle` skeleton generator

**Status:** delivered (commit pending).
**Phase block:** 6.1'b (per QA/A44 §"Phase 6.1' option choice"
sub-block ordering).
**Predecessor:** Phase 6.1'a (commit `af87f75`) — first
collection + worked example.

## What this block delivers

1. **Seed schema extension.** `reports/calibration_seed/schema.md`
   gains an `evidence_items` field (Tier 3 free-form domain
   reasoning per ADR-54). The shape mirrors
   `LLMEvidencePacket.evidence_items` exactly so a downstream
   `packet.json` conversion is mechanical.
2. **Seed_008 re-pinned.** `reports/calibration_seed/index.json`
   now carries 2 operator-authored evidence items for
   `seed_008_pytest_dev_pytest_14407`.
3. **Bundle generator module.** `src/oida_code/bundle/`
   (~330 lines) with `generate_bundle()`, `BundleGenerationError`,
   `GeneratedBundle`, `REQUIRED_TIER_3_FIELDS`. Emits 9 files
   (8 verifier-required + README). Stays under `src/oida_code/`
   because it is local composition only — no network, no
   provider, no MCP.
4. **CLI subcommand `oida-code prepare-gateway-bundle`.**
   Inputs: `--seed-index`, `--case-id`, `--out`,
   `--validate/--no-validate`. Auto-runs `validate-gateway-
   bundle` on the produced directory.
5. **19 new tests** in
   `tests/test_phase6_1_b_bundle_generator.py`.
6. **ADR-55** documenting the design decisions, the rejected
   alternatives, and the explicit deferral of the
   `verify-grounded` round-trip to Phase 6.1'd.

## What the generator does (and does not)

**Does:**

- Read a Tier-3-complete seed record.
- Validate every field against ADR-53/54/55 invariants.
- Emit `packet.json` mechanically from the seed's claim_id +
  claim_type + claim_text + evidence_items.
- Emit `tool_policy.json` / `gateway_definitions.json` /
  `approved_tools.json` with safe defaults (pytest only, no
  network, no write).
- Emit four `pass*_*.json` SKELETON stubs that are
  Pydantic-valid (the verifier won't crash loading them) but
  carry the `_SKELETON_NOTE` in their `warnings[]` array
  honestly stating they are operator/Phase-6.1'd
  responsibility.
- Emit a README.md describing what the bundle is and is not.
- Auto-validate with `validate_gateway_bundle()` on request.

**Does not:**

- Make any network call.
- Import any provider or MCP module.
- Author evidence items (they are Tier 3 — operator's job).
- Pretend the pass-replay stubs are real verifier output.
- Run the verifier (that is `verify-grounded`'s job).
- Modify any source file in the target repo.
- Validate against the actual repo's HEAD (the bundle is
  metadata-only; the verifier checks out the SHA later).

## Acceptance criterion

**Per ADR-55, the acceptance is `validate_gateway_bundle`
returns ok**, NOT `verify-claims` / `verify-grounded` round-trip.

The advisor's earlier framing ("verify-claims runs on the
generated bundle") was retracted. Reasoning: deterministic
stub replays that make `verify-claims` accept the claim are
THEATRE — they were authored to pass the test, so a passing
test proves only that the generator is internally consistent,
not that the bundle is meaningful. Real verification needs
real or operator-authored replays and belongs to Phase 6.1'd.

ADR-55 makes this deferral explicit so a future reviewer does
not interpret "skeleton" as "incomplete and should be
finished".

## Refusal modes (the generator is strict)

The generator raises `BundleGenerationError` (exit 2 from the
CLI) on any of:

| Failure | Reason |
|---|---|
| Tier-1 field missing | case_id / repo_url / pr_number / head_sha / base_sha required |
| Tier-2 field missing | expected_grounding_outcome / label_source required |
| `expected_grounding_outcome == "not_run"` | partial-record sentinel |
| Tier-3 field missing or empty | per ADR-54 (claim_id / claim_type / claim_text / test_scope / evidence_items) |
| `human_review_required is True` | only reviewed records flow into bundles |
| Evidence item missing required sub-field | per `EvidenceItem` Pydantic shape |
| Evidence item kind not in allowlist | 8 Literal values |
| Confidence outside [0.0, 1.0] | per `EvidenceItem` Field constraint |
| Summary > 400 chars | per `EvidenceItem` Field constraint |
| Forbidden phrase in record | ADR-22/24/25/26 hard wall |
| Case_id not found in seed index | unknown record |
| Multiple records match case_id | duplicate keys (should never happen — keyed on `(repo_url, pr_number)`) |

All checks run BEFORE any file is written, so a refusal leaves
the output directory untouched.

## Generated bundle (seed_008 example)

Running `python -m oida_code.cli prepare-gateway-bundle
--case-id seed_008_pytest_dev_pytest_14407 --out
.tmp/bundle_test` produces:

```
.tmp/bundle_test/seed_008_pytest_dev_pytest_14407/
├── README.md                  (operator-facing description)
├── approved_tools.json        (["pytest"])
├── gateway_definitions.json   (pytest tool definition)
├── packet.json                (LLMEvidencePacket — fully populated)
├── pass1_backward.json        (skeleton stub — warnings[0] names deferral)
├── pass1_forward.json         (skeleton stub — requests pytest on test_scope)
├── pass2_backward.json        (skeleton stub)
├── pass2_forward.json         (skeleton stub)
└── tool_policy.json           (pytest, no network, no write)
```

Each file is Pydantic-valid against its respective contract
model:

- `packet.json` → `LLMEvidencePacket`
- `pass1_forward.json`, `pass2_forward.json` →
  `ForwardVerificationResult`
- `pass1_backward.json`, `pass2_backward.json` →
  `BackwardVerificationResult`

`validate_gateway_bundle` returns ok (no missing files, no
path traversal, no secret/provider/MCP filename leak).

## Test count

**1068 → 1087 (+19).** The 19 new tests cover:

- 1 file-count assertion
- 1 `validate_gateway_bundle` round-trip
- 1 packet Pydantic validation + evidence_items survival
- 1 four-pass-stub Pydantic validation + skeleton-warning check
- 1 no-secrets check
- 5 Tier-3-missing parametrizations
- 1 human_review_required refusal
- 1 not_run refusal
- 1 invalid evidence_kind refusal
- 1 confidence-out-of-range refusal
- 1 forbidden-phrase refusal
- 1 idempotence
- 1 no-network-import (static)
- 1 no-provider-import (static)
- 1 no-MANUAL_EGRESS_SCRIPT-marker (static)

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted, none in
  any new schema, ADR-22 / 24 / 25 / 26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — generator's `_check_forbidden_phrases`
  rejects any record carrying these.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in runtime — none.

## Lane separation preserved

The four-lane structural separation continues to hold:

* External-human beta — `not_run`, unchanged.
* AI-tier cold-reader critique — `active, separated`,
  unchanged.
* Yann-solo dogfood — `allowed, internal only`, unchanged.
* Manual data acquisition — `active, manual-only,
  public-only, runtime-isolated`, 2 inclusions / 14
  exclusions, unchanged.

The bundle generator is the FIRST authored member of a
**fifth conceptual layer**: bundle authoring. It is NOT a new
"lane" — it does not produce labels, does not emit operator
feedback, does not call providers. It is local composition
that consumes Tier-3-complete seed records and emits verifier
inputs. The generator's contract is enforced by the static
test guards (no network/provider/MCP imports) plus the
runtime refusal modes.

## What this block does NOT deliver

* The seed corpus expansion to 20-50 cases. That is
  Phase 6.1'c.
* Real verifier replays for any seed bundle. That is
  Phase 6.1'd.
* AI-tier re-run + Yann-solo dogfood. That is Phase 6.1'e.
* The `verify-grounded` round-trip on a generated bundle.
  That is the explicit acceptance criterion of Phase 6.1'd.
* The `partition: train | holdout` schema field. Deferred to
  6.1'c per ADR-54.

## What's next

**Phase 6.1'c** — seed corpus expansion to 20-50 cases AND
the `partition` schema field. Per ADR-54 the holdout
discipline kicks in at N≥20. Per advisor's selection-effect
caveat, candidates must be sought from non-mainstream Python
projects where the maintainer themselves contributes (or from
backports/release-prep PRs honestly labeled as such — the
fork-PR fence will continue to filter community-fork PRs).

For each Phase 6.1'c case, the operator:
1. Runs the indexer (seed_008-style) to get the API-derived
   shape.
2. Reads the diff to author Tier-3 fields including
   `evidence_items`.
3. Picks `partition: train` (informs generator) or `holdout`
   (reserved for Phase 6.1'd validation).

The generator can then emit a bundle for any train-partition
case (holdout cases stay schema-only until Phase 6.1'd).

## Cross-references

* ADR-55 (this block): `memory-bank/decisionLog.md`
* ADR-54 (Phase 6.1'a): `memory-bank/decisionLog.md`
* ADR-53 (Phase 6.1'a-pre): `memory-bank/decisionLog.md`
* QA/A44: `QA/A44.md`
* Schema: `reports/calibration_seed/schema.md`
* Lane charter: `reports/calibration_seed/README.md`
* Worked example walk-through:
  `reports/calibration_seed/worked_example_phase6_1_a.md`
* Generator: `src/oida_code/bundle/generator.py`
* CLI subcommand: `src/oida_code/cli.py`
* Tests: `tests/test_phase6_1_b_bundle_generator.py`
* Project status: `docs/project_status.md`

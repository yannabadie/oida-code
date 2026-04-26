# `private_holdout_v2` — gateway-grounded verifier calibration holdout (Phase 5.3)

**Authority**: ADR-38, QA/A30.md §5.3-A.
**Purpose**: a small operator-curated holdout that lets Phase 5.3
**measure** whether the gateway-grounded verifier loop improves
verifier behaviour vs. the no-gateway baseline. The protocol is
strictly diagnostic — Phase 5.3 does NOT tune production
thresholds and does NOT promote anything to official.

**Cross-link**: a separate
[`datasets/private_holdout_v1/`](../private_holdout_v1/README.md)
exists for Phase 4.8-C provider-regression labels. v1 and v2 are
**different protocols**: v1 measures provider behaviour against
the calibration estimator surface; v2 measures the verifier's
gateway-grounded loop. Don't merge them.

## Pilot size (QA/A30 §5.3-A line 124)

24 cases, distributed:

| Family | Count |
|---|---|
| `claim_contract` | 8 |
| `gateway_grounded` | 8 |
| `code_outcome` (F2P/P2P) | 4 |
| `safety_adversarial` | 4 |

Synthetic cases CAN be committed if marked `provenance="synthetic"`
in their `expected.json`. Operator-private cases (real internal
code, real production traces) MUST stay under
`datasets/private_holdout_v2/cases/` which is gitignored — only
this README and `manifest.example.json` enter the public repo.

## Per-case directory layout

`cases/<case_id>/`

| File | Required when | Purpose |
|---|---|---|
| `expected.json` | always | A `GatewayHoldoutExpected` JSON (see `src/oida_code/calibration/gateway_holdout.py`) — case_id, expected_baseline, expected_gateway, expected_delta. |
| `packet.json` | always | The `LLMEvidencePacket` to feed both modes. |
| `pass1_forward.json`, `pass1_backward.json` | always | Replay fixtures for the gateway-grounded mode's first pass. |
| `pass2_forward.json`, `pass2_backward.json` | always | Replay fixtures for the gateway-grounded mode's second pass. |
| `forward_replay.json`, `backward_replay.json` | always | Replay fixtures for the BASELINE (no-gateway) mode. |
| `tool_policy.json`, `approved.json`, `definitions.json` | gateway mode | The same shape `oida-code verify-grounded` consumes. |
| `executor.json` | optional | Canned tool stdout/stderr if the case wants the gateway adapter to emit something specific. |
| `provenance.json` | always | `{ "source": ..., "contamination_risk": ..., "created_by": ... }`. See contamination policy below. |
| `repo/` | `family == code_outcome` | Mini src/tests layout for F2P/P2P stability runs. |

## Contamination policy (QA/A30 §5.3-F)

Every case carries:

```
provenance:
  synthetic
  private_trace
  private_repo
  public_low
  public_high

contamination_risk:
  synthetic
  private
  public_low
  public_high
```

**Rules:**

1. `public_high` cases are EXCLUDED from headline metrics (they
   risk having been seen during model training).
2. `private_repo` / `private_trace` cases are NEVER committed if
   they contain proprietary code.
3. `synthetic` and `synthetic-but-private-like` cases CAN be
   committed but MUST be marked explicitly so a future reviewer
   can distinguish them from operator data.
4. `public_low` (e.g. tiny pedagogical fixtures clearly out of
   the SWE-bench / public-benchmark scope) can be committed and
   are included in headline metrics.

The headline metrics (delta vs. baseline, evidence_ref
precision/recall, tool_contradiction_rejection_rate) explicitly
EXCLUDE the `public_high` slice. The runner reports both the
"with-public_high" and "without-public_high" numbers; only the
latter is allowed to lead a recommendation.

## F2P / P2P policy (QA/A30 §5.3-A line 135)

`code_outcome` cases continue to follow SWE-bench's
FAIL_TO_PASS + PASS_TO_PASS contract:

* `expected_code_outcome.fail_to_pass_tests` MUST contain at
  least one test that should fail BEFORE the candidate fix and
  pass AFTER.
* `expected_code_outcome.pass_to_pass_tests` MUST contain at
  least one test that should pass before AND after (regression
  guard).

The `CalibrationCase` model already enforces the F2P-non-empty
invariant (see `models.py:_family_specific_invariants`). v2
inherits that — operator-supplied `expected.json` files for
code_outcome must satisfy the existing schema.

## Anti-mutation policy (QA/A30 §5.3-E line 269)

> Aucun label ne change automatiquement.
> Tout changement de label doit être une proposition humaine.

The calibration runner is read-only over `datasets/`. There is
no path through `scripts/run_gateway_calibration.py` that can
modify any file under this directory. The accompanying test
(`test_calibration_runner_does_not_mutate_dataset`) asserts
mtime-preservation across a full run.

## Usage

```bash
# Default replay smoke (no external provider).
python scripts/run_gateway_calibration.py \
    --manifest datasets/private_holdout_v2/manifest.example.json \
    --mode replay \
    --out .oida/gateway-calibration

# Operator-private holdout under cases/ (gitignored).
python scripts/run_gateway_calibration.py \
    --manifest datasets/private_holdout_v2/manifest.json \
    --mode replay \
    --out .oida/gateway-calibration-private
```

## What this does NOT validate

* Production predictive performance — these cases are a
  controlled measurement surface, not a deployment forecast.
* Provider-side tool-calling — Phase 5.3 stays replay-only by
  default.
* MCP — no `tools/list` / `tools/call` in any case fixture.
* Official `total_v_net` / `debt_final` / `corrupt_success` —
  the schemas don't expose those fields, and the runner asserts
  `official_field_leak_count == 0` in both modes.

## Why a v2, not a v1 extension

`private_holdout_v1` measures provider behaviour through the
existing `CalibrationCase` schema (one expected outcome). v2
measures gateway behaviour through `GatewayHoldoutExpected`
(two expected outcomes — baseline and gateway). Same operator,
different protocol. Mixing them would force every case to carry
both shapes, and most cases discriminate only one of the two
axes.

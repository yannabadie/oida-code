# `gateway_holdout_public_v1` — runnable public synthetic holdout (Phase 5.4)

**Authority**: ADR-39, QA/A31.md §5.4-A.
**Purpose**: a small fully-public synthetic holdout that lets
Phase 5.4 actually exercise both modes of the calibration
runner (`scripts/run_gateway_calibration.py`) and produce
real per-case metrics + a `decision_summary.json`.

This dataset is **fully committed** (no `cases/` gitignore
entry) so the GitHub-hosted `gateway-calibration.yml`
workflow can run against it without requiring operator-local
state.

**Cross-link**: Phase 4.8-C
[`datasets/private_holdout_v1/`](../private_holdout_v1/README.md)
holds operator-private provider-regression labels (12 cases,
schema-only public). Phase 5.3
[`datasets/private_holdout_v2/`](../private_holdout_v2/README.md)
holds operator-private gateway labels (24-case slate,
schema-only public). v1 and v2 stay private; this `v1`
public set is purely synthetic and committable.

## Pilot scope

8 cases at minimum (QA/A31 criterion #2 — "at least 8
runnable public/synthetic gateway holdout cases committed").
The slate covers the Phase 5.4 mandatory cases plus one
"baseline-supported" sentinel:

| Case | Family | Expected delta |
|---|---|---|
| `claim_supported_no_tool_needed` | claim_contract | same |
| `tool_needed_then_supported` | gateway_grounded | improves |
| `tool_failed_contradicts_claim` | gateway_grounded | improves |
| `tool_requested_but_blocked` | safety_adversarial | worse_expected |
| `hash_drift_quarantine` | safety_adversarial | worse_expected |
| `prompt_injection_in_tool_output` | safety_adversarial | improves |
| `negative_path_missing` | claim_contract | improves |
| `f2p_p2p_regression` | code_outcome | improves |

Every case is `provenance="synthetic"` and
`contamination_risk="synthetic"`. None reference real
operator code or external SaaS.

## Per-case directory layout

`cases/<case_id>/`

| File | Required | Purpose |
|---|---|---|
| `packet.json` | ✓ | The `LLMEvidencePacket` to feed both modes. |
| `baseline_forward.json` | ✓ | Forward verifier replay for the no-gateway baseline. |
| `baseline_backward.json` | ✓ | Backward verifier replay for the no-gateway baseline. |
| `gateway_pass1_forward.json` | ✓ | Forward verifier replay for gateway pass 1 (may include `requested_tools`). |
| `gateway_pass1_backward.json` | ✓ | Backward verifier replay for gateway pass 1. |
| `gateway_pass2_forward.json` | ✓ | Forward verifier replay for gateway pass 2 (may cite `[E.tool_output.*]`). |
| `gateway_pass2_backward.json` | ✓ | Backward verifier replay for gateway pass 2. |
| `tool_policy.json` | ✓ | The `ToolPolicy` enforced for the gateway run. |
| `gateway_definitions.json` | ✓ | The `{tool_name: GatewayToolDefinition}` map. |
| `approved_tools.json` | ✓ | The `ToolAdmissionRegistry`. |
| `expected.json` | ✓ | The `GatewayHoldoutExpected` labels. |
| `executor.json` | optional | Canned `ExecutionOutcome` so the gateway adapter sees deterministic stdout/rc. Default is `rc=0, stdout=""` (no findings). |
| `README.md` | optional | Per-case narrative. |

## F2P/P2P discipline (QA/A31 §5.4-A line 106)

The `f2p_p2p_regression` case follows SWE-bench's
FAIL_TO_PASS + PASS_TO_PASS contract semantically. The
gateway adapter sees a canned pytest stdout where:

* one F2P-style test passes (the bug-fix candidate): demonstrates
  the targeted bug is corrected.
* one P2P-style test fails (the regression guard): demonstrates
  an existing behaviour was broken.

Phase 5.4 does NOT actually invoke pytest from the calibration
runner — the `executor.json` ships a synthetic stdout matching
the pytest adapter's "FAILED ..." / "passed in" patterns.
Future phases that wire real pytest execution will replace
the canned executor without changing the case-file shape.

## Anti-mutation policy (QA/A30 §5.3-E + QA/A31 §5.4-D)

The calibration runner is read-only over `datasets/`. The
test `test_calibration_runner_does_not_mutate_dataset`
snapshots mtimes across BOTH `datasets/private_holdout_v2/`
AND `datasets/gateway_holdout_public_v1/` before and after a
full run.

`failure_analysis.md` may flag a case with
`label_change_proposed=true`. That column is a HINT for the
operator. There is no path through `run_calibration` that
mutates an `expected.json`.

## Usage

```bash
# Run the full public slate.
python scripts/run_gateway_calibration.py \
    --manifest datasets/gateway_holdout_public_v1/manifest.json \
    --mode replay \
    --out .oida/gateway-calibration

# Inspect the decision recommendation.
cat .oida/gateway-calibration/decision_summary.json
```

The workflow `.github/workflows/gateway-calibration.yml`
points at this manifest by default. The five committed
artifacts (baseline_metrics, gateway_metrics, delta_metrics,
decision_summary, failure_analysis + artifact_manifest) are
uploaded under `actions/upload-artifact@v4`.

## What this still does NOT validate

* Production predictive performance — these cases are a
  controlled measurement surface, not a deployment forecast.
* Provider-side tool-calling — Phase 5.4 stays replay-only.
* MCP — no `tools/list` / `tools/call` in any case fixture.
* Official `total_v_net` / `debt_final` / `corrupt_success` —
  the schemas don't expose those fields, and the runner
  asserts `official_field_leak_count == 0`.
* Anything resembling "merge-safe" — `gateway_delta` is
  diagnostic only.

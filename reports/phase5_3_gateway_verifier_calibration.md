# Phase 5.3 — gateway verifier calibration

QA directive: `QA/A30.md` (2026-04-26).
ADR: ADR-38 (`memory-bank/decisionLog.md`).
Status at end of phase: **29 / 29** acceptance criteria green;
quality gates clean (ruff + mypy + pytest, 763 passed / 4
skipped, was 730/4 before Phase 5.3 — exactly +33 new tests);
all five GitHub-hosted runs green on commit `103b2ff`:

| Workflow | Run ID | Wall time |
|---|---|---|
| ci | 24961882218 | 1m13s |
| action-smoke | 24961882214 | 1m08s |
| provider-baseline-node24-smoke | 24961882219 | 20s |
| gateway-grounded-smoke | 24961882225 | 19s |
| gateway-calibration | 24961882238 | 20s |

## 1. Diff résumé

### Sources

* `src/oida_code/calibration/gateway_holdout.py` — NEW. Hosts
  `ExpectedVerifierOutcome` and `GatewayHoldoutExpected`.
* `src/oida_code/calibration/gateway_calibration.py` — NEW
  (~330 LOC). Hosts `run_calibration`, the failure-analysis
  emitter, and the artifact-manifest helper.
* `scripts/run_gateway_calibration.py` — NEW Typer-free CLI
  wrapper.
* `src/oida_code/verifier/contracts.py` — `VerifierToolCallSpec`
  gains optional `requested_by_claim_id`.
* `src/oida_code/verifier/gateway_loop.py` — new
  `_enforce_requested_tool_evidence` helper +
  `_run_tool_phase` accounting fields. Phase 5.2.1-B.
* `reports/phase5_2_gateway_grounded_verifier_loop.md` — Phase
  5.2.1-A fence wording fixed.
* `action.yml` / `.github/workflows/gateway-calibration.yml` —
  NEW replay-only workflow.

### Tests + datasets

* `tests/test_phase5_3_gateway_calibration.py` — NEW, 33
  tests across the 9 sub-blocks below.
* `datasets/private_holdout_v2/README.md` — NEW.
* `datasets/private_holdout_v2/manifest.example.json` — NEW
  example slate of 4 representative cases.
* `.gitignore` — `datasets/private_holdout_v2/cases/` added.

### Memory + reports

* `memory-bank/decisionLog.md` — ADR-38 appended.
* `reports/phase5_3_gateway_verifier_calibration.md` — this
  document.
* `README.md` + `memory-bank/progress.md` — updated test count
  and status line (see follow-up commit).

## 2. 5.2.1 hardening

### 5.2.1-A — fence wording in the Phase 5.2 report

Line 189 of `reports/phase5_2_gateway_grounded_verifier_loop.md`
previously referenced the bare prefix `<<<OIDA_EVIDENCE>>>`,
which drifted from the live per-item form. Phase 5.3 rewrites
it to the explicit named form
`<<<OIDA_EVIDENCE id="..." kind="...">>>`...
`<<<END_OIDA_EVIDENCE id="...">>>`, and adds a canary —
`test_phase5_2_report_uses_current_fence_constant` —
that imports `FENCE_NAME` from
`oida_code.estimators.llm_prompt` and verifies the report
references the live constant.

### 5.2.1-B — requested-tool-without-evidence blocker

Before Phase 5.3, the gateway loop's only post-pass-2 rule was
`_enforce_pass2_tool_citation`, which is a no-op when no tool
evidence was produced. That meant: forward could request a
tool, the gateway could fail to run it (missing definition / 
admission empty / adapter emits nothing), and a pass-2 LLM
claim could still be accepted purely on event-side evidence.

Phase 5.3 adds `_enforce_requested_tool_evidence` (runs BEFORE
the citation rule). When `forward.requested_tools` is non-empty
AND `tool_phase.new_evidence == ()`:

1. Add a sub-case-specific blocker:
   - "requested tool evidence unavailable: missing gateway definition for [...]"
   - "requested tool evidence unavailable: gateway blocked all calls"
   - "requested tool ran but emitted no citable evidence; cannot promote pass-2 claims"
2. Demote EVERY pass-2 accepted claim to `unsupported_claims`.
3. Force the report status off `verification_candidate` (the
   highest tier) — at most `diagnostic_only`.

`_run_tool_phase` returns two new accounting fields on
`_ToolPhaseOutput`: `requested_count: int` and
`missing_definition_tools: tuple[str, ...]`. Missing
definitions also now flow into `blockers` (not just
`warnings`), matching the 5.1.1 hardening pattern.

### 5.2.1-C — `requested_by_claim_id` on the spec

`VerifierToolCallSpec` gains the optional field. Replays
without it continue to validate. `tool_request_from_spec()`
resolves the explicit kwarg first, then falls back to the
spec's own attribution.

## 3. ADR-38 excerpt

> **Decision:** Phase 5.3 measures whether the gateway-grounded
> verifier loop improves verifier quality on a private/synthetic
> holdout before opening any MCP surface.

The full ADR (Why / Decision / Accepted / Rejected / Outcome)
lives at the bottom of `memory-bank/decisionLog.md`.

## 4. Holdout dataset design

`datasets/private_holdout_v2/` follows the same
schema-only-public, cases-private pattern as v1:

* `README.md` and `manifest.example.json` are committed.
* `cases/` is gitignored (per-operator local content).
* Synthetic cases CAN be committed if the operator chooses; the
  example manifest documents 4 representative slate entries.

Pilot size (per QA/A30 §5.3-A):

| Family | Count |
|---|---|
| `claim_contract` | 8 |
| `gateway_grounded` | 8 |
| `code_outcome` (F2P/P2P) | 4 |
| `safety_adversarial` | 4 |

The schema for `expected.json` is `GatewayHoldoutExpected`,
introduced in `src/oida_code/calibration/gateway_holdout.py`:

```python
class GatewayHoldoutExpected(BaseModel):
    case_id: str
    expected_baseline: ExpectedVerifierOutcome
    expected_gateway:  ExpectedVerifierOutcome
    expected_delta:    Literal["improves", "same",
                                "worse_expected", "not_applicable"]
    required_tool_evidence_refs:  tuple[str, ...] = ()
    forbidden_acceptance_reasons: tuple[str, ...] = ()
```

## 5. Baseline vs gateway protocol

Per case, two runs:

* **baseline** — `run_verifier(packet, forward_replay,
  backward_replay)`. No tool execution. Cites only the packet's
  pre-existing `evidence_items`.
* **gateway** — `run_gateway_grounded_verifier(packet,
  forward_pass1, backward_pass1, forward_pass2, backward_pass2,
  gateway, ...)`. Two-pass loop with `LocalDeterministicToolGateway`.

The runner does not commit one mode over the other; both run on
the same packet, and the `delta_metrics.json` file records the
per-metric difference.

## 6. Metrics

Per-mode (computed independently):

| Metric | Definition |
|---|---|
| `claim_accept_accuracy` | `accepted_correct / (accepted_correct + accepted_wrong)` |
| `claim_macro_f1` | macro-F1 across the three claim outcome buckets |
| `unsupported_precision` | `unsupported_correct / (unsupported_correct + unsupported_wrong)` |
| `rejected_precision` | `rejected_correct / (rejected_correct + rejected_wrong)` |
| `evidence_ref_precision` | citations that exist in the packet / total citations |
| `evidence_ref_recall` | required refs cited / required refs declared |
| `tool_contradiction_rejection_rate` | claims rejected when a tool contradicted them |
| `unsupported_claim_detection_rate` | claims correctly demoted to unsupported |
| `citation_fresh_tool_ref_rate` | gateway accepted_claims that cite at least one new `[E.tool_output.*]` ref / gateway accepted_claims |
| `official_field_leak_count` | runs where any forbidden phrase appeared (must be 0) |

Cross-mode:

| Metric | Definition |
|---|---|
| `gateway_delta` | per-metric `gateway − baseline` |

`gateway_delta > 0`: structural improvement (diagnostic, not a
production threshold).
`gateway_delta = 0`: no measured improvement.
`gateway_delta < 0`: investigate before any default integration.

The `delta_metrics.json` file carries an explicit
`"delta_diagnostic_only": true` flag and a verbatim
`"reserved": ...` warning that mirrors the Phase 4.0
`official_ready_candidate` RESERVED pattern.

## 7. F2P / P2P policy

`code_outcome` cases continue to follow SWE-bench's
FAIL_TO_PASS + PASS_TO_PASS contract. The Phase 4.3
`CalibrationCase` model already enforces F2P-non-empty; v2
inherits the constraint. Operator-supplied `expected.json` for
code_outcome must satisfy the existing schema.

## 8. Contamination policy

`provenance` ladder:
`synthetic` / `private_trace` / `private_repo` / `public_low` /
`public_high`.

`contamination_risk` ladder:
`synthetic` / `private` / `public_low` / `public_high`.

Rules:

1. `public_high` cases are EXCLUDED from headline metrics.
2. `private_repo` / `private_trace` cases are NEVER committed
   if they contain proprietary code.
3. `synthetic` cases CAN be committed but MUST be marked.
4. `public_low` cases CAN be committed and feed headline
   metrics.

The runner reports both the with-public_high and
without-public_high numbers; only the latter is allowed to
lead a recommendation.

## 9. Calibration results

Phase 5.3 ships the protocol + scaffolding. The
`run_calibration` function emits five artifacts under the
chosen `--out` directory:

* `baseline_metrics.json`
* `gateway_metrics.json`
* `delta_metrics.json` (with `delta_diagnostic_only: true`)
* `failure_analysis.md`
* `artifact_manifest.json` (SHA256 hashes of the four above)

For the committed `manifest.example.json`, every case is
classified `insufficient_fixture` because the slate documents
the cases without shipping their per-case replay JSONs. This
is intentional: operators commit per-case fixtures locally
under `datasets/private_holdout_v2/cases/` (gitignored), and
the runner produces real metrics without any code change.

The smoke workflow (`gateway-calibration.yml`) runs against
the example manifest on every push to `main` plus
`workflow_dispatch`, exercises the four-artifact write path,
and uploads the artifacts under `actions/upload-artifact@v4`.

## 10. Failure analysis

The `failure_analysis.md` table has seven columns: `case_id`,
`mode`, `expected`, `actual`, `classification`, `root_cause`,
`recommended_action`. The classification vocabulary is fixed:

| Classification | Meaning |
|---|---|
| `label_too_strict` | Operator label rejected an outcome that turned out to be sound on inspection |
| `gateway_bug` | Gateway routing or admission behaviour diverged from spec |
| `tool_adapter_bug` | A specific deterministic tool adapter produced wrong evidence |
| `aggregator_bug` | The verifier aggregator's rule fired in an unintended way |
| `citation_gap` | Pass-2 forward failed to cite available tool refs (anti-injection or prompt design issue) |
| `insufficient_fixture` | The replay fixture was underspecified relative to the label |
| `expected_behavior_changed` | The product intentionally changed; label needs operator update |

**Anti-mutation invariant**: NO automatic label change ever.
Every classification row is a PROPOSAL. The runner is read-only
over `datasets/` — the test
`test_calibration_runner_does_not_mutate_dataset` snapshots
mtimes before and after a full run and asserts equality.

## 11. No-MCP regression locks

* `test_no_mcp_dependency_added` — pyproject.toml clean.
* `test_no_mcp_workflow_added` — every workflow file checked
  for the JSON-RPC discovery + dispatch verbs.
* `test_no_jsonrpc_runtime_in_calibration_script` — the
  calibration script's body cannot reference `mcp.server`,
  `stdio_server`, `modelcontextprotocol`, `jsonrpc`,
  `json-rpc`.
* `test_no_provider_tool_calling_enabled_in_phase5_3` — regex
  scan against OpenAI / Anthropic SDK call shapes that would
  enable provider-side tool calling.
* `test_gateway_calibration_workflow_no_mcp` — workflow body
  does not reference MCP primitives.
* `test_gateway_calibration_workflow_no_sarif_upload` — Phase
  5.3 calibration is measurement, not code-scanning.

The Phase 4.7 / Phase 5.0 / Phase 5.1 / Phase 5.2 anti-MCP
locks remain active.

## 12. What this still does not prove

* Production predictive performance — the holdout is a
  controlled measurement surface, not a deployment forecast.
* MCP readiness — the gateway has not been exposed to dynamic
  third-party schemas.
* Provider-side tool-calling correctness — Phase 5.3 stays
  replay-only by default.
* Official `total_v_net` / `debt_final` / `corrupt_success` —
  the schemas still don't expose those fields, and the runner
  asserts `official_field_leak_count == 0` in both modes.
* Anything resembling "merge-safe" — `gateway_delta` is
  diagnostic only.

## 13. Recommendation for Phase 5.4

Per QA/A30 §"Après Phase 5.3":

* **If calibration shows clear improvement** — Phase 5.4 =
  integrate the gateway-grounded verifier as an OPT-IN action
  path. `enable-tool-gateway` stays default `"false"`.
* **If improvement is weak or negative** — Phase 5.4 = fix
  verifier prompts / labels / tool-request policy. Investigate
  before any default integration.

Only much later, Phase 5.5+ may revisit the local stdio MCP
mock prototype — contingent on the gateway loop genuinely
improving metrics, holdout stability, clean tool citations,
tool contradictions rejected, and the no-MCP locks still
green.

## 14. Gates

| Gate | Status |
|---|---|
| ruff (`src/`, `tests/`, `scripts/evaluate_shadow_formula.py`, `scripts/real_repo_shadow_smoke.py`, `scripts/run_gateway_calibration.py`) | clean |
| mypy (same set) | clean (92 source files; was 89 before Phase 5.3) |
| pytest full suite | 763 passed / 4 skipped (was 730/4 — exactly +33 new tests) |
| `tests/test_phase5_3_gateway_calibration.py` | 33 / 33 passing |
| GitHub-hosted CI runs | all five green on commit `103b2ff` — ci (24961882218, 1m13s), action-smoke (24961882214, 1m08s), provider-baseline-node24-smoke (24961882219, 20s), gateway-grounded-smoke (24961882225, 19s), gateway-calibration (24961882238, 20s) |

## Honesty statement

Phase 5.3 calibrates the gateway-grounded verifier loop on controlled holdout cases.
It does not implement MCP.
It does not enable provider tool-calling.
It does not validate production predictive performance.
It does not tune production thresholds.
It does not emit official total_v_net, debt_final, or corrupt_success.
It does not modify the vendored OIDA core.

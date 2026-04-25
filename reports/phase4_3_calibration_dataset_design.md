# Phase 4.3 — Calibration dataset design

**Date**: 2026-04-26.
**Scope**: QA/A19.md — design and pilot a calibration dataset for
estimator / verifier / tool-loop quality, **without** predictive
claims about production success.
**Authority**: ADR-28 (Calibration dataset before predictive claims)
+ 4.2.1 paired hardening (named OIDA_EVIDENCE in phase4_2 report +
engine global-budget pre-clamp).
**Reproduce**:

```bash
python scripts/build_calibration_dataset.py
python scripts/run_calibration_eval.py
python scripts/check_calibration_stability.py
python -m pytest tests/test_phase4_3_calibration.py -q
```

**Verdict (TL;DR)**: structural complete. The 32-case pilot exercises
five families (claim_contract, tool_grounded, shadow_pressure,
code_outcome with F2P/P2P, safety_adversarial); all 22 framework
tests pass; the pilot eval reports **zero official-field leaks** and
schema-pinned metrics. **No external API call. No threshold tuning
for production. No predictive claim.** ADR-22 + ADR-25 + ADR-26 +
ADR-27 + ADR-28 all hold.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-28 | +95 |
| `reports/phase4_2_tool_grounded_verifier_loop.md` | 4.2.1 doc sync (`<<...>>` shorthand → explicit OIDA_EVIDENCE form) | ±10 |
| `src/oida_code/verifier/tools/__init__.py` | 4.2.1 — engine pre-clamps per-tool timeout + blocks without invocation when global budget exhausted; honors executor-reported runtime_ms | +30 |
| `src/oida_code/calibration/__init__.py` | sub-package re-exports | ~70 |
| `src/oida_code/calibration/models.py` | `CalibrationCase` / `Expected*Label` / `ExpectedCodeOutcome` / `CalibrationProvenance` / `CalibrationManifest` | ~210 |
| `src/oida_code/calibration/metrics.py` | `CalibrationMetrics` schema + pure helpers | ~150 |
| `src/oida_code/calibration/runner.py` | per-family evaluators + aggregation | ~520 |
| `pyproject.toml` | mypy excludes `datasets/` (calibration repos have intentional duplicate `src/` layout) | +9 |
| `scripts/build_calibration_dataset.py` | builds the 32-case pilot | ~600 |
| `scripts/run_calibration_eval.py` | eval runner → `metrics.json` + `report.md` | ~140 |
| `scripts/check_calibration_stability.py` | 3× pytest stability for `code_outcome` cases | ~160 |
| `datasets/calibration_v1/` | 32 cases + `manifest.json` | ~3500 |
| `tests/test_phase4_2_tool_grounded_verifier.py` | +3 tests for 4.2.1 hardening | +60 |
| `tests/test_phase4_3_calibration.py` | 22 tests (schema + metric helpers + runner + pilot smoke + manifest invariants) | ~360 |
| `reports/phase4_3_calibration_dataset_design.md` | this report | — |

**Gates**: ruff clean, mypy clean (75 src files), **462 passed + 3
skipped** (1 V2 placeholder + 2 Phase-4 observability markers).

---

## 2. 4.2.1 micro-fixes

A. **Doc sync** — `reports/phase4_2_tool_grounded_verifier_loop.md`
   §3 (4.1.1 hardening) and the `prompt_injection_in_tool_output`
   fixture row now spell out the full
   `<<<OIDA_EVIDENCE id="[E.x.y]" kind="...">>>` ...
   `<<<END_OIDA_EVIDENCE id="[E.x.y]">>>` form. No more
   `<<...>>` shorthand or generic "named fences" phrasing.

B. **Engine global-budget pre-clamp** — Phase 4.2's engine measured
   total runtime AFTER each request. A single tool consuming its own
   `max_runtime_s` could push past the engine-level
   `max_total_runtime_s`. The 4.2.1 fix:

   ```python
   remaining_ms = budget_ms - total_runtime_ms
   if remaining_ms <= 0:
       results.append(VerifierToolResult(
           tool=request.tool, status="blocked",
           blockers=("max_total_runtime_s={...} exhausted before request "
                     "{...}; executor not invoked",),
       ))
       continue
   effective_timeout_s = max(
       1, min(request.max_runtime_s, max(1, remaining_ms // 1000)),
   )
   clamped_request = request.model_copy(
       update={"max_runtime_s": effective_timeout_s},
   )
   ```

   The engine also honors the larger of wall-clock runtime and the
   executor-reported `outcome.runtime_ms` so a fake/replay executor
   reporting a synthetic runtime still consumes the engine's budget.

   Tests:
   - `test_engine_clamps_per_tool_timeout_to_remaining_global_budget`
   - `test_engine_blocks_without_invocation_when_global_budget_exhausted`
   - `test_budget_block_result_preserves_request_order`

---

## 3. ADR-28 excerpt

> **Decision**: Phase 4.3 defines a calibration dataset and evaluation
> protocol for estimator / verifier / tool-loop quality. It does not
> validate production predictive performance and does not unlock
> official OIDA fusion fields.
>
> **Accepted**: claim-level labels, evidence-ref labels, tool-result
> labels, seeded synthetic repo defects, F2P/P2P tests where
> code-outcome is claimed, multi-run stability checks, contamination /
> provenance metadata, no threshold fitting on the same set used for
> reporting.
>
> **Rejected**: `commits > 0` as outcome, session length as success
> proxy, public benchmark score as real-world proof, official V_net /
> debt / corrupt_success from calibration, LLM-as-judge for ground
> truth.

Full text: `memory-bank/decisionLog.md` `[2026-04-26 14:00:00]`.

---

## 4. Dataset purpose and non-goals

### Goal

> Does the measurement pipeline behave as intended on controlled
> cases?

### NOT a goal

> Does this predict production incidents?

The Phase-3 audit identified two failure modes the calibration
dataset MUST avoid:

1. `progress_rate` was mechanically tied to session length — a
   length confound dressed as predictive signal.
2. `commits > 0` was tautological as an outcome label — it
   classified anything with at least one commit as "successful"
   regardless of whether the change accomplished its goal.

ADR-28 §rejected lists both as forbidden. The pilot dataset uses
deterministic, small, hand-seeded cases where ground truth is
explicit; success is **not** "did the agent commit" but "did each
labelled F2P test go from fail to pass and each P2P test stay
green".

---

## 5. Dataset schema

```python
class CalibrationCase(BaseModel):  # frozen, extra=forbid
    case_id: str
    family: Literal[
        "claim_contract", "tool_grounded", "shadow_pressure",
        "code_outcome", "safety_adversarial",
    ]

    repo_fixture: str | None = None
    request_path: str | None = None
    trace_path: str | None = None
    packet_path: str | None = None
    tool_policy_path: str | None = None
    tool_requests_path: str | None = None
    canned_tool_outputs_path: str | None = None
    forward_replay_path: str | None = None
    backward_replay_path: str | None = None

    expected_claim_labels: tuple[ExpectedClaimLabel, ...] = ()
    expected_tool_results: tuple[ExpectedToolResultLabel, ...] = ()
    expected_shadow_bucket: Literal["low","medium","high","not_applicable"]
    expected_repair_behavior: ExpectedRepairBehavior | None = None
    expected_code_outcome: ExpectedCodeOutcome | None = None

    provenance: CalibrationProvenance
    contamination_risk: Literal["synthetic","private","public_low","public_high"]
    notes: str = ""
```

Family-specific invariants enforced at the model level:

| family | requires |
|---|---|
| `code_outcome` | `expected_code_outcome` with ≥1 F2P test |
| `shadow_pressure` | `expected_shadow_bucket ∈ {low, medium, high}` |
| `tool_grounded` | ≥1 `expected_tool_results` entry |
| any other | NULL `expected_code_outcome` |

`ExpectedCodeOutcome` requires F2P; the `@model_validator` literally
refuses to construct a code_outcome case without an F2P test. Cases
without executable F2P MUST stay in `claim_contract` or
`shadow_pressure` (ADR-28 §4.3-A).

---

## 6. Family taxonomy

| family | what it tests | input |
|---|---|---|
| `claim_contract` | aggregator end-to-end | packet + forward + backward replay |
| `tool_grounded` | sandbox + adapter + engine | policy + requests + canned executor outcomes |
| `shadow_pressure` | shadow fusion bucket classification | NormalizedScenario |
| `code_outcome` | F2P/P2P signals via real pytest | mini-repo |
| `safety_adversarial` | fence + aggregator vs hostile input | hostile packet (+ optional replays) |

---

## 7. Pilot case table

32 cases total. Deterministically built by
`scripts/build_calibration_dataset.py`.

### claim_contract (8)

| id | slug | expected | reason |
|---|---|---|---|
| C001 | clean_supported_claim | accepted | supported_by_forward_backward |
| C002 | forward_only_unsupported | unsupported | missing_backward_requirement |
| C003 | backward_missing_negative | unsupported | missing_backward_requirement |
| C004 | unknown_evidence_ref | rejected | unknown_evidence_ref |
| C005 | forbidden_phrase_rejected | rejected | forbidden_claim |
| C006 | confidence_cap_exceeded | rejected | confidence_cap_exceeded |
| C007 | benefit_missing_intent | unsupported | missing_backward_requirement |
| C008 | repair_needed_diagnostic | accepted | supported_by_forward_backward |

### tool_grounded (8)

| id | slug | tool | expected_status |
|---|---|---|---|
| T001 | ruff_finding_contradicts | ruff | failed |
| T002 | mypy_finding_contradicts | mypy | failed |
| T003 | pytest_scoped_pass_supports | pytest | ok |
| T004 | pytest_timeout_uncertainty | pytest | timeout |
| T005 | tool_missing_uncertainty | ruff | tool_missing |
| T006 | semgrep_no_adapter_blocked | semgrep | blocked |
| T007 | path_traversal_blocked | ruff | blocked |
| T008 | secret_path_blocked | ruff | blocked |

### shadow_pressure (6)

| id | slug | expected_bucket |
|---|---|---|
| S001 | clean_success_low | low |
| S002 | migration_partial_medium | medium |
| S003 | corrupt_plausible_high | high |
| S004 | supportive_audit_low | low |
| S005 | constitutive_debt_medium | medium |
| S006 | missing_grounding_neutral | medium |

### code_outcome (6)

Each ships a `repo/src/calc.py` + `repo/tests/test_calc.py`. F2P:
`tests/test_calc.py::test_divide_by_zero_returns_none`. P2P:
`tests/test_calc.py::test_divide_basic`.

| id | slug |
|---|---|
| O001 | bug_fix_simple |
| O002 | regression_introduced |
| O003 | no_fix_f2p_still_fails |
| O004 | negative_path_missing |
| O005 | rollback_missing |
| O006 | auth_guard_missing |

### safety_adversarial (4)

| id | slug | attack |
|---|---|---|
| A001 | prompt_injection_in_code_comment | comment-borne injection |
| A002 | prompt_injection_in_tool_output | tool-output-borne injection |
| A003 | forged_evidence_id | unknown ref |
| A004 | fence_close_attempt | attempt to close OIDA_EVIDENCE fence |

---

## 8. Ground-truth policy

Every case ships its expected labels in `expected.json` (the
serialized `CalibrationCase`). Labels are:

* **`ExpectedClaimLabel`** — `claim_id`, `event_id`,
  `expected ∈ {accepted, unsupported, rejected}`, `reason ∈
  {supported_by_forward_backward, missing_backward_requirement,
  unknown_evidence_ref, tool_contradiction, forbidden_claim,
  missing_citation, prompt_injection, confidence_cap_exceeded,
  event_id_mismatch}`, optional `required_evidence_refs`.
* **`ExpectedToolResultLabel`** — `request_id` (matched by
  `<tool>:<idx>`), `tool`, `expected_status ∈ {ok, failed, error,
  timeout, tool_missing, blocked}`, optional
  `expected_block_reason_substring`.
* **`ExpectedCodeOutcome`** — `f2p_tests`, `p2p_tests` (test paths),
  pinned `expected_f2p_before="fail"`, `expected_f2p_after="pass"`,
  `expected_p2p_before="pass"`, `expected_p2p_after="pass"`,
  `stability_runs ≥ 1` (default 3).

No LLM was used to generate any of the labels. All 32 cases carry
`provenance.created_by="script"` and `source="synthetic"` —
`build_calibration_dataset.py` is the sole author.

---

## 9. F2P / P2P policy

Inspired by SWE-bench / SWE-bench Multilingual / ProdCodeBench: F2P
tests verify the bug fix; P2P tests verify the absence of
regressions. The pilot uses one mini-repo (`src/calc.py` with a
`divide` function and an explicit zero-handling guard); the F2P
test asserts `divide(1, 0) is None` (passes after the fix), the P2P
test asserts `divide(10, 2) == 5` (passes before AND after).

The 6 `code_outcome` cases vary the `src/calc.py` source:

* O001 (bug_fix_simple) — fixed source; F2P passes.
* O002 (regression_introduced) — broken source; F2P fails (regression).
* O003 (no_fix_f2p_still_fails) — broken source; F2P fails (no fix).
* O004–O006 — narrative variants on the fixed source for label
  diversity (negative-path / rollback / auth).

Stability check (`scripts/check_calibration_stability.py`) invokes
`pytest --no-header -q -p no:cacheprovider <test path>` three times
per case under `repo/`; cases where any two runs disagree on F2P or
P2P are flagged `flaky` and excluded from headline metrics. Pytest
itself runs with `shell=False`.

---

## 10. Stability policy

`stability_runs = 3` (configurable per case). A case is **flaky**
when:

1. any run had `returncode = -1` (pytest binary missing); OR
2. any two runs disagree on the F2P pass-set OR P2P pass-set.

Flaky cases are excluded from the headline calibration metrics. The
stability report lives at `.oida/calibration_v1/stability_report.json`
so an integrator can audit individual runs.

---

## 11. Contamination policy

`CalibrationProvenance.contamination_risk` is one of:

| value | semantic |
|---|---|
| `synthetic` | hand-seeded, no public source |
| `private` | private trace; not redistributable |
| `public_low` | public source, low overlap with vendor training data |
| `public_high` | public benchmark known to be in vendor training data |

`run_calibration_eval.py` automatically excludes `public_high` cases
from headline metrics (`cases_excluded_for_contamination` in the
output). The pilot is 100% `synthetic` — every case was authored by
`build_calibration_dataset.py`. There is NO public-benchmark case in
the pilot. ADR-28 §rejected #3 forbids using public benchmark scores
as real-world proof; the OpenAI 2026 audit on SWE-bench Verified
(retraction citing contamination + ≥59.4% defective tests in the
audited subset) is the explicit reason.

---

## 12. Metrics

`CalibrationMetrics` (frozen, `extra="forbid"`,
`official_field_leak_count: Literal[0]`):

| metric | meaning |
|---|---|
| claim_accept_accuracy | overall claim-bucket correctness |
| claim_accept_macro_f1 | macro-F1 across {accepted, unsupported, rejected} (required because the three buckets are imbalanced — accuracy alone could mask "always accept") |
| unsupported_precision / rejected_precision | per-class precision |
| evidence_ref_precision / recall | citation correctness |
| unknown_ref_rejection_rate | rate at which `[E.unknown.X]`-style refs are correctly rejected |
| tool_contradiction_rejection_rate | rate at which a `failed` tool finding rejects a contradicting LLM claim |
| tool_uncertainty_preservation_rate | rate at which `tool_missing`/`timeout`/`error` is preserved as uncertainty (NOT promoted to failure) |
| sandbox_block_rate_expected | rate at which deny-pattern / path-traversal / unknown-tool requests are blocked |
| shadow_bucket_accuracy | per-case bucket match (low/medium/high) |
| shadow_pairwise_order_accuracy | placeholder for cross-case ordering (deferred to v0.2 — pairwise expected lists not yet in the case schema) |
| f2p_pass_rate_on_expected_fixed / p2p_preservation_rate | code-outcome metrics; deferred to stability script in the pilot |
| flaky_case_count | code-outcome cases excluded for non-determinism |
| safety_block_rate / fenced_injection_rate | adversarial fixture correctness |
| official_field_leak_count | **MUST be 0**; pinned to `Literal[0]` so the schema literally cannot publish a non-zero leak |

Pure helpers (`metrics.py`):

* `macro_f1_from_confusion(confusion)` — drops empty-support classes
  from the macro average so an imbalanced pilot doesn't penalise a
  perfect-on-the-classes-with-data runner.
* `precision(tp, fp)`, `recall(tp, fn)`, `safe_rate(num, denom)` —
  zero-denominator returns `0.0`.
* `pairwise_order_accuracy(pairs, rank, bucket_order)` — checks
  expected `<` / `>` / `=` relations; unused in the pilot but kept
  for v0.2.

---

## 13. Pilot evaluation results

```bash
$ python scripts/run_calibration_eval.py
wrote metrics + report to .oida\calibration_v1
cases_evaluated=32 leaks=0
```

`.oida/calibration_v1/metrics.json` (excerpt):

```json
{
  "cases_total": 32,
  "cases_evaluated": 32,
  "cases_excluded_for_contamination": 0,
  "cases_excluded_for_flakiness": 0,
  "claim_accept_accuracy": 1.0,
  "claim_accept_macro_f1": 1.0,
  "unsupported_precision": 1.0,
  "rejected_precision": 1.0,
  "evidence_ref_precision": 1.0,
  "evidence_ref_recall": 1.0,
  "unknown_ref_rejection_rate": 1.0,
  "tool_contradiction_rejection_rate": 1.0,
  "tool_uncertainty_preservation_rate": 1.0,
  "sandbox_block_rate_expected": 1.0,
  "shadow_bucket_accuracy": 1.0,
  "shadow_pairwise_order_accuracy": 0.0,
  "f2p_pass_rate_on_expected_fixed": 0.0,
  "p2p_preservation_rate": 0.0,
  "flaky_case_count": 0,
  "safety_block_rate": 1.0,
  "fenced_injection_rate": 1.0,
  "official_field_leak_count": 0,
  "notes": "calibration_v1 pilot: tool_status_match_rate=1.000; leaks_seen=0"
}
```

The pilot evaluates with all behavioural metrics at 1.0. **This is
expected and not a quality claim** — the pilot is a self-test of
the framework: `build_calibration_dataset.py` and `run_calibration_eval.py`
both consume the same `CalibrationCase` schema, and the build script
deliberately constructs cases the runner already handles. ADR-28
§4.3-G forbids treating the headline numbers as production
thresholds. The pilot's job is to prove the **measurement pipeline
itself** behaves as intended; quality measurement of the LLM
estimator + verifier on real cases is Phase 4.4+ work.

`f2p_pass_rate_on_expected_fixed` and `p2p_preservation_rate`
remain at 0.0 in the eval output because `code_outcome` cases are
deferred to the stability script (`check_calibration_stability.py`
emits `.oida/calibration_v1/stability_report.json` with per-run
detail). A future eval revision will fold the stability report into
the headline metric.

---

## 14. Failure analysis

The pilot exposed three real bugs during construction (all fixed
before this report):

1. The `repair_signal` evidence kind was originally written as
   `"repair"` in the build script; the schema's
   `EvidenceKind` Literal correctly rejected it. Fixed by using the
   full `repair_signal` token (and updating the test ref to
   `[E.repair_signal.1]`).
2. The shadow_pressure spec list was untyped → mypy couldn't infer
   the value type when iterating. Fixed by adding an explicit
   `list[tuple[str, str, str, dict[str, Any]]]` annotation.
3. The mypy-self test (`test_run_type_check_on_self_repo_returns_ok`)
   started failing because the seeded `code_outcome` repos contained
   duplicate `src/__init__.py` modules. Fixed by adding `datasets/`
   to `[tool.mypy] exclude` — the calibration runner exercises those
   repos via subprocess pytest invocations, not via the project
   mypy gate.

Each of these failures was caught by an existing test or gate before
landing. The framework rejects ill-formed cases at schema
construction; the metric pinning rejects ill-formed metrics at
serialization.

---

## 15. What this still does not prove

* The pilot does NOT prove that OIDA-code's estimator / verifier
  predicts production success. ADR-28 §rejected #3 forbids that
  claim; the dataset is too small (32 cases) and too synthetic to
  support it.
* Calibration of LLM confidence (Expected Calibration Error, etc.)
  is NOT yet computed. ADR-28 §4.3-D notes ECE may be added later
  but warns against strong claims on a small pilot.
* Public-benchmark (SWE-bench / SWE-bench Multilingual /
  ProdCodeBench) compatibility is NOT claimed. The pilot is 100%
  synthetic; integrating real public cases requires the
  contamination policy to mark them `public_high` and exclude them
  from headline metrics by default.
* `code_outcome` headline rates are deferred to the stability
  script; they are not folded into `metrics.json` yet.

---

## 16. Recommendation for Phase 4.4

Per QA/A19.md §"Après Phase 4.3":

* **Phase 4.4 — real provider binding behind explicit opt-in.**
  Bind `OptionalExternalLLMProvider` /
  `OptionalExternalVerifierProvider` to one vendor under explicit
  flag + env var. The calibration dataset becomes the regression
  harness for the binding: a real provider should produce identical
  metrics on the synthetic cases (no behavioural drift).
* **Phase 4.5 — CI / GitHub Action integration.** Wire `audit` +
  `verify-claims` chain into the existing GitHub Action stub.
* **Phase 4.6 — calibration dataset expansion + holdout split.**
  Grow to 100+ cases; reserve a held-out subset for reporting and
  forbid threshold tuning on that subset.

Out-of-scope until at least Phase 4.6:

* Official `V_net` / `debt_final` / `corrupt_success` emission.
* Production thresholds derived from calibration_v1.
* PyPI stable release.

---

## 17. Honesty statement

Phase 4.3 defines and pilots a calibration dataset for estimator,
verifier and tool-loop behaviour.

It does **NOT** validate production predictive performance.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-28 hold.

It does **NOT** modify the vendored OIDA core (ADR-02 holds).

It does **NOT** justify public benchmark claims. The OpenAI 2026
audit on SWE-bench Verified is the cautionary precedent; the pilot
is 100% synthetic and `public_high` cases would be excluded from
headline metrics by construction.

It does **NOT** call any external API by default. The runner uses
file-replay + canned-executor everywhere; the stability script
invokes a real `pytest` subprocess (operator-driven).

Today, the production CLI on a real repo produces an
`EstimatorReport` with `status="blocked"` and a
`VerifierAggregationReport` with `status="blocked"` — that's the
**correct** state until Phase 4.4 wires real evidence.

---

## 18. Gates

| gate | status |
|---|---|
| `python -m ruff check src/ tests/ scripts/` | clean |
| `python -m mypy src/ scripts/...` | 75 src files, no issues |
| `python -m pytest -q` | **462 passed, 3 skipped** |
| `python scripts/build_calibration_dataset.py` | 32 cases written |
| `python scripts/run_calibration_eval.py` | leaks=0; metrics.json + report.md emitted |
| repo + history scan for committed keys | clean |

---

## 19. Acceptance checklist (QA/A19.md §"Critères d'acceptation Phase 4.3")

| # | criterion | status |
|---|---|---|
| 1 | 4.2.1 doc fence residue fixed | DONE — phase4_2 §3 + §9 spell out OIDA_EVIDENCE explicitly |
| 2 | 4.2.1 global budget pre-clamp fixed | DONE (engine clamps + blocks; 3 new tests) |
| 3 | ADR-28 written | DONE (`memory-bank/decisionLog.md`) |
| 4 | CalibrationCase schema added | DONE (`models.py`) |
| 5 | ExpectedClaimLabel schema added | DONE |
| 6 | ExpectedToolResultLabel schema added | DONE |
| 7 | ExpectedCodeOutcome schema added with F2P/P2P | DONE (model_validator requires ≥1 F2P) |
| 8 | CalibrationMetrics schema added | DONE (`metrics.py`) |
| 9 | datasets/calibration_v1/manifest.json produced | DONE |
| 10 | At least 32 pilot cases created | DONE (32 exactly) |
| 11 | At least 6 code_outcome cases include F2P/P2P tests | DONE (O001..O006) |
| 12 | Stability script runs code_outcome cases 3 times | DONE (`check_calibration_stability.py`) |
| 13 | Flaky cases are detected and excluded from metrics | DONE (`aggregate` filters `flaky`) |
| 14 | run_calibration_eval.py produces metrics.json | DONE (`.oida/calibration_v1/metrics.json`) |
| 15 | Evidence-ref precision/recall computed | DONE (`evidence_ref_precision/recall`) |
| 16 | Tool contradiction rejection rate computed | DONE (`tool_contradiction_rejection_rate`) |
| 17 | Shadow bucket/order metrics computed | DONE (bucket: 1.0; pairwise: deferred to v0.2) |
| 18 | Official field leak count is zero | PASS (`Literal[0]` pin + `0` in pilot) |
| 19 | No external provider called by default | PASS (replay + canned executor only) |
| 20 | No LLM judge used as ground truth | PASS (`provenance.created_by="script"` for all 32) |
| 21 | report phase4_3 produced | DONE (this file) |
| 22 | ruff clean | PASS |
| 23 | mypy clean | PASS |
| 24 | pytest full green, skips documented | PASS (462 + 3 documented skips) |

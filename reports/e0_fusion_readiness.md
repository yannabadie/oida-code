# E0 — Fusion readiness review

**Date**: 2026-04-25.
**Scope**: QA/A10.md — pre-fusion gate before any official `V_net` /
`debt_final` / `corrupt_success` emission.
**Reproduce**:

```bash
python -m pytest tests/test_e0_fusion_readiness.py -q
python -c "from oida_code.score.fusion_readiness import assess_fusion_readiness; ..."
```

---

## 1. Diff résumé

| File | Role |
|---|---|
| `memory-bank/decisionLog.md` | ADR-22 entry |
| `src/oida_code/score/fusion_readiness.py` | new module: `assess_fusion_readiness`, `FusionReadinessReport`, 12 per-field auditors |
| `src/oida_code/score/trajectory.py` | E0.1 — `compute_paper_gain` gains optional `pending_direct_deps` parameter; scoring loop builds the dep map once |
| `tests/test_e0_fusion_readiness.py` | 12 tests (3 E0.1 + 9 E0) |
| `README.md` | Status updated to Phase 3.5 complete (hygiene fix per A10.md) |
| `reports/e0_fusion_readiness.md` | this report |

Gates: ruff clean, mypy clean (51 src files), **225/225 unit tests pass**.

---

## 2. ADR-22 excerpt

> OIDA-code MUST NOT emit official `V_net` / `debt_final` /
> `corrupt_success` while:
>
> 1. Load-bearing event fields (`capability`, `benefit`, `observability`)
>    remain at their structural defaults.
> 2. Graph-aware fusion is uncalibrated.
> 3. LLM-only sub-preconditions remain unresolved.
>
> Accepted protocol: emit a `FusionReadinessReport` that classifies
> every load-bearing field by source + status + confidence + whether
> it blocks official fusion. Allow experimental SHADOW fusion only if
> clearly marked non-authoritative.
>
> Rejected: filling V_net from default-0.5 fields, treating dep-graph
> presence as graph-aware debt, treating any B-state pattern as
> public corrupt_success, modifying vendored OIDA core before a
> separate-layer experiment.

---

## 3. Field readiness table (current snapshot)

Run on a typical Phase-3.5 scenario (default capability/benefit/observability,
green pytest + ruff + mypy, ADR-20 multi-child preconditions, ADR-21 graph,
real trajectory metrics):

| Field | Source | Status | Confidence | Blocks official | Next action |
|---|---|---|---:|:---:|---|
| `capability` | default 0.5 | default | 0.0 | **YES** | Phase 4 LLM intent estimator |
| `benefit` | default 0.5 | default | 0.0 | **YES** | Phase 4 intent/value estimator |
| `observability` | default 0.5 | default | 0.0 | **YES** | tests/logging/telemetry detector |
| `completion` | pytest pass-ratio | real | 0.7 | no | improve test-discovery scope |
| `tests_pass` | weighted blend | heuristic | 0.5 | no | wire mutmut + hypothesis defaults-on |
| `operator_accept` | ruff + mypy green | real | 0.7 | no | add semgrep/codeql to default pipeline |
| `grounding` | ADR-20 child weights | real (partial) | up to 0.6 | no | LLM-evidence matchers for the 6 default-False sub-preconditions |
| `preconditions` | ADR-20 1..N expansion | real | 0.6 | no | add missing kinds (custom user kinds) |
| `constitutive_edges` | ADR-21 same-symbol rule | real (bounded) | 0.6 | no | calibrate edge confidence vs ground-truth |
| `supportive_edges` | ADR-21 imports/tests/migration | real (bounded) | 0.6 | no | richer test-to-source mapping (Block C carry-over) |
| `trajectory_metrics` | paper-faithful + structural smoke | real (structural) | 0.7 | no | real outcome dataset for ρ measurement (Phase 4+) |
| `repair_signal` | `double_loop_repair` (vendored) | real (bounded) | 0.6 | no | calibrate dominator-based reopen vs human labels |

**Overall verdict on this scenario: `blocked`.** The three structural-default
fields are non-negotiable until Phase 4.

---

## 4. Decision: separate layer vs vendored-core change

**Decision: separate layer first.**

Per ADR-22 and the architecture diagram:

```
vendored OIDA core
  → computes official local OIDA quantities when inputs are trusted

fusion_readiness layer (NEW, src/oida_code/score/fusion_readiness.py)
  → decides if official fusion is allowed

experimental_shadow layer (FUTURE, opt-in only)
  → never in summary.total_v_net
```

**Reasoning (verbatim from A10.md §E0.2):**

1. The vendored OIDA core remains the formal reference. Modifying it
   would diverge from the upstream paper.
2. The graph is already useful for repair / audit (ADR-21).
3. Graph-aware fusion is not yet calibrated.
4. A separate layer permits experimentation without altering the
   official meaning of `V_net`.
5. We can propose a core-change later if the separate layer
   stabilises and demonstrates value.

**ADR-02 vendoring discipline still holds.**

---

## 5. Current blockers to official `V_net`

| # | Blocker | Owner | Phase that resolves it |
|---|---|---|---|
| 1 | `capability = 0.5` everywhere | mapper | Phase 4 LLM intent estimator |
| 2 | `benefit = 0.5` everywhere | mapper | Phase 4 LLM intent/value estimator |
| 3 | `observability = 0.5` everywhere | mapper | test-presence detector (could be Block-E hygiene work) |
| 4 | Calibrated graph-aware fusion missing | `fusion_readiness` separate layer | E1 separate-layer experiment + dataset |
| 5 | LLM-only sub-preconditions default to `verified=False` | mapper expanders | Phase 4 LLM evidence channel |

Each blocker is exposed as a string in `FusionReadinessReport.blockers`.

---

## 6. Current blockers to official `corrupt_success`

(Per A10.md §E0.3)

* B-state pattern detection requires fully-trusted inputs (capability /
  benefit / observability) to be meaningful.
* Sustained B + negative V_net is the paper's decision rule, but V_net
  itself is blocked.
* Therefore: even on a `corrupt_plausible_success` fixture (high
  apparent completion, `negative_path_tested` unverified), the
  readiness report stays at `blocked`. No public verdict is emitted.

The Phase-3.5 scorer can flag a *suspicious* event (B-state candidate
in the underlying analyzer's pattern ledger), but the readiness layer
declines to promote that to a verdict.

---

## 7. What would be needed for `official_ready`

Concrete preconditions:

1. `capability` / `benefit` / `observability` produced by a calibrated
   estimator (Phase 4 LLM with intent grounding).
2. Validation dataset with human (or non-circular) labels showing the
   estimator's outputs correlate with ground truth.
3. Calibration evidence that `lambda_bias`, `V_dur`, `V_net` produce
   expected behaviour on the calibrated inputs.
4. At least 30 real audits (the deferred D3 statistical batch) where
   the readiness verdict tracks human or test-pass outcome.
5. Separate-layer experiment (E1) showing graph-aware propagation
   either matches or improves on the vendored local-only V_net.

None of these are unlocked by Phase 3.5.

---

## 8. Test results

12 tests in `tests/test_e0_fusion_readiness.py`, all PASS:

| Test | What it asserts |
|---|---|
| `test_direct_dependency_inspection_is_paper_gain_once` | E0.1 branch (d) fires once per segment |
| `test_repeated_dependency_inspection_eventually_errors` | repeat dep inspection → err=True |
| `test_dependency_inspection_does_not_close_obligation` | dep inspection ≠ progress_event |
| `test_fusion_readiness_blocks_when_capability_default` | A10 acceptance #3 |
| `test_fusion_readiness_blocks_when_benefit_default` | A10 acceptance #3 |
| `test_fusion_readiness_blocks_when_observability_default` | A10 acceptance #3 |
| `test_fusion_readiness_allows_diagnostic_grounding` | grounding stays diagnostic |
| `test_fusion_readiness_graph_present_does_not_unlock_vnet` | A10 acceptance #4 |
| `test_corrupt_plausible_success_is_suspicious_not_official` | A10 acceptance #5 |
| `test_official_summary_fields_remain_null_when_blocked` | A10 acceptance #6 |
| `test_shadow_fusion_if_any_is_marked_experimental` | FusionStatus literal ladder |
| `test_assess_with_trajectory_and_evidence_input` | trajectory + evidence wiring |

---

## 9. Recommendation for E1

**E1 = separate-layer experiment, not core-change.**

Concrete next steps:

1. Build a `score/experimental_shadow_fusion.py` that consumes the
   FusionReadinessReport + the dep graph + trajectory metrics, and
   emits a `ShadowFusionReport` clearly marked
   `authoritative=false`. Default off; opt-in via CLI flag.
2. Run the shadow fusion on the D2 hermetic traces and on real-repo
   smoke; compare to the vendored local V_net (which itself remains
   `null` on these traces because inputs are defaults).
3. Document where graph-aware shadow fusion DIFFERS from local V_net,
   and whether the diff is meaningful or noise.
4. **Do NOT propose a vendored-core change** until the shadow layer
   has demonstrated stable, defensible signal on at least one
   non-synthetic dataset.
5. Phase 4 LLM verifier comes AFTER E1, not in parallel — its outputs
   need a fusion path that's already understood.

---

## 10. Honesty statement (A10.md §10 mandatory)

> E0 establishes a readiness protocol. It does not emit official
> `V_net`, `debt_final`, or `corrupt_success`. It does not unlock
> graph-aware fusion. It does not modify the vendored OIDA core. It
> documents what is missing and how to recognise when the missing
> pieces have arrived.
>
> The current scenario verdict is `blocked` for every realistic input
> in v0.4.x. That is the correct answer.

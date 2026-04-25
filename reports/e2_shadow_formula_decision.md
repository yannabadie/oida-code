# E2 — Shadow formula decision

**Date**: 2026-04-25.
**Scope**: QA/A13.md — keep / revise / reject the E1.1 shadow formula.
**Authority**: ADR-23 (Shadow formula decision protocol).
**Reproduce**:

```bash
python -m pytest tests/test_e1_shadow_fusion.py tests/test_e2_shadow_formula_decision.py -q
python scripts/evaluate_shadow_formula.py        # writes .oida/e2/{sensitivity,ablation,variants}.{json,md}
python scripts/real_repo_shadow_smoke.py         # writes .oida/e2/shadow_smoke.json
```

**Verdict (TL;DR)**: **KEEP V1 (the current E1.1 formula)** with the
two minor revisions already shipped — `(a)` missing-grounding semantics
fix from E1.1, `(b)` per-edge confidence override from this commit
(ADR-23 §5 Option B). V2 (dynamic-renormalized) and V3 (conservative
status downgrade) were considered and rejected for the reasons below.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-23 — Shadow formula decision protocol | +50 |
| `src/oida_code/score/experimental_shadow_fusion.py` | optional `edge_confidences` parameter (Option B) | +20 |
| `tests/test_e2_shadow_formula_decision.py` | 16 tests + 1 V2 placeholder skip | ~470 |
| `scripts/evaluate_shadow_formula.py` | sensitivity sweep + graph ablation + variant comparison | ~530 |
| `scripts/real_repo_shadow_smoke.py` | E2 shadow smoke on oida-code self + attrs | ~250 |
| `reports/e2_shadow_formula_decision.md` | this report | — |

**Gates**: ruff clean, mypy clean (54 src files, was 52 + 2 scripts),
**277 tests pass + 1 skipped (V2 placeholder)**.

---

## 2. E1.1-doc alignment (recap)

`reports/e1_shadow_fusion.md` was re-aligned to E1.1 in commit `508a756`:
`242 → 250`, `list[...] → tuple[...]` on the public surface, frozen
pattern, missing-grounding fix. E2 starts from that aligned baseline.
Test count is now 277 (+27 from E1.1's 250) — the increment is the 17
E2 tests, the 8 E1.1 tests, and the 2 e0 grounding-zero tests already
counted under E1's window (the README's 250 figure was set after E1.1
and is updated to 277 in this commit).

---

## 3. ADR-23 excerpt

> **Decision (E2 protocol)**: evaluate the formula along three axes —
> formula variants, sensitivity sweep, graph ablation — record the
> result in `reports/e2_shadow_formula_decision.md`, and choose
> keep / revise / reject. The shadow report's non-authoritative
> status is non-negotiable regardless of outcome.
>
> **Edge-confidence sub-decision (E2 §5)**: chose **Option B** — keep
> `NormalizedEvent` schema unchanged; pass an optional
> `edge_confidences` mapping into `compute_experimental_shadow_fusion`.
> Default uniform `0.6` when absent.
>
> **Outcome**: `keep` with two minor revisions — already implemented
> in E1.1 (missing-grounding fix) and this commit (`edge_confidences`
> parameter).

Full text: `memory-bank/decisionLog.md` `[2026-04-25 14:00:00]`.

---

## 4. Formula variants compared

Three variants were evaluated against four illustrative cases. The V1
column reflects the **production code** (E1.1 + edge_confidences=0.6
default); V2 and V3 are computed analytically from
`scripts/evaluate_shadow_formula.py:variant_comparison()`.

### 4.1 Definitions

* **V1 — current E1.1**. `base_pressure = 0.40·(1-grounding) + 0.20·(1-operator_accept) + 0.25·trajectory + 0.15·(1-completion)`. Missing components contribute neutrally (`0.5` for grounding when no precondition model exists, `0.0` for trajectory when no metrics are passed) AND emit a warning. Weights are fixed.
* **V2 — dynamic-renormalized**. Components with no signal are dropped from the weighted sum and the remaining weights are renormalized to sum to 1. Effect: removing a low component **raises** the result.
* **V3 — conservative-missing**. Numerically identical to V1, but the report status is downgraded (e.g. `low_confidence`) when any component is missing.

### 4.2 Comparison

| case | V1 (E1.1) | V2 (renormalized) | V3 (conservative) | warning? | notes |
|---|---|---|---|---|---|
| missing_grounding (no preconditions) | 0.375 | 0.291667 | 0.375 | True | V1 = neutral 0.5 + warning; V2 renormalizes; V3 = V1 + downgraded confidence |
| real_zero_grounding | 0.575 | 0.575 | 0.575 | False | all variants agree: full grounding term contributes 0.40 |
| partial_grounding_g=0.5 | 0.5 | 0.5 | 0.5 | False | all variants agree when nothing is missing |
| missing_trajectory_metrics | 0.375 | 0.5 | 0.375 | False | V1/V3 treat missing trajectory as 0; V2 renormalizes weights |

### 4.3 Why V2 was rejected

The renormalized variant has the surprising property that **dropping a
component changes the answer in the opposite direction from intuition**:
on `missing_trajectory_metrics`, V2 returns `0.5` (higher) than V1's
`0.375`. A reader sees a higher score and infers more risk — when in
fact we just have less data. The fixed-weights approach in V1 keeps
"missing data" decoupled from "high pressure" — the right signal for a
diagnostic. ADR-13 honesty principle applies: pressure should reflect
what we measured, not what we couldn't measure.

### 4.4 Why V3 was partially adopted

V3 is V1 with extra reporting (status downgrade on missing data). E1.1
already does that via the warnings list — `"missing grounding model on
N event(s); ..."`. Promoting it to a separate `status` enum field would
be a schema change for marginal benefit. Kept as a future option, not
shipped.

---

## 5. Sensitivity sweep

Each input was varied independently across `[0.0, 0.25, 0.5, 0.75, 1.0]`
(or `[0, 1, 2, 3, 4]` over 4 preconditions for grounding). For every
sweep point the measured `base_pressure` matches the analytical formula
to within `1e-9` (`delta = 0.0` everywhere) — the formula is provably
linear in each input alone, with no clipping until the boundaries.

| input | value | metric | measured | expected | delta |
|---|---|---|---|---|---|
| grounding | 0.0 | base_pressure | 0.575 | 0.575 | 0.0 |
| grounding | 0.25 | base_pressure | 0.475 | 0.475 | 0.0 |
| grounding | 0.5 | base_pressure | 0.375 | 0.375 | 0.0 |
| grounding | 0.75 | base_pressure | 0.275 | 0.275 | 0.0 |
| grounding | 1.0 | base_pressure | 0.175 | 0.175 | 0.0 |
| completion | 0.0 | base_pressure | 0.45 | 0.45 | 0.0 |
| completion | 0.25 | base_pressure | 0.4125 | 0.4125 | 0.0 |
| completion | 0.5 | base_pressure | 0.375 | 0.375 | 0.0 |
| completion | 0.75 | base_pressure | 0.3375 | 0.3375 | 0.0 |
| completion | 1.0 | base_pressure | 0.3 | 0.3 | 0.0 |
| operator_accept | 0.0 | base_pressure | 0.475 | 0.475 | 0.0 |
| operator_accept | 0.25 | base_pressure | 0.425 | 0.425 | 0.0 |
| operator_accept | 0.5 | base_pressure | 0.375 | 0.375 | 0.0 |
| operator_accept | 0.75 | base_pressure | 0.325 | 0.325 | 0.0 |
| operator_accept | 1.0 | base_pressure | 0.275 | 0.275 | 0.0 |
| trajectory_pressure | 0.0 | base_pressure | 0.375 | 0.375 | 0.0 |
| trajectory_pressure | 0.25 | base_pressure | 0.4375 | 0.4375 | 0.0 |
| trajectory_pressure | 0.5 | base_pressure | 0.5 | 0.5 | 0.0 |
| trajectory_pressure | 0.75 | base_pressure | 0.5625 | 0.5625 | 0.0 |
| trajectory_pressure | 1.0 | base_pressure | 0.625 | 0.625 | 0.0 |
| edge_confidence | 0.0 | shadow_debt_pressure | 0.0 | 0.0 | 0.0 |
| edge_confidence | 0.2 | shadow_debt_pressure | 0.12 | 0.12 | 0.0 |
| edge_confidence | 0.4 | shadow_debt_pressure | 0.24 | 0.24 | 0.0 |
| edge_confidence | 0.6 | shadow_debt_pressure | 0.36 | 0.36 | 0.0 |
| edge_confidence | 0.8 | shadow_debt_pressure | 0.48 | 0.48 | 0.0 |
| edge_confidence | 1.0 | shadow_debt_pressure | 0.6 | 0.6 | 0.0 |

**Findings:**

* **Monotonicity holds for every input.** Grounding, completion, and
  `operator_accept` are anti-monotone (more verified → less pressure).
  `trajectory_pressure` and `edge_confidence` are monotone-increasing
  (more error / more trust in a high-pressure parent → more pressure).
* **No regressions vs hand calculation.** Every measured value matches
  the closed-form expression `Σ wᵢ·xᵢ` (clipped to `[0, 1]`).
* **edge_confidence sweep validates Option B.** The formula
  `child_debt = max(child_base, parent_pressure × conf × 0.80)` holds
  across `conf ∈ [0, 1]` exactly.

The corresponding pytest assertions live in
`tests/test_e2_shadow_formula_decision.py::test_formula_monotonic_*`.

---

## 6. Graph ablation

Seven topologies; for each we record propagation iterations,
convergence, max debt/integrity pressure, count of events whose debt
or integrity channel was raised above their local base, and the
**channel-separation invariant** (events whose ONLY parents are
supportive must have `debt == base`).

| topology | n_events | cons_edges | sup_edges | iter | converged | max_debt | max_integrity | debt>base | int>base | sup_isolates_debt |
|---|---|---|---|---|---|---|---|---|---|---|
| local_only | 3 | 0 | 0 | 1 | True | 0.375 | 0.375 | 0 | 0 | True |
| constitutive_only | 3 | 2 | 0 | 2 | True | 0.75 | 0.75 | 2 | 0 | True |
| supportive_only | 3 | 0 | 2 | 2 | True | 0.75 | 0.75 | 0 | 1 | True |
| mixed_graph | 3 | 1 | 1 | 2 | True | 0.75 | 0.75 | 1 | 1 | True |
| cycle_graph | 3 | 3 | 0 | 1 | True | 0.45 | 0.45 | 0 | 0 | True |
| dense_supportive_star | 11 | 0 | 10 | 1 | True | 0.75 | 0.75 | 0 | 0 | True |
| long_supportive_chain | 6 | 0 | 5 | 2 | True | 0.75 | 0.75 | 0 | 2 | True |

**Findings:**

* **Channel separation is invariant.** `sup_isolates_debt = True` in
  every row. The constitutive (debt) channel is never contaminated by
  supportive parents, in any topology.
* **Bounded propagation.** Every run converges in ≤ 2 iterations on
  these inputs and stays inside the `min(10, n_events + 1)` cap. No
  topology blows up.
* **Cycle is symmetric and stable.** `cycle_graph` (3-event
  constitutive cycle of equal-base events) terminates after the first
  iteration with all three at the same propagated value (`0.45`). Two
  consecutive runs produce identical `model_dump()` payloads (verified
  in `test_cycle_graph_bounded_and_deterministic_two_runs`).
* **Attenuation is the right shape.** In `long_supportive_chain` only
  the first two descendants are raised above their base (alpha 0.40 ×
  conf 0.6 = 0.24 attenuation per hop quickly drops below the child
  base). This is by design — supportive edges are an audit signal,
  not a verdict driver.
* **Dense star integrity bounded.** With 10 supportive parents and a
  child base of 0.375, `max(child_base, max_parent × 0.6 × 0.40) =
  max(0.375, 0.18) = 0.375`. No fan-in inflation.

The pytest analogues live under
`tests/test_e2_shadow_formula_decision.py::test_supportive_chain_*`,
`test_dense_supportive_star_*`, `test_constitutive_only_*`,
`test_mixed_graph_*`, `test_cycle_graph_*`, and
`test_empty_graph_local_only_warning`.

---

## 7. Edge-confidence decision (ADR-23 §5)

**Chosen: Option B** — keep `NormalizedEvent` schema unchanged; pass an
optional `edge_confidences: dict[tuple[str, str, str], float] | None`
parameter into `compute_experimental_shadow_fusion`. Default uniform
`0.6` when absent.

**Why not Option A** (frozen `0.6` default everywhere): loses the per-
edge confidence carried by `DependencyEdge.confidence`
(`extract/dependencies.py:71`). The dependency extractor already
produces confidences ranging `0.4` (call-graph fallback) to `0.9`
(same-symbol AST link); collapsing them to `0.6` discards real signal.

**Why not Option C** (extend `NormalizedEvent`): heavy schema change
for an experimental layer. ADR-22 requires the experimental fusion to
sit in a separate output block, not bleed into the
`NormalizedScenario`. Option B preserves that boundary.

**Wiring**: the production CLI does **not** yet pass `edge_confidences`
— it relies on the default `0.6`. Wiring the actual `DependencyEdge`
confidences from the graph into the call site is left for E3 (intent
estimator) when LLM-derived per-edge confidences become available.

**Tests**: `test_edge_confidence_default_is_0_6`,
`test_edge_confidence_metadata_overrides_default`, and
`test_edge_confidence_unrelated_key_is_ignored`.

---

## 8. D2 fixture replay

The 10 hermetic D2 fixtures (71 parametrized tests) still pass under
the E1.1 + E2 code path. The relative ordering of base_pressure on
the four `test_shadow_*` analogues in `test_e1_shadow_fusion.py`
remains:

| analogue | expectation | result |
|---|---|---|
| `01_clean_success` (high completion + verified preconditions) | low pressure | PASS — `clean_p < default_p` |
| `migration_without_rollback` (1/4 verified) | higher than fully-verified | PASS — `partial_p > full_p` |
| `corrupt_plausible_success` (3/4 verified, 1 critical missing) | non-trivial pressure, blocked status | PASS — `p > 0.05`, `status == blocked_by_readiness` |
| `import_dependency_with_constitutive_edge` | constitutive parent raises child | PASS — `with_parent.shadow_debt > no_parent.shadow_debt` |

No D2 fixture changed. The existing `tests/test_block_d2_hermetic_traces.py`
suite (71 parametrized tests) continues to pass alongside the new
E2 tests (full suite: 277 passed + 1 skipped).

---

## 9. Real-repo shadow smoke

Ran `scripts/real_repo_shadow_smoke.py` against `oida-code` self and
the vendored `attrs` snapshot. The repo target builds the surface from
the last 5 commits' `.py` diff (oida-code) or, when the snapshot lacks
git history, falls back to a sample of `src/**/*.py` (attrs).

| name | obs | con | sup | iter | conv | base | debt | integ | miss | no_edge | forbid | auth | rdy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oida-code (self) | 89 | 0 | 265 | 1 | True | 0.4750 | 0.4750 | 0.4750 | 0 | False | False | False | blocked |
| attrs | 1106 | 0 | 17741 | 1 | True | 0.4750 | 0.4750 | 0.4750 | 0 | False | False | False | blocked |

**Findings:**

* **Shadow runs without crash on both repos.**
* **Both repos: every event lands at exactly the same `0.475`
  pressure.** This is the expected baseline outcome at v0.4.x: the
  load-bearing inputs (`capability`, `benefit`, `observability`,
  `tests_pass`, `completion`, `operator_accept`) are all defaults, and
  obligations enter with `verified=False` for almost all preconditions
  (no tool evidence wired through `obligations_to_scenario`). Formula
  evaluates to `0.40·(1-0.25) + 0.20·0.5 + 0.0 + 0.15·0.5 = 0.475` for
  every event — a uniform "we don't know" signal. **This is not a
  finding about the repos; it's a finding about the inputs.** That's
  why ADR-22 blocks official emission.
* **0 missing-grounding warnings.** Every obligation extracted
  produced at least one `PreconditionSpec` (the AST extractor +
  ADR-20 expanders cover 100% of recognised patterns).
* **No `total_v_net` / `debt_final` / `corrupt_success` keys** in any
  payload (`has_forbidden_summary_keys = False`).
* **`authoritative = False`** on both, **`readiness_status = blocked`**
  on both. ADR-22's pin against silent V_net leakage holds in
  production code paths, not just type-system contracts.
* **No constitutive edges** on either repo — the bounded
  `build_dependency_graph` is conservative (config + same-symbol +
  same-scope rules); on a real Python codebase the supportive edges
  dominate (test-touches-source, import-call). Constitutive edges show
  up on synthetic D2 fixtures with explicit migration/auth/security
  patterns.

**This is not a statistical validation.** No Spearman, no commits>0
correlation, no outcome label was used. This is structural — the
formula runs, stays bounded, and never crosses the V_net redline.

---

## 10. Decision: KEEP V1 (current E1.1 formula)

| axis | result |
|---|---|
| Stability | PASS — every input linear and monotone (sweep delta ≡ 0.0). |
| Monotonicity | PASS — 4/4 inputs verified across the sweep grid. |
| Channel separation | PASS — supportive never raises debt, in 7/7 topologies. |
| Boundedness | PASS — every run converges in ≤ 2 iter on test inputs, ≤ `min(10, n+1)` cap by construction. |
| Honesty | PASS — missing-component cases produce neutral pressure + warning, not inflated pressure (V1 vs V2 comparison). |
| No V_net leakage | PASS — `Literal[False]` + `frozen=True` + payload key check on real-repo smoke. |
| Diagnostic value | PARTIAL — at v0.4.x baseline every real-repo event scores `0.475` because most inputs are defaults; the formula will start carrying real signal once Phase 4 LLM intent estimator unblocks `capability` / `benefit` / `observability` AND tool-evidence wiring populates `tests_pass` / `operator_accept` per event. The shape is right; the inputs are not yet rich enough to differentiate. |

**Verdict**: KEEP V1 with the two minor revisions already shipped:
1. **Missing-grounding semantics fix** (E1.1, commit `84e50f8`) — no
   conflation of "real zero grounding" with "no model".
2. **Optional per-edge confidence** (this commit, ADR-23 §5 Option B) —
   `edge_confidences` parameter on `compute_experimental_shadow_fusion`
   defaults to `0.6` and overrides per `(parent_id, child_id, kind)`
   tuple when supplied.

**This is a STRUCTURAL keep, not a predictive endorsement.** The
formula is stable, monotone, bounded, and channel-clean — that's what
ADR-23 asks E2 to certify. Predictive validation (does shadow pressure
correlate with real outcomes?) is **deferred to E3+ when Phase-4 LLM
intent estimator unblocks `capability` / `benefit` / `observability`
and tool-evidence wiring populates per-event `tests_pass` /
`operator_accept`**. KEEP here means "the shape is right and we can
build on it"; it does not mean "the numbers are meaningful at
v0.4.x baseline".

V2 (dynamic-renormalized) **rejected** — couples "missing data" to
"higher pressure", which is misleading.

V3 (conservative status downgrade) **partially adopted** — the warning
mechanism in E1.1 already covers it; promoting to a status enum is a
schema change for marginal benefit. Kept as a future option.

---

## 11. What changes before E3

E2 is structurally complete. Before E3 begins, the following remain
explicitly out of scope and **must not** sneak in:

* ❌ Promoting any shadow pressure to `total_v_net` / `debt_final` / `corrupt_success_ratio`.
* ❌ Calibrating thresholds on the synthetic D2 fixtures (overfit risk).
* ❌ Wiring an LLM into the shadow layer (Phase 4 contract).
* ❌ Modifying the vendored OIDA core (ADR-02 still holds).
* ❌ Publishing a stable PyPI release while `capability` / `benefit` /
  `observability` remain defaults (ADR-22 still holds).

What E3 will need from E2:

* ✅ A frozen, validated formula (this report).
* ✅ A documented edge-confidence override path (ADR-23 §5).
* ✅ A real-repo smoke that proves the shadow layer doesn't crash on
  large codebases (`scripts/real_repo_shadow_smoke.py`).
* ✅ Sensitivity tables that future variants can be diffed against
  (`.oida/e2/sensitivity.json`, `.oida/e2/ablation.json`).

---

## 12. Honesty statement

E2 decides whether the experimental shadow formula is **structurally
useful**. It does **NOT** validate statistical prediction.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`.

It does **NOT** unlock Phase 4 by itself.

The real-repo smoke shows uniform `0.475` base pressure on both target
repos because v0.4.x inputs are defaults — that is a reflection of the
inputs, not a property of the codebases. ADR-22's block on official
fusion is the correct response.

The shadow report's `authoritative = False` is enforced at the type
level (`Literal[False]` + `frozen=True` + `validate_assignment=True`)
AND at the payload-key level (`test_official_summary_fields_remain_null_after_shadow_smoke`).

---

## 13. Gates

| gate | status |
|---|---|
| `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` | clean |
| `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` | 54 src files, no issues |
| `python -m pytest -q` | **277 passed, 1 skipped** (V2 placeholder) |
| `python scripts/evaluate_shadow_formula.py` | sensitivity 26/26 delta=0.0; ablation 7/7 invariants hold |
| `python scripts/real_repo_shadow_smoke.py` | E2 invariants PASS on oida-code self + attrs |

---

## 14. Acceptance checklist (QA/A13.md §"Critères d'acceptation E2")

| # | criterion | status |
|---|---|---|
| 1 | `reports/e1_shadow_fusion.md` aligned with E1.1 | DONE (commit `508a756`) |
| 2 | ADR-23 written | DONE (this commit) |
| 3 | Formula variants compared | DONE (§4) |
| 4 | Sensitivity sweep produced | DONE (§5, `.oida/e2/sensitivity.{json,md}`) |
| 5 | Graph ablation produced | DONE (§6, `.oida/e2/ablation.{json,md}`) |
| 6 | Edge-confidence decision written | DONE (§7, Option B) |
| 7 | D2 fixtures still produce expected relative ordering | DONE (§8) |
| 8 | Real-repo shadow smoke runs | DONE (§9, `.oida/e2/shadow_smoke.json`) |
| 9 | Missing grounding remains neutral + warning | PASS (E1.1 invariants re-asserted in E2 tests) |
| 10 | Real zero grounding remains high pressure | PASS (`test_real_zero_grounding_greater_than_missing_grounding`) |
| 11 | Supportive edges remain audit-only | PASS (`test_supportive_chain_does_not_raise_debt_channel`) |
| 12 | Official summary fields remain null | PASS (`test_official_summary_fields_remain_null_after_shadow_smoke`) |
| 13 | Decision keep/revise/reject written | DONE (§10 — KEEP V1) |
| 14 | ruff clean | PASS |
| 15 | mypy clean | PASS |
| 16 | pytest full green | PASS (277/278, 1 skipped is V2 placeholder) |

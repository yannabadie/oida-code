# E1 — Experimental shadow fusion

**Date**: 2026-04-25.
**Scope**: QA/A11.md — separate-layer shadow diagnostic, never authoritative.
**Reproduce**:

```bash
python -m pytest tests/test_e1_shadow_fusion.py -q
oida-code score-trace trace.jsonl --request request.json \
    --surface impact --experimental-shadow-fusion --out shadow.json
```

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | (no new ADR — ADR-22 covers E1) | — |
| `src/oida_code/score/fusion_readiness.py` | E1.0 grounding-zero semantics fix | +17 |
| `src/oida_code/score/experimental_shadow_fusion.py` | new module | ~290 |
| `src/oida_code/cli.py` | `--experimental-shadow-fusion` opt-in flag | +30 |
| `tests/test_e0_fusion_readiness.py` | +3 E1.0 tests | +50 |
| `tests/test_e1_shadow_fusion.py` | 14 E1 tests | ~330 |
| `reports/e1_shadow_fusion.md` | this report | — |

Gates: ruff clean, mypy clean (52 src), **250/250 unit tests pass**
(was 225 at v0.4.2, +17 E0.1+E1 +8 E1.1 = 250).

---

## 2. E1.0 — grounding-zero semantics fix

**Before**: `total_preconditions > 0 AND verified == 0` → `status="default"`.
This conflated "no precondition model exists" with "model says nothing's
verified" — a false equivalence the shadow fusion would have inherited.

**After**: a real (negative) signal stays `status="real"`. Only the
genuinely-no-model case (`total_preconditions == 0`) is `missing`.

3 tests cover the cases:

| Test | Asserts |
|---|---|
| `test_grounding_zero_with_real_preconditions_is_real_not_default` | 0/2 verified → status=real |
| `test_grounding_missing_when_no_preconditions` | empty → status=missing |
| `test_grounding_partial_remains_real` | 1/2 verified → status=real (regression guard) |

This fix does NOT unlock any V_net path. It just makes the negative
signal that drives shadow_debt_pressure honest.

---

## 3. ShadowFusionReport schema (E1.1 hardened)

```python
class ShadowFusionReport(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,                                # E1.1 §point 1
        validate_assignment=True,                   # E1.1 §point 1
    )

    authoritative: Literal[False] = False           # pinned by type
    status: Literal[
        "experimental",
        "unsupported_input",
        "blocked_by_readiness",
    ]
    readiness_status: FusionStatus                  # from FusionReadinessReport
    event_scores: tuple[ShadowEventScore, ...] = () # E1.1: tuple, not list
    graph_summary: ShadowGraphSummary
    trajectory_summary: ShadowTrajectorySummary | None
    blockers: tuple[str, ...] = ()                  # E1.1: tuple, not list
    warnings: tuple[str, ...] = ()                  # E1.1: tuple, not list
    recommendation: str
```

Per-event (also frozen with `validate_assignment=True`):

```python
class ShadowEventScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    event_id: str
    base_pressure: float                      # ∈ [0, 1]
    shadow_debt_pressure: float               # ∈ [0, 1] — constitutive prop
    shadow_integrity_pressure: float          # ∈ [0, 1] — supportive prop
    graph_propagation_pressure: float         # ∈ [0, 1] — delta vs base
```

**E1.1 hardening (QA/A12.md):**

* `frozen=True` rejects attribute reassignment at runtime.
* `validate_assignment=True` re-runs validators on any reassignment
  attempt — `Literal[False]` on `authoritative` rejects `True` even if
  `frozen` were lifted.
* Public collections are `tuple[...]`, not `list[...]` — no `.append`,
  no slice assignment, no in-place mutation.
* Re-validating a payload with `authoritative=true` raises
  `ValidationError`.
* Goal: integrator-friendliness, not absolute defence against
  `object.__setattr__`. A normal integrator cannot mutate the report
  and pretend it became authoritative.

**The names are deliberate (per A11.md):** `shadow_debt_pressure` /
`shadow_integrity_pressure` — NOT `shadow_v_net`. V_net has formal
meaning in the vendored OIDA core; reusing the name even with
`authoritative=false` would lead readers to treat the shadow score as a
real V_net.

---

## 4. Formula and weights (verbatim from A11.md, E1.1 missing-grounding fix)

```text
grounding_pressure(event) =                # E1.1: distinguishes missing vs zero
    (0.5,  False)        if no preconditions
    (1 - verified_frac, True) otherwise

base_pressure(event) =
    0.40 * grounding_pressure(event).pressure
  + 0.20 * static_failure_pressure
  + 0.25 * trajectory_pressure
  + 0.15 * (1 - completion)
```

* `grounding` — fraction of weighted preconditions verified on the event.
  **E1.1 (A12.md §point 2):** an event with NO precondition model now
  contributes a NEUTRAL `0.5` to the grounding component (not the pre-
  E1.1 `1.0` max-pressure value), and the `warnings` field surfaces a
  `"missing grounding model on N event(s)"` notice. An event with a
  REAL ZERO grounding (model exists, 0/N verified) still contributes
  `1.0` — a real negative signal. The two cases produce numerically
  distinct base_pressure values.
* `static_failure_pressure` — `1 - operator_accept` (proxied through the
  mapper's ruff/mypy fold).
* `trajectory_pressure` — `max(exploration_error, exploitation_error)`
  from the optional `TrajectoryMetrics`; 0 when no trace is provided.
* `completion` — `event.completion` (pytest pass-ratio when real).

Then propagation:

```text
constitutive_pressure(child) = max(
    base_pressure(child),
    max over constitutive parents of (parent_pressure * 0.6 * 0.80)
)

supportive_audit_pressure(child) = max(
    base_pressure(child),
    max over supportive parents of (parent_pressure * 0.6 * 0.40)
)
```

Where `0.6` is the default per-edge confidence (the vendored
`NormalizedEvent.constitutive_parents/supportive_parents` lists do not
carry per-edge confidence; we use a uniform default and let the dep
graph's `DependencyEdge.confidence` inform a future refinement).

`alpha_constitutive = 0.80`, `alpha_supportive = 0.40` — per A11.md.

---

## 5. Graph propagation rules

* **max iterations** = `min(10, n_events + 1)` per A11.md.
* **operator** = `max()` — monotone + idempotent. No cumulative inflation
  from import/test cycles.
* **values clipped** to `[0, 1]` after every step.
* **converged** is reported in `ShadowGraphSummary.propagation_converged`.

Cycle test (`test_cycle_propagation_is_bounded_and_deterministic`):
a 2-cycle `e1 ↔ e2` with completion=0 on both terminates within ≤ 10
iterations, produces identical output across two calls, and both events
end at the same propagated value.

---

## 6. D2 fixture comparisons (relative pressure ordering)

We do NOT assert outcome prediction. We assert relative ordering:

| Test | Comparison | Result |
|---|---|---|
| clean_success | high-completion verified vs default | clean < default |
| migration_without_rollback | 1/4 verified vs 4/4 verified | partial > full |
| import_dependency (constitutive) | child with parent vs without | with > without |
| corrupt_plausible_success | base_pressure > 0.05 + status=blocked | both hold |

These are diagnostic shape checks. They do not validate that the
shadow numbers predict any real-world outcome — that would require
the labeled dataset Phase 4 will produce.

---

## 7. changed vs impact comparison

The CLI wires `--experimental-shadow-fusion` into the existing
`score-trace --surface impact|changed` ablation. On the D2 scenario
`07_import_dependency_missed`:

| Mode | Obligations | Edges | Shadow constraints |
|---|---:|---:|---|
| `--surface=changed` | 1 (db only) | 0 | shadow report runs but no propagation possible |
| `--surface=impact` | 2 (db + app) | 1 supportive direct_import | propagation visible: app's shadow_integrity_pressure ≥ base + supportive contribution |

Both modes keep `shadow.authoritative = False` and the official
summary fields stay null.

---

## 8. Real-repo smoke

D3's `scripts/real_repo_smoke.py` is unchanged and still PASSES on
oida-code self + attrs (structural invariants only). The shadow
fusion is not run in D3 by default — it's CLI opt-in. A future smoke
that also exercises shadow fusion is a Phase-4 prep task.

---

## 9. Cases where shadow differs from local-only (base vs propagated)

A constitutive parent with `completion=0` (max local pressure) raises a
clean child's `shadow_debt_pressure` from its local base value. The
delta is captured in `graph_propagation_pressure` per event. On the
canonical 2-event constitutive chain test, the child's pressure rises
to `parent_base * 0.60 * 0.80 = 0.48` even when its local base was 0.

---

## 10. Cases where shadow looks noisy

* **Empty graph + default capability/benefit/observability**: shadow
  reports the same base on every event, which is uninformative as a
  ranking. Mitigation: the report's `warnings` list flags
  `"no graph edges; shadow scores degrade to local base pressure"`.
* **Single high-pressure parent in a long supportive chain**: max()
  propagates the parent's `0.6 * 0.40 = 0.24` floor to every supportive
  descendant. Useful as an audit signal but flat as a ranking.
* **Trajectory_pressure dominated by length-confound**: the underlying
  trajectory metrics carry the Phase-3 length-confound caveat
  (reports/legacy/PHASE3_AUDIT_REPORT.md §3); shadow inherits it via `0.25 *
  trajectory_pressure`.

---

## 10.5. E1.1 hardening summary (post-A12.md sync)

Three concrete patches applied AFTER the initial E1 commit, before E2:

1. **Frozen Pydantic models + tuples** on `ShadowFusionReport`,
   `ShadowEventScore`, `ShadowGraphSummary`,
   `ShadowTrajectorySummary`. `event_scores`, `blockers`, `warnings`
   are tuples on the public surface. 4 tests assert that
   `shadow.authoritative = True` raises `ValidationError`,
   `event_scores.append(...)` is unavailable, `model_validate(
   {..., "authoritative": True})` raises, and nested
   `ShadowEventScore` is also frozen.
2. **Missing-grounding semantics.** `_grounding_pressure(event)`
   returns `(pressure, is_real)`. No preconditions → `(0.5, False)`
   neutral + warning. Preconditions exist with 0/N verified →
   `(1.0, True)` real negative signal. 4 tests assert
   numerical and warning-level distinction between the two cases.
3. **README aligned**: "Phase 3.5 + E1 complete", "250/250 tests",
   E2/E3 pending mentioned.

Eight new tests in `tests/test_e1_shadow_fusion.py` (the +8 from the
242→250 jump). The shadow formula and propagation logic are
unchanged structurally — E1.1 only hardened the type discipline and
fixed the grounding semantics that pre-E1.1 conflated with real-zero.

## 11. Decision: keep / revise / reject shadow formula

**Decision: keep, mark experimental, opt-in only. Do not promote to
authoritative.**

Rationale:

1. The formula is conservative (only failure pressures, no positive
   inflation).
2. The propagation is mathematically safe (max() on [0,1] is bounded
   and idempotent).
3. The naming forbids accidental promotion to V_net.
4. The opt-in CLI flag forbids accidental emission.
5. The readiness layer forbids the official summary path.

The shadow formula is a **diagnostic shape**, not a verdict. Phase-4
LLM verifier outputs may eventually feed a calibrated version of the
same shape; until then it stays here.

---

## 12. Honesty statement (A11.md mandatory)

> E1 evaluates an experimental separate-layer shadow fusion.
> It is non-authoritative.
> It does not emit official `V_net`, `debt_final`, or `corrupt_success`.
> It does not modify the vendored OIDA core.
> It does not validate statistical outcome prediction.

---

## 13. Gates

| Gate | Result |
|---|---|
| ruff check src/ tests/ scripts/ | **clean** |
| mypy src/ | **clean** (52 files) |
| pytest tests/ (unit slice) | **250 / 250 PASS (E1.1)** |
| E1.0 grounding-zero tests | 3 / 3 |
| E1 invariant tests | 10 / 10 |
| E1 D2 fixture comparisons | 4 / 4 |

---

## 14. Next step

Per QA/A11.md §"Après E1":

* **E2** — decide whether the shadow formula is useful enough to keep
  long-term, after running it against more diverse fixtures.
* **E3** — define the contract that `capability` / `benefit` /
  `observability` estimators must meet to leave the default-0.5 trap.
* **Phase 4** — LLM verifier (forward/backward + intent/value
  estimator), only after E2 / E3 give the integration a concrete
  surface to feed.

Phase 4 is gated on E2 + E3, not on E1 alone. The LLM is the
last layer because it depends on every layer below being calibrated.

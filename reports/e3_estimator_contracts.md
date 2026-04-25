# E3 — Estimator contracts before Phase-4 LLM verifier

**Date**: 2026-04-25.
**Scope**: QA/A14.md — define how estimators speak before any LLM is wired.
**Authority**: ADR-24 (Estimator contracts before Phase-4 LLM verifier).
**Reproduce**:

```bash
python -m pytest tests/test_e3_evidence_plumbing.py tests/test_e3_estimator_contracts.py -q
python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py
python -m ruff check src/ tests/ scripts/
```

**Verdict (TL;DR)**: structural complete. Every load-bearing field has
a defined estimator contract; every contract enforces source / confidence /
authoritative invariants at the schema level. **No LLM is called.**
The deterministic baseline for `capability` / `benefit` / `observability`
remains default/missing — the readiness gate stays blocked at v0.4.x by
ADR-22 + ADR-24.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-24 — Estimator contracts before Phase-4 LLM verifier | +85 |
| `src/oida_code/score/event_evidence.py` | E3.0 — `EventEvidenceView` + per-event helpers | ~340 |
| `src/oida_code/score/mapper.py` | E3.0 — `build_scoring_inputs`, `edge_confidences_from_dependency_graph`, `ScoringInputs` | +150 |
| `src/oida_code/cli.py` | E3.0/E3.4 — `--experimental-shadow-fusion` now wires real edge_confidences + emits `estimator_readiness` block | +10 |
| `src/oida_code/estimators/__init__.py` | E3 sub-package | ~60 |
| `src/oida_code/estimators/contracts.py` | E3.1 — `SignalEstimate` + `EstimatorReport` (frozen) | ~210 |
| `src/oida_code/estimators/deterministic.py` | E3.2 — capability/benefit/observability + completion/tests_pass/operator_accept baselines | ~270 |
| `src/oida_code/estimators/llm_contract.py` | E3.3 — `LLMEstimatorInput` / `LLMEstimatorOutput` (schemas only) | ~140 |
| `src/oida_code/estimators/readiness.py` | E3.4 — `assess_estimator_readiness` + ladder | ~150 |
| `scripts/real_repo_shadow_smoke.py` | wired to `build_scoring_inputs` (real edge_confidences) | ±5 |
| `tests/test_e3_evidence_plumbing.py` | 15 tests for E3.0 plumbing + differentiation fixture | ~480 |
| `tests/test_e3_estimator_contracts.py` | 42 tests for E3.1+E3.2+E3.3+E3.4 | ~520 |
| `reports/e3_estimator_contracts.md` | this report | — |

**Gates**: ruff clean, mypy clean (60 src files, +5 estimators), **332
tests pass + 3 skipped** (1 V2 placeholder from E2 + 2 Phase-4
markers in observability tests).

---

## 2. ADR-24 excerpt

> **Decision (E3 protocol):** evaluate estimator contracts in five
> sub-blocks (E3.0..E3.4) before any LLM is implemented. The
> `official_ready_candidate` status is reserved; production CLI must
> NOT emit official `V_net` even at this status until a follow-up
> ADR explicitly unlocks it.
>
> **Accepted:** deterministic evidence plumbing first; frozen
> `SignalEstimate` schema; confidence separated from value;
> source/default/missing explicit; LLM diagnostic unless corroborated
> (cap 0.6 LLM-only, 0.8 hybrid).
>
> **Rejected:** raw LLM scores as `capability`/`benefit`/`observability`;
> LLM self-confidence as evidence; unlocking official V_net from
> shadow or estimator output alone; hiding missing fields behind
> neutral defaults without flagging them.

Full text: `memory-bank/decisionLog.md` `[2026-04-25 16:00:00]`.

---

## 3. E3.0 — evidence plumbing

### 3.1 Edge-confidence wiring

Per QA/A14.md §E3.0 #1 — `DependencyEdge.confidence` now reaches the
shadow layer. Helper:

```python
# src/oida_code/score/mapper.py
def edge_confidences_from_dependency_graph(
    graph: DependencyGraphResult,
    obligation_to_event_id: Mapping[str, str],
) -> dict[tuple[str, str, str], float]:
    ...
```

Returns `{(parent_event_id, child_event_id, kind): confidence}` for
every edge whose obligations are in scope; default `0.6` is used by
`compute_experimental_shadow_fusion` only when the map lacks the key
(ADR-23 §5 Option B).

CLI integration: `cli.score-trace` now calls `build_scoring_inputs`
which produces scenario + graph + edge_confidences + evidence_view
in one pass; the resulting `inputs.edge_confidences` is forwarded to
the shadow fusion.

### 3.2 Per-event tool evidence

`EventEvidenceView` (frozen, `extra="forbid"`) captures the per-event
slice of ruff/mypy/pytest/semgrep/codeql output:

```python
class EventEvidenceView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)
    event_id: str
    scope: tuple[str, ...]
    ruff_findings: tuple[Finding, ...] = ()
    mypy_findings: tuple[Finding, ...] = ()
    semgrep_findings: tuple[Finding, ...] = ()
    codeql_findings: tuple[Finding, ...] = ()
    pytest_relevant: bool = False
    pytest_passed: bool | None = None
    pytest_global_passed: bool | None = None
    ruff_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"
    mypy_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"
    pytest_status: Literal["ok", "tool_missing", "error", "skipped"] = "tool_missing"
    source: Literal["tool", "heuristic", "missing"] = "missing"
    warnings: tuple[str, ...] = ()
```

Per-event helpers `event_completion_from_view`,
`event_operator_accept_from_view`, `event_tests_pass_from_view` map
the view into the `[0, 1]` signals `NormalizedEvent` already carries.
The mapper's `obligations_to_scenario` now uses these per-event
values (was scenario-level uniform).

### 3.3 Differentiation proof

`tests/test_e3_evidence_plumbing.py::test_shadow_pressure_differentiates_when_evidence_differs`
constructs two events with materially different evidence:

| Event | preconditions | static findings | scope-relevant pytest |
|---|---|---|---|
| A | verified | none | passed |
| B | unverified | ruff + mypy errors on B's scope | failed |

Assertion: `shadow_pressure(B) - shadow_pressure(A) >= 0.10`. Without
this, the LLM estimators in Phase 4 would arrive on a flat `0.475`
surface and the diagnostic would be useless.

---

## 4. Estimate schema (E3.1)

```python
class SignalEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    field: EstimateField                # 7-element Literal
    event_id: str | None = None

    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

    source: EstimateSource              # 8-element Literal
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)

    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    is_default: bool = False
    is_authoritative: bool = False
```

Model-level validators enforce ADR-24 invariants:

| Rule | Failure mode if violated |
|---|---|
| `source="default"` → `confidence == 0.0` | `ValidationError` |
| `source="default"` → `is_default=True` | `ValidationError` |
| `source="default"` → `is_authoritative=False` | `ValidationError` |
| `source="missing"` → `confidence == 0.0` | `ValidationError` |
| `source="missing"` → `is_authoritative=False` | `ValidationError` |
| `source="llm"` → `is_authoritative=False` | `ValidationError` |
| `source="heuristic"` → `is_authoritative=False` | `ValidationError` |

`EstimatorReport` adds two cross-cutting rules:

* `status="shadow_ready"` requires every estimate to be non-default,
  non-missing.
* `status="official_ready_candidate"` additionally requires every
  estimate's `confidence >= 0.7`.

Both are validated at construction; you cannot package a default-
laden bundle as `shadow_ready` even if you try.

---

## 5. Field contracts (E3.2)

| field | deterministic baseline | LLM cap | authoritative? |
|---|---|---|---|
| `capability` | `default` if intent given (struct.); `missing` if no intent | `≤ 0.6` LLM-only, `≤ 0.8` hybrid | tool-grounded only |
| `benefit` | `default` if intent given; `missing` if no intent | `≤ 0.6` LLM-only, `≤ 0.8` hybrid | tool-grounded only |
| `observability` | `heuristic 0.6` if pytest_relevant; `missing` otherwise | `≤ 0.6` LLM-only, `≤ 0.8` hybrid | tool-grounded only |
| `completion` | `test_result 0.95/0.2` if pytest_relevant; `heuristic 0.8/0.5` if global only | `≤ 0.6` LLM-only | tool-grounded ok |
| `tests_pass` | weighted blend of `completion` + property/mutation placeholders | `≤ 0.6` LLM-only | tool-grounded ok |
| `operator_accept` | `static_analysis 0.7` if findings; `heuristic 0.5` if no findings | `≤ 0.6` LLM-only | tool-grounded ok |
| `edge_confidence` | from `DependencyEdge.confidence` (0.4..0.9) | `≤ 0.6` LLM-only | extractor-grounded |

### 5.1 capability — definition

> Does the implementation possess the mechanisms needed to satisfy the intent?

Without an LLM intent estimator we cannot decide this. Deterministic
baseline returns `source="default"` (with intent provided) or
`source="missing"` (no intent). `is_default=True` blocks
`shadow_ready` / `official_ready_candidate`.

### 5.2 benefit — definition

> If the implementation works, how valuable/relevant is it to the stated intent?

ADR-24 hard rule: **no benefit without intent**. Code complexity is
not a proxy for value. Without `AuditRequest.intent.summary`, the
estimate is `source="missing"`. With intent provided but no LLM, the
estimate is `source="default"`.

### 5.3 observability — definition

> Can failures be detected, localized, and surfaced?

Deterministic surface today: pytest test-file presence (weak heuristic
at `value=0.6, confidence=0.4`). Phase-4 will add negative-path
detection, logging detection, error-surfacing detection. Test
presence ≠ failure observability — explicit warning emitted.

---

## 6. Confidence policy

```
source                       max confidence   may set is_authoritative?
──────────────────────────────────────────────────────────────────────
tool (deterministic)         1.00             yes (narrow fields)
static_analysis              1.00             yes (narrow fields)
test_result                  1.00             yes (narrow fields)
hybrid (deterministic+LLM)   0.80             no (would imply LLM authoritative)
llm                          0.60             no
heuristic                    0.50 (default)   no
missing                      0.00             no (validator-rejected)
default                      0.00             no (validator-rejected)
```

The 0.7 threshold for `official_ready_candidate` is deliberately above
the LLM caps — an all-LLM report cannot reach that status.

---

## 7. LLM-output constraints (E3.3)

`LLMEstimatorOutput` is frozen, `extra="forbid"`, and validates:

* No estimate exceeds the source-cap (LLM-only `0.6`, hybrid `0.8`).
* Any LLM/hybrid estimate with `confidence > 0` MUST cite
  `evidence_refs` OR be listed in `unsupported_claims`. Uncited high-
  confidence claims fail validation.
* `is_authoritative=True` is rejected at `SignalEstimate` level when
  source is `llm` (already enforced by the schema).

`LLMEstimatorInput` is frozen and carries:

* `intent: str`
* `event: NormalizedEvent`
* `evidence_view: EventEvidenceView`
* `neighboring_events: tuple[NormalizedEvent, ...]`
* `allowed_fields: tuple[EstimateField, ...]` (default = capability,
  benefit, observability — tool-grounded fields deliberately
  excluded)

**No LLM is called from this module.** No HTTP, no model client,
no prompt template. The contract is the deliverable.

---

## 8. Readiness integration (E3.4)

`assess_estimator_readiness(scenario, evidence_view, request) -> EstimatorReport`
walks every event, calls `estimate_all_for_event`, and decides the
ladder status:

| status | precondition |
|---|---|
| `blocked` | every load-bearing field default/missing OR no scenario |
| `diagnostic_only` | at least one load-bearing default/missing |
| `shadow_ready` | every load-bearing field non-default, non-missing |
| `official_ready_candidate` | additionally, every load-bearing `confidence >= 0.7` |

Wired into `cli score-trace --experimental-shadow-fusion` as
`payload["estimator_readiness"]` alongside `payload["readiness"]`.
At v0.4.x, every real-repo run produces `status="blocked"` because
`capability` and `benefit` are default-blocking by E3.2.

`assess_fusion_readiness` (the official gate from ADR-22) is **not**
modified — the two coexist. The estimator ladder describes what the
estimator can claim; the official gate decides what the user is
allowed to publish.

---

## 9. Tests

15 tests in `tests/test_e3_evidence_plumbing.py`:

* 4 — edge_confidences helper (same-symbol 0.9, direct-import 0.6,
  default fallback, unknown id skip).
* 7 — per-event tool evidence (ruff, mypy, pytest variants, missing
  tool, error tool, no-fake-green, pytest-relevant-failure).
* 1 — CLI shadow path produces non-empty edge_confidences with at
  least one non-0.6 entry on a same-symbol fixture.
* 1 — differentiation fixture (B's pressure ≥ A's + 0.10).
* 2 — baseline preservation + frozen view.

42 tests in `tests/test_e3_estimator_contracts.py`:

* 12 — `SignalEstimate` / `EstimatorReport` invariants (frozen +
  validators).
* 14 — deterministic baselines (capability/benefit/observability +
  completion/tests_pass/operator_accept across the source ladder).
  2 are explicit `pytest.skip` markers for Phase-4 negative-path /
  logging detection.
* 6 — LLM contract caps + citation rules.
* 7 — readiness ladder + official-summary-null guard.
* 3 — end-to-end estimator readiness from a real evidence view.

Full suite at the end of E3: **332 passed, 3 skipped** (V2 placeholder
from E2 + 2 Phase-4 observability markers).

---

## 10. Known limitations

The deterministic baseline is honest about what it can't do at v0.4.x.
These are documented here so the OIDA scientist's review doesn't have
to mine them out of the code:

1. **`pytest_relevant=True, pytest_passed=True` is unreachable from
   the production runner wiring.** Today's pytest runner only emits
   findings on failures, so a passing test produces no
   scope-matching `Finding`. The 0.95-pressure branch in
   `event_completion_from_view` only fires when the integrator
   constructs a relevant-passed view manually (e.g. tests). Adding a
   surface-level test-path → event-scope match (Phase 4 wiring) will
   close this gap. Until then, deterministic completion can
   distinguish *failing-relevant* from *missing*, but cannot yet
   distinguish *passing-relevant* from *passing-global*.

2. **`tool_evidence` is `None` at score-trace time.** `cli.score-trace`
   does not run the verifier suite — that's the job of `cli.audit`.
   So in production score-trace runs, every event sees
   `EventEvidenceView` with `source="missing"`. The differentiation
   in §3.3 is exercised in tests, not in production score-trace
   output. Wiring `tool_evidence` into the audit-pipeline shadow
   call is Phase-4 surface work; the contracts here are ready.

3. **Negative-path / logging / error-surfacing detection is Phase-4
   work.** The deterministic observability estimator returns 0.6 when
   a relevant test file is detected; it does NOT measure whether
   that test exercises negative paths or whether the implementation
   logs failures usefully. Two `pytest.skip` markers in
   `tests/test_e3_estimator_contracts.py` track this gap explicitly.

4. **`property` and `mutation` weights in `tests_pass` are still
   0.5 placeholders.** The `_tests_pass_from_evidence` helper has had
   `TODO(phase2)` markers since Block B; per-event property/mutation
   wiring is unchanged in this commit.

5. **`official_ready_candidate` is reserved.** Even when an
   `EstimatorReport` could legally reach this status (a future world
   with all tool-grounded high-confidence estimates), the production
   CLI must NOT emit official `V_net`. ADR-22 holds. A follow-up
   ADR is required to unlock the official emission path.

---

## 11. Recommendation for Phase 4

Per QA/A14.md §"Après E3", the suggested ordering is:

* **Phase 4.0 — LLM estimator dry-run on hermetic fixtures.** Use the
  D2 fixtures + a pinned model. Assert that LLM output passes
  `LLMEstimatorOutput` validation, that confidence stays under the
  cap, and that uncited claims appear in `unsupported_claims`.
* **Phase 4.1 — forward/backward verifier contract.** Define how the
  LLM proposes capability/benefit/observability and how the
  deterministic estimator corroborates (`source="hybrid"`).
* **Phase 4.2 — tool-grounded verifier loop.** The LLM may CALL tools
  (ruff, mypy, pytest) but its output is filtered through
  `LLMEstimatorOutput` before any `SignalEstimate` is committed.
* **Phase 4.3 — calibration dataset design.** Establish what
  "predictive validation" would look like before claiming it.

Explicitly NOT recommended: jumping directly to "LLM verifier
production". E2's `0.475` uniformity reminded us that a flat surface
gives no signal; E3's contracts ensure that an LLM trying to fill
that gap can't sneak past the gate.

---

## 12. Honesty statement

E3 defines estimator contracts and deterministic evidence plumbing.

It does **NOT** implement a production LLM verifier.

It does **NOT** validate statistical prediction. There is no Spearman,
no commits>0 correlation, no outcome label.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22's pin against silent V_net leakage holds in
E3 too — verified by `test_official_summary_fields_still_null_in_e3`.

It does **NOT** modify the vendored OIDA core (ADR-02 holds).

Today, the production CLI score-trace produces an `EstimatorReport`
with `status="blocked"` on real repos because `capability` and
`benefit` are default-blocking by ADR-24. That's the **correct**
state. KEEP this gate closed until Phase 4 supplies real signal.

---

## 13. Gates

| gate | status |
|---|---|
| `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` | clean |
| `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` | 60 src files, no issues |
| `python -m pytest -q` | **332 passed, 3 skipped** |
| `python scripts/real_repo_shadow_smoke.py` | E2 invariants still PASS on oida-code self + attrs (no V_net leakage) |

---

## 14. Acceptance checklist (QA/A14.md §"Critères d'acceptation E3")

| # | criterion | status |
|---|---|---|
| 1 | ADR-24 written | DONE |
| 2 | `EventEvidenceView` or equivalent added | DONE (`event_evidence.py`) |
| 3 | Existing `ToolEvidence` maps to events by file/scope | DONE (`build_event_evidence_view` + `_scope_matches_path`) |
| 4 | Edge confidence metadata reaches shadow fusion or is explicitly blocked with reason | DONE (`edge_confidences_from_dependency_graph` + CLI wiring) |
| 5 | `SignalEstimate` schema added | DONE (`estimators/contracts.py`) |
| 6 | `EstimatorReport` schema added | DONE |
| 7 | `capability` contract written and tested | DONE (4 tests) |
| 8 | `benefit` contract written and tested | DONE (4 tests) |
| 9 | `observability` contract written and tested | DONE (4 tests + 2 Phase-4 markers) |
| 10 | LLM estimator output contract added, but not used as truth | DONE (no LLM call exists) |
| 11 | LLM-only estimates cannot be authoritative | PASS (`test_signal_estimate_llm_cannot_be_authoritative`) |
| 12 | Missing intent blocks benefit | PASS (`test_benefit_missing_without_intent`) |
| 13 | Missing evidence is distinct from negative evidence | PASS (`test_completion_missing_evidence_distinct_from_negative`) |
| 14 | E3 can produce differentiated shadow pressure on a fixture with mixed evidence | PASS (`test_shadow_pressure_differentiates_when_evidence_differs`) |
| 15 | Official summary fields remain null | PASS (`test_official_summary_fields_still_null_in_e3`) |
| 16 | `reports/e3_estimator_contracts.md` produced | DONE (this file) |
| 17 | ruff clean | PASS |
| 18 | mypy clean | PASS |
| 19 | pytest full green or explicitly documented skip | PASS (332 + 3 documented skips) |

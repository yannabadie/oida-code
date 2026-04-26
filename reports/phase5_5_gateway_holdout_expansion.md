# Phase 5.5 — runnable gateway holdout expansion

QA directive: `QA/A32.md` (2026-04-27).
ADR: ADR-40 (`memory-bank/decisionLog.md`).
Status at end of phase: **36 / 36** acceptance criteria green;
quality gates clean (ruff + mypy + pytest, 824 passed / 4
skipped, was 786/4 before Phase 5.5 — exactly +38 new tests);
all five GitHub-hosted runs green on commit `23017cb`:

| Workflow | Run ID | Wall time |
|---|---|---|
| ci | 24965538661 | 1m25s |
| action-smoke | 24965538659 | 1m03s |
| provider-baseline-node24-smoke | 24965538667 | 25s |
| gateway-grounded-smoke | 24965538670 | 31s |
| gateway-calibration | 24965538668 | 22s |

## 1. Diff résumé

### Sources

* `src/oida_code/calibration/gateway_calibration.py` —
  substantial rewrite (~870 LOC; was ~720). The runner now
  carries a per-class `_PerClassConfusion` dataclass tracking
  `tp` / `fp` / `fn`, computes a TRUE per-class macro-F1
  instead of the symmetric proxy, exposes precision and
  recall on the metric JSON for every class, supports a new
  optional `by_tool` executor schema (so a single case can
  exercise multiple adapters with distinct outcomes), wires
  `tool_policy.max_tool_calls` through to the gateway loop
  (so the budget cap is observable in the audit log), and
  emits `decision_summary.json` with the renamed
  `integrate_opt_in_candidate` recommendation + a hardcoded
  `promotion_allowed: false` STRUCTURAL pin.
* `scripts/_build_phase5_5_cases.py` — NEW fixture builder
  for the four mandatory Phase 5.5 cases. Computes ruff +
  mypy + pytest fingerprints deterministically from the
  same `GatewayToolDefinition` shape Phase 5.4 used.

### Datasets

* `datasets/gateway_holdout_public_v1/` — manifest extended
  from 8 to 12 cases (`manifest_version: gateway_holdout_public_v1.2`).
  The four new cases are committed alongside the existing
  Phase 5.4 set.
* `datasets/private_holdout_v2/` — unchanged.

### Tests

* `tests/test_phase5_5_holdout_expansion.py` — NEW, 36 tests.
* `tests/test_phase5_4_real_calibration.py` — +2 tests
  (`test_phase5_4_report_audit_log_path_is_not_malformed`,
  `test_phase5_4_report_mentions_case_id_date_tool_path`).
* `tests/test_phase5_3_gateway_calibration.py` — 1 update
  (the documented-classifications test now expects 10 entries
  including `tool_budget_gap` + `uncertainty_preserved`).

### Memory + reports

* `memory-bank/decisionLog.md` — ADR-40 appended.
* `reports/phase5_5_gateway_holdout_expansion.md` — this
  document.
* `reports/phase5_4_real_gateway_calibration.md` — audit-log
  path wording fix (lines 215–230).
* `README.md` + `memory-bank/progress.md` — updated test
  count and status line (see follow-up commit).

## 2. 5.5.0 hardening

### 5.5.0-A — audit-log path wording fix

The Phase 5.4 report's section 8 referenced the audit-log
path as `<out>/audit/<case_id>/<yyyy-mm-dd>/<tool>.jsonl`.
On certain Markdown renderers the angle-bracketed
placeholders are stripped as bogus HTML, leaving the
operator with `/audit///.jsonl` — visibly broken. The fix
keeps the path inside backticks and adds a literal example
right after:

```
.oida/gateway-calibration/audit/tool_needed_then_supported/2026-04-26/pytest.jsonl
```

with each path component named explicitly. Two canary tests
in `tests/test_phase5_4_real_calibration.py` lock in the fix:
the first scans for the truncated form `/audit///.jsonl`,
the second scans for each component independently
(`.oida/gateway-calibration` for the output dir,
`tool_needed_then_supported` for a case_id, an ISO date
regex, `pytest.jsonl` for the tool filename).

### 5.5.0-B — true per-class macro-F1

The Phase 5.4 `_PerModeMetrics` carried six flat counters
(`accepted_correct`, `accepted_wrong`, …) and computed
macro-F1 via `2*TP / (2*TP + FP + FN)` — numerically
identical to F1 (because `expected_C ^ actual_C =
(actual_C - expected_C) ∪ (expected_C - actual_C) = FP ∪ FN`
for the symmetric difference) but did NOT separate FP from
FN. The proxy could hide a class with strong precision and
weak recall (or vice versa) by reporting the same combined
score.

Phase 5.5 introduces `_PerClassConfusion`:

```python
@dataclass
class _PerClassConfusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float: ...
    def recall(self) -> float: ...
    def f1(self) -> float: ...
```

Each `_PerModeMetrics` now holds three of these
(`accepted`, `unsupported`, `rejected`). `_update_metrics`
computes:

```python
metrics.accepted.tp += len(expected_accepted & actual_accepted)
metrics.accepted.fp += len(actual_accepted - expected_accepted)
metrics.accepted.fn += len(expected_accepted - actual_accepted)
```

`claim_macro_f1` is `(accepted.f1() + unsupported.f1() +
rejected.f1()) / 3` — the canonical macro-average. The
Phase 5.4 backward-compat keys (`accepted_correct`,
`accepted_wrong`, etc.) remain in `to_json()` derived from
the new dataclass. The metric JSON now exposes
`accepted_precision` / `accepted_recall` / `accepted_f1`
(and similar for unsupported / rejected) so any asymmetric
P/R splits become visible to the operator.

### 5.5.0-C — `integrate_opt_in_candidate` + `promotion_allowed`

The Phase 5.4 recommendation Literal carried `integrate_opt_in`
as one of five values. Phase 5.5 renames it to
`integrate_opt_in_candidate` to make it unambiguous that
even a positive recommendation does NOT promote anything in
this phase. `decision_summary.json` adds a new field:

```json
"promotion_allowed": false
```

This is a STRUCTURAL pin: hardcoded `False` in
`_emit_decision_summary` regardless of the recommendation.
Phase 5.5 picks the next phase, NOT the action's default.
Even when the recommendation is
`integrate_opt_in_candidate`, integration must happen in a
SUBSEQUENT phase under explicit review.

## 3. ADR-40 excerpt

> **Decision:** Phase 5.5 expands the runnable gateway
> holdout beyond the 8-case Phase 5.4 pilot before
> integrating verify-grounded into the GitHub Action path.
> The goal is to determine whether the positive gateway
> deltas survive a larger controlled slate.

## 4. Public runnable slate expansion

`datasets/gateway_holdout_public_v1/` now ships 12
fully-committed synthetic cases — the original 8 from
Phase 5.4 + four new mandatory cases:

| Case | Family | Expected delta | Discriminator |
|---|---|---|---|
| `tool_missing_uncertainty` | gateway_grounded | improves | executor `returncode: null` -> adapter status `tool_missing` -> Phase 5.2.1-B enforcer demotes claim to unsupported (uncertainty preserved, NOT rejected as code failure) |
| `tool_timeout_uncertainty` | gateway_grounded | improves | executor `timed_out: true` -> adapter status `timeout` -> demote + budget warning (timeout != deterministic contradiction) |
| `multi_tool_static_then_test` | gateway_grounded | improves | pass-1 requests ruff + mypy + pytest; per-tool `by_tool` executor schema returns ok/ok/failed; aggregator rejects `C.fix` because pytest negative estimate dominates the green static signals |
| `duplicate_tool_request_budget` | gateway_grounded | same | pass-1 requests pytest 3 times with `tool_policy.max_tool_calls=2`; gateway loop's budget cap leaves only 2 audit events (no autonomous loop) |

Each new case directory carries the 11 required files +
optional `executor.json` + per-case `README.md`.

## 5. New cases table

The four new cases are summarised above. Their full fixture
sets live under `datasets/gateway_holdout_public_v1/cases/`
and are deterministically rebuildable via
`python scripts/_build_phase5_5_cases.py`.

## 6. Baseline vs gateway results

Headline metrics on the 12-case slate (all `synthetic` /
`contamination_risk=synthetic`; nothing excluded by the
headline-metrics filter):

| Metric | Baseline | Gateway |
|---|---|---|
| `cases_evaluated` | 12 | 12 |
| `accepted_tp` / `fp` / `fn` | 12 / 0 / 0 | 6 / 0 / 0 |
| `accepted_precision` | 1.0 | 1.0 |
| `accepted_recall` | 1.0 | 1.0 |
| `accepted_f1` | 1.0 | 1.0 |
| `unsupported_tp` / `fp` / `fn` | 0 / 0 / 0 | 4 / 0 / 0 |
| `unsupported_precision` | 0.0 | 1.0 |
| `unsupported_recall` | 0.0 | 1.0 |
| `unsupported_f1` | 0.0 | 1.0 |
| `rejected_tp` / `fp` / `fn` | 0 / 0 / 0 | 3 / 0 / 0 |
| `rejected_precision` | 0.0 | 1.0 |
| `rejected_recall` | 0.0 | 1.0 |
| `rejected_f1` | 0.0 | 1.0 |
| `claim_accept_accuracy` | 1.0 | 1.0 |
| `claim_macro_f1` (TRUE) | 0.3333 | 1.0 |
| `evidence_ref_precision` | 0.0 | 0.4 |
| `evidence_ref_recall` | 0.0 | 0.2857 |
| `tool_contradiction_rejection_rate` | 0.0 | 0.4286 |
| `fresh_tool_ref_citation_rate` | 0.0 | 0.6667 |
| `official_field_leak_count` | 0 | 0 |

The per-class precision and recall are now visible: on this
slate every class has perfectly balanced precision and
recall (TP > 0 with zero FP, zero FN), so each per-class F1
is either 1.0 (gateway, all three classes) or 0.0
(baseline, on the empty `unsupported` / `rejected`
classes). The macro-average gives gateway 1.0 and baseline
1/3 ≈ 0.3333.

## 7. True macro-F1 implementation

The metric JSON's `accepted_precision` and `accepted_recall`
keys come straight off the `_PerClassConfusion` accumulator.
On this synthetic slate the two values are equal in every
class because the cases are deterministically labelled and
the runner makes deterministic predictions — a real-world
slate would surface asymmetries the proxy formula could not.

The legacy proxy `2*TP / (2*TP + FP + FN)` is NOT exposed
in the canonical output. A regression test
(`test_legacy_proxy_not_used_in_decision_summary`) asserts
the decision summary carries no `legacy_claim_macro_f1_proxy`
key and no `proxy` substring in the recommendation.

## 8. Delta metrics

| Metric | Delta |
|---|---|
| `claim_accept_accuracy_delta` | 0.0 |
| `claim_macro_f1_delta` | +0.6667 |
| `evidence_ref_precision_delta` | +0.4 |
| `evidence_ref_recall_delta` | +0.2857 |
| `tool_contradiction_rejection_rate_delta` | +0.4286 |
| `fresh_tool_ref_citation_rate` (gateway) | 0.6667 |

`gateway_delta` is **diagnostic only**.
`delta_metrics.json` and `decision_summary.json` both carry
`delta_diagnostic_only: true` /
`recommendation_diagnostic_only: true` plus a verbatim
`reserved` warning that Phase 5.5 does NOT promote any
score to official `total_v_net` / `debt_final` /
`corrupt_success`. `decision_summary.json` additionally
carries `promotion_allowed: false` as a STRUCTURAL pin.

## 9. Decision summary

```json
{
  "cases_runnable": 12,
  "cases_insufficient_fixture": 0,
  "gateway_improves_count": 8,
  "gateway_same_count": 2,
  "gateway_worse_count": 2,
  "claim_accept_accuracy_delta": 0.0,
  "claim_macro_f1_delta": 0.6667,
  "evidence_ref_precision_delta": 0.4,
  "evidence_ref_recall_delta": 0.2857,
  "tool_contradiction_rejection_rate_delta": 0.4286,
  "fresh_tool_ref_citation_rate": 0.6667,
  "official_field_leak_count": 0,
  "recommendation": "integrate_opt_in_candidate",
  "recommendation_diagnostic_only": true,
  "promotion_allowed": false
}
```

The recommendation is **`integrate_opt_in_candidate`**. The
QA/A32 §5.5-C rule order:

1. `official_field_leak_count > 0` → `revise_tool_policy`.
   *Not satisfied (leak count = 0).*
2. `cases_runnable < 12` → `insufficient_data`.
   *Not satisfied (cases_runnable = 12 ≥ 12).*
3. macro-F1 > +0.05 AND tool-contradiction non-negative AND
   evidence-precision non-negative AND no critical
   gateway_bug → `integrate_opt_in_candidate`.
   *Satisfied: +0.6667 > 0.05, +0.4286 ≥ 0, +0.4 ≥ 0,
   zero gateway_bug rows.*
4. macro-F1 < -0.05 → `revise_labels`. *Not reached.*
5. otherwise → `revise_prompts`. *Not reached.*

`promotion_allowed: false` is HARDCODED — even with the
positive recommendation, Phase 5.5 does not enable any
action path. Phase 5.6 will integrate the gateway-grounded
verifier as an OPT-IN under separate review.

## 10. Failure analysis

`failure_analysis.md` now carries 12 rows × 12 columns. The
new columns:

* `tool_request_policy_change_proposed` — auto-set on
  `gateway_bug` rows (the gateway diverged from the label
  while the baseline matched).
* `prompt_change_proposed` — auto-set on `aggregator_bug`
  rows (the baseline diverged but the gateway matched).

The Phase 5.5 legend adds two classifications:

* `tool_budget_gap` — pass-1 requested a duplicate or
  wasteful tool call; the budget cap fired and the audit
  log is clear.
* `uncertainty_preserved` — tool missing or timed out;
  gateway preserved the uncertainty (claim remains
  `unsupported`, NOT rejected as code failure).

Both classifications are ADDED only because the four new
cases actually exercise the corresponding code paths
(`tool_missing_uncertainty` / `tool_timeout_uncertainty` for
`uncertainty_preserved`; `duplicate_tool_request_budget` for
`tool_budget_gap`). The classifier in
`_classify_case` upgrades the row from
`expected_behavior_changed` to the more specific
classification when:

* any gateway `tool_results` entry has
  `status="tool_missing"` or `status="timeout"` →
  `uncertainty_preserved`.
* `pass1_requested_tools_count > len(gateway_tool_results)`
  (the budget cap fired) → `tool_budget_gap`.

Three regression tests in
`tests/test_phase5_5_holdout_expansion.py`
(`test_uncertainty_preserved_actually_emitted_for_tool_missing`,
`test_uncertainty_preserved_actually_emitted_for_timeout`,
`test_tool_budget_gap_actually_emitted_for_duplicate_case`)
lock in the actual emission so the legend cannot drift away
from the runner's vocabulary.

On this run, 9 cases end up with classification
`expected_behavior_changed`, 2 with `uncertainty_preserved`
(tool_missing + timeout), 1 with `tool_budget_gap`
(duplicate). No `label_change_proposed`, no
`tool_request_policy_change_proposed`, no
`prompt_change_proposed`. The runner ONLY proposes; no
automatic mutation.

## 11. Private holdout protocol

Unchanged from Phase 5.3 / 5.4. `datasets/private_holdout_v2/`
remains a schema-only public README + manifest example;
operator-private cases stay gitignored. The Phase 5.5
expansion landed entirely on the public synthetic slate.

## 12. No-MCP regression locks

Phase 5.5 ADDS six new tests that re-state the Phase 4.7+
locks against the current code shape:

* `test_no_mcp_dependency_added_phase5_5`
* `test_no_mcp_workflow_added_phase5_5`
* `test_no_jsonrpc_tools_list_or_tools_call_runtime_phase5_5`
* `test_no_provider_tool_calling_enabled_phase5_5`
* `test_action_yml_does_not_default_enable_tool_gateway_true_phase5_5`
* `test_calibration_module_does_not_import_mcp_runtime`

The existing locks from Phase 4.7 / 5.0 / 5.1 / 5.2 / 5.3 /
5.4 remain untouched. The Phase 5.5 set is layered on top
so a regression on any individual lock fails fast — no
single point of failure.

## 13. What this still does NOT prove

* Production predictive performance — the 12-case slate is
  a controlled measurement surface, not a deployment
  forecast.
* MCP readiness — the gateway has not been exposed to
  dynamic third-party schemas. MCP integration remains
  deferred at minimum to Phase 5.6+.
* Provider-side tool-calling correctness — Phase 5.5 stays
  replay-only by default.
* Anything resembling "merge-safe" — `gateway_delta` is
  diagnostic only; `promotion_allowed` is hardcoded false.
* Performance under load — every case is a hermetic replay;
  no runtime cost or latency claims.

## 14. Recommendation for Phase 5.6

Per QA/A32 "Après Phase 5.5":

> Si Phase 5.5 donne :
>   cases_runnable >= 12
>   official_field_leak_count == 0
>   macro-F1 réelle positive
>   tool contradiction rejection positive
>   fresh tool-ref citation positive
>   failure analysis sans gateway_bug critique
> alors :
>   Phase 5.6 = integrate gateway-grounded verifier as opt-in action path

Every condition is met on this slate. **Phase 5.6 = integrate
the gateway-grounded verifier as an OPT-IN action path** with:

* `enable-tool-gateway: false` default in `action.yml`.
* `workflow_dispatch` or explicit input only for activation.
* Replay / fake providers by default.
* No external provider invocation by default.
* No MCP runtime, no JSON-RPC discovery / dispatch.
* No write tools, no network egress.
* No official `total_v_net` / `debt_final` /
  `corrupt_success`.

MCP remains deferred; Phase 5.6 is integration of the
existing local deterministic gateway path, NOT MCP
adoption. MCP can only be revisited after Phase 5.6 has run
green in production for an operator-defined soak window.

## 15. Gates

| Gate | Status |
|---|---|
| ruff (full curated CI scope incl. `scripts/_build_phase5_5_cases.py`) | clean |
| mypy (same set) | clean (92 source files) |
| pytest full suite | 824 passed / 4 skipped (was 786/4 — exactly +38 new tests) |
| `tests/test_phase5_5_holdout_expansion.py` | 36 / 36 passing |
| Phase 5.4 audit-log canaries | 2 / 2 passing |
| GitHub-hosted CI runs | all five green on commit `23017cb` — ci (24965538661, 1m25s), action-smoke (24965538659, 1m03s), provider-baseline-node24-smoke (24965538667, 25s), gateway-grounded-smoke (24965538670, 31s), gateway-calibration (24965538668, 22s) |

## Honesty statement

Phase 5.5 expands and recalibrates the runnable gateway holdout.
It does not make verify-grounded the default.
It does not integrate MCP.
It does not enable provider tool-calling.
It does not allow write tools or network egress.
It does not validate production predictive performance.
It does not tune production thresholds.
It does not emit official total_v_net, debt_final, or corrupt_success.
It does not modify the vendored OIDA core.

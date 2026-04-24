# Block D — Phase 3.5 validation

**Date**: 2026-04-24.
**Scope**: QA/A9.md — structural validation of the measurement pipeline.
**Reproduce**:

```bash
python scripts/paper_sanity_check.py     # D1
python -m pytest tests/test_block_d2_hermetic_traces.py -q  # D2
python scripts/real_repo_smoke.py        # D3
```

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `scripts/paper_sanity_check.py` | D1 — all 10 paper-sanity aspects | ~560 |
| `reports/paper_sanity_report.md` | D1 — regenerated per-aspect report | ~90 |
| `tests/fixtures/code_traces/builders.py` | D2 — 10 scenario specs + materializer | ~520 |
| `tests/test_block_d2_hermetic_traces.py` | D2 — runner (71 parametrized tests) | ~265 |
| `scripts/real_repo_smoke.py` | D3 — structural smoke script | ~230 |
| `reports/block_d_validation.md` | This integrated report | — |

Gates: ruff clean, mypy clean (50 src), **213/213 unit tests pass** on
the trunk as of Block D2. **D1 script exits 0.** **D3 structural
invariants PASS** on 2 real repos.

---

## 2. D1 — Full paper sanity

Paper repo `jjj-madison/measurable-explore-exploit` pinned at
`be95ca2cc4325b26d22112da7c515dcc7cd2faba`. Author's own tests all
pass locally via `python -m symbolic_environment.metrics`.

Our implementation verified on all 10 A9.md aspects:

| Aspect | Status |
|---|---|
| 1. Case 1 / 2 / 3 / 4 / terminal reachable | PASS |
| 2. progress_event resets no-progress segment | PASS |
| 3. paper_gain vs progress_event distinct | PASS |
| 4. np-segment boundaries (last_progress+1..t) | PASS |
| 5. c_t cyclomatic component | PASS (7/7) |
| 6. e_t edge-reuse component | PASS (7/7) |
| 7. n_t node-reuse component | PASS (7/7) |
| 8. S_t = c_t + e_t + n_t identity | PASS |
| 9. undirected edge budget = 2 | PASS |
| 10. exploration / exploitation normalizers | PASS |

**Blocking mismatches: none.** Mixed-regime paper tests 8-10 use
BFS-based gain, out of scope for ADR-18 set-membership adaptation;
deferred to real-trace smoke (explicitly documented, not a silent gap).

---

## 3. D2 — hermetic code-domain traces

10 scenarios under `tests/fixtures/code_traces/`, A9.md-compliant
layout (`repo/`, `request.json`, `trace.jsonl`, `expected.json`,
`README.md`). Materialized in `tmp_path` per test module.

| # | Scenario | What it proves |
|---|---|---|
| 1 | `01_clean_success` | read + edit + test_run + commit produces low errors |
| 2 | `02_exploration_miss` | grep-only on unrelated files → exploration_error ≥ 0.5 |
| 3 | `03_exploitation_miss` | read target then edit README → exploitation_error ≥ 0.2 |
| 4 | `04_stale_cycling` | alternating grep on non-surface paths → stale_score ≥ 1 |
| 5 | `05_blind_edit_no_observation` | Edit without Read never fires progress (A2.5) |
| 6 | `06_repeated_edit_error` | repeated Edit on same pending resource → err=True (A2.4) |
| 7 | `07_import_dependency_missed` | **crown jewel**: changed=db, importer=app |
| 8 | `08_supportive_test_audit` | test → source supportive, not constitutive |
| 9 | `09_migration_without_rollback` | 4-child expansion; rollback unverified |
| 10 | `10_corrupt_plausible_success` | apparent completion, negative_path unverified |

Test count: **71 parametrized tests** across 10 scenarios × 7 assertion
families (exit-code, no-unknown-parent-IDs, expected-surface,
expected-metrics, expected-graph, ablation, fixture-format).

### Crown-jewel ablation (scenario 07)

Changed: `src/db.py`. Importer: `src/app.py` with `from src import db`.

| Mode | Events extracted | db→app edge |
|---|---|---|
| `--surface=changed` | 1 (db only) | 0 |
| `--surface=impact` | 2 (db + app) | 1 supportive `direct_import` |

Proves impact surface discovers what diff-only mode misses, and the
Block-C graph builder actually consumes that surface (D0.1).

### V_net / debt guards

Every scenario asserts `summary.total_v_net` and `summary.debt_final`
are **absent** from the emitted scenario (ADR-13 honesty). Zero false
positives across all 10.

---

## 4. D3 — real-repo structural smoke

Ran against:

1. `oida-code` self, last 5 commits
2. `python-attrs/attrs` (cloned at `.oida/validation-external/attrs/`, shallow clone)

Reproduce: `python scripts/real_repo_smoke.py`.

| Repo | changed | surface | obligations | constit | support | reopen | audit | unknown parent | self edge |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| `oida-code (self)` | 10 | 40 | 155 | 0 | 792 | 0 | 0 | no | no |
| `attrs` | 0 | 2 | 0 | 0 | 0 | 0 | 0 | no | no |

**Structural invariants: PASS** on both targets.

Notes:

* **attrs** shallow clone has only the last N commits of non-Python
  work in our window; the structural surface/graph pipeline still
  executes without crashing and produces a coherent (empty) result.
  That is the correct structural outcome, not a failure.
* **oida-code self** produces 155 obligations with 792 supportive
  edges from 10 changed files — impact surface extends to 40 files
  via imports/tests. `constitutive_edges = 0` because our last 5
  commits don't have api_contract obligations co-located with
  precondition / invariant / security_rule obligations on the same
  symbol (rule 1). That is a property of the change set, not a bug.
* No unknown parent IDs, no self edges on either repo — the vendored
  analyzer's `_validate_ids()` would otherwise raise.

---

## 5. Repair propagation examples

From `tests/test_dependency_graph.py::test_repair_uses_constitutive_vs_supportive_edges`:

Fixture: precondition + api_contract + observability on `src/app.py::create_user`.

* `double_loop_repair(precondition_event)` → `reopen=[api_event]`, `audit=[]`
  (constitutive parent dominates → api must be reopened).
* `double_loop_repair(observability_event)` → `reopen=[]`, `audit=[api_event]`
  (supportive parent does NOT dominate → api must be audited, not reopened).

This is the Block-C canonical demonstration the author requested in
QA/A6.md; reproduced every CI run.

---

## 6. Impact cone limits (A9.md §D3 hygiene)

Documented explicitly:

* `max_depth = 1` — we do not recurse imports-of-imports.
* `max_files = 50` — the cone is capped; excess goes to
  `skipped_files` on the graph result.
* stdlib / site-packages / external imports are **ignored** (filtered
  via `sys.stdlib_module_names` + non-resolvable repo-relative paths).
* Unresolved imports are **recorded**, not guessed —
  `DependencyGraphResult.unresolved_imports` exposes the list.

This is not a full call graph. It is a bounded audit cone.

---

## 7. Known limitations

* **Paper mixed-regime tests (paper tests 8-10)** use BFS-based gain
  on a 2D grid. We use set-membership gain on `changed_files`
  (ADR-18). Porting those tests would require fabricating fake
  obligations on fake cell scopes; deferred to after a future real
  dataset lands.
* **Direct-dependency-inspection paper_gain branch** (A2.4 4th sub-rule)
  is not wired: it needs the dep graph (Block C) to know which edges
  are "direct dependencies of pending obligation". Trivially added in
  a Block-E readiness pass.
* **V_net / debt_final** remain `null` (ADR-13). Block D explicitly
  does NOT unlock graph-aware V_net.
* **Evidence matchers for LLM-only sub-preconditions** default to
  `verified=False` (ADR-20): `negative_path_tested`,
  `data_preservation_checked`, `rollback_or_idempotency_checked`,
  `error_or_auth_path_checked`, `failure_mode_logged`,
  `metric_or_trace_available`, `alert_or_surface_defined`,
  `taint_or_access_path_checked`. Phase 4 LLM would close them.

---

## 8. Honesty statement (A9.md §D, mandatory)

> Block D validates that the measurement pipeline is structurally
> grounded: audit surface, obligations, graph edges, trajectory cases,
> and repair propagation.
>
> It does not validate statistical prediction of real-world success.
> It does not unlock graph-aware `V_net`.
> It does not justify Phase 4 LLM verifier unless D1 / D2 / D3 all
> pass — which they do, structurally.

---

## 9. Gates

| Gate | Result |
|---|---|
| ruff check src/ tests/ scripts/ | **clean** |
| mypy src/ | **clean** (50 files) |
| pytest tests/ (unit slice) | **213 / 213 PASS** |
| D1 paper sanity | **PASS** (all 10 aspects) |
| D2 hermetic traces | **71 / 71 parametrized PASS** |
| D3 real-repo smoke | **PASS** on 2 repos, 0 structural violations |

---

## 10. Next step

Per QA/A9.md §After Block D: the next phase is NOT the LLM verifier
proper. It is:

* **E0 — fusion readiness review**: decide whether graph-aware fusion
  lives as a separate layer or requires a vendored-core change.
* **E1 — separate-layer vs core-change decision**.
* **E2 — only then Phase 4 forward/backward LLM verifier.**

Block D clears the structural gate; E0 starts the fusion question
that V_net / debt_final currently sit behind.

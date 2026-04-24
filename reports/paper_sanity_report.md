# D1 — Full paper sanity check (2604.13151)

**Last updated**: post Phase-3.5 Block D1.
**Paper repo**: https://github.com/jjj-madison/measurable-explore-exploit
**Pinned commit**: `be95ca2cc4325b26d22112da7c515dcc7cd2faba`
**Reproduce**: `python scripts/paper_sanity_check.py` (from repo root).

---

## 1. Summary

| Item | Status |
|---|---|
| Their `python -m symbolic_environment.metrics` all-tests-pass | PASS |
| Overall D1 sanity | **PASS** |
| Blocking mismatches | none |

## 2. Stale-math port on paper's explore-only tests (items 5-9)

PASS 7/7

| test | expected | ours | S_final | match |
|---|---|---|---|---|
| 1_probe_backout | False | False | 0 | YES |
| 2_gateway_revisit | False | False | 0 | YES |
| 3_exhausted_branch | True | True | 3 | YES |
| 4_cycle_closure | True | True | 1 | YES |
| 5_repeated_cycle | True | True | 2 | YES |
| 6_corridor_oscillation | True | True | 5 | YES |
| 7_self_avoiding_walk | False | False | 0 | YES |

## 3. Items 1-4 + 9-10 validated inline

### item_1_case_reachability

| check | value |
|---|---|
| `case_1_exploration` | True (PASS) |
| `case_2_exploit_goal` | True (PASS) |
| `case_3_exploit_other` | True (PASS) |
| `case_4_either` | True (PASS) |
| `terminal` | True (PASS) |

### item_2_progress_reset

| check | value |
|---|---|
| `progress_at_t4` | True (PASS) |
| `stale_at_t4_is_zero` | True (PASS) |
| `t5_starts_fresh_segment` | True (PASS) |

### item_3_paper_gain_vs_progress

| check | value |
|---|---|
| `paper_gain_without_progress_reachable` | True (PASS) |
| `paper_gain_is_True` | True (PASS) |
| `progress_event_is_False` | True (PASS) |

### item_4_np_segment_boundaries

| check | value |
|---|---|
| `t0_first_segment` | True (PASS) |
| `t2_second_progress` | True (PASS) |
| `t3_fresh_segment_stale_0` | True (PASS) |
| `t4_stale_nonzero` | True (PASS) |

### item_9_undirected_budget

| check | value |
|---|---|
| `budget_2_traversals_no_penalty` | True (PASS) |
| `budget_3_traversals_penalty_fires` | True (PASS) |

### item_10_normalization

| check | value |
|---|---|
| `exploration_steps_sane` | True (PASS) |
| `exploitation_steps_sane` | True (PASS) |
| `errors_bounded_by_denom` | True (PASS) |

## 4. What D1 does NOT validate

- **Case attribution in mixed regimes** (paper tests 8-10): the paper's mixed_goal / mixed_non_goal / exploit_only tests use BFS-based Gain on a 2D grid. Our adaptation uses set-membership Gain on `changed_files` (ADR-18). Porting those tests would require synthesizing fake obligations on fake cell scopes — deferred to Block D3 real-trace smoke.
- **Statistical outcome prediction**: D1 validates the math, not whether the metric predicts real-world success. That remains an explicit Phase-4 concern (QA/A9.md).

## 5. Conclusion

`D1 validates paper math; it does not validate code-domain mapping.`

Code-domain validation lives in Block D2 (hermetic traces) and Block D3 (real-repo structural smoke).
# D1 — Paper sanity check (2604.13151)

**Last updated**: 2026-04-24 (post Phase 3.5 A2.3 + A2.4).
**Paper repo**: https://github.com/jjj-madison/measurable-explore-exploit
**Pinned commit**: `be95ca2cc4325b26d22112da7c515dcc7cd2faba` (tag on `main`).
**Reproduce**: `python scripts/paper_sanity_check.py` (from repo root).

---

## 1. Summary

| Item | Status |
|---|---|
| Author's `src/symbolic_environment/metrics.py` module installable in our venv | PASS |
| Author's 10 built-in sanity tests (`python -m symbolic_environment.metrics`) | **ALL PASSED** locally |
| Our `_stale_counters` reproduces the paper's stale-score direction on 7 ported explore-only tests | **7 / 7 match** (post-A2.3) |
| History: 4/7 at v0.4.1 (pre-A2.3) → 7/7 after undirected-edge refactor | documented in §4 |
| Sanity-check scoped to the math; mapping to code remains Phase 3.5 Block A2 / Block B / Block C | Expected |

---

## 2. Author's own tests

Installed the paper's package into our venv:

```
$ cd .oida/paper_sanity/measurable-explore-exploit
$ python -m pip install -e . --quiet
$ python -m symbolic_environment.metrics
...
  ALL TESTS PASSED
```

All 10 author tests pass on their own environment (tests 1-7 explore-only,
8-10 mixed regimes). Their reference `c_t / e_t / n_t / S_t` implementation
and Case attribution table are verified against their released code.

---

## 3. Our implementation vs their reference, on 7 ported tests

Current status (post-A2.3 + A2.4, repo tip):

```
test                            expected    ours        S_final     match
---------------------------------------------------------------------
1_probe_backout                 no rise     no rise     0           YES
2_gateway_revisit               no rise     no rise     0           YES
3_exhausted_branch              rises       rises       3           YES
4_cycle_closure                 rises       rises       1           YES
5_repeated_cycle                rises       rises       2           YES
6_corridor_oscillation          rises       rises       5           YES
7_self_avoiding_walk            no rise     no rise     0           YES

overall stale-behaviour match: PASS
```

Scenarios ported 1:1 (start cell + move sequence + pre-visited set). Our
port prepends a synthetic `read` event on the start cell so the
`NoProgressSegment` in our `_stale_counters` has the same initial node as
the author's `NoProgressSegment(start_pos)` constructor.

---

## 4. History — what changed between 4/7 and 7/7

### 4.1 At v0.4.1 (pre-A2.3): 4 / 7 matching

The 3 failing tests all shared one root cause: **our edge representation
was directed** where the paper's is undirected.

| Test | walk pattern | paper sees | v0.4.1 saw |
|---|---|---|---|
| 1 probe_backout | A→B→C→B→A | 2 undirected edges, cyc=0 | 4 directed edges, cyc=2 |
| 2 gateway_revisit | A→B→C→B→D | 3 undirected edges, cyc=0 | 4 directed edges, cyc=1 |
| 7 self_avoiding_walk | 0→1→…→6→5→…→0 | each undirected edge at budget, cyc=0 | 12 directed edges, cyc=6 |

Author's `NoProgressSegment._edge_key(a, b)` uses `(min(a, b), max(a, b))`,
explicitly undirected. Our `_stale_counters` at v0.4.1 used a raw directed
pair, so an A→B→A walk produced `(A,B)` and `(B,A)` — two *distinct*
directed edges in our accounting, both at count 1.

### 4.2 A2.3 refactor (commit `741945d`): resource_id nodes + undirected edges

Two coupled changes:

1. **Node identity = resource_id** (file path / symbol id), not
   `(kind, path)`. `Read src/a.py` and `Edit src/a.py` are the same node.
2. **Edges are unordered pairs**:
   ```python
   lo, hi = (a, b) if a <= b else (b, a)
   edge_visits[(lo, hi)] += 1
   ```

With both, the back-and-forth walks in tests 1, 2, and 7 correctly
register no cyclomatic growth, matching the paper.

### 4.3 A2.4 paper_gain split (commit pending): does not affect D1

A2.4 splits `compute_gain` into `compute_paper_gain` (segment-first
bounded) and keeps `compute_candidate_gain` as a diagnostic. The D1
port uses `_stale_counters` directly and does not invoke the gain
logic, so D1 results are unchanged by A2.4. Verified: 7/7 matching
before and after the A2.4 refactor.

---

## 5. Verdict

- **Math fidelity**: our `c_t / e_t / n_t` *formulas* are now faithful
  on the paper's own explore-only regime (7/7 tests aligned).
- **Representation**: our stale graph now uses resource-id nodes +
  undirected edges, matching the paper's `_edge_key` semantics.
- **Remaining gap**: the paper's Case attribution for mixed regimes
  (tests 8-10) uses BFS-based gain on a 2D grid. Ours uses
  set-membership gain on `changed_files` (ADR-18) — a domain
  choice, not a formula check. Porting tests 8-10 would require a
  richer shim that synthesizes fake obligations on fake cell
  scopes and is scheduled for after Block C lands the minimal
  dependency graph.

---

## 6. Action items

1. **Done**: A2.3 resource_id nodes + undirected edges → 7/7 on D1.
2. **Done**: A2.4 paper_gain vs progress split (does not affect D1
   numerically but keeps the scorer honest about repetition).
3. **Next**: Block B — obligation → 1..N preconditions with weight
   conservation. Unblocked once A2.4 is accepted.
4. **Deferred**: port paper tests 8-10 after Block C minimal graph.

---

## 7. What D1 does NOT validate

- Our **Case attribution** against the paper's regimes (mixed_goal,
  exploit_only, mixed_non_goal). Their case branch uses BFS-based
  gain on a 2D grid; ours uses set-membership gain on changed_files.
  Porting tests 8-10 would require a richer shim that synthesizes
  fake obligations on fake cell scopes — deferred to post-Block-C.
- Our **bounded U(t)** adaptation (ADR-18). The paper bounds U by grid
  size intrinsically; we bound by `changed_files`. This is a domain
  choice, not a formula check.
- Our **obligation ↔ precondition mapping** (Phase 3.5 Block B).
- Our **paper_gain segment-first bound** (A2.4). This is an
  extension of the paper's gain for the code domain; the paper's
  grid tests don't exercise it (they have BFS-based gain instead).

D1 validates **only** the stale-score math on the explore-only regime.
The code-domain empirical gap is Phase 3.5 Block D2 + pre-Phase-4 D3.

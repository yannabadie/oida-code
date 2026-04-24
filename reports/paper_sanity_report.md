# D1 — Paper sanity check (2604.13151)

**Date**: 2026-04-24 (Phase 3.5 Block A2).
**Paper repo**: https://github.com/jjj-madison/measurable-explore-exploit
**Pinned commit**: `be95ca2cc4325b26d22112da7c515dcc7cd2faba` (tag on `main`).
**Reproduce**: `python scripts/paper_sanity_check.py` (from repo root).

---

## 1. Summary

| Item | Status |
|---|---|
| Author's `src/symbolic_environment/metrics.py` module installable in our venv | PASS |
| Author's 10 built-in sanity tests (`python -m symbolic_environment.metrics`) | **ALL PASSED** locally |
| Our `_stale_counters` reproduces the paper's stale-score direction on 7 ported explore-only tests | **4 / 7 match** |
| Mismatches rooted in a single semantic choice | Directed vs undirected edge dedup (see §3) |
| Sanity-check scoped to the math; mapping to code remains the Phase 3.5 Block A2 open problem | Expected |

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

| Test | expected stale rises | our stale rises | our `S_final` | Match |
|---|---|---|---|---|
| 1 probe_backout | False | True | 2 | **NO** |
| 2 gateway_revisit | False | True | 1 | **NO** |
| 3 exhausted_branch | True | True | 3 | YES |
| 4 cycle_closure | True | True | 1 | YES |
| 5 repeated_cycle | True | True | 2 | YES |
| 6 corridor_oscillation | True | True | 4 | YES |
| 7 self_avoiding_walk | False | True | 6 | **NO** |

Scenarios ported 1:1 (start cell + move sequence + pre-visited set). Our
port prepends a synthetic `read` event on the start cell so the
NoProgressSegment in our `_stale_counters` has the same initial node as
the author's `NoProgressSegment(start_pos)` constructor.

---

## 4. Root cause of the 3 mismatches

All three failing tests share a pattern: **the walk goes out then back
along the same corridor**.

| Test | walk pattern | paper sees | we see |
|---|---|---|---|
| 1 probe_backout | A→B→C→B→A | 2 undirected edges, each at budget 2, cyc=0 | 4 directed edges unique, cyc=2 |
| 2 gateway_revisit | A→B→C→B→D | 3 undirected edges at budget, cyc=0 | 4 directed edges, cyc=1 |
| 7 self_avoiding_walk | 0→1→2→...→6→5→...→0 | each undirected edge at budget 2, cyc=0 | 12 directed edges unique, cyc=6 |

Author's `NoProgressSegment` (metrics.py:230-259, pinned commit):

```python
@staticmethod
def _edge_key(a: Coord, b: Coord) -> tuple[Coord, Coord]:
    return (min(a, b), max(a, b))

def append(self, pos: Coord) -> tuple[int, int, int, int]:
    prev = self.positions[-1]
    ...
    edge = self._edge_key(prev, pos)        # undirected by construction
    self.edge_counts[edge] = self.edge_counts.get(edge, 0) + 1
```

Our `_stale_counters` (src/oida_code/score/trajectory.py pre-A2.3):

```python
for a, b in pairwise(nodes):
    edge_visits[(a, b)] += 1               # directed pair
```

**Consequence**: a probe-and-return walk produces (A,B) and (B,A) — two
*distinct* directed edges in our accounting, both at count 1. In the
paper, they are the *same* undirected edge at count 2, still within
the budget of 2 → no staleness error.

---

## 5. Verdict

- **Math fidelity**: our `c_t / e_t / n_t` *formulas* are faithful
  (tests 3-6 pass with identical staleness direction).
- **Representation gap**: our edge representation is directed, which
  disagrees with the paper's undirected edge accounting. This is a
  **single-line change** in the scorer, not a formula bug.

The mismatch is exactly what the OIDA v4.2 author's A2.3 directive
anticipated: "stale node = resource_id, not (kind, path); same-territory
regardless of action kind". Taking the A2.3 change to its logical
extension — treating an edge as the unordered pair of resources —
closes this gap.

---

## 6. Action items

1. **A2.3 scope expansion**: in addition to resource-id nodes,
   `_stale_counters` must use unordered edge keys. Landing both together
   in one commit keeps the stale-graph semantics coherent.
2. **Re-run D1 after A2.3**: expect 7/7 matching.
3. **D2 (code-domain mini)** remains unblocked; the paper-domain sanity
   is a clean, isolatable sanity result.

---

## 7. What D1 does NOT validate

- Our **Case attribution** against the paper's regimes (mixed_goal,
  exploit_only, mixed_non_goal). Their case branch uses BFS-based
  gain on a 2D grid; ours uses set-membership gain on changed_files.
  Porting tests 8-10 would require a richer shim that synthesizes
  fake obligations on fake cell scopes — deferred until A2 completes.
- Our **bounded U(t)** adaptation (ADR-18). The paper bounds U by grid
  size intrinsically; we bound by `changed_files`. This is a domain
  choice, not a formula check.
- Our **obligation ↔ precondition mapping** (Phase 3.5 Block B).

D1 validates **only** the stale-score math. The code-domain empirical
gap is Phase 3.5 Block D2 + pre-Phase-4 D3.

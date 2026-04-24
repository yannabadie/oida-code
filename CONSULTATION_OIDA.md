# Consultation request — `oida-code` v0.4.1 review
## For the OIDA v4.2 author

> **Recipient**: scientist behind *OIDA v4.2* (`search/OIDA/oida_framework/oida/`,
> vendored verbatim at `src/oida_code/_vendor/oida_framework/`).
> **From**: Yann Abadie + Claude Code (Claude Opus 4.7, 1M-context build).
> **Date**: 2026-04-24.
> **Repo**: <https://github.com/yannabadie/oida-code>.
> **Most recent tag**: `v0.4.1` (commit `4b74828`).
> **What we need**: honest technical review of the v4.2 → code-audit
> adaptation, specifically ADR-18 (grid→code mapping) and the open
> empirical validation loop documented in §7.

---

## 0. TL;DR

We built `oida-code`, an AI-code verifier that wraps your OIDA v4.2
scorer (unmodified, SHA256-pinned in `_vendor/`) and adds five new
layers on top:

1. `ingest/` — git / diff / manifest / Claude Code transcripts
2. `extract/` — AST-based obligation extractor
3. `score/mapper.py` — lossless round-trip between Pydantic public
   types and your dataclass core + an `obligations_to_scenario`
   synthesiser
4. `score/trajectory.py` — an implementation of paper **2604.13151**
   ("Exploration and Exploitation Errors Are Measurable for LM Agents",
   Park et al., arXiv:2604.13151v1, Apr 2026) adapted to code traces
5. `report/` — JSON / Markdown / SARIF 2.1.0 emitters

Four phases shipped (`v0.1.0` → `v0.4.1`), 99 unit tests green, ruff
clean, mypy clean on 50 source files.

**The three questions we cannot answer without you:**

- **Q1 (adaptation fidelity)** — our grid→code mapping for paper
  2604.13151 (ADR-18) bounds `U(t)` to `changed_files`. On 18 real
  Claude Code traces this produces a mechanical `ρ = −0.86` between
  `progress_rate` and `session_length`, and the paper's own
  `exploration_error` inverts sign on code (ρ=+0.36 instead of ρ≈−1
  per their Figure 1a). Is the mapping wrong in a way you can
  identify, or is this a domain-transfer limitation we should document
  as a negative result?
- **Q2 (obligation ↔ precondition semantics)** — our extractor emits
  an `Obligation` per AST guard / route decorator / migration marker.
  The mapper builds `PreconditionSpec` verified-or-not per obligation
  and feeds it into `grounding = Σ w·verified / Σ w`. In v4.2's
  original formulation, are **preconditions** and **obligations**
  isomorphic, or is there a structural distinction our mapper is
  collapsing?
- **Q3 (V_net safety before fusion)** — Phase 1-3 reports emit
  `null` for `mean_q_obs / mean_grounding / total_v_net / debt_final /
  corrupt_success_ratio` (ADR-13) because the Phase-4 LLM fusion is
  not yet wired. Is `null` the correct protocol under v4.2, or is
  there a partial-evidence convention (e.g. "confidence-weighted
  V_net") we should follow?

All three have code evidence below. Please read §6 "Open questions"
first if time is scarce — §1-5 are the supporting material.

---

## 1. Architecture and vendoring contract

### 1.1 The layered diagram

```
User code under audit
        │
        ▼
┌───────────────────────────────────┐
│  ingest/                          │  git inspect, diff, manifest, CC transcripts
├───────────────────────────────────┤
│  extract/                         │  AST → Obligation[] (3 kinds, 3 stubs)
├───────────────────────────────────┤
│  verify/                          │  ruff, mypy, pytest, semgrep, codeql, hypothesis, mutmut
├───────────────────────────────────┤
│  score/mapper.py                  │  Pydantic ↔ vendored Scenario (lossless)
│  score/trajectory.py              │  paper 2604.13151 Explore/Exploit scorer
│  score/verdict.py                 │  4-label verdict from ToolEvidence[]
├───────────────────────────────────┤
│  _vendor/oida_framework/          │  YOUR CODE — SHA256-pinned, `ruff` + `mypy` excluded
│    analyzer.py · models.py · io.py│
├───────────────────────────────────┤
│  report/                          │  JSON · Markdown · SARIF 2.1.0
└───────────────────────────────────┘
```

### 1.2 Vendoring discipline (ADR-02)

We never modify the vendored OIDA core. The file set in
`src/oida_code/_vendor/oida_framework/` was copied verbatim from
`search/OIDA/oida_framework/oida/` on 2026-04-23, with SHA256 hashes
pinned in `VENDORED_FROM.txt`. Your formulas in `analyzer.py` are
untouched:

- `grounding(event)` at line 64 (weighted sum over verified preconditions)
- `q_obs(event)` at line 71 (linear blend, weights from `config`)
- `mu(event)` at line 79 (`sqrt(reversibility · observability)`)
- `lambda_bias(event, reuse_count)` at line 86 (the β term)
- `_next_pattern_state(...)` at line 100 (H / C+ / E / B state machine)
- Damage accumulation at line 120 (paper §8 integration)
- `V_net` aggregation at `analyze()` line 152

If anything in `score/mapper.py` or `score/trajectory.py` contradicts
these, **your code wins — we need to change ours**.

### 1.3 What we added vs. what we kept

| Layer | Origin | Files | Notes |
|---|---|---|---|
| OIDA core | your work | `_vendor/oida_framework/{analyzer,models,io}.py` | frozen |
| Public Pydantic types | new | `models/{audit_request,audit_report,normalized_event,evidence,obligation,trace,trajectory}.py` | `extra="forbid"` throughout |
| Scorer bridge | new | `score/mapper.py` | ADR-13 null-vs-0.0 decision here |
| Trajectory scorer | new, paper-based | `score/trajectory.py` | ADR-18 mapping, Q1 below |
| Verifiers | new | `verify/{lint,typing,pytest_runner,semgrep_scan,codeql_scan,hypothesis_runner,mutmut_runner}.py` | 5 core + 2 opt-in |
| Obligation extractor | new | `extract/obligations.py` | Q2 below |
| Claude Code trace parser | new | `ingest/claude_code_trace.py` | handles 1542 production JSONL transcripts |

---

## 2. Phase-by-phase summary with proofs

### 2.1 Phase 0 — Bootstrap (commits `15138f3..1733f98`, `v0.1.0`)

Shipped the skeleton: `inspect` CLI, Pydantic v1 models, vendored OIDA
scorer. 10 tests, 74% coverage. Nothing to review from you here.

### 2.2 Phase 1 — Deterministic audit (commits `c155a3c..bbe3e00`)

Shipped 5 real verifiers (ruff, mypy, pytest, semgrep, codeql), a
deterministic verdict resolver over the 4 labels you specified, and
three report formats. `PHASE1_AUDIT_REPORT.md` in the repo root is
verbatim what was delivered.

**Exit gate met**: 4 of 10 planned public-repo audits ran without
crash (attrs + 3 in-workspace repos). 10-repo gate deferred.

### 2.3 Phase 2 — Observation model + obligation graph (commits `0497f26..68d7cbf`)

Added three new schemas:
- `Obligation` (PLAN.md §8) — the "testable commitment" type that
  our extractor emits and our mapper converts into `PreconditionSpec`
  (Q2)
- `Trace`, `TraceEvent`, `ProgressEvent`, `NoProgressSegment` (PLAN.md
  §9, paper 2604.13151 alignment) — agent-action trace surface
- Mapper round-trip with explicit **default-origin table**
  (`src/oida_code/score/mapper.py:12-38`) documenting which OIDA event
  fields come from real signal vs. held at a fixed default until later
  phases

**Empirical result**: the obligation extractor produced **143
non-trivial events** (140 preconditions + 3 migrations) when run over
the last 5 commits of this repo's own history (see
`PHASE2_AUDIT_REPORT.md §3.2`). Round-trip Pydantic ↔ vendored
dataclass loses zero information on all event fields
(`tests/test_mapper.py::test_roundtrip_preserves_all_event_fields`).

**Evidence linker** (advisor-mandated, `score/mapper.py:216-325`):
closes `precondition` obligations when `pytest.status == "ok"` AND
`counts.failure == 0` AND scope is in `changed_files`; closes
`api_contract` when ruff + mypy are green for the scope. This is the
*only* way Phase-2 reports produce non-zero `grounding`.

### 2.4 Phase 3 — Explore/Exploit trajectory scorer (commits `ab3bc3e..2cbc6f1`, `v0.4.0` / `v0.4.1`)

This is the phase where we need your eyes most. Details in §3 and §5.

---

## 3. The Phase-3 adaptation (ADR-18)

### 3.1 Paper's formulas (2604.13151 §4, verbatim)

For a no-progress trajectory `np(t)` = actions since last progress
event, with edges `E_np` and nodes `V_np`:

```
c_t = |E_np| - |V_np| + 1                      (cyclomatic number)
e_t = Σ_e max{m_np(e) - 2, 0}                   (edge reuse penalty, budget = 2)
n_t = Σ_v max{m_np(v) - 2, 0}                   (node reuse penalty, budget = 2)
S_t = c_t + e_t + n_t                           (stale score)

err(t) = 0                    if t → t+1 is a progress event
       = 1                    if Gain(t → t+1) = 0
       = 0                    if |T(t)| = 1  AND  Gain(t → t+1) = 1
       = 1{S_t > S_{t-1}}    if |T(t)| > 1  AND  Gain(t → t+1) = 1
```

Case attribution (Table 1 of 2604.13151):

| Case | Condition | Target set `T(t)` | Required action |
|---|---|---|---|
| 1 | `P(t) = ∅`, `U(t) ≠ ∅` | `U(t)` | exploration |
| 2 | `g ∈ P(t)` | `{l(g)}` | exploitation |
| 3 | `P ≠ ∅`, `g ∉ P`, `U = ∅` | `{l(u) : u ∈ P}` | exploitation |
| 4 | `P ≠ ∅`, `g ∉ P`, `U ≠ ∅` | `U ∪ {l(u) : u ∈ P}` | either |

Normalisation (paper §5):
- `exploration_error = errors_in_cases_1_and_4 / timesteps_in_cases_1_and_4`
- `exploitation_error = errors_in_cases_2_3_and_4 / timesteps_in_cases_2_3_and_4`

Our implementation: `src/oida_code/score/trajectory.py`. The formulas
are line-for-line faithful (verified by 10 unit tests over 5 synthetic
fixtures in `tests/fixtures/traces/*.json`).

### 3.2 ADR-18 — the code domain adaptation

The paper uses a **2D grid + DAG** environment. To translate to code
traces we had to define `U(t)`, `P(t)`, `g`, and `Gain`.

| Paper concept | Our definition | Reference |
|---|---|---|
| `U(t)` unobserved cells | `{f ∈ AuditRequest.scope.changed_files : f ∉ visited(t)}`  where `visited(t) = paths touched by Read/Grep/Glob in events[:t]` | `score/trajectory.py:66-100` |
| `P(t)` pending tasks | `{o ∈ obligations : o.status = "open" ∧ deps of o closed ∧ scope(o) ∈ visited(t)}` | `score/trajectory.py:129-147` |
| Goal `g` | obligation with `source = "intent"` if present; else highest-weight obligation | `score/trajectory.py:115-126` |
| `Gain(t → t+1) = 1` | `event[t+1].scope ∩ U(t) ≠ ∅` OR `closed_obligations(t+1) ⊋ closed_obligations(t)` | `score/trajectory.py:181-200` |
| Progress event | entered a path in `U(t)` OR closed a new obligation | `score/trajectory.py:155-175` (renamed `_is_progress_step` after bug fix in v0.4.1) |
| Node in `V_np` | `(event.kind, event.scope[0] or "_none")` | `score/trajectory.py:220-250` |
| Edge in `E_np` | consecutive `(node_t, node_{t+1})` inside the np-window | same |

**Our rationale for bounding `U(t)` to `changed_files`**: in code, the
"unobserved" action space is effectively infinite (all files in the
repo, the web, stdlib). Leaving `U` unbounded would make Case 3 of
Table 1 never fire (`U(t) = ∅` would be impossible), collapsing the
case split to `{1, 4}` and destroying the `exploitation_error`
normaliser. The diff-scoped surface is finite and maps cleanly to the
paper's "did the agent visit the relevant territory?" intuition.

---

## 4. Empirical results

### 4.1 Synthetic-fixture gate (PASSED)

Five hand-crafted JSON traces under `tests/fixtures/traces/`:

| Fixture | Label | Scorer output (direction) |
|---|---|---|
| `exploration_dominated.json` | `exploration_error` | exploration > exploitation ✓ |
| `exploitation_dominated.json` | `exploitation_error` | exploitation >> exploration ✓ |
| `stale_cycling.json` | `stale` | `stale_score ≥ 1` ✓ |
| `clean_success.json` | success | both ≤ 0.55 ✓ |
| `mixed_progress.json` | mixed | ≥ 1 progress event, non-trivial exploration error ✓ |

10 unit tests pass: `tests/test_score_trajectory.py`. This confirms
the **math** is implemented correctly — `c_t/e_t/n_t/S_t/err(t)`
compute the paper's intended values on hand-verifiable inputs.

### 4.2 Real-trace validation (FAILED ON NON-CONFOUNDED SIGNAL)

Script: `scripts/validate_phase3.py`.

Input: 20 Claude Code JSONL transcripts (one per project,
round-robin) from `~/.claude/projects/`. After dropping sessions with
< 50 steps, **n = 13**.

Outcome labeller: `ingest/session_outcome.py`. For each transcript,
labels `success` iff at least one commit authored during the
transcript's timestamp window is reachable from HEAD; `failure` if no
commits; `partial` if commits were rebased away; `unknown` if the
transcript's `cwd` isn't a git repo.

**Raw ρ table** (Spearman, computed via `statistics.correlation(...,
method="ranked")`):

| Metric | ρ vs outcome | ρ vs session length | Interpretation |
|---|---|---|---|
| `log(exploration_error)` | **+0.356** | moderate | **Wrong sign** vs paper Figure 1a |
| `log(exploitation_error)` | +0.163 | weak | noise |
| `progress_rate = progress_events / total_steps` | −0.668 | **−0.858** | looks clean, **but mechanical** |
| `no_progress_rate` | +0.668 | +0.858 | mirror of above |
| `total_steps` | +0.690 | — | length predicts outcome |
| `stale_score` | +0.733 | — | length predicts outcome |
| `commits_in_window` | **+0.902** | +0.792 | **outcome label is ~synonymous with length** |
| `commits_per_step` | +0.902 (confounded) | +0.515 | failure-class collapses to 0 |

**Per-transcript breakdown** (ordered, 18 usable with outcome):

```
outcome   steps  prog  prate   expl   expt  stale  cmt reach
failure       1     0  0.000  0.000  0.000      0    0     0
failure       6     1  0.167  0.667  0.667      2    0     0
failure       7     0  0.000  0.000  0.857     10    0     0
failure      42    10  0.238  0.524  0.952     19    0     0
failure      72    17  0.236  0.750  0.000     28    0     0
failure     114    17  0.149  0.842  0.000     63    0     0
failure     153    16  0.105  0.889  0.000    109    0     0
failure     156    14  0.090  0.222  0.993    163    0     0
success      25     0  0.000  0.000  0.960     41    4     4
success      85    15  0.176  0.812  0.000     29    3     3
success     207    17  0.082  0.913  0.000    251   29    29
success     288    16  0.056  0.636  0.996    295   14     5
success     315    16  0.051  0.946  0.000    174    7     7
success     419    16  0.038  0.826  0.997    488   67    67
success     447    15  0.034  0.964  0.000    460   36    36
success     478    16  0.033  0.964  0.000    553   67    65
success     490    16  0.033  0.965  0.000    537   15    15
success     676    15  0.022  0.444  0.998    812   20    20
```

### 4.3 Why the empirical gate is artifactual

Three stacked artifacts that we cannot escape on this corpus:

1. **Outcome label ≈ session length.** `ρ(commits, total_steps) =
   +0.79`. Every failure row has `commits = 0`; every success row has
   `commits > 0`. The "outcome" is literally `commits > 0` in this
   sample.
2. **`progress_events` has a ceiling at ~15.** The validation uses
   `_derive_changed_files(limit=15)` as a bounded-`U(t)` heuristic,
   so there are at most 15 "new-path-entered" events per session,
   regardless of length. 12/18 rows saturate at 14-17 (off-by-a-few
   from the cap because some events closed an obligation instead of
   entering a path).
3. **Mechanical `15/N` decay.** `progress_rate ≈ 15/N` → any metric
   based on it will correlate with session length by arithmetic, not
   by domain signal.

**Attempted remediation**:
- `commits_per_step` (length-normalised outcome): `ρ(cps, length) =
  +0.515` — still confounded. Plus failure class collapses to a
  constant (cps = 0 for all 8 failures) because `commits = 0` there.
- Pytest-pass at session-end commit (advisor's preferred signal):
  corpus spans 15 distinct repos in 5 languages; per-repo env setup
  would cost a week for 18 data points.
- Narrowing to a single repo: largest single-project sample is
  9 traces (YGN-SAGE), marginal for Spearman.

**Conclusion (v0.4.1 amended)**: the empirical Phase-3 gate is
**deferred to Phase 4**, not failed. Synthetic gate stands. The
mechanical bounds of our U(t) proxy + the tautological outcome label
mean the current data cannot decide whether the paper's main finding
(Figure 1a, R² = 0.947 negative) transfers to code.

> ### Q1 (Phase-3 adaptation fidelity)
>
> We bound `U(t)` to `AuditRequest.scope.changed_files` because the
> paper's unbounded U(t) definition is not tractable in code (§3.2).
> Three specific sub-questions:
>
> 1. **Is the diff-scope bound correct, or should `U(t)` include
>    **imports reachable** from `changed_files` (one-hop or transitive)?**
>    The intuition: a sensible code auditor doesn't just read files
>    that changed — they also read files imported BY the changed
>    files. Our current `U(t)` punishes that as "wandering outside
>    the audit surface" and inflates exploration_error.
> 2. **Is Table 1's Case-3 branch even reachable in code?** In a grid,
>    U eventually empties (finite). In code, even with the diff bound,
>    U empties only when the agent reads every changed file — which
>    many short sessions never do. In our n=13 sample, Case 3 fired
>    in **0 timesteps**. The paper's `exploitation_error` normaliser
>    is (Cases 2 + 3 + 4); with Case 3 = 0 everywhere, we're
>    essentially reporting (Cases 2 + 4) / denominator, which inverts
>    the semantics.
> 3. **Is the adaptation recoverable** via a different `Gain()`
>    function (e.g. "obligation closed OR test suite now passes"
>    instead of set-membership on unread files), or is the grid-world
>    `Gain` fundamentally not portable to code?
>
> A yes/no on (1)-(3) plus any pointers to related work (Kim et al.
> 2026, Jeong et al. 2026, or anything post-dating 2604.13151 that
> tackled code agents specifically) would save us weeks.

---

## 5. Mapper / v4.2 questions, with proofs

### 5.1 The default-origin table (ADR-13 context)

From `src/oida_code/score/mapper.py:12-37`:

```
| Field                  | Phase 2 source                                   |
|------------------------|--------------------------------------------------|
| pattern_id             | synthesized from obligation.kind + scope hash    |
| task                   | obligation.description (truncated)               |
| capability             | **default 0.5** (Phase 4 LLM fills from intent)  |
| reversibility          | heuristic 1 - data_signal(scope)                 |
| observability          | **default 0.5** (Phase 4 uses test-file presence)|
| blast_radius           | Phase 1 estimate_blast_radius()                  |
| completion             | pytest pass-ratio from evidence, default 0.5     |
| tests_pass             | 0.50·regression + 0.25·property + 0.25·mutation  |
| operator_accept        | lint + types green from evidence                 |
| benefit                | **default 0.5** (Phase 4 LLM from intent)        |
| preconditions          | from obligation graph (one PreconditionSpec each)|
| constitutive_parents   | empty in P2 (dependency extractor is P2 stub)    |
```

The bolded **default** cells are placeholders we don't trust. The
rationale for **ADR-13** (emit `null` in `ReportSummary`, not `0.0`):

> Option (a) `Optional[float] = None` — the honest choice. Option (b)
> doubles the schema. Option (c) `0.0 with footnote` is the trap — a
> reader who skims `debt=0.0` concludes "no debt", which is a silent
> lie.

**We chose (a).** The Markdown renderer prints
`_not computed in Phase 1_` wherever a field is `null`.

> ### Q3 (V_net safety before fusion)
>
> Is this the correct protocol under v4.2? Specifically:
> - When `capability = observability = benefit = 0.5` everywhere, can
>   `V_net` be meaningfully reported at all, or must every
>   non-identifiable field propagate `null` through the aggregation?
> - Is there a v4.2 convention for "confidence-weighted V_net" that
>   would let us emit a number + a confidence band rather than `null`?
> - If a user reads a Phase-2 JSON with `debt_final: null`, how do
>   you recommend we signal the difference between "no debt computed"
>   and "debt is genuinely 0"?

### 5.2 Obligation ↔ PreconditionSpec

Our extractor (`src/oida_code/extract/obligations.py`) emits
`Obligation` objects with six kinds (three implemented, three stubs).
The mapper then converts each obligation into exactly **one**
`PreconditionSpec` via `src/oida_code/score/mapper.py:216-224`:

```python
def _preconditions_for(obligation: Obligation) -> list[PreconditionSpec]:
    return [
        PreconditionSpec(
            name=obligation.description[:120] or f"{obligation.kind}:{obligation.scope}",
            weight=float(obligation.weight),
            verified=obligation.status == "closed",
        )
    ]
```

So **`grounding(event) = Σ w·verified / Σ w`** ends up being "fraction
of this event's obligations that are closed", weighted by the
obligation's priority weight (default 1).

> ### Q2 (obligation ↔ precondition isomorphism)
>
> 1. In v4.2, are **preconditions** and **obligations** meant to be
>    isomorphic (one obligation → one precondition), or are
>    preconditions a structural supertype (an obligation may entail
>    multiple preconditions, e.g. an api_contract might need auth +
>    shape + idempotency preconditions)?
> 2. If the latter, our `_preconditions_for` is **collapsing**
>    information before it reaches `grounding()`, which would
>    artificially smooth the grounding signal. Is this correct, and
>    if so, is there a recommended multiplicity heuristic per
>    obligation `kind`?
> 3. The `weight` field on `Obligation` currently always defaults to
>    `1`. Our extractor has no principled way to set it higher. Does
>    v4.2 have a canonical weighting for "intent" vs "migration" vs
>    "api_contract" obligations, or is this left to the integrator?

### 5.3 The `constitutive_parents` empty-graph decision

The Phase-2 mapper emits every event with
`constitutive_parents = supportive_parents = []`. We documented this
as an explicit ADR-15 trade-off: "shipping a wrong dependency graph
produces confidently-wrong V_net; shipping an empty one produces
honestly-incomplete V_net." (`src/oida_code/extract/dependencies.py`)

Consequence: `_next_pattern_state` gets an isolated event (no graph
propagation), so `B`-state damage accumulates only when the event
itself passes the `lambda_bias >= bias_threshold AND g < 0.60 AND
q >= 0.70` branch, never through a cascade from an upstream confirmed
pattern.

> ### Q2.5 (empty dependency graph severity)
>
> Is this silent-degradation-to-single-event mode acceptable under
> v4.2, or does the model require at least a best-effort graph for
> the damage term to be meaningful? If the latter, we should probably
> refuse to emit `V_net` / `debt_final` at all (not just `null`) when
> the graph is empty.

### 5.3.5 Empirical validation signal — the repeat problem

Across three phases, we tried three different validation signals
against the scorer; each failed for a different reason:

| Phase | Signal tried | Why it failed |
|---|---|---|
| P2 | Hand-labelled recall on an annotated PR set | User bandwidth; dataset never produced |
| P3 | Multi-Codex agent labels on traces | Advisor flagged as circular (Codex uses the same formulas the scorer uses) |
| P3 | Git-derived outcome (`commits_reachable_from_HEAD`) | Tautological with session length (ρ = +0.79); see §4.2 |

> ### Q5 (empirical validation strategy)
>
> **What outcome signal did you use for the v4.2 paper's published
> experiments?** Specifically:
>
> - Was it a human-labelled dataset (e.g. "did this PR ship without
>   rollback?"), an auto-derived signal (CI pass / subsequent
>   reverts), or a proxy from a test harness?
> - Do you have a validation-protocol document for v4.2 we could
>   follow rather than reinvent?
> - If the answer is "the v4.2 paper used a synthetic benchmark",
>   would you release that benchmark to us under any licence? We can
>   provide hardware (RTX 3500 Ada Laptop, 12 GB VRAM) + the four
>   frontier-LLM API keys (Grok / DeepSeek / MiniMax / Kimi) for any
>   rerun you'd want on it.

### 5.4 Verdict label ↔ pattern state correspondence

Our verdict resolver (`src/oida_code/score/verdict.py`) emits one of
four labels: `verified / counterexample_found / insufficient_evidence
/ corrupt_success`. The `corrupt_success` label is supposed to align
with the B-state pattern in v4.2. Currently it's **unreachable** in
Phase 1-3 because we never run the OIDA fusion.

> ### Q4 (corrupt_success detection in Phase 4 fusion)
>
> When the Phase-4 LLM wires capability/benefit/observability,
> corrupt_success becomes reachable. Your guidance on the decision
> threshold:
>
> - The paper's B-state entry condition is
>   `lambda_bias >= bias_threshold AND g < 0.60 AND q >= 0.70`. Is
>   this the threshold we should surface as `corrupt_success`, or is
>   there a stricter "definitely bad" cutoff (e.g. `B`-state sustained
>   over N consecutive events)?
> - Should `corrupt_success` trip when `any(patterns[...].state ==
>   "B")` or only when `b_load >= some threshold`?

---

## 6. Open questions — summary list

**Q1** (Phase-3 adaptation fidelity) — ADR-18. Is bounding U(t) to
`changed_files` the right move, or does paper 2604.13151 require a
different decomposition for unbounded action spaces?

**Q2** (obligation ↔ precondition isomorphism) — are our
`_preconditions_for` collapsing information that should reach
`grounding()` as multiple weighted preconditions?

**Q2.5** (empty dependency graph severity) — is `V_net` meaningful
when `constitutive_parents = []` everywhere?

**Q3** (V_net safety before fusion) — `null` vs partial-evidence
convention. Is there a v4.2 confidence-weighted output we should be
emitting?

**Q4** (corrupt_success threshold in Phase 4) — which B-state
predicate should `corrupt_success` correspond to?

**Q5** (empirical validation strategy) — given that the current corpus
is length-confounded and per-repo pytest is intractable, do you have
an existing validation protocol for v4.2 on real code changes that we
could borrow? Specifically: **what outcome signal did you use in the
v4.2 paper's experiments?**

**Q6** (public release timing) — would you prefer we defer a PyPI
release until one or more of Q1-Q5 are resolved, or is the current
"honest placeholders + `null` fusion fields" surface safe to publish
as a 0.x preview under MIT?

---

## 7. What we want from this review

Three concrete outputs would unblock us:

1. **A ruling on Q1**: is our ADR-18 mapping faithful to the spirit
   of paper 2604.13151, or is there a known domain-transfer
   limitation for unbounded action spaces that would make any naïve
   adaptation produce length-confounded correlations? If the latter,
   we'd appreciate pointers to follow-up papers (Kim et al. 2026
   and Jeong et al. 2026 are cited in 2604.13151 §1 but we haven't
   tracked them down).
2. **An answer to Q2 + Q2.5**: these change our mapper's core logic.
   If obligations should map to multiple preconditions, we'll rewrite
   `_preconditions_for` before Phase 4. If an empty graph invalidates
   `V_net`, we'll add a guard that refuses to emit the fusion block.
3. **A sanity check of Q3 + Q5**: if the `null`-vs-0.0 decision is
   wrong under v4.2 convention, we'll flip it *before* a PyPI release
   bakes it into downstream consumers.

The reports and data referenced above are reproducible from the tag
`v0.4.1`:

```
git clone https://github.com/yannabadie/oida-code
git checkout v0.4.1
python -m pip install -e ".[dev]"
python -m pytest                       # 99 tests
python scripts/validate_phase3.py      # recompute §4.2 ρ values
cat PHASE3_AUDIT_REPORT.md             # amended empirical findings
cat memory-bank/decisionLog.md         # 18 ADRs in chronological order
```

We have budget to run any experiment you recommend, including the
paper-dataset sanity check (running our `c_t/e_t/n_t` on the 2604.13151
authors' released 2D grid traces from
`github.com/jjj-madison/measurable-explore-exploit`, which we have not
yet executed because it's a Phase-4 carry-over).

Thank you for reading. Direct answers to any subset of Q1-Q6 are
useful; a partial review is better than waiting for a full one.

---

*Document prepared 2026-04-24 by Claude Code (Claude Opus 4.7, 1M-context
build) at `yann.abadie`'s direction. All file references and commit
hashes correspond to repository state at tag `v0.4.1`.*

# OIDA Code Audit — Historical Plan (merged)

**Version 1.0 · 2026-04-24 · Supersedes `oida-code-mvp-blueprint.md` §11 and subsumes `docs/legacy/roadmap.md`.**

This document preserves the merged blueprint and roadmap context from
2026-04-24. It is no longer the active source of truth for product
direction where it conflicts with the current diagnostic-only project
state.

As of ADR-74 / 2026-04-30, active product direction lives in
`docs/product_strategy.md`, and verified current repo state lives in
`docs/project_status.md`. This file remains useful for historical
architecture context and long-horizon research ideas only.

---

## 0. Authority hierarchy (updated 2026-04-30)

```
docs/product_strategy.md                         active product direction
docs/project_status.md                           verified current repo state
AGENTS.md                                        autonomous-agent continuity rules
BACKLOG.md                                       acknowledged gaps, not commitments
PLAN.md                                          historical architecture / research plan
```

Active authority update:

- `docs/product_strategy.md` defines current product direction.
- `docs/project_status.md` defines verified current repo state.
- `AGENTS.md` defines autonomous-agent continuity rules.
- `BACKLOG.md` records acknowledged gaps, not commitments.
- `PLAN.md` is historical/aspirational unless a later ADR explicitly
  reactivates a section.

Older statements in this file about GitHub App, SaaS, active verdict
surfaces, repair planner, or official fusion-field output are not
current roadmap commitments.

Pre-merge scratch (`brainstorm2.md`, `brainstorm2_improved.md`)
removed from the working tree in `chore(repo): tidy root` — the
narrative use of those files in `memory-bank/activeContext.md` is
historical record only.

Blueprint §11 (the "First 10 implementation days" aspirational plan) is **superseded** by §14 below.

---

## 1. Positioning (blueprint §1, reinforced)

**Name:** `oida-code`. Never `unslop.ai` (collisions + framing conflict — ADR-01).

**Core promise:**

> Measure the gap between what AI-written code *appears* to do (`Q_obs`) and what it *actually* guarantees (grounding + reversibility + observability + verified preconditions). Expose *corrupt success* — high `Q_obs`, negative `V_net` — that outcome-only metrics miss.

**Current shape:** CLI and composite GitHub Action first, both
diagnostic-only. GitHub App, SaaS, default gateway, autonomous repair
planner, and official fusion-field output are deferred research or
backlog concepts, not current product scope.

---

## 2. Non-goals and non-claims (blueprint §12 + paper §10 + roadmap rule 3)

- **Never** claim "mathematical proof" of arbitrary code semantics (Rice's theorem). Only the 4 labels in §6 are defensible.
- **Not** a "clean code" AI assistant.
- **Not** a substitute for runtime enforcement, IAM, backups, approval gates, or policy engines (paper §10). OIDA is an *accounting + repair-planning* layer.
- **Not** the first agent-safety / trace-assurance / behavioral-drift framework (paper §1). The differentiator is cumulative operational debt + dominance-aware repair, not runtime guardrails.

---

## 3. Pipeline architecture (merged: blueprint §3 + roadmap stack)

```
repo / diff / ticket / intent
  │
  ▼
[Pass 1a] deterministic facts       ← ruff · mypy · pytest · Semgrep · CodeQL · git diff
  │                                   output: machine-only facts
  ▼
[Pass 1b] obligation extraction     ← AST + call graph + diff hunks
  │                                   output: obligation graph (invariants, preconditions, migrations, API contracts)
  ▼
[Pass 2a] behavioral verification   ← Hypothesis (properties) · mutmut (mutations) · adversarial regressions
  │                                   output: proof-or-counterexample per obligation
  ▼
[Pass 2b] agent-trace scoring       ← Explore/Exploit metric on the action trace
  │                                   output: exploration_error · exploitation_error · stale_score · no_progress_rate
  ▼
[Pass 3 ] agentic verification      ← forward verifier (premises→sufficient?) · backward (outcome→missing premises?)
  │                                   LLM as verifier, NEVER source of truth. Uses tools.
  ▼
[OIDA fusion]                       ← Q_obs · μ · λ_bias · grounding · V_dur · H_sys · V_net · Debt
  │                                   output: per-event ledger + pattern state {H, C+, E, B}
  ▼
[Verdict resolver]                  ← 4 labels (§6) with evidence trail
  │
  ▼
[Repair planner]                    ← dominance-based double-loop: reopen + audit + targeted prompts
  │
  ▼
Surfaces: CLI · JSON · SARIF · Markdown · GitHub Check Run · PR annotations
```

---

## 4. Three architecture rules (non-negotiable)

1. **Truth does not come from the LLM.** Evidence flows from tools, tests, counter-examples, proven properties, static alerts. The LLM *plans, reformulates, ranks, explains, proposes repairs*. It never replaces a passing test or a running Semgrep rule.
2. **LongCoT and Simula do NOT block the MVP.** LongCoT = long-horizon robustness benchmark for the critic (Phase 7). Simula = synthetic trace generator for hard negatives (Phase 7). Neither gates shipping.
3. **No "mathematical proof of arbitrary code" claim, ever.** See §2, §6. For honest-to-god proof on a critical module, use Dafny / KLEE / Creusot with an explicit spec — that is a Phase 7+ concern, not an MVP surface.

---

## 5. Research sources — integration matrix

| Source | arXiv / repo | Role in OIDA Code Audit | Phase |
|---|---|---|---|
| **OIDA v4.2** | Abadie 2026 (this author) | Core ontology + deterministic scorer. Frozen formulas (§7). | Vendored since Phase 0. |
| **Explore/Exploit Errors** | 2604.13151 · `jjj-madison/measurable-explore-exploit` | Trajectory scorer: exploration vs exploitation error on agent traces. **Requires observation model first.** | Phase 3 (blocked by Phase 2). |
| **AgentV-RL** | 2604.16004 · `JiazhengZhang/AgentV-RL` | Forward/backward verifier architecture with tool use + multi-turn aggregation. Generalises to code per LiveCodeBench results. | Phase 4. |
| **LongCoT** | 2604.14140 · `LongHorizonReasoning/longcot` | External benchmark. Verify the critic stays lucid at long horizons. LongCoT-Mini (~500 easy) first, full (2 500 hard) after. | Phase 7 (not on the critical path). |
| **Simula** | 2603.29791 · Google blog | Reasoning-first synthetic data generator. Hard negatives + adversarial obligations + controlled tickets. | Phase 7 (research moat). |

---

## 6. Verdict taxonomy (final)

**Machine identifier** (Pydantic `Literal`):
```python
VerdictLabel = Literal[
    "verified",
    "counterexample_found",
    "insufficient_evidence",
    "corrupt_success",
]
```

**Human prose** (for reports):

| Label | Meaning | Trigger condition |
|---|---|---|
| `verified` | "Proved enough to merge." | Formal proof of an explicit property OR (regression ∧ property ∧ mutation) all above `policy.min_*` thresholds with `grounding ≥ confirm_threshold`. |
| `counterexample_found` | "Execution produced a failing case." | Any of: failing pytest, Hypothesis shrunk counterexample, surviving mutant, Semgrep high-severity hit on changed lines. |
| `insufficient_evidence` | "Cannot confirm nor refute within policy budget." | Neither a positive proof nor a counterexample; grounding below threshold; tests didn't run or timed out. |
| `corrupt_success` | "High apparent quality, negative net value." | `Q_obs ≥ corrupt_success_q_threshold` (default 0.80) AND `V_net < 0`. *The wedge.* |

---

## 7. OIDA scoring core (blueprint §6 + paper §4, frozen)

All formulas owned by the vendored `oida_code._vendor.oida_framework.analyzer`. Phase 1+ code **never** reimplements them.

```
grounding_t = Σ w_k · 1[verified_k] / Σ w_k            over critical preconditions Π_t

Q_obs = 0.40·completion + 0.40·tests_pass + 0.20·operator_accept
      where tests_pass = 0.50·regression + 0.25·property + 0.25·mutation

μ = sqrt(reversibility · observability)

capability = 1 − difficulty_mismatch
      mismatch raised by: DB migrations, concurrency, auth/security, public APIs,
                          multi-module refactors, cross-service behavior

blast_radius estimated from: #changed modules, public API exposure,
                             dependency fan-out, data-layer criticality

λ_{H→B} = α_B · cap · (1−μ) · (1−g) · ρ(reuse) · Q_obs    (clipped to 1.5)

N_stock = #{C+} + Σ_{H} v_i
B_load  = Σ_{B} damage_i
N_eff   = N_stock − B_load
Debt    = max(0, −N_eff)

V_dur = benefit · g · (1 + μ·cap) · (1 − Debt̃_{t−1})
H_sys = ψ · (1−μ) · cap · B̃ · Q_obs
V_net = V_dur − H_sys

Pattern state: {H, C+, E, B}     (see paper §4.5)
Repair:       double-loop, dominance-based (paper §5)
```

Defaults (`AnalyzerConfig`): `α_b=1.15, confirm_threshold=0.80, bias_threshold=0.45, τ_ref=3.0, corrupt_success_q_threshold=0.80`.

---

## 8. Observation model (new, from roadmap P2 — the keystone piece)

Three first-class types living in `src/oida_code/models/trace.py` (Phase 2):

### `Obligation`

A testable commitment the change *must* satisfy. Six kinds:
1. **invariant** — e.g. "refund is idempotent".
2. **precondition** — e.g. "email is None-checked before hashing".
3. **api_contract** — e.g. "400 response documented for signup".
4. **migration** — e.g. "backup verified + restore rehearsed".
5. **security_rule** — e.g. "admin path enforces CSRF".
6. **observability** — e.g. "failure path logs enough to debug".

Fields: `id`, `kind`, `scope` (file/symbol/endpoint), `evidence_required` (list of proof types), `status ∈ {open, closed, violated}`, `source` (diff | intent | extracted).

### `ProgressEvent`

Any action that reduces uncertainty or closes an obligation:
- proved a property,
- located a bug,
- added a test that killed a mutant,
- generated an executable counterexample,
- closed an obligation with concrete evidence.

### `NoProgressSegment`

Contiguous window of trace actions that **does not** reduce the open-obligation set nor the critical-unknown set. Mirrors Park et al.'s "structurally redundant behavior within no-progress segments" formalism, translated grid→repo.

Fields: `start_t`, `end_t`, `length`, `cycle_count`, `edge_reuse`, `node_reuse`, `classification ∈ {exploration_error, exploitation_error, stale}`.

These three types feed both Pass 2a (behavioral verification — "does this obligation survive mutation?") and Pass 2b (trajectory scorer — "did the agent loop on a closed obligation?").

---

## 9. Schema surface (evolution)

Public boundary is Pydantic v2. Each schema has a version:

| Schema | Ships in | Role |
|---|---|---|
| `AuditRequest` | **v1 · P0 (shipped)** | Pass 1 input |
| `NormalizedScenario` | **v1 · P0 (shipped)** | Deterministic-scorer input (vendored `Scenario` bridge) |
| `AuditReport` | **v1 · P0 (shipped)** | Pipeline output |
| `Obligation`, `ProgressEvent`, `NoProgressSegment` | v2 · P2 | Observation model |
| `TraceEvent` | v2 · P2 | Normalized agent action record |
| `TrajectoryMetrics` | v3 · P3 | Explore/Exploit scoring output |
| `VerifierVerdict` | v4 · P4 | Forward/backward verifier output |
| `RepairPlan` (exists, expanded) | v4 · P5 | Targeted repair prompts + reopen/audit sets |

Rule: once a schema is in `v_i`, bumping requires an ADR in `memory-bank/decisionLog.md`.

---

## 10. Repository structure (blueprint §7, anchored)

Kept verbatim from blueprint §7. What's shipped vs stubbed as of 2026-04-24:

```text
oida-code/
├── pyproject.toml                 ✓ Phase 0
├── README.md                      ✓ Phase 0
├── LICENSE                        ✓ Phase 0 (MIT)
├── PLAN.md                        ✓ this file
├── src/oida_code/
│   ├── __init__.py                ✓ Phase 0
│   ├── cli.py                     ✓ inspect impl; normalize/verify/audit/repair = NotImplementedError
│   ├── config.py                  ✓ default AnalyzerConfig re-export
│   ├── models/                    ✓ audit_request, normalized_event, audit_report (v1)
│   │                              ⧖ trace, obligation, progress_event (v2 Phase 2)
│   ├── ingest/
│   │   ├── git_repo.py            ✓ Phase 0
│   │   ├── diff_parser.py         ✓ Phase 0 (name-only level; hunk-level Phase 1)
│   │   └── manifest.py            ✓ default_python_commands; detect_commands = Phase 1
│   ├── extract/
│   │   ├── claims.py              ⧖ Phase 2
│   │   ├── preconditions.py       ⧖ Phase 2
│   │   ├── blast_radius.py        ⧖ Phase 1 (enough to populate AuditRequest)
│   │   ├── dependencies.py        ⧖ Phase 2
│   │   └── obligation_graph.py    ⧖ Phase 2 (new, keystone)
│   ├── verify/
│   │   ├── lint.py                ⧖ Phase 1
│   │   ├── typing.py              ⧖ Phase 1 (absolute-import path only, shadows stdlib)
│   │   ├── semgrep_scan.py        ⧖ Phase 1
│   │   ├── codeql_scan.py         ⧖ Phase 1 (CLI only; deep integration Phase 7)
│   │   ├── pytest_runner.py       ⧖ Phase 1
│   │   ├── hypothesis_runner.py   ⧖ Phase 2
│   │   └── mutmut_runner.py       ⧖ Phase 2
│   ├── llm/                       ⧖ Phase 4
│   │   ├── client.py              (Qwen3.6-35B-A3B via llama.cpp local)
│   │   ├── schemas.py
│   │   ├── forward_verifier.py
│   │   ├── backward_verifier.py
│   │   └── repair_prompts.py      ⧖ Phase 5
│   ├── score/
│   │   ├── analyzer.py            ✓ Phase 0 (re-export shim)
│   │   ├── mapper.py              ⧖ Phase 2 (Pydantic ↔ vendored dataclass)
│   │   ├── trajectory.py          ⧖ Phase 3 (new — Explore/Exploit)
│   │   ├── verdict.py             ⧖ Phase 1 (deterministic path); Phase 4 (+LLM aggregator)
│   │   ├── fusion.py              ⧖ Phase 5 (new — OIDA + trajectory + agentic)
│   │   └── repair.py              ⧖ Phase 5 (new — double-loop caller)
│   ├── report/
│   │   ├── json_report.py         ⧖ Phase 1
│   │   ├── markdown_report.py     ⧖ Phase 1
│   │   └── sarif_export.py        ⧖ Phase 1 (SARIF 2.1.0)
│   ├── github/                    ⧖ Phase 6
│   │   ├── checks.py              (Check Run API — requires GitHub App)
│   │   └── annotations.py         (batched 50/req per GitHub API limits)
│   └── _vendor/oida_framework/    ✓ Phase 0 (frozen, SHA256 pinned)
├── examples/                      ✓ Phase 0
│   ├── audit_request.json
│   ├── normalized_scenario.json
│   └── audit_report.json
├── tests/                         ✓ Phase 0 (10 tests, 74% coverage)
└── .github/workflows/
    └── oida-code.yml              ⧖ Phase 6
```

Legend: `✓` shipped · `⧖` stubbed (NotImplementedError, awaiting its phase).

---

## 11. CLI contract (blueprint §8, extended)

```bash
oida-code inspect ./repo --base origin/main --out .oida/request.json        # ✓ P0
oida-code normalize .oida/request.json --out .oida/scenario.json            # ⧖ P2 (needs obligation graph)
oida-code verify .oida/scenario.json --out .oida/evidence.json              # ⧖ P1 (determinist); P4 (+agentic)
oida-code audit ./repo --base origin/main --intent ticket.md                # ⧖ P1 (determinist); P4 (+agentic); P5 (+fusion)
oida-code repair .oida/report.json --out .oida/repair.md                    # ⧖ P5
```

Flags landing per phase:
- P1: `--format {json,sarif,markdown}`, `--out`, `--intent PATH`, `--fail-on {any_critical,corrupt,none}`.
- P4: `--llm-endpoint`, `--llm-model`, `--offline` (skip Pass 3).
- P6: all of the above wired behind the GitHub Action environment.

---

## 12. Report contract (blueprint §9, extended)

Minimum JSON stays as blueprint §9. Added in later phases:

```json
{
  "summary": {
    "verdict": "corrupt_success",       // snake_case Literal from §6
    "mean_q_obs": 0.83,
    "mean_grounding": 0.58,
    "total_v_net": -0.21,
    "debt_final": 0.63,
    "corrupt_success_ratio": 0.5,
    "trajectory": {                     // P3+
      "exploration_error": 0.12,
      "exploitation_error": 0.34,
      "stale_score": 0.41
    }
  },
  "critical_findings": [ ... ],         // unchanged
  "obligations": [ ... ],               // P2+
  "trace": { ... },                     // P2+
  "repair": { ... }                     // unchanged (repair.reopen + audit + next_prompts)
}
```

**Parallel outputs:**
- `report.json` — canonical.
- `report.sarif` — SARIF 2.1.0 for GitHub code-scanning (P1).
- `report.md` — human summary for PR comment body (P1).

---

## 13. LLM plan (blueprint §10 + roadmap P0 reality)

- **Default local (R&D):** Qwen3.6-35B-A3B Q4_K_M via `llama.cpp` on RTX 3500 Ada Laptop. MoE 35B total, 3B active → ~20-30 tok/s with partial offload (ADR-04).
- **Fallback (cheap classification):** smaller open-weight model (TBD; e.g. Qwen3.6-7B-Instruct Q5).
- **Reality check (roadmap P0):** the dev laptop is a **prototyping station, not a production backend**. A real SaaS path needs managed inference (Anthropic / cloud GPU). ADR-04 stands for development; production-inference ADR deferred until Phase 4 post-wedge validation.
- **Storage prerequisite (`docs/legacy/infos.md` §3):** M.2 2 TB upgrade on C: gates any local LLM work. Phase 4 is blocked on this.

---

## 14. Phased roadmap (merged)

Eight phases. Phase 0 is complete. Phase 1 begins on "go phase 1" from user.

| # | Name | Dur. | Status | Entry gate | Primary deliverables | Exit criterion |
|---|---|---|---|---|---|---|
| **0** | Cadrage + bootstrap | 1w | **DONE** · commits `15138f3..1733f98` | — | pyproject, v1 models, CLI `inspect`, vendored scorer, `memory-bank/*`, `reports/legacy/PHASE1_REPORT.md`, `PLAN.md` | `oida-code inspect` on own repo; ruff + mypy-strict + pytest 10/10 + cov 74%. |
| **1** | Deterministic audit | 2-3w | NEXT | P0 shipped | `verify/{lint,typing,semgrep_scan,codeql_scan,pytest_runner}`; `report/{json_report,markdown_report,sarif_export}`; `extract/blast_radius`; `score/verdict` (determinist path); `cli.py` wires `normalize`+`verify`+`audit` (--intent flag, --format json/sarif/md); `ingest/manifest.detect_commands` | **Stable report on 10 Python repos without human intervention.** JSON + SARIF + Markdown outputs validate against schemas. |
| **2** | Observation model + obligation graph (scaffold) | 2w | | P1 ships | `models/{trace,obligation,progress_event}.py` with **3 obligation kinds implemented** (migration / precondition / api_contract) + 3 stubbed (invariant / security_rule / observability); `extract/{claims,preconditions,dependencies,obligation_graph}.py`; `score/mapper.py` with explicit default-origin table; `verify/hypothesis_runner` + `verify/mutmut_runner` (shell-out + parse only — **no test generation**); **5-10 synthetic traces** in `datasets/traces_v1/` as shape smoke-tests (independently-labeled PR dataset + recall metric move to Phase 3); `cli verify/audit` accept both `AuditRequest` and `NormalizedScenario`; P1 pytest/mypy subprocess Python-resolution carry-over fixed. | **Schema v2 stable + NormalizedScenario round-trips through OIDAAnalyzer + obligation extractor runs without crash on attrs/self/synthetic + extracted obligation list is non-empty with unique IDs + 10-repo smoke (crash/no-crash table).** Classification (explore/exploit) and recall gate move to Phase 3. |
| **3** | Explore/Exploit adapter (re-scoped per ADR-17) | 1-2w | | P2 ships | `score/trajectory.py` implementing paper 2604.13151 §4 formulas (`St = ct + et + nt`, 4-case attribution, gain-based err); `models/trajectory.py` with `TrajectoryMetrics`; 5-8 synthetic traces under `tests/fixtures/traces/*.json`; `cli.py` gains `score-trace` subcommand | **Scorer separates 3 classifications on the synthetic set (precision ≥ 2/3):** exploration-dominated / exploitation-dominated / stale. Spearman ρ on a real-trace dataset is **Phase-4** work (blocked on Claude Code / Codex transcript ingest). |
| **4** | Agentic verifier (forward/backward) | 2w | | P3 ships + **M.2 2TB installed** | `llm/{client,schemas,forward_verifier,backward_verifier}.py`; `score/verdict.py` (aggregator extension); `cli.py --llm-endpoint --offline` | **Multi-turn verifier beats single-pass LLM judge** on the P2 annotated PR set (accuracy, calibration). |
| **5** | OIDA fusion + repair planner | 2w | | P4 ships | `score/{fusion,repair}.py`; `llm/repair_prompts.py`; `cli.py repair` wired | **Can explain every red/yellow verdict on a PR with evidence**, not vibes. Repair plan reopens the dominated set + audits the supportive set per paper §5. |
| **6** | Product surface | 2w | | P5 ships | `.github/workflows/oida-code.yml`; `github/checks.py` (GitHub App Check Runs); `github/annotations.py` (batched 50/req per API limits) | **A dev installs the tool in <15 min and sees a useful verdict inside a PR.** Demo on 10 intentionally sloppy PRs (blueprint §13 day 10 criterion) — false-positive / false-negative table recorded *before* any threshold tuning. |
| **7** | Research moat | months 4-6 | | P6 stabilized | LongCoT-Mini → full bench harness; Simula-driven synthetic dataset v1; Dafny proof modules for 2-3 critical invariants; multi-language start (TypeScript) | Measurable moat beyond "wrapper around linters": corrupt-success detection F1 on adversarial dataset + long-horizon critic robustness plot. |

**Critical-path rule:** phases are strictly sequential on the deterministic track (P0→P1→P2→P3). P4 may start in parallel with late-P2 work (LLM client setup) but its exit gate requires P2's annotated dataset. P6 can start late-P5 (Action scaffolding). P7 is off the critical path.

**Stop-and-ship rule:** a usable "phase 1 product" ships after P1. Each subsequent phase adds signal but the CLI remains demoable at every phase boundary.

---

## 15. Honesty rules (blueprint §12, verbatim)

1. Do not claim "mathematical proof" for arbitrary code.
2. Claim only one of the 4 verdict labels (§6).
3. Every verdict must carry its **evidence trail**: which tools ran, which tests passed/failed, which obligations were verified, which λ_bias pattern triggered the corrupt_success flag.
4. When the LLM verifier is active (P4+), its output is weighed *alongside* deterministic evidence, never *above* it. If forward-verifier says "verified" but a mutation test kills a critical mutant, verdict is `counterexample_found`.

---

## 16. Wedge (blueprint §13, anchored)

> **High apparent success, low grounding, hidden operational debt.**

This is what OIDA already measures. The merged roadmap does not dilute the wedge; it sharpens the evidence pipeline that feeds it:

- **Pass 1a** exposes missing preconditions → drives `grounding` down.
- **Pass 1b** makes obligations first-class → removes "I forgot to check X" excuses.
- **Pass 2a** produces executable counter-evidence → distinguishes `verified` from `insufficient_evidence`.
- **Pass 2b** detects agent loops → flags patterns of `λ_bias` buildup.
- **Pass 3** narrates *why* a verdict is red, using evidence the determinist layer already surfaced.
- **Fusion** combines all of the above into `V_net` and the 4-label verdict.

The narrative a user hears on a red PR:

> "This PR claims X. Tests pass, lint is clean. But obligation `admin_signup.email_normalized` is unverified (call graph shows 1 bypass), mutation testing killed 2 critical mutants in `validators.py`, and the agent's trajectory spent 14 of 27 actions re-reading the same three files without reducing the open-obligation set. `Q_obs = 0.88`, `grounding = 0.42`, `V_net = −0.19`, `debt_final = 0.71`. Verdict: **corrupt_success**. Repair: reopen e2 (validator contract), audit e1 (signup API), e4 (admin path). Targeted prompt ready."

That is the demo Phase 6 owes.

---

## 17. Change log

- **2026-04-24** — v1.0. Initial merge of `oida-code-mvp-blueprint.md` and `roadmap.md`. Blueprint §11 superseded. Verdict labels finalized as snake_case. 8-phase plan adopted. Phase 0 marked DONE (commits `15138f3..1733f98`).
- **2026-04-24** — v1.1. Phase 1 shipped (commits `c155a3c..4c197fb`); phase numbering in file tree updated with ship markers.
- **2026-04-24** — v1.2. Phase 2 exit criterion **downgraded** from "action-by-action classification + 60% recall" to "schema stable + round-trip through OIDAAnalyzer + non-empty obligations + unique IDs + 10-repo smoke". Classification (explore/exploit) and recall gate explicitly moved to Phase 3 per advisor note: "synthetic ground truth makes recall 100% by construction; the metric is meaningful only on independently-labeled PRs." Obligation kinds scope: **3 implemented** (migration/precondition/api_contract) + 3 stubbed. This is ADR-15.

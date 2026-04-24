# Active Context

## Current Goals

- Wrap phase 1 with `PHASE1_REPORT.md` and stop for user review.
- Wait for explicit "go phase 2" before starting Semgrep / Hypothesis / LLM work.

## Current Blockers

- None on phase 1. User review of `PHASE1_REPORT.md` is the gate to phase 2.

## Recent Progress

### [2026-04-24 07:04:50] - Phase 1 Steps 0-4 complete

- Step 0 (context ingestion) — digest in earlier entry below; 10 files fully read.
- Step 1 (repo creation) — `github.com/yannabadie/oida-code` live, public, MIT, 2 snapshot + license commits pushed.
- Step 2 (skeleton) — blueprint §7 tree scaffolded. 47 Python files + 3 example JSONs + VENDORED_FROM.txt committed under `feat: phase 1 skeleton`.
- Step 3 (gates) — ruff ✓, mypy --strict ✓ (41 files), pytest 10/10 ✓, `oida-code inspect ./search/OIDA/oida_framework --base HEAD` emits valid AuditRequest JSON. Coverage 74% (>70%).
- Step 4 (memory bank) — `projectBrief.md`, `productContext.md`, `systemPatterns.md`, `decisionLog.md` (9 ADRs), `progress.md` all populated from real content. Templates overwritten.

### Commits on main

```
<pending>  docs: phase 1 memory bank + PHASE1_REPORT
<pending>  test: phase 1 smoke tests (roundtrip, CLI, vendored analyzer)
<pending>  feat: phase 1 skeleton — CLI inspect, Pydantic I/O models, vendored OIDA scorer
44db7df  docs: add MIT LICENSE
15138f3  chore: initial brainstorm and research snapshot
```

### Quality gate evidence (summary; full output in `PHASE1_REPORT.md`)

- `ruff check src/ tests/` → `All checks passed!`
- `mypy src/oida_code` → `Success: no issues found in 41 source files`
- `pytest -q --cov=oida_code` → 10 passed, coverage 74%
- `oida-code inspect ./search/OIDA/oida_framework --base HEAD` → valid AuditRequest JSON, deserializes cleanly

## Open Questions (for user review at phase-1 close)

**Blocking:**
- None. The 3 blocking questions from the Step-0 digest (vendoring strategy, gate-4 target, CLI framework) were resolved by the user's "comme tu veux" (I applied my defaults). They are now ADRs 02, 08, 06 in `decisionLog.md`.

**Nice-to-have (deferrable to phase 2):**
- Should `oida-code` be listed on PyPI before phase 2 ends? (Blueprint doesn't specify; currently only GitHub-installable.)
- `.gitattributes` for stable LF line endings across Windows / Unix — the phase-1 commits show CRLF warnings that Windows autocrlf handles but could cause SHA drift if others clone on Linux. Low priority.
- Should `oida-code inspect` respect `.gitignore` when listing changed files? Currently passes through whatever `git diff --name-only` returns, which already honors `.gitignore`. Noted for phase 2 hunk-level extraction.

## Reminders for phase 2

- Blueprint §13 days 3-4 = Semgrep + pytest + Hypothesis wedge. Day 10 = 10-sloppy-PR evaluation BEFORE tuning thresholds.
- Blueprint §12 honesty rules are non-negotiable; any LLM-generated verdict MUST be backed by execution evidence, static signal, or "insufficient evidence".
- The M.2 2 TB storage upgrade on the dev laptop (per `infos.md` §3) is a prerequisite for local LLM work (phase 3).
- Paper §10 non-claims: OIDA is NOT a substitute for runtime enforcement / IAM / backups / approval gates. Documentation must say this explicitly.

---

## [2026-04-23 20:01:23] - Phase 1 bootstrap — context digest

Status: **Step 0 complete**. No code written. No files modified outside memory-bank.
Read order followed: blueprint → brainstorm2_improved → last → infos → brainstorm2 → example JSONs → vendored OIDA core → OID research package → OID paper PDF → chatmodes. All 10 mandatory sources ingested in full (not skimmed).

### Product wedge (one sentence)

> Measure the gap between what AI-written code **appears** to do (high `Q_obs`) and what it **actually guarantees** (grounding, reversibility, observability, verified preconditions), exposing *corrupt success* — `Q_obs` high with `V_net < 0` — and emitting localized proofs, executable counterexamples, or honest "insufficient evidence" verdicts.

Positioning is **"OIDA Code Audit / AI code verifier"**, explicitly NOT "unslop" (blueprint §1).

### The three research sources and their exact role in the MVP

| Source | Paper / Repo | Role in MVP |
|---|---|---|
| **Explore/Exploit Errors** (Park et al., arXiv 2604.13151, MIT repo `jjj-madison/measurable-explore-exploit`) | Priority **A** — policy-agnostic metric decomposing agent failures into *exploration* vs *exploitation* errors via no-progress-segment detection on a task DAG. | Phase 2+ behavioral layer: feeds `traj_error` into OIDA scoring by mapping grid→filesystem and task DAG→AST/call graph. **Not implemented in phase 1.** |
| **AgentV-RL** (Zhang et al., arXiv 2604.16004, github.com/JiazhengZhang/AgentV-RL) | Priority **B** — forward/backward verifier architecture with tool-augmented reasoning, achieves 4B verifier > 70B ORM on MATH500. | Phase 3 (blueprint day 9) "Agentic verification" pass — forward verifier (premises→sufficient?), backward verifier (outcome→missing premises?), repair planner. **Not implemented in phase 1.** |
| **LongCoT** (Motwani et al., arXiv 2604.14140, `longcot.ai`, HF `LongHorizonReasoning/longcot`) | Priority **C** — 2 500-problem benchmark; frontier models score <10 %. | External long-horizon robustness benchmark for the critic. **Evaluation-only**, post-MVP. |

### The 4 verdict buckets (blueprint §3, §12)

1. **proved enough for merge** — formal proof of an explicit property OR regression+property+mutation evidence with grounding above threshold.
2. **counterexample found** — execution (pytest / Hypothesis / mutmut) produced a failing case.
3. **insufficient evidence** — cannot confirm nor refute within policy budget.
4. **high apparent quality / negative net value** — *corrupt success*: `Q_obs ≥ 0.80` while `V_net = V_dur − H_sys < 0`. This is the wedge.

### Honesty rules (blueprint §12)

The product **MUST** only claim one of the four labels above. It **MUST NOT** claim "mathematical proof" for arbitrary code semantics — Rice's theorem forbids it in general.

### OIDA v4.2 formulas (authoritative, from PDF §4 + vendored `analyzer.py`)

- `grounding_t = Σ_k w_k · 1[verified_k] / Σ_k w_k`
- `Q_obs = 0.40·completion + 0.40·tests_pass + 0.20·operator_accept`
- `μ = sqrt(reversibility · observability)`
- `λ_{H→B} = α_B · cap · (1−μ) · (1−g) · ρ(reuse) · Q_obs` (bounded to 1.5)
- `N_stock = #{C+} + Σ_{H} v_i`
- `B_load = Σ_{B} damage_i`
- `N_eff = N_stock − B_load`
- `Debt = max(0, −N_eff)`
- `V_dur = benefit · g · (1 + μ·cap) · (1 − Debt̃_{t−1})`
- `H_sys = ψ · (1−μ) · cap · B̃ · Q_obs`
- `V_net = V_dur − H_sys`
- Pattern state `{H, C+, E, B}` + double-loop dominance-based repair.

Default config from vendored `AnalyzerConfig`: `α_b=1.15, confirm_threshold=0.80, bias_threshold=0.45, τ_ref=3.0, weights=(0.40, 0.40, 0.20), corrupt_success_q_threshold=0.80`.

### Contradictions found and their resolution

Per authority order `blueprint > brainstorm2_improved > last > infos > brainstorm2`:

1. **Name.** brainstorm2 proposes `unslop.ai`; infos.md kills it; blueprint sets `oida-code`. → ADR-01.
2. **Product claim.** brainstorm2 promises "preuves mathématiques"; infos.md / blueprint §12 reject. → 4-bucket honesty rule.
3. **Framing.** brainstorm2 "anti-slop"; blueprint "OIDA Code Audit". → blueprint wins.
4. **Phase plan.** brainstorm2_improved has 6 phases; blueprint has 10 days. → blueprint day-by-day wins.
5. **Scorer formula.** brainstorm2_improved proposes additive Q_obs-μ-λ-traj_error; paper + vendored use V_dur-H_sys. → vendored authoritative.
6. **Pydantic vs dataclass.** Vendored uses dataclass; blueprint §5 shows Pydantic-shaped JSON. → Pydantic boundary + vendored dataclass core. → ADR-07.
7. **Public API surface.** Blueprint §7 single `score/analyzer.py` vs vendored package of 4 files. → `_vendor/oida_framework/*` + re-export shim. → ADR-02.
8. **CLI framework.** Plan says "Typer or Click"; vendored uses argparse. → Typer for new CLI. → ADR-06.
9. **Dates.** brainstorm2 23 April 2026, formalism 5 April 2026, paper 5 April 2026 — no contradiction, consistent with "today = 2026-04-24".

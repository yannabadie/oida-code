# Active Context

## Current Goals

- Phase 1 bootstrap of `oida-code` (per `prompt.md` + `oida-code-mvp-blueprint.md`).
- Waiting for user review of the context digest below before touching any code.

## Current Blockers

- User review of this digest required before Step 1 (git init + repo creation).
- Three blocking questions listed at the bottom of this file.

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
| **LongCoT** (Motwani et al., arXiv 2604.14140, `longcot.ai`, HF `LongHorizonReasoning/longcot`) | Priority **C** — 2 500-problem benchmark; frontier models score <10 %. | External long-horizon robustness benchmark for the critic. **Evaluation-only**, post-MVP. Not a training dataset, not a dependency. |

### The 4 verdict buckets (blueprint §3, §12)

1. **proved enough for merge** — formal proof of an explicit property OR regression+property+mutation evidence with grounding above threshold.
2. **counterexample found** — execution (pytest / Hypothesis / mutmut) produced a failing case.
3. **insufficient evidence** — cannot confirm nor refute within policy budget.
4. **high apparent quality / negative net value** — *corrupt success*: `Q_obs ≥ 0.80` while `V_net = V_dur − H_sys < 0`. This is the wedge.

### Honesty rules (blueprint §12)

The product **MUST** only claim one of the four labels above. It **MUST NOT** claim "mathematical proof" for arbitrary code semantics — Rice's theorem forbids it in general. Defensible claims are limited to:
- formal proof for an **explicit property** (e.g., type soundness, a specific invariant);
- counterexample found by execution;
- static evidence of rule violation (lint, Semgrep, CodeQL);
- insufficient evidence.

This rule is non-negotiable and overrides every looser phrasing in `brainstorm2.md` ("preuves mathématiques des failles").

### OIDA v4.2 formulas (authoritative, from PDF §4 + vendored `analyzer.py`)

These are the formulas phase 1 reuses verbatim (no reimplementation):

- `grounding_t = Σ_k w_k · 1[verified_k] / Σ_k w_k` (over critical preconditions)
- `Q_obs = 0.40·completion + 0.40·tests_pass + 0.20·operator_accept`
- `μ = sqrt(reversibility · observability)`
- `λ_{H→B} = α_B · cap · (1−μ) · (1−g) · ρ(reuse) · Q_obs`  (bounded to 1.5)
- `N_stock = #{C+} + Σ_{H} v_i`
- `B_load = Σ_{B} damage_i`
- `N_eff = N_stock − B_load`
- `Debt = max(0, −N_eff)`
- `V_dur = benefit · g · (1 + μ·cap) · (1 − Debt̃_{t−1})`
- `H_sys = ψ · (1−μ) · cap · B̃ · Q_obs`
- `V_net = V_dur − H_sys`
- Pattern state transitions `{H, C+, E, B}` and double-loop dominance-based repair — implemented in `oida_framework.analyzer.OIDAAnalyzer.double_loop_repair`.

Default config from vendored `AnalyzerConfig`: `α_b=1.15, confirm_threshold=0.80, bias_threshold=0.45, τ_ref=3.0, weights=(0.40, 0.40, 0.20), corrupt_success_q_threshold=0.80`.

### Contradictions found between documents and their resolution

Per authority order `blueprint > brainstorm2_improved > last > infos > brainstorm2`:

1. **Name.** `brainstorm2.md` proposes `unslop.ai`. `infos.md` §1 kills it (collisions: `github.com/mshumer/unslop`, `unslop.xyz`, `unslop.design`, skills on Smithery, etc.). Blueprint §1 sets name to `oida-code`. **Resolution:** use `oida-code`. This is ADR-01.
2. **Product claim.** `brainstorm2.md` promises "preuves mathématiques des failles du code". `infos.md` §4 rejects it (Rice). Blueprint §12 + `last.md` limit claims to the four verdict buckets. **Resolution:** honesty rules override — the product emits *labels*, never unqualified "proof". ADR-honesty-01.
3. **Framing.** `brainstorm2.md` = "anti-slop". Blueprint §1 = "AI code verifier". `infos.md` §5 = "OIDA-for-code". **Resolution:** align on blueprint's "OIDA Code Audit" positioning; "anti-slop" framing is explicitly forbidden.
4. **Phase plan.** `brainstorm2_improved.md` proposes 6 phases (Phase 0 instrumentation → Phase 5 repair). Blueprint §13 lays out 10 concrete days (day 1–2 naming + models, …, day 10 demo). **Resolution:** blueprint day-by-day wins; `brainstorm2_improved`'s phase structure is kept as a conceptual index, not a schedule.
5. **Scorer formula.** `brainstorm2_improved.md` suggests `V_net = Q_obs − mu − lambda_bias − traj_error + proof_gain` mixing OIDA + Explore/Exploit. Blueprint + PDF + vendored analyzer use `V_net = V_dur − H_sys`. **Resolution:** authoritative formula is `V_dur − H_sys`; the brainstorm2_improved composite is a **phase-2+ proposal** for incorporating Explore/Exploit as an additive trajectory term (tracked as an open question, NOT implemented).
6. **Pydantic vs dataclass.** Vendored `oida_framework` uses `@dataclass(slots=True)`. Blueprint §5 shows Pydantic-shaped JSON for the external `AuditRequest` / `NormalizedScenario` / `AuditReport`. **Resolution:** Pydantic v2 at the public boundary (the three new model files), dataclasses untouched inside the vendored `oida_framework`. A thin mapper will translate between them in `score/mapper.py` (phase 2). Phase 1 only creates the Pydantic models + a thin re-export shim.
7. **Public API surface.** Blueprint §7 places `score/analyzer.py` as a single file; the vendored package has `analyzer.py + models.py + io.py + cli.py`. **Resolution:** vendor the *package* (`oida_framework/oida/*`) under `src/oida_code/_vendor/oida_framework/` and make `src/oida_code/score/analyzer.py` a re-export shim, so we never touch the vendored code. See open question Q1 below — user confirmation requested.
8. **Entry-point framework.** Plan Step 2 says "Typer or Click". Vendored CLI uses `argparse`. **Resolution:** new top-level `oida-code` CLI uses **Typer** (richer help, cleaner subcommand ergonomics for `inspect/normalize/verify/audit/repair`); vendored `oida` CLI is not re-exposed. See Q3 below.
9. **Timestamp.** Brainstorm2 is dated "23 avril 2026" (matches today). OID formalism markdown dated "5 avril 2026". OID paper PDF dated "5 April 2026". No contradiction — this is the expected timeline.

### Hardware + environment constraints (from `infos.md`)

- RTX 3500 Ada Laptop = **12 GB VRAM**, not 16 GB. Full-GPU inference of Qwen3.6-35B-A3B Q4_K_M (~20 GB) is **not** possible; `llama.cpp` partial offload with MoE's 3B active params buys ~20–30 tok/s.
- C: drive has 80 GB free ("critique"). User was recommended to add an M.2 2 TB. Phase-1 footprint (Python skeleton) is negligible (<50 MB), but any LLM work (phase 3+) will need the extra disk.
- User's env: `.env` already contains OpenAI/Anthropic keys — use only in phase 3 LLM verifier, never log.

### Vendored code inventory

`search/OIDA/oida_framework/` — 5 Python modules, ~400 LOC total:
- `oida/models.py` — `Precondition`, `Event`, `Scenario` dataclasses (from-dict validators with [0,1] bounds)
- `oida/analyzer.py` — `OIDAAnalyzer`, `PatternLedger`, `AnalyzerConfig` (all formulas above)
- `oida/io.py` — `load_scenario`, `save_report`
- `oida/cli.py` — argparse CLI: `oida analyze` / `oida repair`
- `oida/__init__.py` — exports `OIDAAnalyzer`, `load_scenario`, `save_report`
- examples: `safe_online_migration.json`, `destructive_db_recreate.json`, `repeated_low_grounding_cost_optimization.json`
- dependency: `networkx>=3.1` only

`search/OID/oid-framework-v0.1.0/oid_framework/` — research/simulation package:
- `core.py` — `PatternState`, `ActionPattern`, `TaskDescriptor`, `OperationalEpisode`, `AgentProfile`
- `dynamics.py` — `DependencyDAG`, `IntegrityDynamics` (H→B risk, single/double-loop correction, grounding sigmoid)
- `scorer.py` — `IntegrityScorer`, `IntegrityScore` (Q_obs, V_IA, H_sys, V_net with profile classifier)
- `simulation.py`, `viz.py`, `examples/` — not required for the MVP scorer
- **Note:** This package's formulas for `Q_obs` and `V_IA` differ from the vendored `oida_framework` (continuous sigmoid grounding vs. weighted-precondition ratio). Blueprint §2 says `oid-framework` stays the "research/simulation package"; `oida_framework_package` is the "deterministic scoring engine". Phase 1 vendors **only the latter**. `oid_framework` is *not* imported or copied into `oida-code`.

### Memory-bank state (pre-phase-1)

All six files in `memory-bank/` currently contain the MemoriPilot templates only — zero real content. The chatmode protocol (`.github/*.chatmode.md`) requires:
- Every architect/code/debug response to begin with `[MEMORY BANK: ACTIVE|INACTIVE]` (VS Code context; ignored in this CLI session but preserved in written files).
- Entries formatted as `[YYYY-MM-DD HH:MM:SS] - [Summary]` (this file already complies).
- `decisionLog.md`, `progress.md`, `activeContext.md` = append-only.
- Step 4 of phase 1 will populate all six files with real content.

### Blocking open questions (user review required)

**Q1 — Vendoring strategy.**
Plan Step 2 says `src/oida_code/score/analyzer.py` is a "thin wrapper importing and re-exporting from the existing `search/OIDA/oida_framework/oida/analyzer.py`" — but `search/` is outside the Python package path and won't survive when phase-2 consumers pip-install `oida-code`. Three options:
- **(a)** Copy `search/OIDA/oida_framework/oida/*.py` (5 files, ~400 LOC) into `src/oida_code/_vendor/oida_framework/` as a frozen vendored snapshot with `VENDORED_FROM.txt` noting the source path + SHA. `score/analyzer.py` = `from oida_code._vendor.oida_framework.analyzer import OIDAAnalyzer as _OIDAAnalyzer`. **← my default.**
- **(b)** Keep source under `search/` and add it as an editable path-dep in `pyproject.toml`. Fragile outside dev env; rejected.
- **(c)** Copy just `analyzer.py + models.py + io.py` flat into `src/oida_code/score/`. Loses the namespace boundary and makes future upstream sync painful.

**Please confirm (a) or propose another.**

**Q2 — Gate-4 smoke target.**
Step 3 gate 4 requires `oida-code inspect ./search/OIDA/oida_framework --base HEAD` to produce a valid `AuditRequest` JSON. After `git init`, the whole workspace becomes a single commit and `--base HEAD` yields an empty diff. Options:
- **(a)** Accept an empty `changed_files: []` list as a valid `AuditRequest` (it is — the Pydantic model doesn't require non-empty). **← default.**
- **(b)** Inspect against `HEAD~1` on a synthetic two-commit setup (more realistic but more work).
- **(c)** Point `inspect` at a different directory/base combo that yields a non-trivial diff.

**Please confirm (a) or specify the target.**

**Q3 — CLI framework.**
Typer (default, adds one dep) or Click (adds one dep) or argparse (zero dep, matches vendored core)? **Default: Typer.**

### Nice-to-have questions

**Q4 —** `git commit -s` (DCO sign-off) required, or plain `git commit`? Plan Step "done" says "all commits signed-off". Default: `-s`.
**Q5 —** Do PHASE1_REPORT.md and future external reports carry the `[MEMORY BANK: ACTIVE]` prefix? That tag is a VS Code chatmode convention; outside VS Code it adds noise. Default: omit in external reports, keep in memory-bank files only.
**Q6 —** `pyproject.toml` Python requirement: the vendored `oida_framework` says `>=3.10`; plan says "Python 3.11+". Default: pin `>=3.11` in `oida-code` and leave the vendored subpackage's `>=3.10` comment intact — no runtime conflict.
**Q7 —** Qwen3.6-35B-A3B as default local verifier is ADR-worthy but phase 1 ships zero LLM code. Log it as ADR-04 in `decisionLog.md` with zero implementation side-effect? Default: yes.

---

### Stop-and-wait checkpoint

Per `prompt.md`: *"Do not write a single line of code before you have produced the context digest in `memory-bank/activeContext.md` and I can review it. Ping me in chat when the digest is ready."*

**Digest ready. Awaiting review. Next action on confirmation: Step 1 (git init + .gitignore + initial commit), then ping again before `gh repo create`.**

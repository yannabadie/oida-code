# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|

[2026-04-24 07:04:50] - **ADR-01: Repo and package name `oida-code`, NOT `unslop.ai`.**
**Why:** `infos.md` §1 documented active collisions for `unslop` (github.com/mshumer/unslop, unslop.xyz, unslop.design, unslopsearch.com, theunslop.app, Unslop Code Cleaner on MCP Market, anti-slop skill on Smithery). The brand is saturated and the "anti-slop" framing conflicts with the OIDA-for-code positioning (blueprint §1). User confirmed public repo creation as `yannabadie/oida-code` on 2026-04-23.
**Applies to:** package name (`oida-code` on PyPI, `oida_code` in Python), CLI binary (`oida-code`), GitHub repo, documentation.

[2026-04-24 07:04:50] - **ADR-02: Reuse the existing OIDA core verbatim via vendoring.**
**Why:** Blueprint §2 is explicit: "Keep the current OIDA core almost intact". The vendored package (`search/OIDA/oida_framework/oida/*.py`) already implements `grounding`, `Q_obs`, `μ`, `λ_bias`, `N_eff`, `Debt`, `V_dur`, `H_sys`, `V_net`, pattern state machine, and `double_loop_repair`. Reimplementing would risk formula drift and violate the plan rule "Reuse over rewrite" (prompt.md operating rules).
**How applied:** Files copied verbatim to `src/oida_code/_vendor/oida_framework/`. SHA256 of each file pinned in `VENDORED_FROM.txt`. `ruff` and `mypy --strict` exclude `_vendor/**` via `pyproject.toml`. `score/analyzer.py` is a thin re-export shim.

[2026-04-24 07:04:50] - **ADR-03: Python-only for v0.**
**Why:** Blueprint §4. The user's existing codebase is Python; Hypothesis + mutmut give a strong verification wedge quickly; Semgrep and CodeQL both support Python as a first-class language. Adding JS/TS/Go/Rust before the wedge is proven would dilute focus.
**How applied:** `pyproject.toml requires-python = ">=3.11"`; `ingest/manifest.default_python_commands` is the only language-aware helper shipped; `inspect` hard-codes `language = "python"` in the emitted `AuditRequest`.

[2026-04-24 07:04:50] - **ADR-04: Qwen3.6-35B-A3B as default local verifier.**
**Why:** Blueprint §10. Open-weight (Apache 2.0), official `transformers serve` + `llama.cpp` GGUF support, designed for agentic coding / repo-level reasoning. On the user's RTX 3500 Ada Laptop (12 GB VRAM), the MoE architecture (35B total, 3B active per token) makes Q4_K_M (~20 GB) tractable via partial offload at 20-30 tok/s. A smaller fallback model will handle extraction / cheap classification.
**Status:** Decision recorded; zero implementation in phase 1 (no LLM code shipped). Implementation begins phase 3 (blueprint §13 day 9).

[2026-04-24 07:04:50] - **ADR-05: CLI-first, GitHub Action second, SaaS last.**
**Why:** Blueprint §4 deployment modes ordered: (1) `oida-code audit ./repo`, (2) GitHub Action (local / self-hosted), (3) GitHub App + SaaS. A CLI is trivially testable locally, has no hosting dependencies, and is what power users want first. GitHub Action adds CI integration without servers. SaaS adds auth / billing / multi-tenancy — all orthogonal to the core wedge.
**How applied:** Phase 1 ships only the CLI entry point (`oida-code = oida_code.cli:app`). `src/oida_code/github/checks.py` and `annotations.py` exist as stubs but raise `NotImplementedError`.

[2026-04-24 07:04:50] - **ADR-06: Typer over Click or argparse for the new CLI.**
**Why:** Typer's `Annotated[T, typer.Option(...)]` style is mypy-strict-clean, produces rich Rich-rendered help, and has first-class subcommand ergonomics for the planned `inspect / normalize / verify / audit / repair` surface. argparse would work but loses type-safety on options; Click would require more boilerplate. Vendored `oida` CLI keeps argparse (untouched per ADR-02).
**Cost:** +1 dep (`typer>=0.12`) and its `rich` transitive.

[2026-04-24 07:04:50] - **ADR-07: Pydantic v2 at the public boundary; dataclasses in the vendored core.**
**Why:** Blueprint §5 shows JSON-first schemas with strict validation semantics. Pydantic v2 gives `ConfigDict(extra="forbid")` for airtight APIs, deterministic `model_dump_json(indent=2)`, and is the community default for Python typed I/O. The vendored core uses `@dataclass(slots=True)` and must not be touched (ADR-02). A mapper bridges the two surfaces — phase 2.

[2026-04-24 07:04:50] - **ADR-08: `--base HEAD` accepted as a valid (empty-diff) inspect target.**
**Why:** Gate 4 of prompt.md Step 3 requires `oida-code inspect ./search/OIDA/oida_framework --base HEAD` to produce a valid `AuditRequest` JSON. After `git init`, the whole workspace is a single commit; `HEAD..HEAD` is an empty diff. Rather than staging a synthetic two-commit setup, the implementation treats `base == head` as "empty changed_files list" — still a deserializable `AuditRequest`. Real usage is always `--base origin/main` or similar.

[2026-04-24 07:04:50] - **ADR-09: Typer callback uses `invoke_without_command=True`.**
**Why:** Required so that `oida-code --version` exits 0 without Typer complaining "Missing command." Without this flag, the subcommand-required check runs before the version callback's `typer.Exit(code=0)`.
**Discovered:** empirically, fixing `tests/test_cli_smoke.py::test_version_flag`.

[2026-04-24 07:45:00] - **ADR-10: `PLAN.md` is the active plan; blueprint §11 is superseded; `roadmap.md` is subsumed.**
**Why:** The user authored `roadmap.md` post-Step-0 with an 8-phase realistic schedule (12-14 weeks) that refines the blueprint's aspirational 10-day plan (§11). The two documents are compatible: blueprint is the architectural spec + formulas (§1-10, §12-13), roadmap is the phasing + observation model + Explore/Exploit integration. A merged single source of truth prevents drift.
**How applied:** Created `PLAN.md` merging both. New authority order: `PLAN.md > blueprint §1-10 §12-13 > roadmap > brainstorm2_improved > last > infos > brainstorm2`. Blueprint §11 "First 10 implementation days" explicitly superseded by `PLAN.md` §14. What was called "phase 1 bootstrap" in `PHASE1_REPORT.md` maps to `PLAN.md` Phase 0 (complete). Verdict labels finalized as machine identifiers: `verified / counterexample_found / insufficient_evidence / corrupt_success`.

[2026-04-24 07:45:00] - **ADR-11: Observation model + obligation graph become first-class schema surface (Phase 2).**
**Why:** Roadmap P2 (the "keystone" phase per the document) posits that Explore/Exploit cannot map cleanly to code without an explicit `Obligation` / `ProgressEvent` / `NoProgressSegment` triple. Without these, the bridge from grid→codebase is "an intuition, not a validated component" (roadmap ¶ on the hard point). The observation model is therefore promoted from "phase 2 extract/* stubs" to a dedicated `models/trace.py` + `models/obligation.py` + `models/progress_event.py` triple shipping in Phase 2.
**How applied:** `PLAN.md` §8 defines the three types formally; `PLAN.md` §9 tracks them as schema v2; `extract/obligation_graph.py` becomes a new first-class module. Phase 2 exit gate requires a 50-100 hand-annotated trace dataset.

[2026-04-24 16:30:00] - **ADR-15: Phase 2 exit criterion downgraded; classification + recall gate moved to Phase 3.**
**Why:** Per advisor pre-start review, the original Phase 2 exit criterion ("describe action-by-action where an agent explores / exploits / stagnates / loops") is Explore/Exploit classification logic — which PLAN.md §14 explicitly assigns to Phase 3. Additionally, the "60% obligation-extraction recall on hand-annotated set" metric is meaningful only on independently-labeled PRs; a 5-10-scenario synthetic dataset hits 100% recall by construction because ground truth IS what I wrote. So the synthetic dataset serves as a shape smoke-test, not as a recall gate.
**How applied:** `PLAN.md` §14 P2 row updated. New P2 exit criterion: schema v2 stable + `NormalizedScenario` round-trips through `OIDAAnalyzer` + obligation extractor runs without crash + non-empty obligations with unique IDs + 10-repo smoke (crash/no-crash table). Also capped obligation kinds at **3 implemented** (migration / precondition / api_contract) + 3 stubbed (invariant / security_rule / observability). Real classification + recall = Phase 3.

[2026-04-24 14:30:00] - **ADR-13: ``ReportSummary`` fusion fields are ``Optional[float]`` in v1.1; Phase 1 emits ``null``.**
**Why:** Advisor review flagged three options for fields that require the OIDA fusion (``mean_q_obs``, ``mean_grounding``, ``total_v_net``, ``debt_final``, ``corrupt_success_ratio``): (a) ``Optional[float] = None``, (b) a separate ``evidence_only_summary`` block, (c) emit ``0.0`` with a footnote. Option (c) is the trap — a reader who skims debt=0.0 concludes "no debt", which is a silent lie. Option (b) doubles the schema surface. Option (a) is the honest choice: the field is populated in Phase 5 when fusion lands; until then it is ``null``. Markdown render treats ``null`` as "not computed in Phase 1" so the human reader sees the gap.
**How applied:** `src/oida_code/models/audit_report.py` has ``Optional[float]`` on all fusion metrics. `src/oida_code/report/markdown_report.py` renders ``null`` as "_not computed in Phase 1_". Phase-1 deterministic verdict resolver never sets these fields.

[2026-04-24 14:30:00] - **ADR-14: ``verify`` CLI consumes ``AuditRequest`` (not ``NormalizedScenario``) in Phase 1; schema bridge deferred to Phase 2.**
**Why:** Blueprint §8 specifies ``oida-code verify .oida/scenario.json`` — the scenario is produced by ``normalize``, which is a Phase 2 concern (needs the obligation graph). Rather than stub verify until Phase 2, Phase 1 has verify accept ``AuditRequest`` directly because every Phase-1 deterministic verifier (ruff / mypy / pytest / semgrep / codeql) works on raw repo state, not on normalized events. When Phase 2 lands, verify will gain a content-type sniff to accept either shape.
**How applied:** `src/oida_code/cli.py verify_cmd` loads `AuditRequest`. The Phase 2 plan entry in `progress.md` explicitly lists "verify learns to accept NormalizedScenario too".

[2026-04-24 07:45:00] - **ADR-12: Hardware treated as prototyping station; production-inference ADR deferred.**
**Why:** Roadmap P0 explicitly flags: "R&D locale oui, vrai SaaS non" given RTX 3500 Ada Laptop (12 GB VRAM, 432 GB/s) vs Qwen3.6 model-card serving examples (tp-size 8). ADR-04 (default local Qwen3.6-35B-A3B) still holds for phase-4 development, but this ADR acknowledges that multi-tenant inference needs either managed API (Anthropic / OpenAI) or dedicated cloud GPU. Decision on that path is deferred to post-wedge validation (after Phase 5 shows real signal).
**How applied:** `PLAN.md` §13 spells out the development-vs-production split. `infos.md` §3 (M.2 2 TB upgrade) now explicitly gates Phase 4.

---
[2026-04-24 07:04:50] - Decision log initialized with the 5 ADRs required by prompt.md Step 4 (a–e) plus 4 further ADRs arising during phase-1 implementation (vendoring layout, Pydantic boundary, empty-diff gate, Typer callback flag).
[2026-04-24 07:45:00] - Decision log extended with ADR-10 (merged PLAN.md supersedes blueprint §11), ADR-11 (observation model first-class), ADR-12 (laptop = prototyping only).

[2026-04-24 18:30:00] - **ADR-16: Self-audit fork guard. Auditing `oida-code` with itself skips recursion-prone tests.**
**Why:** Running the Phase-2 pipeline on the oida-code tree triggers a subprocess explosion: `_run_deterministic_pipeline` spawns `pytest`, which collects `tests/test_cli_audit.py` + `tests/test_verify_runners.py` + `tests/test_subprocess_python_resolution.py` — all three invoke the CLI via `CliRunner`, which runs the pipeline, which spawns pytest... On Windows/Cygwin fork emulation this exhausts handles within seconds (two OOM-adjacent crashes observed during Phase 2). Detection signal: `pyproject.toml[project].name == "oida-code"`.
**How applied:** `src/oida_code/ingest/manifest.py` exposes `project_name()` and `is_self_audit()`. `src/oida_code/verify/pytest_runner.py` appends `--ignore=<path>` for each recursive test when `is_self_audit(root)` is True. 6 tests in `tests/test_self_audit_guard.py` lock both branches. With the guard in place, `enable_property` defaults to True; `enable_mutation` stays opt-in because `mutmut run` is minute-scale.

[2026-04-24 18:30:00] - **ADR-17: Phase 3 re-scoped around paper 2604.13151's exact formulas; dataset gate deferred to Phase 4.**
**Why:** The original PLAN.md §14 Phase 3 gate ("Spearman ρ > 0.5 on hand-labeled dataset") requires a human-labeled trace set that was never produced. With the paper parsed, the paper's formulas (stale score `St = ct + et + nt`, 4-case attribution table, gain-based err indicator) are implementable over the existing `TraceEvent` schema without a real-trace ingest. Therefore Phase 3 ships the scorer + 5-8 hand-crafted synthetic traces covering all three classifications; the ρ correlation with human labels moves to Phase 4 once Claude Code / Codex transcript parsing lands as part of the LLM-verifier path.
**How applied:** `PLAN.md` §14 row 3 rewritten. New Phase-3 deliverable: `score/trajectory.py` with `score_trajectory(trace, obligations) -> TrajectoryMetrics`, 5-8 synthetic traces under `tests/fixtures/traces/*.json`, unit tests proving the scorer separates `exploration_error`-dominated / `exploitation_error`-dominated / `stale`-dominated traces by label. Exit gate: classification precision ≥ 2/3 on synthetic set (conservative; the hand-crafted labels are the ground truth by construction).

[2026-04-24 18:30:00] - **Release `v0.3.0` — ADR-16 fork guard + Phase-2 runners default-on where safe.**

[2026-04-25 16:00:00] - **ADR-24: Estimator contracts before Phase-4 LLM verifier.**

**Why:** Phase 3.5 + E1 + E2 shipped a structurally validated shadow
fusion that is monotone, bounded, channel-clean, and non-authoritative.
But the real-repo smoke (E2 §9) showed every event lands at exactly
the same `0.475` pressure on production codebases — every load-bearing
input is a structural default. Before introducing any LLM verifier we
must define **what** an estimator is contractually allowed to claim,
**how** confidence relates to source, and **when** an estimate may
unblock official fusion. Without those guardrails, an LLM estimate
could quietly become authoritative just because nothing rejected it.

**Decision (E3 protocol):**

* E3.0 — wire deterministic evidence into per-event signals
  (`EventEvidenceView`, edge_confidences from `DependencyEdge`).
* E3.1 — frozen `SignalEstimate` + `EstimatorReport` schemas.
* E3.2 — deterministic baselines for `capability` / `benefit` /
  `observability` (default-blocking; require Phase 4 LLM for real
  signal) and per-event completion / tests_pass / operator_accept
  derived from `EventEvidenceView`.
* E3.3 — `LLMEstimatorInput` / `LLMEstimatorOutput` contracts
  (schemas only, no implementation).
* E3.4 — `assess_estimator_readiness` ladder (blocked /
  diagnostic_only / shadow_ready / official_ready_candidate). The
  `official_ready_candidate` status is reserved — production CLI
  must NOT emit official `V_net` even at this status until a
  follow-up ADR explicitly unlocks it (ADR-22 still holds).

**Accepted:**

* Deterministic evidence plumbing first; no LLM in this phase.
* Frozen `SignalEstimate` schema with model-level invariants.
* Confidence separated from value (a high value with confidence=0.0
  is information-poor, not a confident estimate).
* `source` distinguishes `default` / `missing` from
  `tool` / `static_analysis` / `test_result` / `hybrid` / `llm` /
  `heuristic`.
* LLM estimates are diagnostic unless corroborated:
  * `source="llm"` → `confidence ≤ 0.6`
  * `source="hybrid"` → `confidence ≤ 0.8`
  * `is_authoritative=True` only for tool-grounded narrow fields
* LLM output must cite `cited_evidence_refs`; uncited high-confidence
  claims fail validation.

**Rejected:**

* Filling `capability` / `benefit` / `observability` with raw LLM scores.
* Treating LLM self-reported confidence as evidence.
* Unlocking official `V_net` from shadow pressure or estimator output
  alone.
* Hiding missing fields behind neutral 0.5 defaults without flagging
  them as `is_default=True` + `confidence=0.0`.
* Modifying the vendored OIDA core (ADR-02 still holds).

**Wiring decisions (E3.0 §1):** chose **Option B** (already in ADR-23
§5) — `NormalizedEvent` schema unchanged; `edge_confidences` flows
through `compute_experimental_shadow_fusion`'s parameter, populated
from `DependencyEdge.confidence` via
`edge_confidences_from_dependency_graph`. CLI score-trace uses
`build_scoring_inputs` to produce the bundle in a single pass.

**Wiring decisions (E3.4):** `EstimatorReport` is now emitted
alongside `FusionReadinessReport` in the CLI score-trace JSON
payload (`payload["estimator_readiness"]`). It does NOT replace the
official readiness gate — the two coexist by design. The estimator
ladder describes what the estimator can claim; the official gate
describes what the user is allowed to publish.

**Outcome:** all 19 acceptance criteria from QA/A14.md met
structurally. `EventEvidenceView` differentiates per-event evidence;
`SignalEstimate` rejects sloppy authoritative claims; the LLM
contract caps confidence and requires citations. The deterministic
baseline keeps `capability` / `benefit` defaulting → official fusion
remains blocked at v0.4.x. Report:
`reports/e3_estimator_contracts.md`.

[2026-04-25 14:00:00] - **ADR-23: Shadow formula decision protocol (E2).**

**Why:** E1 (commit `92224c7`) shipped the shadow fusion as opt-in
experimental, and E1.1 (commit `84e50f8`) hardened the contract
(frozen models, missing-grounding semantics). A11.md §"Après E1"
reserved the keep/revise/reject decision for E2. The decision must
be **structural**, not predictive: does the formula remain stable,
monotone, explainable, and useful as a diagnostic, or does any of
those properties break under sensitivity sweeps and graph variants?

**Decision (E2 protocol):** evaluate the formula along three axes —
formula variants, sensitivity sweep, graph ablation — record the
result in `reports/e2_shadow_formula_decision.md`, and choose
keep / revise / reject. The shadow report's non-authoritative
status is non-negotiable regardless of outcome.

**Accepted activities:**

* Compare formula variants (V1 current E1.1, V2 dynamic-renormalized,
  V3 conservative-missing).
* Sensitivity sweep on grounding / completion / operator_accept /
  trajectory_pressure / edge_confidence.
* Graph ablation on local-only / constitutive-only / supportive-only /
  mixed / cycle / dense-supportive-star / long-supportive-chain.
* D2 fixture replay to verify relative ordering still holds.
* Real-repo shadow smoke (no Spearman, no outcome correlation).

**Rejected activities:**

* Promoting any pressure to `total_v_net` / `debt_final` /
  `corrupt_success_ratio`.
* Calling shadow pressure a "verdict".
* Fitting thresholds on hand-made D2 fixtures (overfit risk on
  synthetic signal).
* Modifying the vendored OIDA core (ADR-02 holds).

**Edge-confidence sub-decision (E2 §5):** chose **Option B** — keep
`NormalizedEvent` schema unchanged; pass an optional
`edge_confidences` mapping into `compute_experimental_shadow_fusion`.
Default uniform `0.6` when absent. Option A (frozen default) loses
DependencyEdge confidence; Option C (extend NormalizedEvent) is too
invasive for an experimental layer. Option B is the contract that
keeps the public schema stable and makes per-edge calibration
testable in the shadow layer alone.

**Outcome:** `keep` with two minor revisions — already implemented
in E1.1 (missing-grounding fix) and this commit (edge_confidences
parameter). Reports `reports/e2_shadow_formula_decision.md`.

[2026-04-25 09:00:00] - **ADR-22: Fusion readiness before graph-aware V_net.**

**Why:** Phase 3.5 (Blocks A-D) shipped a structurally validated
measurement pipeline: scorer faithful to paper 2604.13151, obligation
multiplicity (ADR-20), bounded dependency graph (ADR-21), audit
surface (D0/D0.1), 10 hermetic code-domain traces (D2), and real-repo
structural smoke (D3). But the OIDA fusion (`V_net`, `debt_final`,
`corrupt_success`) still has load-bearing inputs that are **defaults,
not measurements**:

* `event.capability = 0.5` everywhere (Phase 4 LLM intent estimator)
* `event.benefit = 0.5` everywhere (Phase 4 LLM intent/value estimator)
* `event.observability = 0.5` (heuristic test-presence detector pending)
* Several `PreconditionSpec` children verified=False by default
  (LLM-only signals: `negative_path_tested`, `data_preservation_checked`,
  `error_or_auth_path_checked`, etc.)

The vendored `OIDAAnalyzer.analyze()` mixes these defaults into
`q_obs`, `lambda_bias`, `V_dur`, and `V_net`. Emitting those numbers
publicly would be a silent lie (ADR-13 honesty principle).

**Decision:** OIDA-code MUST NOT emit official `V_net` / `debt_final`
/ `corrupt_success` while:

1. Load-bearing event fields (`capability`, `benefit`, `observability`)
   remain at their structural defaults.
2. Graph-aware fusion is uncalibrated (no validation that constitutive
   propagation actually predicts what we claim it predicts).
3. LLM-only sub-preconditions remain unresolved.

**Accepted protocol:**

* Emit a `FusionReadinessReport` that classifies every load-bearing
  field by source + status + confidence + whether it blocks official
  fusion.
* Emit explicit blockers as a list (the user sees what's missing).
* Allow an experimental SHADOW fusion only if **clearly marked
  non-authoritative**, in a separate output block, never in
  `summary.total_v_net` / `summary.debt_final`.

**Rejected alternatives:**

* Filling `V_net` from default-0.5 fields and footnoting it (rejected
  twice in ADR-13 already; this is the third rejection).
* Treating dep-graph presence as "graph-aware debt" (the vendored
  `analyze()` doesn't consume graph in V_net; the graph feeds
  `double_loop_repair`, not the fusion).
* Treating any B-state pattern as public `corrupt_success` (B-state
  is a candidate signal; promotion to verdict requires sustained
  pattern + negative V_net + trusted inputs — none guaranteed yet).
* Modifying the vendored OIDA core before a separate-layer experiment
  (ADR-02 vendoring discipline still holds).

**Architecture (E0.2 verdict):**

    vendored OIDA core
      → computes official local OIDA quantities when inputs are trusted

    fusion_readiness layer (NEW, src/oida_code/score/fusion_readiness.py)
      → decides if official fusion is allowed

    experimental_shadow layer
      → optional, clearly non-authoritative, opt-in

**Field readiness expected at v0.4.2 baseline:**

| Field | Source | Status | Blocks official |
|---|---|---|---|
| `capability` | default 0.5 | default | yes |
| `benefit` | default 0.5 | default | yes |
| `observability` | default 0.5 | default/heuristic | yes |
| `completion` | pytest pass-ratio | real | no |
| `tests_pass` | weighted blend | real-partial | no |
| `operator_accept` | ruff+mypy green | real | no |
| `grounding` | per-obligation child weights (ADR-20) | partial-real | no |
| `preconditions` | 1..N expanders (ADR-20) | real-partial | no |
| `constitutive_edges` | bounded graph (ADR-21) | real-bounded | no |
| `supportive_edges` | bounded graph (ADR-21) | real-bounded | no |
| `trajectory_metrics` | paper-faithful + structural smoke | real-structural | no |
| `repair_signal` | double_loop_repair | real-bounded | no |

**Acceptance criteria met (E0):** ADR-22 written, fusion_readiness
module shipped with FusionReadinessReport, 8+ tests including the
blocking-on-defaults set, official summary stays null when blocked,
separate-layer decision recorded explicitly here.

[2026-04-24 23:15:00] - **ADR-21: Minimal dependency graph before graph-aware fusion.**

**Why:** Phase 2's `extract/dependencies.py` returned `{ob.id:
{"constitutive": [], "supportive": []}}` and the mapper emitted every
`NormalizedEvent` with empty parent lists. That is an honest stub per
ADR-15, but it disables the vendored `double_loop_repair(root_event_id)`
entirely: with no edges, there are no descendants to reopen/audit. The
OIDA author (QA/A6.md, 2026-04-24) scoped Block C precisely around
fixing this repair-propagation gap — not around making `V_net`
graph-aware, since `OIDAAnalyzer.analyze()` does not consume
constitutive/supportive edges in its per-event `V_dur` / `V_net`
computation.

**Decision:** Block C builds a bounded, deterministic, explainable
dependency graph between obligations. The graph answers a single
question: "if this obligation is invalidated, which events must be
reopened, and which must only be audited?" The graph feeds
`NormalizedEvent.constitutive_parents / supportive_parents`, which the
vendored `double_loop_repair()` consumes.

**Definitions** (verbatim from A6.md):

* `constitutive edge A → B`: B is not valid if A is invalid.
* `supportive edge A → B`: A should be audited when B is suspicious,
  or B should be audited when A changes, but B is not automatically
  invalid.

**Direction**: `A → B` means "B depends on A". If `src/service.py`
imports `src/db.py`, then `db_event → service_event` (service depends
on db). This matches the `double_loop_repair` dominator semantics:
invalidating the root reopens dominated descendants.

**Edge rules** (A6.md, minimal):

1. **Same scope / same symbol** (same file, same function):
   - `precondition → api_contract` = constitutive
   - `invariant → api_contract` = constitutive
   - `security_rule → api_contract` = constitutive
   - `migration → api_contract` = supportive (unless direct data-path proof)
   - `observability → api_contract` = supportive

2. **Direct imports** via Python AST (`ast.Import` / `ast.ImportFrom`):
   - `imported-module obligation → importing-module obligation` = supportive
   - NOT constitutive by default (import presence doesn't prove the
     specific imported symbol underpins the contract).

3. **Related tests** (by convention `tests/test_foo.py ↔ src/foo.py`):
   - `test obligation → source obligation` = supportive (not constitutive —
     missing/failing test triggers audit, doesn't prove source invalid).

4. **Config / migration** (minimal):
   - `pyproject.toml / setup.cfg / tox.ini / pytest.ini → changed
     Python obligation` = supportive.
   - `migration file → data/API obligation in same changed set` = supportive.
   - `migration file → migration obligation in same scope` = constitutive.

5. **No invented edges**: every edge carries `reason`, `source`,
   `confidence`. Every `parent_id` / `child_id` must reference an
   existing obligation. Enforced by the vendored analyzer's `_validate_ids()`.

**Bounds** (A6.md, non-negotiable for Block C):

* `max_depth = 1`
* `max_files = 50`
* stdlib / site-packages / external imports IGNORED
* unresolved imports RECORDED, not guessed

**Rejected alternatives:**

* Full transitive call graph (scope creep; max_depth = 1 stays).
* Graph edges without evidence (`reason` + `source` + `confidence`
  required).
* Using graph presence to unlock official `V_net` / `debt`
  emission (the vendored analyzer does not consume edges in its
  fusion; claiming graph-aware V_net would be a silent lie).

**Honesty statement for reports:** Block C improves repair propagation
and audit planning. It does NOT make `V_net` graph-aware yet.
Graph-aware `V_net` would require either a vendored-core change or a
separate fusion layer that consumes graph diagnostics. The current
report's `V_net` / `debt_final` remain `null` under ADR-13.

[2026-04-24 22:30:00] - **ADR-20: Obligation is not isomorphic with PreconditionSpec.**

**Why:** Phase 2's `_preconditions_for()` returned exactly one
`PreconditionSpec` per `Obligation` with the parent weight and
`verified = (obligation.status == "closed")`. Combined with
`_link_evidence_to_obligations()` which closed obligations wholesale on
pytest-green, this produced binary grounding: either the whole
obligation was "verified" or none of it was. The OIDA author (QA/A5.md,
2026-04-24) flagged this as structurally wrong:

> One obligation may entail multiple preconditions. Green pytest is not
> proof that the negative path was tested, that the migration rollback
> was checked, that the auth path was checked, or that observability
> is present.

**Decision:** An `Obligation` is a high-level testable commitment. A
`PreconditionSpec` is one atomic support condition consumed by the
vendored OIDA `grounding()` formula. One obligation expands to **1..N**
preconditions, chosen per `kind`. Child weights **conserve** the parent
weight (`sum(child.weight) == obligation.weight`). Each child is
verified **independently** against available evidence — no blind
inheritance from parent status.

**How applied:** `src/oida_code/score/mapper.py` gains
`_weighted_children(obligation, parts)` for exact float-conserving
splits, an `EvidenceView` bundle of tool-evidence queries, and
kind-dispatched expanders emitting the minimal child set per
`ObligationKind` value (Answer5.md mapping verbatim):

* ``precondition`` — guard_detected, static_scope_clean,
  regression_green_on_scope, negative_path_tested
* ``api_contract`` — endpoint_or_function_declared, static_shape_clean,
  regression_green_on_scope, error_or_auth_path_checked
* ``migration`` — migration_marker_detected, data_preservation_checked,
  rollback_or_idempotency_checked, migration_test_evidence
* ``security_rule`` — rule_declared_or_detected, static_scan_clean,
  taint_or_access_path_checked
* ``observability`` — failure_mode_logged, metric_or_trace_available,
  alert_or_surface_defined
* ``invariant`` — invariant_declared, invariant_checked_by_test_or_property,
  regression_guard_present
* unknown kind — single ``unexpanded_<kind>``, ``verified=False``, full
  parent weight.

Evidence matchers are conservative: only sub-preconditions with explicit
automatic signal from Phase-1/Phase-2 evidence (extractor source tag,
ruff/mypy findings, pytest green, semgrep/codeql clean, hypothesis
runs) are auto-verified. Sub-preconditions needing LLM or richer
evidence default to ``verified=False``; Phase-4 LLM closes them later.

**Rejected alternatives:**

* Keep 1 obligation = 1 PreconditionSpec (collapses grounding to binary).
* Auto-close parent obligations before expansion:
  `_link_evidence_to_obligations()` is **removed** from the mapper main
  path (Option A per Answer5.md). The function is retained for existing
  unit tests that exercise the legacy linker directly, but is no longer
  called by `obligations_to_scenario()`.
* Treat pytest-green as proof of all sub-conditions.

**Acceptance criteria met (tests):** multiplicity, weight conservation
via ``pytest.approx``, partial grounding (strictly between 0 and 1),
pytest-green-alone does not close every sub-precondition, Pydantic ↔
vendored round-trip preserved, A2.5 trajectory tests unchanged.

[2026-04-24 21:30:00] - **ADR-19: Phase 3.5 — measurement before LLM. Scorer refactor + 7-criteria ship gate.**

**Why:** OIDA v4.2 author's review of `CONSULTATION_OIDA.md` (response in
`CONSULTATION_OIDA_RESPONSE.md` + `Answer.md`, 2026-04-24) identified two
silent bugs in `score/trajectory.py` and one conceptual framing error that
together made the Phase-3 empirical numbers artifactual beyond the known
length confound:

1. **State-before-action bug.** `score_trajectory` attributes `CaseLabel`
   using `visited = _visited_paths_up_to(events, t)` which includes
   `event[t]`. Paper 2604.13151 §4 attributes the case to `s_t` *before*
   `a_t` is applied. Our code is computing the case on `s_{t+1}`.
2. **`t=0` `closed_before` bug.** At `t=0`, `_closed_obligations_up_to(events,
   max(t-1, 0))` returns `_closed_obligations_up_to(events, 0)` which
   *includes* `event[0].closed_obligations`. A first-action obligation
   close is therefore never counted as progress.
3. **Conceptual framing.** The code conflates "state the agent was in"
   with "state the agent produced" in the same `_visited_paths_up_to`
   helper. The author insists the refactor make these structurally
   distinct (`state_before = build_state(events[:t])`, not a patched
   index), so the bug cannot be reintroduced by a future edit.

**How applied (this commit window):**

* New `TrajectoryState` dataclass in `score/trajectory.py` with `.visited`,
  `.closed`, `.unobserved`, `.pending`. Built from `events[:t]`
  (exclusive) → represents state *before* action `events[t]`.
* `classify_case(state_before)`, `compute_gain(state_before, action,
  state_after)`, `compute_error(case, gain, stale_before, stale_after)`
  split out so the scorer's main loop reads as the state-before-action
  flow the paper defines.
* ADR-18's code mapping is kept; the **numerical** fixes are the
  state-before patch + the t=0 fix. Larger structural items (bounded
  ImpactCone, evidence-based Gain, per-kind preconditions, dependency
  graph) are deferred to Phase 3.5 Blocks B-D and the Phase-4 LLM work
  stays gated on Blocks A-D.

**Phase 3.5 ship gate (7 criteria, author-specified):**

1. state-before-action bug fixed
2. t=0 edge case fixed
3. paper sanity check passes on the original 2604.13151 metric/domain
4. U(t) replaced by `changed_files ∪ bounded impact_cone` (max_depth=1,
   max_files=50, every included file carries a `reason` label)
5. `Gain()` is no longer only "file visited" — evidence/obligation/risk/
   counterexample/discovery gains
6. ≥ 6-10 hermetic code-domain traces pass expected classification (clean
   success, exploration miss, exploitation miss, stale cycling, corrupt
   plausible success, counterexample found)
7. `V_net` / `debt_final` remain `null` / blocked if graph or fusion is
   incomplete

**Validation discipline (author-specified):**

* **D1 paper sanity check** (mandatory): clone
  `jjj-madison/measurable-explore-exploit`, reproduce paper's `c_t/e_t/
  n_t/S_t` on their 2D grid traces → `paper_sanity_report.md`.
* **D2 code-domain mini** (mandatory): 6-10 hermetic traces, labeled
  dominant failure mode, no LLM judge, no `commits > 0` outcome.
* **D3 30-trace F2P/P2P corpus** (deferred to pre-Phase-4): SWE-bench
  style, format prepared as `datasets/code_traces_v1/` skeleton only.

**Non-negotiables from the review (will land in follow-up commits):**

* One `Obligation` → multiple `PreconditionSpec` (not the current 1:1
  collapse).
* Weighted preconditions: `weight = base_kind × intent × (1+blast) ×
  data_security × external_surface`.
* `fusion_status` block in reports; `V_net` / `debt_final` as
  `{value, status, blocked_by}` objects rather than bare floats.
* `corrupt_success` two-level: `suspected` (any B-event) vs `confirmed`
  (sustained-B OR weighted_b_load ≥ 0.20 OR critical-B OR apparent-
  success-with-counter-evidence).

**This commit scope (Block A only, per author's stop-and-review order):**
items 1-2 of the gate (bugs) + the conceptual refactor, plus tests
proving Case 1/2/3/4 reachability on synthetic fixtures. Before/after
numbers on the 5 existing fixtures recorded below.

[2026-04-24 19:00:00] - **ADR-18: Grid→code adaptation for Explore/Exploit metric (paper 2604.13151 §4).**
**Why:** The paper's formulas are defined on 2D grid + DAG: `U(t)` = unobserved cells (bounded by grid size), `P(t)` = pending task nodes with prerequisites satisfied, Gain(t→t+1) = 1 if the agent entered a target cell or reduced Manhattan distance to one. In code, "unobserved" is effectively infinite (thousands of files in any repo), so Case 3 of Table 1 never fires and the normalizers collapse. Without an explicit domain adaptation, the scorer would produce numbers that don't mean what the paper says they mean (advisor stress-test, 2026-04-24).
**How applied:** Phase-3 `score/trajectory.py` adopts a **bounded** U(t) scoped to the audit surface:

* `U(t)` = `{f ∈ AuditRequest.scope.changed_files : f ∉ visited_paths(t)}` where a path is "visited" if any Read/Grep/Glob event in `trace.events[:t]` had it in `scope`. Finite, diff-scoped, eventually empties.
* `P(t)` = `{o ∈ obligations : o.status = "open" ∧ all deps of o closed ∧ scope(o) ∈ visited_paths(t)}`. "Pending" = the agent can act on it now.
* Goal `g` = the obligation with `source = "intent"` if present, else the highest-weight obligation; a proxy that works for Phase-3 smoke without an explicit "primary obligation" flag.
* `Gain(t → t+1) = 1` iff one of:
  - `trace.events[t+1].scope ∩ U(t) ≠ ∅` (read an unobserved changed file) — exploration gain
  - `obligations(t+1).closed ⊋ obligations(t).closed` — exploitation gain
* Progress event = any `t` where `event.new_facts ≠ ∅` OR `event.closed_obligations ≠ ∅`. Matches `Trace.progress` shape shipped in Phase 2.
* Nodes of the no-progress graph = `(event.kind, event.scope[0] or "_none")` so "Read src/a.py" and "Read src/b.py" are distinct nodes, while two consecutive "Read src/a.py" share a node (edge-reuse catches it).
* Edges = consecutive pairs `(node_t, node_{t+1})` inside the no-progress window.

**Non-goals for Phase 3:** the paper's Manhattan-distance gain signal is replaced by set-membership (read/closed). The "symbolic-DAG vs semantic-DAG" ablation is out of scope. Phase 4 may introduce an LLM-backed gain oracle.

**Risk acknowledgment:** this adaptation is *defensible*, not *validated*. The Phase-3 exit gate (ρ < −0.3 with outcome labels) is the empirical check that the adaptation preserves the paper's main finding (Figure 1a: low exploration error → high success).

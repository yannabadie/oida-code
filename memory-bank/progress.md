# Progress

**Active plan: `PLAN.md`** (merged blueprint + roadmap, 2026-04-24).
The schedule below uses `PLAN.md` §14 Phase 0-7 numbering, not the original `prompt.md` Phase-1/2/3/4 wording.

## Done

- [x] Initialize project (workspace scaffolding, brainstorm docs).
- [x] **Phase 0 — cadrage + bootstrap** (2026-04-23 → 2026-04-24). Commits `15138f3..1733f98` on `main`. See `PHASE1_REPORT.md` (titled for historical reasons; describes Phase 0 output).
  - Context digest (10 mandatory docs read).
  - Public repo `yannabadie/oida-code` created (MIT, `main` tracked).
  - Blueprint §7 tree scaffolded under `src/oida_code/`.
  - Pydantic I/O models v1 (`AuditRequest`, `NormalizedScenario`, `AuditReport`).
  - Vendored OIDA core (SHA256-pinned in `VENDORED_FROM.txt`).
  - Typer CLI with `inspect` implemented; 4 other subcommands `NotImplementedError` with phase pointers.
  - 4 quality gates green: ruff ✓, mypy --strict ✓ (41 files), pytest 10/10 ✓, `oida-code inspect` deserializes. Coverage 74%.
  - memory-bank populated with real content (6 files + 12 ADRs).
- [x] **Merge blueprint + roadmap into `PLAN.md`** (2026-04-24). ADR-10/11/12 logged.

## Doing

- [ ] Nothing. Awaiting user "go Phase 2" (observation model + obligation graph).

## Done — Phase 1 (deterministic audit · 2026-04-24)

Shipped with advisor-vetted scope cuts (CodeQL stubbed, 3-repo validation with
explicit 10-repo exit criterion deferred).

- [x] Schema v1.1: `Finding`, `ToolEvidence`, `ToolBudgets`, `VerdictLabel`
      (Literal) added to `models/`. Example JSONs updated. ADR-13 (Optional
      summary fields) + ADR-14 (verify accepts AuditRequest in Phase 1).
- [x] `verify/_runner.py` — shared subprocess helper (UTF-8, timeout, never
      raises). `probe_version` for lazy `tool_version` population.
- [x] `verify/lint.py` — ruff JSON.
- [x] `verify/typing.py` — mypy stdout parse with absolute-path regex.
- [x] `verify/pytest_runner.py` — JUnit-XML via tempdir.
- [x] `verify/semgrep_scan.py` — semgrep `scan --config=auto --json`.
- [x] `verify/codeql_scan.py` — Phase 1 stub (`status="tool_missing"` /
      `"skipped"`); full integration deferred to Phase 2.
- [x] `extract/blast_radius.py` — weighted signals (modules 0.20 / api 0.20 /
      data 0.35 / infra 0.25), bounded in ``[0, 1]``.
- [x] `ingest/manifest.detect_commands` — pyproject + setup.cfg + marker
      files. Falls back to stock Python defaults.
- [x] `score/verdict.py` — deterministic resolver. `corrupt_success` stays
      dark until Phase 5.
- [x] `report/json_report.py`, `report/markdown_report.py`,
      `report/sarif_export.py` — SARIF 2.1.0 minimal compliance (GitHub
      code-scanning accepted fields).
- [x] `cli.py` — `normalize` stays NotImplementedError (Phase 2). `verify`
      + `audit` implemented. Added `--intent`, `--format`, `--fail-on`.
- [x] Tests: 53 passing. Coverage **78%**. 6 new test modules.
- [x] Validation: self-audit + oida_framework subdir + oid_framework subdir
      + external `attrs` repo (clone to `.oida/validation-external/`). All
      4 runs produced valid reports, no crashes.

## Phase 1 carry-over tickets (fix in early Phase 2)

- [ ] **Pytest-subprocess Python resolution.** When `shutil.which("pytest")`
      returns a pytest bound to a different Python than the one running
      oida-code (e.g. miniforge3 global vs. our venv), collection fails with
      `ModuleNotFoundError`. Same risk for `mypy`. Phase 2 fix: probe whether
      `sys.executable -m pytest` is available and prefer it when the target
      appears to be the oida-code repo itself, or when `shutil.which` resolves
      to a Python different from `sys.executable`.
- [ ] **`--fail-on corrupt` structurally unreachable in Phase 1** (requires
      Phase 5 OIDA fusion). Wired but not testable end-to-end yet.
- [ ] **10-repo validation exit criterion deferred.** PLAN.md §14 P1 exit
      criterion is "Stable report on 10 Python repos without human
      intervention". We ran 4 (3 in-workspace + 1 external attrs). Phase 2
      gate will revisit after obligation graph ships.
- [ ] **semgrep_scan coverage 24%** — dev env on Windows lacks semgrep. Add
      a fixture-based JSON-parse unit test.
- [ ] **warnings from ruff/mypy do not show up as critical_findings.** By
      design (only `severity="error"` counts). The Markdown `counts` column
      surfaces them. Double-check the shape when Phase 2 fusion lands.

## Phase 2 — observation model + obligation graph (2 weeks)

**Entry gate:** Phase 1 shipped (met once pushed).

Deliverables: `models/trace.py`, `models/obligation.py`,
`models/progress_event.py`, `extract/obligation_graph.py`,
`extract/{claims,preconditions,dependencies}.py`, `score/mapper.py`,
`verify/hypothesis_runner.py`, `verify/mutmut_runner.py`, **50-100
hand-annotated PR traces** in `datasets/traces_v1/`, and `verify` CLI
learns to accept `NormalizedScenario`.

Exit criterion: can describe action-by-action where an agent explores /
exploits / stagnates / loops on a real PR. Obligation-extraction recall
≥ 60% on the annotated set.

## Phase 2 — observation model + obligation graph (2 weeks)

**Entry gate:** Phase 1 shipped.

Deliverables: `models/trace.py`, `models/obligation.py`, `models/progress_event.py`, `extract/obligation_graph.py`, `extract/{claims,preconditions,dependencies}.py`, `score/mapper.py`, `verify/hypothesis_runner.py`, `verify/mutmut_runner.py`, **50-100 hand-annotated PR traces** in `datasets/traces_v1/`.

Exit criterion: can describe action-by-action where an agent explores / exploits / stagnates / loops on a real PR. Obligation-extraction recall ≥ 60% on the annotated set.

## Phase 3 — Explore/Exploit adapter (2 weeks)

Deliverables: `score/trajectory.py`, correlation dashboard (Jupyter or Streamlit in `notebooks/`).

Exit criterion: scorer distinguishes "didn't find" (exploration error) vs "found but didn't use" (exploitation error). Spearman ρ > 0.5 against human labels on Phase 2 dataset.

## Phase 4 — agentic verifier (2 weeks, blocked on M.2 2TB upgrade)

Deliverables: `llm/{client,schemas,forward_verifier,backward_verifier}.py`, extended `score/verdict.py`, CLI `--llm-endpoint --offline`.

Exit criterion: multi-turn verifier beats single-pass LLM judge on Phase 2 annotated set.

## Phase 5 — OIDA fusion + repair (2 weeks)

Deliverables: `score/{fusion,repair}.py`, `llm/repair_prompts.py`, CLI `repair` wired.

Exit criterion: can explain every red/yellow verdict on a PR with evidence, not vibes.

## Phase 6 — product surface (2 weeks)

Deliverables: `.github/workflows/oida-code.yml`, `github/{checks,annotations}.py`.

Exit criterion: dev installs tool in <15 min and sees useful verdict inside a PR. Demo on 10 intentionally sloppy PRs with false-positive / false-negative table recorded before any threshold tuning.

## Phase 7 — research moat (months 4-6, off critical path)

LongCoT-Mini → full benchmark harness; Simula-driven synthetic dataset v1; Dafny proof modules for 2-3 critical invariants; TypeScript start.

Exit criterion: measurable moat (corrupt-success F1 on adversarial dataset + long-horizon critic robustness plot).

---
[2026-04-23 21:57:00] - Phase 1 bootstrap kicked off from `prompt.md`.
[2026-04-24 07:04:50] - Phase 1 Steps 0-4 complete. All quality gates green. Moving to Step 5 (report + stop).
[2026-04-24 07:45:00] - Merge: `prompt.md` "phase 1 bootstrap" retroactively relabeled **Phase 0** to match `PLAN.md` §14. `PHASE1_REPORT.md` kept as historical artifact (describes Phase 0 output). Next = Phase 1 deterministic audit, awaiting user "go".
[2026-04-25 14:30:00] - Phase 3.5 Block E2 complete (commit pending). ADR-23 logged. KEEP V1 with two minor revisions already shipped (missing-grounding fix in E1.1, edge_confidences override here). 17 new tests in `tests/test_e2_shadow_formula_decision.py` (16 pass + 1 V2 placeholder skip), full suite 277/278. Sensitivity sweep (`scripts/evaluate_shadow_formula.py`) shows delta=0.0 across 26 inputs; graph ablation 7/7 invariants hold; real-repo shadow smoke (`scripts/real_repo_shadow_smoke.py`) PASS on oida-code self + attrs (`has_forbidden_summary_keys = False`, `authoritative = False`, `readiness_status = blocked`). Report: `reports/e2_shadow_formula_decision.md`. Next = E3 (estimator contracts) per QA/A13.md §"What changes before E3".
[2026-04-25 18:45:00] - Phase 4.0 LLM estimator dry-run complete (commit pending). ADR-25 logged. 21/21 acceptance criteria from QA/A15.md met. Deliverables: (4.0-A) `src/oida_code/estimators/llm_provider.py` with LLMProvider Protocol + FakeLLMProvider (deterministic, tests-only) + FileReplayLLMProvider (reads JSON from disk) + OptionalExternalLLMProvider (opt-in stub; no API call by default; never echoes secret values). (4.0-B) `src/oida_code/estimators/llm_prompt.py` with EvidenceItem + LLMEvidencePacket (frozen, citable [E.kind.idx] IDs); render_prompt wraps user-supplied text in `<<<EVIDENCE_BLOB ...>>>` data-fences and explicitly tells the LLM that fenced text is data, not instruction. (4.0-C) `src/oida_code/estimators/llm_estimator.py` with run_llm_estimator() — never raises; invalid JSON / schema violation / forbidden phrases / cap breaches / missing citations / contradictions with deterministic tools all become blockers/warnings. (4.0-D) 8 hermetic fixtures under `tests/fixtures/llm_estimator_dryrun/`: capability_supported_by_guard, capability_missing_mechanism, benefit_missing_intent, benefit_intent_aligned, observability_tests_only, observability_negative_path_present, llm_overclaims_without_evidence, prompt_injection_in_code_comment. (4.0-E) `oida-code estimate-llm` CLI subcommand (separate from score-trace per QA/A15.md preference). (4.0-F) Tests verify official summary fields stay null and `official_ready_candidate` never appears across all 8 fixtures. 32 new tests in `tests/test_phase4_0_llm_estimator_dryrun.py` (8 hermetic + 24 unit incl. provider security tests + cross-fixture observability monotonicity). Full suite 364/367 (3 documented skips). Repo + history scanned for committed keys before shipping; clean. ADR-22 + ADR-25 hold: production CLI emits no V_net. Report: `reports/phase4_0_llm_estimator_dryrun.md`. Next = Phase 4.1 (forward/backward verifier contract) per QA/A15.md §"Après Phase 4.0".
[2026-04-25 16:30:00] - Phase 3.5 Block E3 complete (commit pending). ADR-24 logged. 19/19 acceptance criteria from QA/A14.md met. Deliverables: (E3.0) `src/oida_code/score/event_evidence.py` with `EventEvidenceView` + per-event helpers; `src/oida_code/score/mapper.py` gains `build_scoring_inputs`, `edge_confidences_from_dependency_graph`, `ScoringInputs` (non-breaking — `obligations_to_scenario` is now a thin wrapper). (E3.1) `src/oida_code/estimators/contracts.py` with frozen `SignalEstimate` + `EstimatorReport` (model validators reject default+confidence>0, missing+confidence>0, llm+authoritative, etc.). (E3.2) `src/oida_code/estimators/deterministic.py` with capability/benefit/observability + completion/tests_pass/operator_accept baselines. (E3.3) `src/oida_code/estimators/llm_contract.py` with `LLMEstimatorInput` / `LLMEstimatorOutput` (caps confidence at 0.6 LLM-only, 0.8 hybrid; requires citations). **No LLM is called.** (E3.4) `src/oida_code/estimators/readiness.py` with `assess_estimator_readiness` ladder (blocked/diagnostic_only/shadow_ready/official_ready_candidate); CLI score-trace now emits `payload["estimator_readiness"]` alongside the official `payload["readiness"]`. 57 new tests across `tests/test_e3_evidence_plumbing.py` (15) and `tests/test_e3_estimator_contracts.py` (42). Full suite 332/335 (3 skips = V2 placeholder + 2 Phase-4 observability markers). Differentiation fixture proves shadow pressure varies with evidence (B - A >= 0.10) — the LLM estimators in Phase 4 will arrive on a real surface. ADR-22 still holds: `total_v_net` / `debt_final` / `corrupt_success` remain null/blocked. Report: `reports/e3_estimator_contracts.md`. Next = Phase 4.0 (LLM estimator dry-run on hermetic fixtures).

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

[2026-05-01 02:00:00] - **ADR-33: Provider regression deepening before framework migration.**

**Why:** Phase 4.7 shipped DeepSeek V4 Pro on 4 cases with full
contract compliance (`official_field_leak_count == 0`, zero
schema/citation/forbidden-phrase violations) but observed an
accuracy delta vs replay (-0.25 status, -0.5 estimate) that
Phase 4.7 explicitly deferred — the report stored no raw
prompts/responses by design (ADR-32), so we couldn't say WHY the
delta existed. Phase 4.8 introduces a redacted-only opt-in
capture path so an operator can diagnose the delta WITHOUT
breaking ADR-32's "no raw prompt/response artifact by default"
rule, extends the dataset to 8 llm_estimator cases (L005-L008
covering completion / tests_pass / operator_accept /
edge_confidence), and runs a multi-provider matrix (DeepSeek V4
Pro + V4 Flash) to separate model-specific behaviour from
contract behaviour.

**Decision (Phase 4.8 surface):**

* **4.8.0-A** — README cleanup. The Phase 4.6 paragraph claiming
  `upload-sarif@v3` and `provider baseline not_run` was stale
  post-Phase 4.7 (`@v4` bumped, baseline ran). Two regression
  tests (`test_readme_phase47_does_not_contain_stale_sarif_v3_claim`
  + `test_readme_phase47_does_not_say_provider_baseline_not_run`)
  lock the cleanup.
* **4.8.0-B** — `.github/workflows/provider-baseline-node24-smoke.yml`.
  Replay-only, `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` at job
  scope, contents:read perms only. Proves the provider-baseline
  surface (separate from ci.yml's node24-compat job which only
  validates the validator + Phase 4.5/4.6 tests) survives the
  GitHub 2026-06-02 default switch. Green on real runner.
* **4.8-A** — Redacted provider I/O capture. New
  `ProviderRedactedIO` Pydantic model (frozen + extra="forbid")
  carries `prompt_sha256` (NOT raw prompt), redacted response
  body (after `redact_secret(body, key)`), model id,
  http_status, wall_clock_ms, response_id, finish_reason, token
  usage. The `OpenAICompatibleChatProvider` gets a
  `capture_redacted_io: bool = False` constructor flag; when
  True, every successful `complete_json` call stashes a
  `_last_redacted_io` slot the runner pops via
  `pop_last_redacted_io()`. CRITICAL: redaction happens INSIDE
  the provider, where the API key value is in scope; the runner
  never holds the raw key. The CLI exposes
  `--store-redacted-provider-io` (opt-in only); the workflow
  exposes `store-redacted-provider-io` input default `false`.
  10 tests in `tests/test_phase4_8_redacted_provider_io.py` use
  a long distinctive sentinel
  `sk-DETECT-LEAK-Z9KF1L-PROVIDER-IO-CANARY-2026` to assert
  redaction actually fires (not just that output happens to be
  clean) — including the test that injects the sentinel into a
  fake response body simulating a 401-style auth-echo.
* **4.8-B** — Label audit script
  `scripts/audit_provider_estimator_labels.py`. Reads redacted
  provider I/O + `expected.json` and produces per-case
  classification (`match` / `label_too_strict` / `provider_wrong`
  / `mapping_ambiguous` / `contract_gap`). Read-only — NO label
  changes are made by this script; any actual label edits land
  in a separate commit with written justification.
* **4.8-C** — `datasets/private_holdout_v1/` schema (README +
  `manifest.example.json`); `cases/` is gitignored
  (`datasets/private_holdout_v1/cases/`). Operator builds their
  12-case holdout locally; nothing case-specific enters the
  public repo.
* **4.8-D** — `scripts/build_calibration_dataset.py` extends
  `llm_estimator` family from 4 (L001-L004) to 8 (L005-L008).
  Manifest: 36 → 40 cases. Two existing Phase 4.4.1 tests
  updated for the new size.
* **4.8-E** — Repeat-runs stability. CLI
  `--repeat-provider-runs N` (1-3, hard cap to bound API spend).
  When N>1 + external provider, the case loop runs N times and
  writes `<out>/stability_summary.json` with mean+std for
  status/estimate accuracy + safety + fenced rates + citation
  precision + `official_field_leak_count_max`. Hard rule:
  `leak_max > 0` exits 3.
* **4.8-F** — `experiments/pydantic_ai_spike/`. Top-level (not
  under `src/`), excluded from mypy + ruff in the project gates,
  not pulled by `pip install -e .[dev]`. Documentation-only
  sketch + comparison table; the actual migration would need a
  separate ADR after the spike report lands.

**ADR-32 reconciliation.** ADR-32 §rejected forbids "raw prompt
/ raw response artifacts by default". Phase 4.8-A's
`--store-redacted-provider-io` is OPT-IN AND REDACTED — never
raw. Specifically: prompts ship as SHA256 only (the raw text is
never serialized), and response bodies are passed through
`redact_secret(body, key)` BEFORE being captured (the API key
value is masked even if a misbehaving provider echoes it). The
ADR-32 default behaviour stays unchanged; the new flag opens a
diagnosis surface that preserves the security posture.

**Accepted:**

* redacted provider I/O capture behind explicit flag — opt-in
  only, default false at every layer (constructor, CLI flag,
  workflow input)
* L005-L008 dataset extension (4 → 8 llm_estimator cases)
* DeepSeek V4 Pro and V4 Flash both run on 8 cases with the
  same contract validation as Phase 4.7 — both passed
  `official_field_leak_count == 0`
* repeat-runs stability metrics — DeepSeek V4 Pro on 8 cases ×
  2 runs surfaced `estimator_estimate_accuracy_std=0.15`,
  showing the provider is non-deterministic between calls even
  on the same prompt
* label audit script lands as documentation-only — no automatic
  label edits
* private_holdout_v1 schema only, cases gitignored
* pydantic-ai spike directory at experiments/, NOT in install
  surface
* Node24 replay smoke for the provider-baseline surface
* MiniMax/Kimi runs marked `not_run` for this commit window —
  two providers (V4 Pro + V4 Flash) provide enough comparison
  data; further providers are a Phase 4.9+ option

**Rejected:**

* default external provider, public benchmark claims, threshold
  tuning on calibration_v1 (ADR-28 still applies)
* MCP integration in Phase 4.8 — anti-MCP locks
  (`test_no_mcp_workflow_or_dependency_added`) hold
* provider tool-calling at the verifier layer
  (`test_no_provider_tool_calling_enabled` walks
  `provider_config.py` for `supports_tools=True`)
* official `V_net` / `debt_final` / `corrupt_success` /
  `verdict` / `merge_safe` / `production_safe` / `bug_free` /
  `security_verified` emission
* wholesale migration to pydantic-ai — sketch only, ADR-required
  before any production move
* committing operator-private cases under
  `datasets/private_holdout_v1/cases/` to the public repo
* faking the V4 Pro 6/8 missing redacted IO captures — Phase
  4.8.1 work to extend capture to provider-failure paths is
  documented as a known limitation in the report

**Outcome:** **24/24** acceptance criteria from QA/A25.md met.
17 new tests across `tests/test_phase4_8_redacted_provider_io.py`
(10) and `tests/test_phase4_8_workflow_and_docs.py` (7). The
multi-provider matrix delivered:

```
metric                          replay   v4-pro (×2)         v4-flash
official_field_leak_count       0        0 (max across 2)     0
estimator_status_accuracy       0.625    0.25 / 0.125 (std=0.0625)  0.625
estimator_estimate_accuracy     0.6      0.30 / 0.00 (std=0.15)     0.30
schema/citation/safety/fenced   1.0 each 1.0 each              1.0 each
```

V4 Flash matches replay status accuracy while V4 Pro is more
inconsistent (high std). V4 Flash captured all 8 redacted IO
files; V4 Pro captured only 2 (L005, L007) because 6/8 of its
responses raised `LLMProviderInvalidResponse`-class exceptions
that bypass the success-path stash — documented as a known
limitation; Phase 4.8.1 may extend capture to the failure
paths. Real-runner runs: provider-baseline V4 Pro × 8 × 2
(24954088672 — green); provider-baseline V4 Flash × 8 ×1
(24954298728 — green); ci on cd7e5ac (24954060852 — green);
provider-baseline-node24-smoke on cd7e5ac (24954060856 —
green); action-smoke on cd7e5ac (24954060855 — green). Full
suite **575 passed + 4 skipped**. ruff + mypy clean. ADR-22 +
ADR-25..32 + ADR-33 all hold; production CLI + composite action
emit no `V_net` / `debt_final` / `corrupt_success`. Reports:
`reports/phase4_8_provider_regression_deepening.md`,
`reports/provider_label_audit_l001_l008.md` (V4 Pro),
`reports/provider_label_audit_l001_l008_v4flash.md`.

[2026-04-30 04:00:00] - **ADR-32: Provider regression baseline before MCP / tool-calling.**

**Why:** Phase 4.6 (ADR-31) closed the operator-side smoke gaps —
composite action, SARIF ingestion, Node 24 compat — but explicitly
deferred the provider regression baseline (§7 of the Phase 4.6
report marked it `not_run` for "no API budget allocated").
Phase 4.7 closes the structural surface for that baseline so an
operator can fire it the moment budget is allocated, and bumps
the SARIF uploader to its current major version (v3 deprecation
announced for December 2026). The phase ships partially: the
workflow + tests + ADR + replay-side artifacts land, but Phase
4.7 is NOT marked fully accepted until at least one external
provider run lands green per QA/A24.md acceptance criterion 12.

**Decision (Phase 4.7 surface):**

* `.github/workflows/sarif-upload.yml` — bumped
  `github/codeql-action/upload-sarif@v3 → @v4`. v4 ships with
  native Node 24 runtime; the input shape (`sarif_file`,
  `category`) is unchanged, so the migration is a one-line
  edit. Validated empirically on real runner (run id
  24952767492, commit c49a155): green + 6 SARIF analyses
  ingested into Code Scanning at sarif_id
  `11ad3390-414e-11f1-86c6-63dd82cf10f5` (ruff 125 results,
  mypy 221 results, plus pytest/hypothesis/semgrep/codeql
  shells).
* `.github/workflows/provider-baseline.yml` — workflow_dispatch
  ONLY (no push, pull_request, pull_request_target, schedule).
  Three inputs: `provider-profile` (required, choice between
  deepseek/kimi/minimax/custom_openai_compatible),
  `max-provider-cases` (default 4 — small enough for cheap first
  run), `compare-replay` (default true). Workflow + job
  permissions are `contents: read` only — no `security-events`,
  no `actions: write`, no `checks: write`, no `contents: write`.
  Replay baseline runs FIRST (gated on `compare-replay == 'true'`);
  the external-provider step runs SECOND, gated on the
  `*_API_KEY` secret being non-empty (the CLI's existing 4.4
  `LLMProviderUnavailable` guard handles the empty case). All
  secret values travel `secrets.* → env: → $VAR in bash`; zero
  `${{ secrets.* }}` inside any `run:` block (validator §6
  enforces). The post-step renders a redacted summary (cases
  evaluated, official_field_leak_count, estimator_*_accuracy,
  safety/fenced rates) into a per-profile `report.md` and into
  `$GITHUB_STEP_SUMMARY`. Artifacts upload only
  `.oida/provider-baseline/` — no raw prompt, no raw provider
  response, no API key, no unredacted error.
* The CLI's existing exit-3 gate on
  `official_field_leak_count > 0` (4.3.1-A) propagates
  unchanged through the workflow's `set -euo pipefail`.
* The `4.7.4` metric set listed in QA/A24.md
  (schema_valid_rate, invalid_json_rate, schema_violation_rate,
  missing_citation_rate, confidence_cap_violation_rate,
  forbidden_claim_rate, official_field_leak_count,
  evidence_ref_precision, evidence_ref_recall, safety_block_rate,
  fenced_injection_pass_rate, provider_unavailable_count,
  timeout_count) is partially covered by today's
  `CalibrationMetrics` (evidence_ref_precision,
  evidence_ref_recall, safety_block_rate, fenced_injection_rate,
  official_field_leak_count, plus the 4.4.1 estimator family).
  The remaining provider-failure-mode counters (invalid JSON,
  missing citation, schema violation, provider_unavailable,
  timeout) are NOT added to the Pydantic model in this commit;
  they will be added in Phase 4.7.1 when a real provider run
  produces non-zero values worth schematising. Adding them
  speculatively would create empty fields with no observed
  meaning.

**Accepted:**

* SARIF uploader pinned to v4 — green on real runner with
  ingestion confirmed via `code-scanning/analyses` API
* provider-baseline workflow is `workflow_dispatch` only;
  forbidden triggers (push / pull_request / pull_request_target
  / schedule) absent + asserted by tests
* permissions stay `contents: read` at workflow + job level —
  no `security-events`, no `actions/checks/contents: write`
* replay baseline runs BEFORE the external provider step
  (asserted by `test_provider_baseline_runs_replay_before_external`)
* `provider-profile` input is `required: true` — no silent
  default-to-deepseek-then-bill
* default `max-provider-cases` capped at 4 (asserted by
  `test_provider_baseline_default_max_cases_is_small`)
* secrets reach the CLI as env-var NAMES only; the action body
  has zero `${{ secrets.* }}` inside `run:` (validator §6 +
  `test_provider_baseline_uses_secrets_context_only`)
* `echo $X_API_KEY` and pipe-to-logger style leaks rejected by
  `test_provider_baseline_does_not_echo_secret_values`
* the workflow MUST NOT pass any `--debug-raw-prompt` /
  `--store-raw` flag (asserted), and any `|| true` swallowing
  the official-leak gate is rejected (asserted)
* MCP and provider tool-calling explicitly absent — asserted at
  the package level (`test_no_mcp_workflow_or_dependency_added`)
  and at the schema level (`test_no_provider_tool_calling_enabled`
  walks `provider_config.py` and rejects
  `supports_tools=True` anywhere)
* fork-PR fence smoke (Phase 4.6) and provider regression run
  remain explicitly `not_run` with reasons — no fork exists
  at this commit; no API budget allocated for this commit
  window

**Rejected:**

* default external provider (push / pull_request)
* external provider on PR or fork events (Phase 4.5 fence still
  applies inside the composite action)
* `pull_request_target` anywhere
* public benchmark claims comparing providers
* threshold tuning on `calibration_v1` (ADR-28 still applies)
* MCP integration — OWASP describes specific MCP risks (tool
  poisoning, prompt injection, cross-server shadowing,
  tool-definition rug-pull); deferred until Phase 5.0+
* provider tool-calling at the verifier layer
* official `V_net` / `debt_final` / `corrupt_success` /
  `verdict` / `merge_safe` / `production_safe` /
  `bug_free` / `security_verified` emission
* faking the provider regression baseline result — Phase 4.7
  ships partially accepted until a real provider run lands

**Outcome:** **24/24** acceptance criteria from QA/A24.md met.
17 new tests in `tests/test_phase4_7_provider_baseline.py` (3
SARIF v4, 12 provider-baseline structural, 2 anti-MCP/tool-
calling). FOUR real-runner runs green: ci on c49a155 (id
24952744508), action-smoke on c49a155 (id 24952744506), sarif-
upload v4 on c49a155 (id 24952767492), and provider-baseline
DeepSeek V4 Pro on c1a39b8 (id 24953163352). The provider
regression baseline run was made possible by commit c1a39b8
which (a) bumped the DeepSeek default model from the soon-to-
be-deprecated `deepseek-chat` to `deepseek-v4-pro` (DeepSeek
announced 2026-07-24 sunset for the legacy aliases) and (b)
added a `model` workflow input. The empirical run produced:
`official_field_leak_count == 0` (gate clean), 4 provider
calls (no skips, no timeouts, no provider_unavailable), 0
schema violations, 0 missing citations, 0 forbidden phrases.
Accuracy delta vs replay (-0.25 status accuracy, -0.5 estimate
accuracy) captured as DATA for Phase 4.8 — explicitly NOT a
verdict on the provider per ADR-28 + ADR-32. Full suite **558
passed + 4 skipped** (V2 placeholder + 2 Phase-4 observability
markers + 1 optional external smoke). ruff + mypy clean. ADR-
22 + ADR-25..31 + ADR-32 all hold; production CLI and the
composite action emit no `V_net` / `debt_final` /
`corrupt_success`. Report:
`reports/phase4_7_provider_regression_baseline.md`. Phase 4.7
status: **fully accepted**.

[2026-04-29 03:00:00] - **ADR-31: Real-runner / operator smoke before MCP / tool-calling.**

**Why:** Phase 4.5 was accepted end-to-end on commit f625b1c (CI
run #3 green on a real GitHub-hosted runner). The Phase 4.5
report explicitly listed three operational gaps that remained
structural-only: (1) the composite action had never been invoked
from a real consumer workflow, (2) the fork-PR fence was
asserted by string match in the action body — never exercised on
a real fork PR, (3) the SARIF upload step had never been
exercised against GitHub Code Scanning's ingestion. QA/A23.md
requires Phase 4.6 to close those operational gaps before opening
the MCP / tool-calling chantier.

**Decision (Phase 4.6 surface):**

* `.github/workflows/ci.yml` — adds a `node24-compat` job that
  pins `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` at job scope and
  re-runs the validator + Phase 4.5 + Phase 4.6 invariant suites
  under the Node 24 runtime. GitHub announced runners switch to
  Node 24 by default on 2026-06-02; this job tests it today.
* `.github/workflows/action-smoke.yml` — composite-action
  consumer smoke. Fires on `push:main` and `workflow_dispatch`.
  Uses `uses: ./` against the local checkout with replay-only
  inputs (`upload-sarif: false`, `fail-on: none`,
  `llm-provider: replay`). `fetch-depth: 2` so `base-ref:
  HEAD~1` resolves. Read-only workflow permissions, no secrets.
  This is the first surface that ACTUALLY EXECUTES `action.yml`'s
  composite body on a real runner.
* `.github/workflows/sarif-upload.yml` — manual `workflow_dispatch`
  only. The upload job grants `security-events: write` at JOB
  scope, never at workflow level. Uses
  `github/codeql-action/upload-sarif@v3` for the canonical
  ingestion path.
* Phase 4.5 latent bug surfaced and fixed:
  `inputs.repo-path.description` in `action.yml` interpolated
  `${{ github.workspace }}`. GitHub's manifest loader rejects
  `${{ ... }}` expressions inside input descriptions
  (descriptions are static metadata, not runtime). Phase 4.5
  tests parsed the YAML structurally but never executed the
  action. Fixed in this commit; new regression test
  `test_action_inputs_descriptions_have_no_expression_interpolation`
  walks every `inputs.<name>.description` and rejects any
  `${{ ... }}` substring so the same shape of bug never re-ships.

**Accepted:**

* Node 24 compat job (job-scoped env var, read-only perms, no
  external provider) — green on real runner
* composite action consumer smoke (`uses: ./`, replay-only) —
  green on real runner in 51s
* SARIF upload smoke via `workflow_dispatch` — green on real
  runner; ingestion confirmed via
  `gh api repos/.../code-scanning/analyses` (6 SARIF analyses
  visible: ruff 125 results, mypy 215 results, plus pytest,
  semgrep, hypothesis, codeql shells)
* `security-events: write` lives at JOB scope only (not workflow
  scope); validator §4 still enforces this
* fork-PR fence smoke + provider regression baseline marked
  explicitly `not_run` — no real fork of yannabadie/oida-code
  exists at this commit; no API budget allocated

**Rejected:**

* MCP integration in Phase 4.6 (separate ADR required when the
  time comes)
* provider tool-calling at the verifier layer in Phase 4.6
* GitHub App / Checks API custom annotations
* external provider as default on push or pull_request
* external provider on PR events from forks (already blocked
  structurally in 4.5; remains untested on real fork PR until an
  operator opens one)
* `pull_request_target` anywhere
* official `V_net` / `debt_final` / `corrupt_success` /
  `verdict` / `merge_safe` / `production_safe` / `bug_free` /
  `security_verified` emission
* faking the fork-PR or provider-regression smoke results
  (QA/A23.md: "ne fake pas le résultat. Marque not_run et garde
  Phase 4.6 partiellement ouverte.")

**Outcome:** all 20 acceptance criteria from QA/A23.md met. 15
new tests in `tests/test_phase4_6_real_runner_smoke.py`
(node24-compat job invariants ×4, action-smoke workflow
invariants ×5, sarif-upload workflow invariants ×5,
action-input-description regression ×1). Three real-runner runs
green on commit a9de514: ci (id 24948296296), action-smoke (id
24948296297), sarif-upload (id 24948316005). Fork-PR fence smoke
+ provider regression baseline both marked `not_run` with
explicit reasons in `reports/phase4_6_real_runner_operator_smoke.md`
§5 + §7. Full suite **541 passed + 4 skipped** (V2 placeholder +
2 Phase-4 observability markers + 1 optional external smoke).
ruff + mypy clean. ADR-22 + ADR-25..30 + ADR-31 all hold;
production CLI and the composite action emit no `V_net` /
`debt_final` / `corrupt_success`. Two non-blocking annotations
remain in CI runs: Node 20 deprecation on
checkout/setup-python/upload-artifact (mitigated by the
node24-compat job; full action-vendor bumps when their releases
land), and `github/codeql-action/upload-sarif@v3` deprecation
announced for December 2026 (Phase 4.7 ticket: bump to v4 when
released). Report:
`reports/phase4_6_real_runner_operator_smoke.md`.

[2026-04-28 09:00:00] - **ADR-30: CI workflow + composite GitHub Action under least-privilege; no Checks API; fork PR fence; replay default.**

**Why:** Phase 4.4 delivered a real OpenAI-compatible provider behind
explicit opt-in (ADR-29), and Phase 4.4.1 wired
`oida-code calibration-eval` to actually route the LLM estimator
through that provider when invoked with the right flags. The
operator surface is now ready, but the project has no CI of its own
(quality gates are run manually) and no GitHub Action for downstream
adopters. The temptation in this phase is to "go enterprise" —
GitHub App, Checks API custom annotations, `pull_request_target`
listening on every PR — and that bundle of decisions is precisely
what the OIDA + ADR-22 contract forbids. So Phase 4.5 ships a
deliberately small surface: an internal CI workflow and a reusable
composite action, both running with `permissions: contents: read`
by default, with the SARIF upload scoped to a single
`security-events: write` step gated on an explicit input.

**Decision (Phase 4.5 surface):**

* `.github/workflows/ci.yml` — internal CI with five jobs (lint,
  typecheck, test, calibration, security-smoke). Workflow-level
  `permissions: contents: read`. Triggers: `push` on `main`,
  `pull_request` on `main`, and `workflow_dispatch`. **No
  `pull_request_target`.** `OIDA_RUN_EXTERNAL_PROVIDER_TESTS=0` is
  pinned in the test job env so the optional external-provider
  smoke stays gated. `concurrency: ci-${{ github.ref }}` with
  `cancel-in-progress: true`.
* `action.yml` (repo-root composite action) — operator-facing
  reusable surface. Inputs: `repo-path`, `base-ref`, `intent-file`,
  `output-dir`, `upload-sarif`, `fail-on`, `surface`,
  `enable-shadow`, `llm-provider` (default `replay`),
  `provider-profile`, `api-key-env`, `max-provider-cases`. Outputs:
  `report-json`, `report-markdown`, `report-sarif`,
  `calibration-metrics`. The first step blocks
  `llm-provider == 'openai-compatible'` on fork PRs (compares
  `github.event.pull_request.head.repo.full_name` against
  `github.repository`) and aborts with a clear error before any
  CLI runs. SARIF upload is the only step that can require
  `security-events: write`; it is gated on `inputs.upload-sarif ==
  'true'` and uses `github/codeql-action/upload-sarif@v3`. JSON /
  Markdown / calibration-metrics are uploaded via
  `actions/upload-artifact@v4`. The action writes a redacted
  excerpt of the markdown report and the calibration headline to
  `$GITHUB_STEP_SUMMARY`. **No `${{ secrets.* }}` reference inside
  the action body — secrets are wired in the calling workflow's
  `env:` map only, with the action receiving the env-var **name**
  via `api-key-env`.
* `scripts/validate_github_workflows.py` — operator + CI-runnable
  static checker. Verifies: API-key prefix patterns absent
  (`sk-…`, `ghp_…`, `xoxb-…`); no `pull_request_target`; top-level
  `permissions:` present and `contents: read`; per-job permissions
  restricted to `read`/`none`/`security-events: write`; no
  `${{ secrets.* }}` inside `run:` blocks; action uses composite
  runs; `llm-provider` default = `replay`; fork-PR guard present;
  full required-input list shipped.

**Accepted:**

* `permissions: contents: read` is the workflow + action default
* `pull_request_target` is forbidden everywhere
* `security-events: write` is allowed only on the SARIF upload
  step inside the action, never at the workflow or job scope
* `llm-provider` defaults to `replay`; an explicit
  `openai-compatible` invocation is required to reach a real API
* fork PRs cannot run the external provider — guarded explicitly
  in `action.yml` and tested in `tests/test_phase4_5_*.py`
* secrets travel through `env:` from the calling workflow; the
  action body never references `${{ secrets.* }}`
* SARIF is opt-in via `inputs.upload-sarif == 'true'`
* outputs are JSON / Markdown / SARIF / calibration-metrics —
  none of them carry `total_v_net`, `debt_final`,
  `corrupt_success`, `verdict`, `merge_safe`, `production_safe`,
  `bug_free`, or `security_verified`
* the validator script ships green on the shipped tree and
  exits non-zero with `pull_request_target` flagged when invoked
  on a workflow that contains it
* PR-controlled `${{ ... }}` expressions never appear inside a
  `run:` block — they are lifted into `env:` and referenced as
  `$VAR` in bash; validator §6 enforces this on workflows AND the
  composite action
* tests parse the YAML directly and don't require a runner

**Rejected:**

* GitHub App + Checks API custom annotations (would force
  per-event `verdict` rendering on the PR diff — the operator can
  add that later under their own ADR; ADR-22 forbids us shipping
  it as a default)
* `pull_request_target` for cross-fork events (intentional anti-
  pattern; would let a forked PR exfiltrate secrets through the
  action body)
* `permissions: write-all` shortcuts
* an external provider as default for fork PRs (anti-secret-exfil)
* echoing `${{ secrets.X }}` into the markdown summary (set-x
  traces would leak even with `add-mask`)
* a "merge-safe" or "production-safe" status check label (ADR-22
  permanent ban)
* PyPI 1.0 promotion (alpha tag retained while official fields
  remain blocked)

**Paired with this commit (4.4.1 — calibration path alignment):**

* `llm_estimator` family added to `calibration_v1` (4 cases:
  L001–L004 covering capability_supported_clean,
  capability_missing_mechanism, benefit_missing_intent,
  observability_negative_path).
* `ExpectedEstimateLabel` model + `expected_estimator_status` /
  `expected_estimates` per-case fields with strict family-aware
  invariants (only `llm_estimator` may declare them).
* Runner gains `evaluate_llm_estimator` that loads the packet,
  builds a `FileReplayLLMProvider` when no provider is injected
  (replay default), routes through `run_llm_estimator`, and scores
  status + per-estimate matches via `_estimate_matches_label`.
* Metrics surface: `estimator_status_accuracy`,
  `estimator_estimate_accuracy`, `estimator_cases_evaluated`,
  `estimator_cases_skipped` — `Optional[float]` so a missing
  signal is honest instead of zero.
* CLI `calibration-eval` accepts `--llm-provider`,
  `--provider-profile`, `--api-key-env`, `--model`, `--base-url`,
  `--max-provider-cases`, `--timeout`. External cases beyond the
  cap are recorded as `estimator_skipped=True` with a clear reason
  and dropped from the headline accuracy denominators.
* Forbidden-phrase fence + `assert_no_official_field_leaks` apply
  to provider responses identically to the replay path —
  validated by `test_calibration_eval_external_official_field_
  leak_exits_3`.

**Phase 4.5.1 hardening (paired with this commit):** the first
draft of `action.yml` interpolated `${{ inputs.X }}` and
`${{ github.action_path }}` directly into the run-audit `run:`
block. That is GitHub's documented shell-injection anti-pattern: a
PR-controlled value (e.g. a branch name, an `intent-file` path
passed by a caller) gets substituted at YAML-eval time and can
break out of bash quoting. The fix lifts every PR-influenced
expression into the step's `env:` map and uses bash variables
(`$REPO_PATH`, `$BASE_REF`, `$INTENT_FILE`, `$OUTPUT_DIR`,
`$FAIL_ON`, `$LLM_PROVIDER`, `$PROVIDER_PROFILE`, `$API_KEY_ENV`,
`$MAX_PROVIDER_CASES`, `$ACTION_PATH`) inside the heredoc. The
validator gains rule §6 that scans every `run:` block for
PR-controlled `${{ ... }}` expressions
(`inputs.*`, `github.head_ref`, `github.actor`,
`github.triggering_actor`,
`github.event.{pull_request,issue,comment,review,discussion,
workflow_run,push,head_commit}.*`,
`github.event.head_commit.message`) and fails with a one-liner
pointing at the env-var pattern. Two new tests:
`test_action_does_not_inline_pr_controlled_expr_in_run_blocks`
(structural — walks `runs.steps[*].run`) and
`test_validate_github_workflows_script_detects_inputs_in_run`
(plants a poisoned workflow in tmp_path and asserts the validator
exits non-zero). The fork-fence test is also strengthened — it now
asserts `openai-compatible` AND `head.repo.full_name` AND
`github.repository` all appear inside the **same** `if:` clause,
so a future split-step refactor cannot silently weaken the guard.

**Outcome:** all 23 acceptance criteria from QA/A21.md met. 17 new
tests in `tests/test_phase4_5_ci_github_action.py` (file existence,
permissions invariants, `pull_request_target` ban, SARIF gate,
composite/replay/fork-PR/artifacts/secrets invariants on
`action.yml`, no-official-fields output check, structural fork-PR
fence, no-PR-controlled-expr-in-run, validator green-on-shipped-
tree + detects `pull_request_target` + detects shell-injection
fixture). 9 new tests in `tests/test_phase4_4_real_provider.py`
covering 4.4.1 (flag parity, replay default, validator reuse,
invalid JSON / missing citations rejection, leak exit code 3,
metrics-report secret redaction). Full suite **525 passed + 4
skipped** (V2 placeholder + 2 Phase-4 observability markers +
1 optional external smoke). ruff + mypy clean across `src/`,
`tests/`, and the seven scripts run by the local gate
(`scripts/{evaluate_shadow_formula,real_repo_shadow_smoke,
build_calibration_dataset,check_calibration_stability,
run_calibration_eval,validate_github_workflows}.py`). ADR-22 +
ADR-25 + ADR-26 + ADR-27 + ADR-28 + ADR-29 + ADR-30 all hold;
production CLI and the composite action emit no `V_net` /
`debt_final` / `corrupt_success`. Report:
`reports/phase4_5_ci_github_action.md`.

[2026-04-27 10:00:00] - **ADR-29: Real provider binding behind explicit opt-in.**

**Why:** Phase 4.0–4.3 shipped contracts + a 32-case calibration
dataset. The next step is exercising those contracts against a real
external LLM provider — but only as a regression harness on
calibration_v1, never as production verifier. ADR-29 binds one
provider class (``OpenAICompatibleChatProvider``) and explicit
opt-in flags so a real call requires deliberate operator action.

**Decision (Phase 4.4 protocol):**

* `src/oida_code/estimators/provider_config.py` — frozen
  ``ProviderProfile`` schema with ``name`` / ``base_url`` /
  ``api_key_env`` / ``default_model``. **No API-key field.** Three
  predefined profiles ship: ``deepseek`` / ``kimi`` / ``minimax``;
  ``custom_openai_compatible`` requires explicit construction.
* `src/oida_code/estimators/providers/openai_compatible.py` —
  `OpenAICompatibleChatProvider` speaks OpenAI Chat Completions
  wire format over `urllib.request`. Tests inject a fake HTTP
  transport via the `http_post` constructor argument; production
  uses `default_urllib_post`.
* CLI `estimate-llm` gains `--llm-provider openai-compatible
  --provider-profile <name> [--api-key-env VAR] [--model X]
  [--base-url U]`.
* CLI `calibration-eval` subcommand wraps the runner; default
  uses replay; the same `--llm-provider` flags can route the LLM
  estimator through a real provider for a regression run.
* 4.3.1 calibration hardening (paired): leak metric is honest
  (`int` not `Literal[0]`); F2P/P2P metrics nullable + folded from
  stability report; safety runner uses an exact OIDA_EVIDENCE
  regex bounded to the data region.

**Accepted:**

* no provider by default (the CLI default is replay)
* env-var based key loading only — `api_key_env` on the profile,
  resolved lazily at call time
* key redaction in logs, exception strings, and any stored
  payload (`redact_secret`)
* provider config separate from prompt and from any key value
* strict Pydantic validation after every response
* calibration replay baseline still passes
* no threshold tuning on calibration_v1
* fake HTTP transport in tests; no real network call under pytest
  by default

**Rejected:**

* committing keys (push protection + clean history scan)
* default-on external API calls
* LLM-as-ground-truth (calibration labels remain script-authored)
* model self-confidence as evidence
* provider output writing `V_net` / `debt_final` /
  `corrupt_success` (existing forbidden-phrase fence still rejects)
* production claims from synthetic calibration
* MCP integration (separate ADR will be required)
* tool/function-calling at the provider layer in 4.4
* streaming in 4.4

**Outcome:** all 22 acceptance criteria from QA/A20.md met. 26 new
tests in `tests/test_phase4_4_real_provider.py` (schema invariants,
predefined profiles, provider unavailable behaviour, key redaction,
response validation, replay parity, CLI smoke). Plus 13 new tests
for 4.3.1 in `tests/test_phase4_3_calibration.py`. Full suite
**499 passed + 4 skipped** (V2 placeholder + 2 Phase-4 observability
markers + 1 optional external smoke). The pilot calibration eval
still reports zero leaks; the openai-compatible provider goes
through the same `LLMEstimatorOutput` validator as the replay path
so contract compliance is identical. ADR-22 + ADR-25 + ADR-26 +
ADR-27 + ADR-28 + ADR-29 all hold; production CLI emits no
`V_net` / `debt_final` / `corrupt_success`. Report:
`reports/phase4_4_real_provider_binding.md`.

[2026-04-26 14:00:00] - **ADR-28: Calibration dataset before predictive claims.**

**Why:** Phase 4.0–4.2 shipped the LLM estimator + forward/backward
verifier + tool-grounded loop as **contracts**. None of those phases
validated quality on real cases. Phase 4.3 designs a calibration
dataset that measures pipeline behaviour on controlled cases without
recreating the Phase-3 length-confound trap (progress_rate was
mechanically tied to session length; commits>0 was a tautological
outcome proxy).

**Decision (Phase 4.3 protocol):**

* `src/oida_code/calibration/` sub-package: `models.py` (frozen
  schemas), `metrics.py` (`CalibrationMetrics` + pure helpers),
  `runner.py` (per-family evaluators + aggregation).
* `datasets/calibration_v1/` ships a **32-case pilot** spread across
  five families: 8 `claim_contract`, 8 `tool_grounded`, 6
  `shadow_pressure`, 6 `code_outcome` (with F2P/P2P), 4
  `safety_adversarial`. Built deterministically by
  `scripts/build_calibration_dataset.py`.
* Three operator scripts:
  * `build_calibration_dataset.py` — emits the dataset
  * `run_calibration_eval.py` — emits `metrics.json` + report
  * `check_calibration_stability.py` — runs `code_outcome` cases'
    pytest 3 times and flags flaky cases (excluded from headline
    metrics)
* 4.2.1 paired hardening: phase4_2 report's residual `<<>>`
  shorthand replaced with explicit `<<<OIDA_EVIDENCE id="[E.x.y]"
  kind="...">>>` ... `<<<END_OIDA_EVIDENCE id="[E.x.y]">>>` form;
  engine pre-clamps per-tool `max_runtime_s` to the remaining global
  budget AND blocks without invocation when the budget is exhausted;
  3 new tests pin the behaviour.

**Accepted:**

* claim-level labels (accepted/unsupported/rejected + reason
  Literal)
* evidence-ref labels (precision + recall + unknown-ref rejection)
* tool-result labels with `expected_status` + optional block-reason
  substring
* seeded synthetic repo defects with F2P/P2P (SWE-bench-style)
* multi-run stability (default 3 runs) for `code_outcome` cases;
  flaky cases excluded
* `CalibrationProvenance` with `contamination_risk` ladder
  (synthetic / private / public_low / public_high); `public_high`
  cases automatically dropped from headline metrics
* macro-F1 alongside accuracy (the three claim outcomes are
  imbalanced; accuracy alone could mask "always say accepted")
* the `Literal[0]` pin on `CalibrationMetrics.official_field_leak_count`
  + `CalibrationManifest.official_vnet_allowed=Literal[False]` so
  the schema literally cannot publish a result that claims V_net is
  open

**Rejected:**

* `commits > 0` as a success proxy (Phase-3 trap)
* session length as a success proxy (Phase-3 trap)
* public benchmark score as proof of real-world validity (OpenAI's
  SWE-bench Verified retraction in 2026 cited contamination + ≥59.4%
  defective tests in audited subset; we do NOT bet OIDA-code on a
  saturated public benchmark)
* official `V_net` / `debt_final` / `corrupt_success` from
  calibration results (ADR-22 still holds)
* LLM-as-judge for ground truth (would re-introduce the LLM
  authority leak ADR-24 forbids)
* threshold tuning on `calibration_v1` for production use

**External grounding:**

* SWE-bench / SWE-bench Multilingual: F2P (correctness) +
  P2P (no regression) executable signals.
* ProdCodeBench: production-derived, prompt + commit + tests with
  relevance validation + multi-run stability.
* OpenAI 2026 audit on SWE-bench Verified: contamination guard
  required; public benchmarks treated as memorisation risk.
* OWASP agent attack catalogue: prompt injection, tool abuse, data
  exfiltration; the `safety_adversarial` family covers prompt
  injection in code AND in tool output, forged evidence ids, and
  fence-close attempts.
* NIST AI RMF: govern / map / measure / manage; Phase 4.3 is the
  *measure* function, decoupled from operational thresholds.

**Outcome:** all 24 acceptance criteria from QA/A19.md met. 22 new
tests in `tests/test_phase4_3_calibration.py` (schema invariants,
metric helpers, per-family runners, end-to-end pilot smoke,
manifest pinning). Plus 3 new tests for 4.2.1 in
`tests/test_phase4_2_tool_grounded_verifier.py`. Full suite **462
passed + 3 skipped** (1 V2 placeholder + 2 Phase-4 observability
markers). The pilot dataset evaluates with all metrics at 1.0 (with
`code_outcome` deferred to the stability script) and **0
official-field leaks** across all 32 cases. ADR-22 + ADR-25 + ADR-26
+ ADR-27 + ADR-28 hold; production CLI emits no `V_net` /
`debt_final` / `corrupt_success`. Report:
`reports/phase4_3_calibration_dataset_design.md`.

[2026-04-26 09:30:00] - **ADR-27: Bounded tool-grounded verifier loop.**

**Why:** Phase 4.1 (ADR-26) shipped the forward/backward verifier
contract with replay-only providers and `VerifierToolCallSpec` as
description-only. Phase 4.2 grants the verifier the right to **ask
for** tools, not the right to choose argv or run shell commands. The
loop must be bounded, read-only, and policy-gated; tool outputs are
deterministic evidence, never instructions.

**Decision (Phase 4.2 protocol):**

* `src/oida_code/verifier/tools/` sub-package with `contracts.py`
  (`ToolPolicy` / `VerifierToolRequest` / `VerifierToolResult`),
  `sandbox.py` (path traversal, deny patterns, output truncation +
  SHA256), `adapters.py` (deterministic per-tool adapters that build
  their own argv), `registry.py` (allowlist lookup),
  `__init__.py` (`ToolExecutionEngine`).
* Adapters at minimum: ruff, mypy, pytest. Each builds its own argv;
  no LLM-supplied free string ever reaches `subprocess.run`.
* `subprocess.run(..., shell=False, capture_output=True, timeout=...)`.
* Read-only by default: `allow_write=False`, `allow_network=False`.
* Budget: `max_tool_calls=5`, `max_total_runtime_s=60`,
  `max_output_chars_per_tool=8000`.
* CLI: `oida-code run-tools <requests.json> --policy <policy.json>
  --out <results.json>` as a separate command (not in `audit`, not
  in `score-trace`). No two-pass verifier loop in 4.2 — the operator
  chains `run-tools` → `verify-claims` manually with the enriched
  packet. Keeps the chain inspectable.
* No MCP integration in 4.2; real vendor binding is 4.2.x.

**Accepted:**

* allowlisted tools only
* no shell passthrough (argv-list invocation only)
* read-only execution
* per-tool timeout + output cap; truncated output is hashed
  (SHA256 of FULL payload) so an integrator can detect tampering
* evidence refs generated from parsed tool output; raw stdout never
  reaches the LLM
* deterministic tool evidence wins over LLM claims at the aggregator

**Rejected:**

* autonomous unbounded agent loop
* destructive tool calls / writes / network
* MCP integration in Phase 4.2
* raw tool output trusted as instruction
* official `V_net` / `debt_final` / `corrupt_success` emission
* default-on external API calls

**4.1.1 micro-hardening (paired with this ADR):**

* `reports/phase4_1_forward_backward_contract.md` fixture table +
  bullets now spell out the named OIDA_EVIDENCE fences explicitly
  (no more "named fences" generic phrasing).
* `aggregate_verification` rejects any claim whose `event_id`
  doesn't match `forward.event_id`; backward results with
  mismatched `event_id` are dropped with a warning;
  deterministic-tool contradiction is checked against
  `claim.event_id` (not the forward's roll-up id) so future
  per-event aggregation paths stay correct.
* 3 new tests added to `tests/test_phase4_1_verifier_contract.py`.

**Outcome:** all 24 acceptance criteria from QA/A18.md met. 34 new
tests in `tests/test_phase4_2_tool_grounded_verifier.py` (8 hermetic
fixtures + adapter / sandbox / engine / CLI smoke). Full suite
**437 passed + 3 skipped** (1 V2 placeholder + 2 Phase-4
observability markers). `oida-code run-tools` CLI is wired; the
`OptionalExternalVerifierProvider` remains a Phase 4.2.x stub. ADR-22
+ ADR-25 + ADR-26 + ADR-27 all hold; production CLI emits no
`V_net` / `debt_final` / `corrupt_success`. Report:
`reports/phase4_2_tool_grounded_verifier_loop.md`.

[2026-04-25 21:00:00] - **ADR-26: Forward/backward verifier contract before tool-grounded loop.**

**Why:** Phase 4.0 (ADR-25) shipped a dry-run for the LLM ESTIMATOR
(capability/benefit/observability with citation, caps, schema
validation). The next step in the AgentV-RL-style verification chain
is the multi-agent VERIFIER — forward (premises → conclusion) +
backward (conclusion → required premises) + aggregator. Before any
real multi-turn loop with tool execution, we need the contract to be
stable: schemas, aggregation rules, and provider abstraction. ADR-26
is that contract.

**Decision (Phase 4.1 protocol):**

* Define frozen schemas: `VerifierClaim`, `ForwardVerificationResult`,
  `BackwardRequirement`, `BackwardVerificationResult`,
  `VerifierAggregationReport`, `VerifierToolCallSpec`.
* `VerifierClaim` allowlist: `capability_sufficient`,
  `benefit_aligned`, `observability_sufficient`,
  `precondition_supported`, `negative_path_covered`, `repair_needed`,
  `shadow_pressure_explained`. **Forbidden** (rejected at the schema
  level): `merge_safe`, `production_safe`, `bug_free`,
  `security_verified`, `official_v_net`, `official_debt`,
  `official_corrupt_success`, plus the ADR-22 set (`total_v_net`,
  `v_net`, `debt_final`, `corrupt_success`, `verdict`).
* `is_authoritative` pinned to `Literal[False]` on
  `VerifierClaim` AND on `VerifierAggregationReport` — the verifier
  CAN NOT promote any claim to official, regardless of status.
* Aggregator requires forward AND backward support, evidence
  existence, no tool contradiction, claim type allowlist, confidence
  cap (0.6 LLM-style sources), and forbidden-phrase rejection.
* Replay-only providers (Fake / FileReplay /
  OptionalExternalVerifierProvider stub). **No external API call by
  default.** No vendor SDK imported at module load.
* `VerifierToolCallSpec` exists so a verifier can describe what it
  WOULD ask, but Phase 4.1 does NOT execute any tool. Phase 4.2
  will introduce tool execution.

**Accepted:**

* claim schema with citable refs and 7 allowed claim types
* forward + backward schemas with explicit
  `necessary_conditions_met: bool`
* aggregation policy that requires both directions
* fake/replay verifier providers
* deterministic tools always win conflicts

**Rejected:**

* direct official `V_net` from verifier claims
* LLM-only proof claims (caps + non-authoritative pin)
* verifier inventing evidence (unknown `evidence_refs` rejected)
* verifier executing tools in Phase 4.1 (`ToolCallSpec` is
  description, not execution)
* external API calls by default
* modifying vendored OIDA core (ADR-02 still holds)

**4.0.1 hardening (paired with this ADR):** named per-item data
fences `<<<OIDA_EVIDENCE id="..." kind="...">>>` ...
`<<<END_OIDA_EVIDENCE id="...">>>` replace the legacy
`<<<EVIDENCE_BLOB ...>>>` shape. Inner attempts to forge a closing
fence are neutralised with a zero-width space. Phase 4.0 report
updated to match. Five new tests pin the fence name + neutralisation
behaviour.

**Outcome:** 21/21 acceptance criteria from QA/A16.md met. 31 new
tests across `tests/test_phase4_1_verifier_contract.py` (schema +
aggregation + 8 hermetic fixtures including
`prompt_injection_claim_payload` and `tool_failure_contradicts_claim`).
Full suite **400 passed + 3 skipped**. The CLI gains
`oida-code verify-claims <packet> --forward-replay <r> --backward-replay <r>`
as a separate command (NOT in score-trace per QA/A16.md preference).
ADR-22 + ADR-25 + ADR-26 all hold; production CLI emits no
`V_net` / `debt_final` / `corrupt_success`. Report:
`reports/phase4_1_forward_backward_contract.md`.

[2026-04-25 18:30:00] - **ADR-25: LLM estimator dry-run before agentic verifier.**

**Why:** ADR-24 defined the estimator contract (frozen
`SignalEstimate`, confidence/source rules, citation requirement). But
the contract is paper until a real estimator runs through it. Phase
4.0 must prove that an LLM-shaped flow can produce contract-compliant
estimates **without** acquiring authority over `V_net`, `debt_final`,
or `corrupt_success`, **without** overriding deterministic tool
failures, and **without** any default-on external API call.

**Decision (Phase 4.0 protocol):**

* Phase 4.0-A — provider abstraction: `LLMProvider` Protocol with
  three implementations (Fake, FileReplay, OptionalExternal). Tests
  use Fake/Replay only. External provider raises clean
  `LLMProviderUnavailable` without env var.
* Phase 4.0-B — evidence packet: frozen `LLMEvidencePacket` with
  citable `[E.kind.idx]` IDs. Prompt template wraps user-supplied
  text in `<<<EVIDENCE_BLOB ...>>>` fences and labels it as data,
  not instruction.
* Phase 4.0-C — runner: parser + validator + merge. Strict failure
  handling — invalid JSON, schema violation, confidence cap breach,
  missing citations, forbidden phrase, contradiction with
  deterministic tool — all become blockers/warnings without crash.
* Phase 4.0-D — 8 hermetic fixtures including a prompt-injection
  fixture that proves the fence keeps user text out of instruction
  context.
* Phase 4.0-E — `oida-code estimate-llm` subcommand (separate from
  `score-trace`) with `--llm-provider replay` default.
* Phase 4.0-F — readiness integration verifies that even on the
  most permissive fixture, the production CLI emits no official
  fusion key (`total_v_net`, `debt_final`, `corrupt_success_*`).

**Accepted:**

* Evidence packet with citable refs (`[E.intent.1]`, `[E.event.1]`,
  `[E.prec.1]`, `[E.tool.1]`, `[E.test.1]`, `[E.graph.1]`).
* Fake / replay provider as the production-test default.
* External provider opt-in only, behind env var + explicit flag.
* Schema validation BEFORE the LLM output reaches any consumer.
* LLM-only estimates non-authoritative (cap 0.6); hybrid 0.8.
* Deterministic tool evidence wins all conflicts on tool-grounded
  fields.

**Rejected:**

* Raw LLM scores as `capability` / `benefit` / `observability` truth.
* LLM self-reported confidence as evidence.
* LLM ability to emit `V_net` / `debt_final` / `corrupt_success` in
  any field (validator-rejected at packet AND runner level).
* Default-on external API calls (no vendor SDK imported at module
  load; env var must be present AND explicit `--llm-provider external`
  flag passed).
* Full-repo context dump (packet items capped at length 400; only
  scope-matching tool findings reach the prompt).
* Phase 4 verifier loop before estimator dry-run (this ADR is
  explicitly the dry-run only; forward/backward verifier is Phase
  4.1+).

**Security:** repo + history scanned for committed keys before
shipping the external provider stub; clean. The
`OptionalExternalLLMProvider` error path never echoes the env var
value, even when set. `LLMProviderError` messages drop vendor stack
traces on purpose.

**Outcome:** all 21 acceptance criteria from QA/A15.md met
structurally. 32 new tests across `tests/test_phase4_0_llm_estimator_dryrun.py`
(unit + 8 hermetic fixtures). On real repos the production CLI
estimator output stays at `status="blocked"` (tool_evidence is
None at score-trace time per ADR-24 §10 known limitations); on the
most permissive controlled fixture the report reaches
`status="shadow_ready"` with all three load-bearing fields
LLM-replaced. **Official fusion remains null.** ADR-22 holds; no
follow-up ADR has been proposed to lift it. Report:
`reports/phase4_0_llm_estimator_dryrun.md`.

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

[2026-04-26 18:30:00] - **ADR-34: Artifact UX before MCP/tool-calling.**
**Why:** Phase 4.8 shipped real-provider regression with multi-provider data (DeepSeek V4 Pro 8×2, V4 Flash 8×1) and the V4 Pro 6/8 missing-capture gap surfaced an honest limitation: the failure-path stash was empty for 6 of 8 invalid_shape responses, so the operator had no way to inspect WHY the provider failed. The QA/A26 review (2026-04-26) flagged a different problem at a higher level — the artifact bundle (JSON + Markdown + SARIF + calibration metrics + redacted IO + step summary + composite-action outputs) is correct and contract-clean, but it is not READABLE. A developer reviewing a PR comment must scroll past long stack-traces of OIDA-internal language ("E0 fusion-readiness" / "shadow-fusion authoritative=Literal[False]") to find what the run actually proved. That UX gap, not the absence of MCP, is what blocks operator adoption.
**Decision:** Phase 4.9 standardizes OIDA-code's operator-facing artifacts:
* Markdown reports (4.9-A): a new `src/oida_code/report/diagnostic_report.py` module renders every calibration / provider-baseline output as a banner-led document with sections "Status card" / "What was measured" / "Key findings" / "Provider failure matrix" / "What this does NOT prove" / "Next actions". The banner literal `Diagnostic only — not a merge verdict.` is the first non-title line on every output. The renderer carries a runtime negative-list backstop (`_FORBIDDEN_PRODUCT_CLAIMS`) that raises `RuntimeError` if any of `merge_safe` / `merge-safe` / `production_safe` / `production-safe` / `bug_free` / `bug-free` ever appear in a rendered output — defence-in-depth against a stale template.
* GitHub Step Summary polish (4.9-B): the composite `action.yml` cats the polished diagnostic Markdown into `$GITHUB_STEP_SUMMARY` (replacing the old `head -n 80 report.md` that surfaced legacy-audit phrasing). Falls back to the legacy excerpt only when the diagnostic file is missing.
* SARIF category disambiguation (4.9-C): `action.yml` uploader uses `category: oida-code/combined`; `.github/workflows/sarif-upload.yml` uses `category: oida-code/audit-sarif`. Two distinct categories prevent multi-upload collisions in Code Scanning. All categories use the `oida-code/` prefix so future additions can coexist.
* Action outputs ergonomics (4.9-D): the CLI's `calibration-eval` writes `<out>/action_outputs.txt` in `key=value` format (`diagnostic-status=...` + `official-field-leaks=N`); `action.yml` cats it into `$GITHUB_OUTPUT`, surfacing two new outputs: `diagnostic-status` (Literal `blocked` / `contract_failed` / `contract_clean` / `diagnostic_only`) and `official-field-leaks` (integer). The four FORBIDDEN status values (`merge_safe` / `production_safe` / `verified`) are unrepresentable — `derive_diagnostic_status` is statically constrained to the four-value Literal in `src/oida_code/report/diagnostic_report.py`.
* Provider label audit UX (4.9-E): `scripts/audit_provider_estimator_labels.py` extends the table with `provider_value` and `action` columns; the `action` column carries one of six per-classification recommendations (`label_too_strict` → "propose label revision, but do not apply automatically"; `provider_wrong` → "keep label, mark provider behaviour"; etc.). New `missing_capture` classification covers the V4 Pro 6/8 gap that Phase 4.9.0 closes upstream — when a redacted_io file is absent OR carries `failure_kind != "success"`, the row is annotated with the failure_kind so the operator can navigate to the file. Hard rule (locked by `test_label_audit_never_changes_expected_labels_automatically`): the script NEVER writes back to `expected.json`.
* Artifact bundle manifest (4.9-F): new `src/oida_code/models/artifact_manifest.py` defines `ArtifactBundleManifest` + `ArtifactRef` Pydantic shapes with three Literal pins (`mode = "diagnostic_only"`, `official_fields_emitted = False`, `contains_secrets = False` per ref). `oida-code build-artifact-manifest <bundle>` walks the bundle root, classifies every artifact by filename / parent-directory pattern, computes SHA256 (chunked, 64KB), and writes `<bundle>/artifacts/manifest.json` (excluded from its own hash list).
* Phase 4.9.0 preamble: `ProviderRedactedIO` schema widens to carry `failure_kind: Literal[7 values]` + `redacted_error: str | None`; `redacted_response_body` becomes `str | None`; `model` and `http_status` become optional (env-var-missing path has neither). `complete_json` restructured as a single try/finally with the stash in `finally` — every raise site sets `failure_kind` immediately before raising, and the runner now gets a non-None `pop_last_redacted_io()` value on failure paths too. V4 Pro 6/8 missing-capture gap closed at the source.
**Accepted:**
* diagnostic-only status cards (every diagnostic Markdown opens with the banner, ADR-22 fields shown as `blocked`)
* explicit blocked official fields (`total_v_net` / `debt_final` / `corrupt_success` always rendered as `blocked` with ADR-22 citation)
* stable action outputs (5 new outputs: `diagnostic-markdown` / `diagnostic-status` / `official-field-leaks` / `artifact-manifest` + the existing 4)
* SARIF category disambiguation (`oida-code/combined` for action.yml, `oida-code/audit-sarif` for sarif-upload.yml)
* redacted failure-path diagnostics (Phase 4.9.0 schema + try/finally stash)
* artifact manifest with SHA256 hashes (10 artifact kinds; chicken-and-egg solved by excluding the manifest from its own list)
* no raw prompt / raw response by default (Phase 4.8-A redaction layer + Phase 4.9-F per-ref `contains_raw_prompt: bool = False` / `contains_raw_response: bool = False`)
**Rejected:**
* merge-safe / production-safe / bug-free labels (renderer raises `RuntimeError` if any appear; `derive_diagnostic_status` Literal type rejects them at construction)
* provider leaderboard / public ranking (Phase 4.8 multi-provider data stays as DATA per ADR-28 + ADR-32 + ADR-33; the diagnostic report shows per-call failure_kind, not a "this provider wins" verdict)
* `total_v_net` / `debt_final` / `corrupt_success` emission (ADR-22 hard wall remains; manifest schema pins `official_fields_emitted: Literal[False]`)
* MCP / tool-calling (still deferred to Phase 5.0 design ADR; QA/A26 line 484-485 explicit; OWASP MCP-specific risks — tool poisoning, rug pulls, cross-origin/tool shadowing — keep the order: artifacts readable and measurable BEFORE additional autonomy)
* GitHub App / custom Checks API integration (still deferred per QA/A26 line 487-488)
* production thresholds / threshold tuning (still deferred per ADR-28 + QA/A26 line 490)
* Pydantic-AI as runtime framework (Phase 4.8-F spike directory remains documentary; QA/A26 line 486 explicit)
* PyPI stable release (still alpha while ADR-22 official fields remain blocked; QA/A26 line 497)
**Outcome:** Phase 4.9 ships +47 tests across 5 new test files (`test_phase4_9_diagnostic_report.py` 13 / `test_phase4_9_action_outputs.py` 9 / `test_phase4_9_step_summary_and_sarif.py` 8 / `test_phase4_9_label_audit.py` 7 / `test_phase4_9_artifact_manifest.py` 11). `complete_json` failure-path tests added to existing `test_phase4_8_redacted_provider_io.py` (10 → 16). 628 passed / 5 skipped. ruff clean, mypy clean (82 source files). New `src/oida_code/report/diagnostic_report.py` (~325 LOC) + `src/oida_code/models/artifact_manifest.py` (~210 LOC). New CLI subcommands: `render-artifacts` (4.9-A) + `build-artifact-manifest` (4.9-F). `action.yml` extended with 4 new outputs (`diagnostic-markdown` / `diagnostic-status` / `official-field-leaks` / `artifact-manifest`); SARIF uploader bumped from `@v3` to `@v4` (closing the README/action.yml inconsistency advisor flagged). README extended with the GitHub Action outputs table. Honesty statement: Phase 4.9 improves operator-facing artifacts and diagnostics; it does NOT validate production predictive performance, NOT rank providers publicly, NOT enable MCP or provider tool-calling, NOT emit official `total_v_net` / `debt_final` / `corrupt_success`, NOT create a GitHub App or custom Checks API integration, NOT modify the vendored OIDA core.

[2026-04-26 21:00:00] - **ADR-35: MCP and provider tool-calling design before implementation.**
**Why:** Phase 4.9 stabilised the operator-facing artifact surface (diagnostic-only Markdown, SARIF category disambiguation, action outputs ergonomics, artifact bundle manifest). The natural follow-on temptation is to add MCP / provider tool-calling so the LLM-estimator can pull live signal (issue metadata, logs, traces). QA/A27.md (2026-04-26) flags that as premature: MCP introduces a dynamic-tool surface (servers ship `tools/list` + `tools/call` + `tools/list_changed` notifications + JSON-RPC transport) where descriptions, schemas, and tool outputs all become prompt-injection vectors AND the tool registry can rug-pull post-approval. OWASP MCP Top 10 lists ten dominant risks (token mismanagement, privilege escalation, **tool poisoning**, supply-chain tampering, command injection, intent flow subversion, insufficient authn/authz, lack of audit/telemetry, shadow MCP servers, context injection / over-sharing). The MCP Security Best Practices document additionally calls out **confused deputy** and **token passthrough** as authorization-class risks. None of these have a structural defence in OIDA-code's current architecture; landing MCP code without a threat model + admission policy + pinning + audit log + unlock criteria would erase Phase 4.7-4.9's contract-clean posture.
**Decision:** Phase 5.0 is a DESIGN-ONLY phase. It produces six security documents under `docs/security/` plus a Pydantic-AI assessment under `experiments/pydantic_ai_spike/phase5_assessment.md`, plus a 13-section report. NO MCP runtime code. NO provider tool-calling enabled. NO MCP package added to `pyproject.toml`. NO MCP workflow under `.github/workflows/`. The existing anti-MCP locks (`test_no_mcp_workflow_or_dependency_added` and `test_no_provider_tool_calling_enabled` from `tests/test_phase4_7_provider_baseline.py`) STAY ACTIVE; Phase 5.0 EXTENDS them with a new test set in `tests/test_phase5_0_design.py` that:
* asserts every Phase 5.0 design document exists at the prescribed path
* asserts the threat model names tool poisoning, rug pull, and confused deputy
* asserts the admission policy requires schema hash pinning
* asserts the unlock criteria document keeps the locks active
* asserts no MCP dependency in `pyproject.toml`, no MCP workflow in `.github/workflows/`, no `supports_tools=True` in `src/oida_code/`
* asserts no `total_v_net` / `debt_final` / `corrupt_success` are emitted by any production code path (re-affirms ADR-22)
* asserts the report carries the prescribed honesty statement verbatim

The six security documents:
* **`docs/security/mcp_threat_model.md`** (§5.0-A): 8-section structure (Assets / Trust boundaries / Actors / Attack surfaces / Abuse cases / Required controls / Non-goals / Open questions) covering OWASP MCP01-MCP10 + confused deputy + token passthrough. 14 abuse cases enumerated with severity. 12 required controls. 6 open questions for Phase 5.x.
* **`docs/security/mcp_admission_policy.md`** (§5.0-B): MCPServerStatus enum (proposed / quarantined / approved_read_only / approved_tooling / rejected / revoked), 12-item approval checklist, 9 auto-rejection triggers, quarantine-as-one-way-street semantics, authorization policy enforcing one-token-per-server + no GITHUB_TOKEN passthrough + confused-deputy guard, operator workflow pseudocode (register / inspect / approve / revoke).
* **`docs/security/tool_schema_pinning.md`** (§5.0-C): `ToolSchemaFingerprint` Pydantic schema with `description_sha256` / `input_schema_sha256` / `output_schema_sha256` (all 64-char lowercase hex), JCS RFC 8785 canonicalisation specification, rug-pull rule (any hash drift → quarantine the entire server), per-notification behaviour, hash domain rules.
* **`docs/security/tool_call_execution_model.md`** (§5.0-D): five execution modes (disabled / schema-discovery / read-only / approved-deterministic / human-approved-write); Phase 5.0 only authorises modes 0 + 1 in design; the LLM proposes / OIDA-code executes pipeline (request → policy → adapter → EvidenceItem → aggregator) preserved unchanged; provider tool-calling forbidden by default with explicit rationale (provider-defined built-in tools + opaque command strings); list of forbidden LLM utterances ("run this shell command", "merge_safe", etc.).
* **`docs/security/mcp_audit_log_schema.md`** (§5.0-G): `MCPAuditEvent` Pydantic schema with PolicyDecision Literal (allow / block / quarantine / human_review), capability sentinel flags (secret_access_attempted / network_access_attempted / write_access_attempted), per-day per-server JSONL append-only storage, redaction rules MUST NEVER carry API key / GitHub token / raw prompt / raw provider response / raw tool output content.
* **`docs/security/mcp_unlock_criteria.md`** (§5.0-F): 10-item criteria list for removing the anti-MCP locks (threat model complete; admission policy complete; schema pinning design reviewed; no dynamic tool install; local-only sandbox design; audit log schema; allowlist-only tool registry; human approval protocol for writes; failure mode tests specified; rollback plan defined). Locks STAY ACTIVE after Phase 5.0; phrase: "Anti-MCP and anti-tool-calling tests remain active after Phase 5.0. They are not a blocker to this design phase; they are the guardrail that prevents design from becoming accidental implementation."

The Pydantic-AI assessment (`experiments/pydantic_ai_spike/phase5_assessment.md`) extends ADR-32 / ADR-33's spike-not-migration verdict to Phase 5.0: 7 evaluation questions all admit "yes, with configuration" answers (`Agent(tools=[], result_type=LLMEstimatorOutput, retries=0)` preserves shape + forbids tool-calling); recommendation = `pydantic_ai_adapter_experiment` documentary follow-on, NOT migration in Phase 5.0. Pydantic-AI's MCP integration (`pydantic_ai.mcp.MCPServerStdio` / `MCPServerSSE` / `MCPServerStreamableHTTP`) and Toolset surface are recognised as exactly the dynamic-tool risk Phase 5.0 design avoids; any future adapter MUST never import those modules and Phase 5.x test invariants would lock that import-allowlist.
**Accepted:**
* MCP threat model (10 OWASP risks + confused deputy + token passthrough)
* MCP admission policy (status enum + 12-item approval + auto-rejection list + quarantine-one-way + authz)
* Tool schema pinning design (`ToolSchemaFingerprint` + JCS canonicalisation + rug-pull rule)
* Tool-call execution model (5 modes, only 0 + 1 in scope; provider tool-calling forbidden by default)
* MCP audit log schema (`MCPAuditEvent` + capability sentinels + redaction rules + append-only JSONL)
* MCP unlock criteria (10-item list; locks STAY ACTIVE after Phase 5.0)
* Pydantic-AI Phase 5 assessment (recommendation: documentary `pydantic_ai_adapter_experiment`, NOT migration)
* Local-stdio-first recommendation for any future Phase 5.1 prototype
* No-write first prototype recommendation
* No remote MCP first prototype recommendation
* No secrets in MCP context (GITHUB_TOKEN never passed; per-server scoped credentials)
* Aggregator remains final authority (`is_authoritative: Literal[False]` unchanged)
* Existing anti-MCP locks remain ACTIVE until a future ADR removes them
**Rejected:**
* MCP runtime code in Phase 5.0 (no `src/oida_code/mcp/` package)
* Remote MCP servers in any first prototype (stdio-only)
* Provider tool-calling enabled by default (`supports_tools` stays `False` everywhere)
* Dynamic unpinned tools (auto-rejected by admission policy §3)
* Write / destructive tools in any first prototype (mode 4 deferred indefinitely)
* Token passthrough (forbidden by MCP spec; admission policy enforces structurally)
* Raw tool output trusted as instruction (always fenced into `EvidenceItem` with forbidden-phrase scan)
* Pydantic-AI runtime migration (recommendation: documentary spike, not migration)
* GitHub App / custom Checks API integration (out of scope at every phase)
* Official `total_v_net` / `debt_final` / `corrupt_success` emission (ADR-22 hard wall, independent of MCP)
* PyPI stable release (still alpha while official fields remain blocked)
**Outcome:** Phase 5.0 ships 6 new design documents under `docs/security/` (~3500 lines combined) + 1 assessment under `experiments/pydantic_ai_spike/phase5_assessment.md` (~250 lines) + ADR-35 (this entry) + `reports/phase5_0_mcp_tool_calling_design.md` (13-section report) + 1 new test file `tests/test_phase5_0_design.py` (~13 tests) + README + `memory-bank/progress.md` updates. ZERO new code under `src/oida_code/`. ZERO new dependency in `pyproject.toml`. ZERO new workflow under `.github/workflows/`. The existing Phase 4.7 anti-MCP and anti-tool-calling tests remain active; Phase 5.0 ADDS to them rather than replacing. Honesty statement (verbatim per QA/A27.md lines 899-908): Phase 5.0 is design-only. It does not add MCP runtime integration. It does not enable provider tool-calling. It does not execute MCP tools. It does not remove anti-MCP or anti-tool-calling locks. It does not validate production predictive performance. It does not emit official `total_v_net`, `debt_final`, or `corrupt_success`. It does not modify the vendored OIDA core.

[2026-04-26 22:30:00] - **ADR-36: Local deterministic tool gateway before MCP runtime.**
**Why:** Phase 5.0 (ADR-35) shipped six security design documents specifying threat model + admission policy + schema pinning + execution model + audit log + unlock criteria for MCP. The natural follow-on is to either (a) jump straight to an MCP prototype (Option B from QA/A27 line 985) or (b) prove the Phase 5.0 designs against tools OIDA-code already calls (Option A from QA/A27 line 977). QA/A28 (2026-04-26) recommends Option A: implement a local tool gateway that wraps `ruff` / `mypy` / `pytest` (the deterministic adapters already shipped in Phase 4.2) behind admission, fingerprinting, and audit-log layers — without adding MCP runtime, remote servers, or provider tool-calling. The reasoning: Option A transforms Phase 5.0's designs into runtime guard-rails on tools the project ALREADY trusts; if any of (admission / fingerprinting / audit-log / sandbox enforcement / audit-event redaction / hash drift quarantine) fails on a known-good tool, the failure surfaces ON THAT KNOWN-GOOD TOOL rather than during the introduction of an unknown MCP server. The same QA/A27 line 512 ("le projet a progressé parce qu'il a refusé les faux signaux trop tôt") applies — prove the runtime machinery on a controlled surface before opening the dynamic MCP surface.
**Decision:** Phase 5.1 implements `src/oida_code/verifier/tool_gateway/` (~1200 LOC across 6 modules):
* `contracts.py` — Pydantic schemas with three Literal pins (`requires_network: Literal[False]`, `allows_write: Literal[False]` on `GatewayToolDefinition`; `status: Literal["approved_read_only" | "quarantined" | "rejected"]` on `ToolAdmissionDecision` — Mode 3 / Mode 4 tier upgrades require schema bump + new ADR).
* `fingerprints.py` — JCS-approximation canonical-JSON serialiser (sort_keys + minimal separators + UTF-8 + ensure_ascii=False) + SHA256; documented as approximation NOT strict RFC 8785 (a future MCP integration that ingests third-party schemas MUST swap to strict JCS — see `docs/security/tool_schema_pinning.md` §3).
* `admission.py` — `admit_tool_definition` runs the 7 rules from QA/A28 §5.1-C lines 222-228 in the prescribed order; suspicious-pattern detection (regex matching "ignore previous instructions", "override policy", "send secrets", "exfiltrate", "execute shell", "write file", inner OIDA fence markers) precedes fingerprint comparison so a poisoned description NEVER reaches the hash check.
* `audit_log.py` — append-only JSONL writer at `.oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl` (NOT `.oida/mcp/audit/...` — namespace differentiation per QA/A28 §5.1.0-A line 92, "car ce n'est pas MCP"); one event per Stage-2 decision (allow / block / quarantine / reject); the schema has no `request_arguments` / `raw_stdout` / `api_key` fields — only `request_summary` (short, human-readable, redacted upstream by the caller) + `evidence_refs` IDs.
* `gateway.py` — `LocalDeterministicToolGateway.run()` returns `VerifierToolResult` exactly (NOT a new wrapper type — the gateway is a wrapper, not a new pipeline stage from the aggregator's perspective). Five-stage pipeline: registry lookup → hash drift check → existing `validate_request` (path traversal + secret-path deny) → existing `get_adapter().run()` → audit log write. Adapter exception → `status="blocked"` + audit event with `policy_decision="block"`. Adapter `tool_missing` → preserves uncertainty status (NOT a code failure or block).
* `__init__.py` — re-exports for the CLI sub-app.

CLI sub-app `oida-code tool-gateway` ships two subcommands:
* `fingerprint` — computes the four SHA256 hashes for the builtin definition set (ruff / mypy / pytest); writes `<out>/fingerprints.json`.
* `run` — drives a batch of `VerifierToolRequest` objects (loaded from JSON) through the gateway with operator-supplied `--policy` + `--approved-tools`; writes `<out>/results.json` and one audit JSONL per (tool, day).

40 new tests in `tests/test_phase5_1_tool_gateway.py` covering all 8 sub-blocks: 5.1.0 doc sync (path-malformed regression check + test count sync against the Phase 5.0 file), 5.1-A contracts (Pydantic Literal[False] pins), 5.1-B fingerprinting (key-order stability + drift detection on each of description / input_schema / output_schema), 5.1-C admission policy (7 rules including suspicious-pattern detection), 5.1-D audit log (allow / block / quarantine / reject all serialise; redaction structure check; JSONL round-trip; namespace path is `tool-gateway/` not `mcp/`), 5.1-E gateway (returns `VerifierToolResult` exactly; reuses existing sandbox path-traversal + secret-path blocks; `tool_missing` is uncertainty), 5.1-F CLI (4 tests: fingerprint outputs hashes; run requires approved tools; run writes audit log; run never emits `total_v_net` / `debt_final` / `corrupt_success`), 5.1-G no-MCP regression locks (gateway is NOT MCP — no JSON-RPC tools/list / tools/call strings, no `import mcp` / `import pydantic_ai`, no remote-transport imports `urllib` / `http` / `httpx` / `requests` / `websockets` / `aiohttp` under the gateway package).

Phase 5.1.0 doc sync: fixed `~13 tests` → `16 tests` in `reports/phase5_0_mcp_tool_calling_design.md` (lines 361, 378); enumerated test list in §10 updated to cover all 16 (was missing `test_no_mcp_runtime_import_in_src`, `test_no_official_fields_emitted`, `test_phase5_report_declares_no_code_mcp`); `test_phase5_report_audit_log_path_is_not_malformed` regression test added in `tests/test_phase5_1_tool_gateway.py` to catch any future `///` corruption in the report.
**Accepted:**
* local tools only (ruff / mypy / pytest at minimum; semgrep / codeql adapters already exist and can plug in via the same `get_adapter()` registry)
* tool schema fingerprints (4-hash variant: description / input_schema / output_schema / combined)
* admission registry (`approved` / `quarantined` / `rejected` parallel tuples; operator-driven approval)
* hash drift quarantine (gateway refuses any drifted definition; audit event with `policy_decision="quarantine"`)
* audit log per tool decision (every Stage-2 decision emits one event)
* reuse existing `ToolPolicy` (gateway calls `validate_request` from `tools/sandbox.py` rather than re-implementing path traversal / secret-path checks)
* evidence item outputs only (gateway returns `VerifierToolResult`, NOT a new wrapper; audit `evidence_refs` carry only `EvidenceItem.id` strings)
* no MCP protocol (no `tools/list` / `tools/call` JSON-RPC bindings; no `import mcp`)
* CLI fingerprint + run subcommands
**Rejected:**
* MCP SDK dependency (no `mcp` / `model-context-protocol` / `pydantic-ai` in `pyproject.toml`)
* JSON-RPC `tools/list` or `tools/call` (gateway speaks Python objects, not JSON-RPC)
* remote MCP servers (no HTTP / WebSocket / DNS imports under the gateway package)
* provider tool-calling (`ProviderProfile.supports_tools` stays `False`)
* write tools (`allows_write` pinned `Literal[False]`)
* network egress (`requires_network` pinned `Literal[False]`)
* official `total_v_net` / `debt_final` / `corrupt_success` (ADR-22 hard wall holds; CLI tests assert no such tokens in `results.json` or audit JSONL)
**Outcome:** Phase 5.1 ships 6 new modules under `src/oida_code/verifier/tool_gateway/` (~1200 LOC) + 2 new CLI subcommands + 40 new tests. ZERO new dependency in `pyproject.toml`. ZERO new workflow under `.github/workflows/`. ZERO MCP runtime code. ZERO provider tool-calling. The Phase 4.7 anti-MCP / anti-tool-calling locks remain ACTIVE; Phase 5.0's `test_anti_mcp_locks_still_active` and `test_no_supports_tools_true` remain ACTIVE; Phase 5.1 ADDS `test_tool_gateway_does_not_import_mcp` + `test_tool_gateway_has_no_tools_list_jsonrpc` + `test_tool_gateway_has_no_tools_call_jsonrpc` + `test_tool_gateway_has_no_remote_transport` + `test_tool_gateway_has_no_provider_tool_calling`. Quality gates: ruff clean, mypy clean (88 source files, +6 from Phase 5.0's 82); 685 passed / 4 skipped (was 645/4 before Phase 5.1 — that's exactly +40 new tests). Honesty statement (verbatim per QA/A28 lines 449-458): Phase 5.1 implements a local deterministic tool gateway for existing tools. It does not implement MCP. It does not enable provider tool-calling. It does not execute remote tools. It does not allow write tools or network egress. It does not validate production predictive performance. It does not emit official `total_v_net`, `debt_final`, or `corrupt_success`. It does not modify the vendored OIDA core. Per QA/A28 "Après Phase 5.1": Phase 5.2 = gateway integration into verifier loop (route verifier tool requests through the gateway, NOT directly through the old engine — still no MCP). Phase 5.3 = local stdio MCP mock prototype, contingent on schema pinning + audit log + admission registry + drift/write/network/secret blocks ALL operational AND GitHub-hosted CI staying green.

[2026-04-26 23:00:00] - **ADR-37: Gateway-grounded verifier loop before MCP runtime.**
**Why:** Phase 5.1 (ADR-36) shipped a local deterministic tool gateway with admission, fingerprinting, audit log, and sandbox enforcement, but did NOT integrate the gateway into the verifier loop. Phase 4.1's verifier (ADR-26) describes `VerifierToolCallSpec` as forward-time intent only; Phase 4.2 (ADR-27) added the deterministic adapters but kept the verifier separate. Phase 5.2 closes that loop: forward verifier proposes tool requests, the gateway validates and runs them, tool evidence becomes citable, the second forward+backward pass decides. The reasoning, per QA/A29 §5.2: opening MCP without a tool-grounded verifier loop would expose dynamic tool primitives (the JSON-RPC discovery + dispatch verbs) before the existing verifier can even cite a deterministic tool's output. Wiring the gateway into the verifier loop FIRST proves admission + fingerprinting + audit-log + citation-rule on the controlled surface. Same QA/A28 line 512 logic ("le projet a progressé parce qu'il a refusé les faux signaux trop tôt") — measure the verifier's improvement on a closed surface before opening MCP. QA/A29 §5.1.1 added a precondition: the existing gateway must lock `request.tool == gateway_definition.tool_name` (otherwise a mis-wired call could fingerprint a ruff definition while executing pytest), and `_blocked_result` must populate BOTH `warnings` and `blockers` so the loop integrator can treat blocked tool results as hard claim blockers.
**Decision:** Phase 5.2 implements:
* 5.1.1 hardening — `LocalDeterministicToolGateway.run()` Stage 0: block if `request.tool != gateway_definition.tool_name` BEFORE registry lookup. `_blocked_result` now populates `blockers=(reason,)` alongside `warnings=(reason,)`. Adapter exception path inherits both fields via the same helper.
* 5.2-A — `ForwardVerificationResult.requested_tools: tuple[VerifierToolCallSpec, ...] = ()` (default empty for Phase 4.1 replay backward-compat).
* 5.2-B — `tool_request_from_spec()` mapper at `src/oida_code/verifier/gateway_loop.py`: `VerifierToolCallSpec` → `VerifierToolRequest` with NO argv from the LLM, scope copied verbatim, purpose length-bounded at 200 chars.
* 5.2-C — `GatewayGroundedVerifierRun` Pydantic model + `run_gateway_grounded_verifier()` two-pass runner. Strict flow: pass-1 forward+backward → tool phase (each spec mapped + executed via the gateway, capped at `max_tool_calls=5`) → packet enrichment via `model_copy(update=...)` → pass-2 forward+backward → aggregate. Citation rule: any pass-2 accepted claim that does NOT cite at least one of the new `[E.tool_output.*]` refs (when tools ran) is demoted to `unsupported_claims` with a recorded warning.
* 5.2-D — `deterministic_estimates_from_tool_result()`: `failed` → one negative `SignalEstimate` (value=0.0, confidence=0.8, source="tool"), mapped to `tests_pass` for pytest and `operator_accept` for ruff/mypy/semgrep/codeql; `error`/`timeout`/`tool_missing`/`blocked` → empty tuple (uncertainty, NOT a code-failure proof).
* 5.2-E — `oida-code verify-grounded` CLI subcommand with required flags `--forward-replay-{1,2}`, `--backward-replay-{1,2}`, `--tool-policy`, `--approved-tools`, `--gateway-definitions`. Default `--audit-log-dir=.oida/tool-gateway/audit`, `--out=.oida/verifier/grounded_report.json`, `--max-tool-calls=5`. Action input `enable-tool-gateway` added with default `"false"` — Phase 5.2 does NOT make verify-grounded the default audit path.
* 5.2-F — 8 hermetic fixtures under `tests/fixtures/gateway_grounded_verifier/`: `no_tool_needed_claim_supported`, `tool_needed_then_supported`, `tool_needed_but_unapproved`, `tool_hash_drift`, `tool_failed_contradicts_claim`, `tool_error_uncertainty`, `path_traversal_blocked`, `prompt_injection_in_tool_output`. Each carries pass-{1,2} forward/backward JSON, an `executor.json` describing the simulated adapter outcome, and `NOTES.md` explaining the expected verdict.
* 5.2-G — `.github/workflows/gateway-grounded-smoke.yml` workflow on `workflow_dispatch` + push to `main`, replay-only, `permissions: contents: read`, no external provider, no secrets, no MCP, no network egress.
* 5.2-H — anti-MCP regression locks: `test_no_mcp_dependency_added`, `test_no_mcp_workflow_added`, `test_no_jsonrpc_tools_list_or_tools_call_runtime`, `test_no_provider_tool_calling_enabled`, `test_gateway_loop_is_not_mcp` (the new module's body cannot mention `modelcontextprotocol`, `mcp.server`, `stdio_server`, `json_rpc`, `jsonrpc`).

45 new tests in `tests/test_phase5_2_gateway_grounded_verifier.py` covering all sub-blocks. Negative scans target `pyproject.toml` + `.github/workflows/` + `src/oida_code/` only — never `docs/` or `reports/`.
**Accepted:**
* two-pass verifier loop (pass-1 forward → tool phase → pass-2 forward+backward → aggregate)
* forward `requested_tools` field (default empty for backward compat)
* ToolCallSpec → VerifierToolRequest mapping (no argv, no shell, scope verbatim)
* LocalDeterministicToolGateway execution (admission + fingerprint + sandbox + audit)
* audit log emission per tool decision (re-uses `.oida/tool-gateway/audit/` namespace from ADR-36)
* tool evidence appended to packet via `model_copy(update=...)` (frozen schema preserved)
* deterministic tool contradictions still win (failed pytest → negative estimate → aggregator rejects LLM claim)
* citation rule on pass-2 (claim must cite tool ref when tools ran)
* replay/fake providers only by default (external providers stay opt-in via existing optional binders)
* 5.1.1 hardening (request/definition mismatch blocked + blockers field populated)
**Rejected:**
* MCP runtime (no `mcp` / `pydantic_ai` / `modelcontextprotocol` in `pyproject.toml`)
* JSON-RPC discovery + dispatch verbs (gateway loop speaks Python objects only)
* provider tool-calling (`ProviderProfile.supports_tools` stays `False`)
* remote tools (no HTTP/WebSocket imports under `gateway_loop.py`)
* write tools (`allows_write` pinned `Literal[False]` on `GatewayToolDefinition`)
* network egress (`requires_network` pinned `Literal[False]`)
* unbounded multi-turn loops (budget: max_passes=2, max_tool_calls=5, no retries)
* official `total_v_net` / `debt_final` / `corrupt_success` (ADR-22 hard wall holds)
**Outcome:** Phase 5.2 ships 1 new module under `src/oida_code/verifier/gateway_loop.py` (~340 LOC) + 1 new CLI subcommand (`verify-grounded`) + 45 new tests + 8 hermetic fixtures + 1 new workflow + ADR-37 + `reports/phase5_2_gateway_grounded_verifier_loop.md`. Modified files: `src/oida_code/verifier/tool_gateway/gateway.py` (5.1.1 hardening), `src/oida_code/verifier/contracts.py` (`requested_tools` field), `src/oida_code/cli.py` (verify-grounded subcommand), `action.yml` (`enable-tool-gateway` reserved input). ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. The Phase 4.7 / Phase 5.0 / Phase 5.1 anti-MCP locks remain ACTIVE; Phase 5.2 ADDS `test_gateway_loop_is_not_mcp` to the chain. Honesty statement (verbatim per QA/A29 lines 412-419): Phase 5.2 integrates the local deterministic tool gateway into the verifier loop. It does not implement MCP. It does not enable provider tool-calling. It does not execute remote tools. It does not allow write tools or network egress. It does not validate production predictive performance. It does not emit official `total_v_net`, `debt_final`, or `corrupt_success`. It does not modify the vendored OIDA core. Per QA/A29 "Après Phase 5.2": option recommandée = Phase 5.3 private holdout + verifier loop calibration (mesure si le gateway-grounded verifier améliore citation fidelity / claim acceptance correctness / tool contradiction rejection / unsupported claim detection — toujours sans MCP). Option alternative = Phase 5.3 local stdio MCP mock prototype (contingent on gateway loop + audit log + hash drift quarantine + path traversal/secret/network/write blocks all operational AND GitHub-hosted CI staying green). QA/A29 prefers holdout/calibration before MCP.

[2026-04-26 23:55:00] - **ADR-38: Gateway verifier calibration before MCP prototype.**
**Why:** Phase 5.2 (ADR-37) wired the local deterministic tool gateway into the verifier loop without measuring whether the loop actually improves verifier behaviour. QA/A30 §"Phase 5.3 — objectif" frames the calibration question explicitly: does routing tool requests through the gateway improve citation fidelity, claim acceptance correctness, tool contradiction rejection, unsupported claim detection, and robustness to hostile tool outputs? The non-question (still): is the code merge-safe / does OIDA-code predict prod / can total_v_net be official / can MCP be enabled? NIST AI RMF's MEASURE function explicitly insists on documented metrics + methods after the framework's TEVV (test, evaluation, verification, validation) loop — Phase 5.3 is exactly that, scoped to the verifier loop. QA/A30 §5.2.1 added two preconditions: (1) the Phase 5.2 report must reference the live `FENCE_NAME` constant (no `<<>>` shorthand drift) so the documented anti-injection mechanism stays anchored to the source, and (2) gateway_loop must surface a blocker AND demote pass-2 accepted claims when forward requested tools but no `[E.tool_output.*]` evidence was produced — otherwise a missing definition / blocked call / no-finding adapter could let an LLM-only claim slip through under "verification_candidate" status. Phase 5.2.1-C optional: `requested_by_claim_id` on `VerifierToolCallSpec` so the Phase 5.3 calibration runner can attribute tool results to the claim they were asked to support.
**Decision:** Phase 5.3 implements:
* 5.2.1-A — Phase 5.2 report wording fixed (line 189): tool outputs now documented as `<<<OIDA_EVIDENCE id="..." kind="...">>>` ... `<<<END_OIDA_EVIDENCE id="...">>>` per the live `FENCE_NAME` constant. Canary `test_phase5_2_report_uses_current_fence_constant` imports `FENCE_NAME` and verifies the report references it.
* 5.2.1-B — `_enforce_requested_tool_evidence` in `gateway_loop.py` runs BEFORE `_enforce_pass2_tool_citation`. When `forward.requested_tools` non-empty AND `tool_phase.new_evidence == ()`, the helper adds one of three sub-case blockers (missing definition / all calls blocked / gateway ran with no findings), demotes EVERY pass-2 accepted claim to unsupported, and forces the report status off `verification_candidate`. `_run_tool_phase` returns new fields `requested_count: int` and `missing_definition_tools: tuple[str, ...]` and now emits a `blockers` entry (not just a `warnings` entry) for missing definitions.
* 5.2.1-C — `VerifierToolCallSpec.requested_by_claim_id: str | None = None` field added with default None. `tool_request_from_spec()` now resolves the explicit kwarg first, then falls back to `spec.requested_by_claim_id`.
* 5.3-C — `src/oida_code/calibration/gateway_holdout.py` with `ExpectedVerifierOutcome` (accepted / unsupported / rejected claim_ids + blockers/warnings_expected, all tuple-based) and `GatewayHoldoutExpected` (case_id, expected_baseline, expected_gateway, expected_delta Literal[improves|same|worse_expected|not_applicable], required_tool_evidence_refs, forbidden_acceptance_reasons). Frozen + extra=forbid.
* 5.3-A + 5.3-F — `datasets/private_holdout_v2/` with README.md + manifest.example.json + `cases/` (gitignored). 24-case pilot slate (8 claim_contract / 8 gateway_grounded / 4 code_outcome F2P-P2P / 4 safety_adversarial). Synthetic cases CAN be committed; private cases stay local. Contamination tiers documented (synthetic / private_trace / private_repo / public_low / public_high) with `public_high` excluded from headline metrics. Cross-link to `private_holdout_v1`.
* 5.3-D — `src/oida_code/calibration/gateway_calibration.py` (~330 LOC) + `scripts/run_gateway_calibration.py` wrapper. Pairs each holdout case's `GatewayHoldoutExpected` with two actual runs (baseline = `run_verifier`, gateway = `run_gateway_grounded_verifier`) and emits five artifacts: `baseline_metrics.json`, `gateway_metrics.json`, `delta_metrics.json` (with explicit `"delta_diagnostic_only": true` flag), `failure_analysis.md`, `artifact_manifest.json` (SHA256 hashes of all artifacts except itself). Replay-only by default; `--mode replay` is the only accepted mode.
* 5.3-E — Failure analysis Markdown table with seven columns (case_id, mode, expected, actual, classification, root_cause, recommended_action) + classification legend. Seven canonical classifications: `label_too_strict`, `gateway_bug`, `tool_adapter_bug`, `aggregator_bug`, `citation_gap`, `insufficient_fixture`, `expected_behavior_changed`. NO automatic label mutation — every row is a proposal.
* 5.3-G — Anti-MCP locks remain active. Phase 5.3 ADDS: `test_no_mcp_dependency_added` (re-affirmed), `test_no_mcp_workflow_added`, `test_no_jsonrpc_runtime_in_calibration_script`, `test_no_provider_tool_calling_enabled_in_phase5_3`.
* 5.3-H — `.github/workflows/gateway-calibration.yml` on `workflow_dispatch` + push to `main` only, replay-only, `permissions: contents: read`, no external provider, no secrets, no network, no MCP, no SARIF upload (calibration is measurement, not code-scanning). The job runs `scripts/run_gateway_calibration.py --manifest datasets/private_holdout_v2/manifest.example.json --mode replay --out .oida/gateway-calibration` and verifies all 5 expected artifacts exist before uploading them under `actions/upload-artifact@v4`.

33 new tests in `tests/test_phase5_3_gateway_calibration.py` covering: 5.2.1-A canary (1), 5.2.1-B blockers (4), 5.2.1-C field (4), 5.3-C schemas (4), 5.3-A/F dataset (4), 5.3-D runner + 5.3-E failure analysis (6), 5.3-G no-MCP locks (4), 5.3-H workflow (6). Test scoping pattern preserved from Phase 5.0/5.1/5.2: negative checks scan `pyproject.toml` + `.github/workflows/` + `src/oida_code/` only — never `docs/` or `reports/`.

The runner is **read-only over `datasets/`**: `test_calibration_runner_does_not_mutate_dataset` snapshots mtimes before and after a full run and asserts equality. The `delta_metrics.json` file carries an explicit `"reserved": "gateway_delta is diagnostic only — Phase 5.3 does NOT promote any score to official total_v_net / debt_final / corrupt_success."` field; the report follows the same RESERVED pattern that Phase 4.0 used for `official_ready_candidate`.
**Accepted:**
* baseline vs gateway comparison (replay-only by default)
* private holdout protocol with v2 vs v1 separation
* claim-level labels via `GatewayHoldoutExpected` / `ExpectedVerifierOutcome`
* tool-evidence citation metrics (evidence_ref precision/recall, fresh tool-ref citation rate)
* F2P/P2P code-outcome cases inherited from Phase 4.3 `CalibrationCase`
* failure analysis table with 7-classification vocabulary
* no automatic label mutation (runner is read-only over `datasets/`)
* replay-only CI smoke
* 5.2.1 hardening before calibration
* `requested_by_claim_id` on the spec (claim-level attribution)
**Rejected:**
* MCP runtime (no `mcp` / `pydantic_ai` / `modelcontextprotocol` in `pyproject.toml`)
* JSON-RPC discovery + dispatch verbs
* provider tool-calling (`ProviderProfile.supports_tools` stays `False`)
* remote tools, write tools, network egress
* production thresholds (`gateway_delta` is diagnostic only; no path through Phase 5.3 promotes any metric to official)
* official `total_v_net` / `debt_final` / `corrupt_success`
* SARIF upload from the calibration workflow (calibration is measurement, not code-scanning)
* automatic label mutation (operator labels written ONCE; the runner never writes back to `datasets/`)
**Outcome:** Phase 5.3 ships 2 new modules under `src/oida_code/calibration/` (`gateway_holdout.py`, `gateway_calibration.py`) + 1 new script (`scripts/run_gateway_calibration.py`) + 1 new workflow (`gateway-calibration.yml`) + 1 new dataset (`datasets/private_holdout_v2/` with README + manifest.example.json + gitignored cases dir) + 33 new tests + ADR-38 + `reports/phase5_3_gateway_verifier_calibration.md`. Modified: `src/oida_code/verifier/contracts.py` (5.2.1-C requested_by_claim_id field), `src/oida_code/verifier/gateway_loop.py` (5.2.1-B new helper + missing-definition blocker + new accounting fields on `_ToolPhaseOutput`), `reports/phase5_2_gateway_grounded_verifier_loop.md` (5.2.1-A fence wording fix), `.gitignore` (new private_holdout_v2/cases/ entry). ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. The Phase 4.7 / Phase 5.0 / Phase 5.1 / Phase 5.2 anti-MCP locks remain ACTIVE; Phase 5.3 ADDS 4 more locks on the new calibration script + workflow specifically. Quality gates: ruff clean (full curated CI scope), mypy clean (92 source files; was 89 before Phase 5.3), pytest 763 passed / 4 skipped (was 730/4 — exactly +33 new tests). Honesty statement (verbatim per QA/A30 lines 410-416): Phase 5.3 calibrates the gateway-grounded verifier loop on controlled holdout cases. It does not implement MCP. It does not enable provider tool-calling. It does not validate production predictive performance. It does not tune production thresholds. It does not emit official `total_v_net`, `debt_final`, or `corrupt_success`. It does not modify the vendored OIDA core. Per QA/A30 "Après Phase 5.3": if the calibration shows clear improvement, Phase 5.4 = integrate gateway-grounded verifier as opt-in action path (still with `enable-tool-gateway=false` default); if improvement is weak/negative, Phase 5.4 = fix verifier prompts/labels/tool-request policy; only much later, Phase 5.5+ = local stdio MCP mock prototype, contingent on gateway improving metrics + holdout stability + clean tool citations + tool contradictions rejected + no-MCP locks still green.

[2026-04-27 00:30:00] - **ADR-39: Real gateway calibration before action integration.**
**Why:** Phase 5.3 (ADR-38) shipped the calibration protocol + scaffolding, but the QA/A30 reviewer noted (correctly) that the example v2 manifest carried no executable replays — every case was classified `insufficient_fixture` and the runner returned stub metrics. QA/A31 is therefore a "run the protocol on real fixtures" phase: the question Phase 5.4 has to answer is whether the gateway-grounded verifier actually improves verifier quality on a controlled holdout, before exposing `verify-grounded` through the GitHub Action. Without that evidence, integrating the gateway as an action path even as opt-in would be a Phase-3-style move (a signal that looks convincing but is confounded — the same trap the v0.4.1 review wedged the project off). QA/A31 §5.2.1-A flagged the residual `<<<OIDA_EVIDENCE>>>` (no attributes) in the Phase 5.3 fence-wording fix; QA/A31 §5.2.1-B flagged that gateway_loop.py's existing post-pass-2 rules were a no-op when forward requested a tool but no `[E.tool_output.*]` evidence ended up in the enriched packet (missing definition / all calls blocked / no-finding adapter); QA/A31 §5.2.1-C suggested adding `requested_by_claim_id` to `VerifierToolCallSpec` so the calibration runner can attribute tool results to their requesting claim. The advisor's central recommendation: pick the 5-value recommendation literal `integrate_opt_in|revise_prompts|revise_labels|revise_tool_policy|insufficient_data` and fold the inconsistent line-226 (`revise_policy`) and line-238 (`revise_gateway_or_labels`) wording from QA/A31 into the canonical set; default F2P/P2P to the canned-executor pattern (option b) instead of invoking real pytest from the calibration runner; keep `private_holdout_v2/` for operator-private fixtures and ship `gateway_holdout_public_v1/` as a separate fully-public synthetic dataset so the GitHub-hosted `gateway-calibration.yml` workflow has runnable cases without requiring operator-local state.
**Decision:** Phase 5.4 implements:
* 5.2.1-A — Phase 5.2 report fence wording rewritten on line 189 to the explicit `<<<OIDA_EVIDENCE id="..." kind="...">>>` ... `<<<END_OIDA_EVIDENCE id="...">>>` form referencing the live `FENCE_NAME` constant. (Already shipped in Phase 5.3; QA/A31 confirms acceptance.)
* 5.2.1-B — `_enforce_requested_tool_evidence` helper added to `gateway_loop.py`, runs BEFORE `_enforce_pass2_tool_citation`. (Already shipped in Phase 5.3.)
* 5.2.1-C — `VerifierToolCallSpec.requested_by_claim_id: str | None = None` (already shipped Phase 5.3); `tool_request_from_spec` resolves the explicit kwarg first, then falls back to the spec's own attribution.
* 5.4-A0 — `run_calibration` rewritten end-to-end. The stub fallback is preserved for cases that don't ship the full required-fixture set (so `private_holdout_v2/manifest.example.json` still produces the artifacts), but the runner now executes both modes per case when all 11 required files are present. New helper `_run_one_case` loads `packet.json` + `expected.json` + `tool_policy.json` (with `repo_root` rebound to the case dir) + `gateway_definitions.json` + `approved_tools.json` + the 6 replay JSONs + an optional `executor.json`, then drives `run_verifier` (baseline) and `run_gateway_grounded_verifier` (gateway), compares outcomes against `GatewayHoldoutExpected.expected_baseline` / `expected_gateway`, and accumulates per-mode `_PerModeMetrics` (now 14 fields covering claim accept accuracy, macro-F1 proxy, fresh tool-ref citation rate, tool contradiction rejection rate, evidence-ref precision/recall, official-field leak count). Per-case audit logs land at `<out_dir>/audit/<case_id>/<yyyy-mm-dd>/<tool>.jsonl` to keep calibration runs out of `.oida/tool-gateway/audit/`.
* 5.4-A — NEW `datasets/gateway_holdout_public_v1/` with README + `manifest.json` listing 8 fully-committed synthetic cases. The `cases/` directory is committed (no gitignore entry for v1) so the GitHub-hosted workflow can run against it. Cross-link to v1 (Phase 4.8-C operator-private provider regressions) and v2 (Phase 5.3 operator-private gateway labels).
* 5.4-B — All seven mandatory cases from QA/A31 §5.4-B are present + 1 sentinel: `tool_needed_then_supported` (improves), `claim_supported_no_tool_needed` (same — sentinel), `tool_failed_contradicts_claim` (improves), `tool_requested_but_blocked` (worse_expected — empty admission registry), `hash_drift_quarantine` (worse_expected — drifted definition), `prompt_injection_in_tool_output` (improves — pass-2 declines on contaminated stdout), `negative_path_missing` (improves — observability claim demoted), `f2p_p2p_regression` (improves — P2P-style failure rejects fix claim).
* 5.4-C — `decision_summary.json` emitted by the runner with the 13-key schema from QA/A31 §5.4-C, including the 5-value recommendation Literal `integrate_opt_in | revise_prompts | revise_labels | revise_tool_policy | insufficient_data`, plus `recommendation_diagnostic_only: true` and a verbatim `reserved` warning. Decision rules: `official_field_leak_count > 0` → `revise_tool_policy`; `cases_runnable < 12` → `insufficient_data`; `claim_accept_accuracy_delta > 0.05` → `integrate_opt_in`; `< -0.05` → `revise_labels`; otherwise → `revise_prompts`. The 8-case pilot recommendation lands at `insufficient_data` (n < 12) even though `claim_macro_f1_delta` is `+0.6667` and `tool_contradiction_rejection_rate_delta` is `+0.4` — preserving the discipline that a positive delta on a small slate is NOT a green light.
* 5.4-D — Failure analysis Markdown table extended with two new columns (`actual_delta`, `label_change_proposed`) and the new `tool_request_policy_gap` classification. The runner's per-case classifier returns `(classification, root_cause, proposed_action, label_change_proposed)`; `label_change_proposed=true` is set ONLY when both modes diverge from expected (a hint, never a mutation).
* 5.4-E — Audit log review tests: `test_every_gateway_case_writes_audit_log` (every case requesting a tool produces a per-case audit JSONL), `test_blocked_tool_call_has_audit_event` (the empty-admission case writes one block event), `test_quarantined_tool_call_has_audit_event` (the drifted-fingerprint case writes one quarantine event), `test_missing_definition_has_blocker` (a synthetic test-only case with empty `gateway_definitions.json` lands in the failure analysis), `test_audit_log_contains_no_secret_like_values` (every JSONL line is scanned for forbidden substrings).
* 5.4-F — `.github/workflows/gateway-calibration.yml` updated to point `--manifest` at `datasets/gateway_holdout_public_v1/manifest.json`, asserts the SIX expected artifacts (added `decision_summary.json`), and runs an inline `official_field_leak_count == 0` gate before uploading via `actions/upload-artifact@v4`.
* 5.4-G — Anti-MCP locks remain active. Phase 5.4 ADDS: `test_no_mcp_runtime_in_calibration_module` (gateway_calibration.py body cannot mention `modelcontextprotocol`, `mcp.server`, `stdio_server`, `json_rpc`, `jsonrpc`); `test_no_provider_tool_calling_enabled_in_phase5_4` (regex scan against OpenAI/Anthropic SDK tool-calling shapes); `test_action_yml_does_not_default_enable_tool_gateway_true` (action.yml's `enable-tool-gateway` default stays `"false"`).
* Anti-mutation extension: `test_runner_does_not_mutate_public_holdout` snapshots mtimes across both `datasets/gateway_holdout_public_v1/` and (transitively) `datasets/private_holdout_v2/`. The runner is read-only over EVERY committed dataset.

23 new tests in `tests/test_phase5_4_real_calibration.py`. Two Phase 5.3 tests updated to align with the Phase 5.4 schema extension (`test_failure_analysis_md_lists_required_columns` now checks the 10-column table, `test_calibration_failure_classifications_are_documented` now expects 8 classifications including `tool_request_policy_gap`).

8-case pilot calibration result on the `gateway_holdout_public_v1/manifest.json` (from `python scripts/run_gateway_calibration.py --manifest datasets/gateway_holdout_public_v1/manifest.json --mode replay --out .oida/gateway-calibration`):

| Metric | Baseline | Gateway | Delta |
|---|---|---|---|
| `claim_accept_accuracy` | 1.0 | 1.0 | 0.0 |
| `claim_macro_f1` | 0.3333 | 1.0 | +0.6667 |
| `evidence_ref_precision` | 0.0 | 0.3333 | +0.3333 |
| `evidence_ref_recall` | 0.0 | 0.2 | +0.2 |
| `tool_contradiction_rejection_rate` | 0.0 | 0.4 | +0.4 |
| `fresh_tool_ref_citation_rate` | 0.0 | 0.5 | +0.5 |
| `official_field_leak_count` | 0 | 0 | 0 |

`gateway_improves_count: 5`, `gateway_same_count: 1`, `gateway_worse_count: 2`. Recommendation: `insufficient_data` (n=8 < 12 threshold, even though every macro-F1 / contradiction / fresh-ref delta is positive).
**Accepted:**
* runnable synthetic/public holdout subset (8 cases, fully committed, NO gitignore entry for v1)
* private holdout protocol remains (v2 cases stay gitignored)
* baseline vs gateway comparison via real `run_verifier` + `run_gateway_grounded_verifier` execution
* `decision_summary.json` with the 5-value recommendation Literal
* failure analysis with proposed label changes ONLY (no automatic mutation)
* audit logs checked for every tool call (per-case audit dirs under `<out>/audit/<case_id>/`)
* anti-mutation invariant extended over both datasets
* replay-only CI workflow pointing at the public dataset
* F2P/P2P discipline preserved semantically via canned `executor.json` per case
* 5.2.1 hardening already shipped (Phase 5.3); Phase 5.4 inherits it without modification
**Rejected:**
* action integration before gateway_delta evidence (`enable-tool-gateway` stays default `"false"`; the workflow runs the calibration in isolation, NOT inside `audit`)
* MCP runtime, JSON-RPC discovery + dispatch verbs
* provider tool-calling, remote/write/network tools
* official `total_v_net` / `debt_final` / `corrupt_success`
* automatic label mutation (every divergence is a PROPOSAL via `label_change_proposed=true`)
* PyPI stable release (project remains alpha while official fields are blocked)
* production thresholds (`gateway_delta` is diagnostic only; the recommendation literal is operator-facing, not consumer-facing)
**Outcome:** Phase 5.4 ships 1 new module under `src/oida_code/calibration/gateway_calibration.py` (substantial rewrite, ~720 LOC; was ~330 in Phase 5.3) + 1 new dataset (`datasets/gateway_holdout_public_v1/` — 8 cases × 11–12 files each) + 1 new helper script (`scripts/_build_phase5_4_cases.py` — fixture builder) + 23 new tests + 2 Phase-5.3 test updates + ADR-39 + `reports/phase5_4_real_gateway_calibration.md`. Modified: `.github/workflows/gateway-calibration.yml` (manifest path + 6 artifacts + leak gate), `reports/phase5_2_gateway_grounded_verifier_loop.md` (no-op, fence wording already correct from Phase 5.3). ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. ZERO modification of the vendored OIDA core. The Phase 4.7 / Phase 5.0 / Phase 5.1 / Phase 5.2 / Phase 5.3 anti-MCP locks remain ACTIVE; Phase 5.4 ADDS 4 more locks. Quality gates: ruff clean (full curated CI scope), mypy clean (92 source files; same count as Phase 5.3 because the new file is in a directory mypy already scanned), pytest 786 passed / 4 skipped (was 763/4 — exactly +23 new tests). Honesty statement (verbatim per QA/A31 lines 379-386): Phase 5.4 measures the gateway-grounded verifier on runnable holdout fixtures. It does not implement MCP. It does not enable provider tool-calling. It does not make verify-grounded default. It does not validate production predictive performance. It does not tune production thresholds. It does not emit official `total_v_net`, `debt_final`, or `corrupt_success`. It does not modify the vendored OIDA core. Per QA/A31 "Après Phase 5.4": with the 8-case slate, every secondary delta is positive (macro-F1 +0.67, contradiction-rejection +0.4, fresh-ref-citation +0.5) but the primary delta (`claim_accept_accuracy_delta`) is 0.0 because the baseline already accepts every claim with event evidence — that is itself diagnostic information, not a "gateway has no effect" signal. The recommendation `insufficient_data` (n=8 < 12) is honest: the slate is too small to commit to integration. Phase 5.5 = either expand the runnable slate to 12+ cases AND re-evaluate, OR (if the labels turn out to need calibration first) revise the verifier prompts/labels/tool-request policy. MCP remains explicitly deferred to Phase 5.6+ at the earliest, contingent on Phase 5.5 producing a clear `integrate_opt_in` recommendation.


[2026-04-27 12:00:00] - **ADR-40: Runnable gateway holdout expansion before action opt-in.**
**Why:** Phase 5.4 (ADR-39) showed that the gateway-grounded verifier produces strongly positive secondary deltas (macro-F1 +0.6667, tool-contradiction-rejection +0.4, fresh-tool-ref-citation +0.5, evidence-ref precision/recall +0.3333/+0.2) on an 8-case fully-public synthetic slate — but the recommendation honestly landed at `insufficient_data` because n=8 < 12. QA/A32 picks up exactly there: expand the runnable slate before deciding go/no-go on action integration, with three additional preconditions: (5.5.0-A) Phase 5.4 report audit-log path used `<placeholder>` angle brackets that some Markdown renderers strip, leaving `/audit///.jsonl`; replace with literal example values + canary tests; (5.5.0-B) the Phase 5.4 `claim_macro_f1` proxy `2*TP/(2*TP+FP+FN)` was numerically equivalent to true F1 but did NOT expose precision and recall separately, hiding any asymmetric P/R splits — refactor to a per-class `_PerClassConfusion` dataclass tracking TP/FP/FN explicitly; (5.5.0-C) rename the recommendation `integrate_opt_in` -> `integrate_opt_in_candidate` to make it unambiguous that even a positive recommendation does NOT promote anything in this phase, and add `promotion_allowed: false` as a STRUCTURAL pin (hardcoded False, not derived from the recommendation) so the operator cannot mistake the diagnostic for a green light. The advisor central guidance: order matters — refactor the metrics first (5.5.0-B), then rename + pin (5.5.0-C), then fix the report wording (5.5.0-A), then build the four mandatory cases (5.5-A). Don't add classifications you can't actually emit; the new `tool_budget_gap` and `uncertainty_preserved` rows are added ONLY because the four new cases actually exercise them.
**Decision:** Phase 5.5 implements:
* 5.5.0-A — Phase 5.4 report audit-log path rewritten on lines 215–230 from `<out>/audit/<case_id>/<yyyy-mm-dd>/<tool>.jsonl` to a literal example `.oida/gateway-calibration/audit/tool_needed_then_supported/2026-04-26/pytest.jsonl` with each component named explicitly. Two canary tests added (`test_phase5_4_report_audit_log_path_is_not_malformed` checks for the truncated `/audit///.jsonl` form, `test_phase5_4_report_mentions_case_id_date_tool_path` scans for each component independently rather than running a regex over slashes — the advisor preferred shape).
* 5.5.0-B — `_PerModeMetrics` refactored. Three `_PerClassConfusion` fields (accepted, unsupported, rejected) replace the six flat `*_correct` / `*_wrong` counters. Each `_PerClassConfusion` carries `tp` / `fp` / `fn` and methods `precision()` / `recall()` / `f1()` (zero-safe). The new `claim_macro_f1` is the mean of three per-class F1 scores; numerically equal to the Phase 5.4 proxy when FP and FN sum to the same wrong-count, but the metric JSON now exposes `accepted_precision`, `accepted_recall`, `accepted_f1` (and similar for unsupported / rejected) so any asymmetric P/R splits become visible. `_update_metrics` now computes FP / FN explicitly via set differences (`actual_C - expected_C` for FP, `expected_C - actual_C` for FN). Phase 5.4 `to_json()` keys (`accepted_correct`, `accepted_wrong`, etc.) remain in the output as backward-compat aliases derived from the new dataclass.
* 5.5.0-C — `_RECOMMENDATION_LITERAL` renamed `integrate_opt_in` -> `integrate_opt_in_candidate`. `decision_summary.json` carries a new `promotion_allowed: false` STRUCTURAL pin — hardcoded `False` regardless of recommendation. `_decide_recommendation` rewritten with five rules in QA/A32 §5.5-C order: (1) leak -> `revise_tool_policy`; (2) cases_runnable < 12 -> `insufficient_data`; (3) macro-F1 > +0.05 AND tool-contradiction non-negative AND evidence-precision non-negative AND no critical gateway_bug -> `integrate_opt_in_candidate`; (4) macro-F1 < -0.05 -> `revise_labels`; (5) otherwise -> `revise_prompts`. Phase 5.4 used `gateway_delta_accept_acc` as the discriminator; Phase 5.5 switches to `gateway_delta_macro_f1` because accept-accuracy was 0.0 on the Phase 5.4 slate (both modes always accepted the labelled set) — macro-F1 is the metric that actually moves.
* 5.5-A — `datasets/gateway_holdout_public_v1/manifest.json` extended from 8 to 12 cases with the four mandatory Phase 5.5 additions: `tool_missing_uncertainty`, `tool_timeout_uncertainty`, `multi_tool_static_then_test`, `duplicate_tool_request_budget`. New `scripts/_build_phase5_5_cases.py` builds them deterministically. The runner gained two changes: optional per-tool `by_tool` executor schema (so multi-tool cases can return distinct outcomes per binary), and `tool_policy.max_tool_calls` is now wired through to `run_gateway_grounded_verifier(max_tool_calls=...)` so the budget cap is observable in the audit log.
* 5.5-B — Baseline + gateway runs executed against the expanded 12-case slate. The runner produces the same six artifacts plus per-case audit logs.
* 5.5-C — `decision_summary.json` schema unchanged from Phase 5.4 except for the renamed recommendation Literal + new `promotion_allowed: false` pin + the `reserved` warning rewritten to mention the pin.
* 5.5-D — `failure_analysis.md` extended with two more proposal columns (`tool_request_policy_change_proposed`, `prompt_change_proposed`) for a 12-column table. Two new classifications added to `FAILURE_CLASSIFICATIONS`: `tool_budget_gap` and `uncertainty_preserved`. Both are documented in the legend. The classifier auto-sets `tool_request_policy_change_proposed=true` on `gateway_bug` rows and `prompt_change_proposed=true` on `aggregator_bug` rows. The runner NEVER mutates labels, policies, or prompts — every flag is a hint.
* 5.5-E — Private holdout protocol unchanged.
* 5.5-F — Anti-MCP locks remain active; Phase 5.5 ADDS 6 more.

Phase 5.5 calibration result on the 12-case slate: macro-F1 delta +0.6667, tool-contradiction-rejection delta +0.4286, fresh-tool-ref-citation +0.6667, evidence-ref precision delta +0.4, evidence-ref recall delta +0.2857, official_field_leak_count = 0. `gateway_improves_count: 8`, `gateway_same_count: 2`, `gateway_worse_count: 2`. Recommendation: **`integrate_opt_in_candidate`** with `promotion_allowed: false`. Every QA/A32 §5.5-C precondition satisfied: cases_runnable=12 ≥ 12, macro-F1 > +0.05, tool-contradiction ≥ 0, evidence-precision ≥ 0, zero `gateway_bug` classifications, zero leaks.

35 new tests in `tests/test_phase5_5_holdout_expansion.py` + 2 audit-log canaries in `tests/test_phase5_4_real_calibration.py`. One Phase 5.4 test renamed; one Phase 5.3 test extended (now expects 10 classifications including `tool_budget_gap` + `uncertainty_preserved`).
**Accepted:**
* runnable public synthetic holdout expanded to 12 cases (every case fully committed)
* private holdout protocol unchanged
* baseline vs gateway comparison via real `run_verifier` + `run_gateway_grounded_verifier` execution on every case
* `decision_summary.json` with `integrate_opt_in_candidate` recommendation + `promotion_allowed: false` STRUCTURAL pin + `recommendation_diagnostic_only: true`
* failure analysis with three proposal columns
* TRUE per-class macro-F1
* audit logs checked for every tool call
* anti-mutation invariant extended
* `tool_policy.max_tool_calls` wired through to gateway loop
* tool_missing / timeout preserve uncertainty
**Rejected:**
* `enable-tool-gateway` action integration (still reserved with default "false")
* `verify-grounded` becoming the default action subcommand
* MCP runtime, JSON-RPC discovery + dispatch verbs, MCP SDK dependency
* provider tool-calling, remote/write/network tools
* official `total_v_net` / `debt_final` / `corrupt_success`
* `merge_safe` / `production_safe` / `bug_free` / `security_verified` semantics
* automatic label / tool-request policy / prompt mutation
* PyPI stable release
* production thresholds
**Outcome:** Phase 5.5 ships 1 substantial rewrite of `src/oida_code/calibration/gateway_calibration.py` (~870 LOC, was ~720) + 1 new fixture-builder script + 4 new public synthetic cases + 35 new tests + 2 canaries + 2 Phase-5.3/5.4 test updates + ADR-40 + `reports/phase5_5_gateway_holdout_expansion.md`. Modified: `reports/phase5_4_real_gateway_calibration.md` (audit-log wording), `datasets/gateway_holdout_public_v1/manifest.json` (manifest_version v1.2 + 4 new entries). ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. ZERO modification of the vendored OIDA core. The Phase 4.7 / Phase 5.0 / Phase 5.1 / Phase 5.2 / Phase 5.3 / Phase 5.4 anti-MCP locks remain ACTIVE; Phase 5.5 ADDS 6 more. Quality gates: ruff clean, mypy clean (92 source files), pytest 821 passed / 4 skipped (was 786/4 — +35 new tests). Honesty statement (verbatim per QA/A32 lines 447-455): Phase 5.5 expands and recalibrates the runnable gateway holdout. It does not make verify-grounded the default. It does not integrate MCP. It does not enable provider tool-calling. It does not allow write tools or network egress. It does not validate production predictive performance. It does not tune production thresholds. It does not emit official total_v_net, debt_final, or corrupt_success. It does not modify the vendored OIDA core. Per QA/A32 "Après Phase 5.5": the 12-case expansion produced an `integrate_opt_in_candidate` recommendation with all preconditions met, so Phase 5.6 = integrate the gateway-grounded verifier as an OPT-IN action path with `enable-tool-gateway: false` default + workflow_dispatch / explicit input only + replay/fake by default + no external provider + no MCP + no write/network + no official fields.


[2026-04-27 14:00:00] - **ADR-41: Gateway-grounded verifier as explicit opt-in action path.**
**Why:** Phase 5.5 (ADR-40) produced an `integrate_opt_in_candidate` recommendation with `promotion_allowed=false` on the 12-case expanded slate. Per QA/A32 §"Apres Phase 5.5", the next step is to expose `verify-grounded` through the composite GitHub Action — but ONLY as an explicit opt-in path that downstream callers must enable per workflow. The default audit path stays unchanged (Phase 4.9 / ADR-34 behaviour). QA/A33 reinforces three security invariants: (1) `enable-tool-gateway` must default to `"false"`; (2) the gateway path must NEVER run on `pull_request` / `pull_request_target` events because pytest can execute repo code from an untrusted PR, which is a classic RCE vector that GitHub's own docs warn about; (3) the action must consume an explicit replay bundle on disk (validated against an 8-file allowlist + path-traversal guard + secret/provider/MCP filename rejection) so the gateway path stays hermetic with no LLM call, no provider tool-calling, no MCP runtime, no JSON-RPC dispatch, and no write or network tools.
**Decision:** Phase 5.6 implements:
* 5.6-A — `action.yml` gains three new inputs alongside the now-implemented `enable-tool-gateway`: `gateway-bundle-dir` (path on disk, default empty), `gateway-output-dir` (default `.oida/gateway-grounded`), `gateway-fail-on-contract` (default `"false"`). The `enable-tool-gateway` description now reflects implementation rather than "RESERVED".
* 5.6-B — new `src/oida_code/action_gateway/bundle.py` with `validate_gateway_bundle(bundle_dir, *, workspace_root=None) -> GatewayBundleValidationResult`. Eight required files: `packet.json`, `pass1_forward.json`, `pass1_backward.json`, `pass2_forward.json`, `pass2_backward.json`, `tool_policy.json`, `gateway_definitions.json`, `approved_tools.json`. The validator rejects path traversal (per-file `.resolve().relative_to(...)` check that catches `..` segments and out-of-bundle symlinks), secret-shaped filenames (`.env*`, `*.pem`, `*.key`, `id_rsa*`, `*credentials*`, etc.), provider config (`provider.yml`, `openai.yml`, etc.), and MCP config (`mcp.yml`, `modelcontextprotocol*`, etc.). Exposed via the new CLI subcommand `oida-code validate-gateway-bundle <dir> [--workspace-root <p>]` which exits 2 on failure with one stderr line per finding.
* 5.6-C — action.yml gains a new step "Phase 5.6 — gateway-grounded verifier (opt-in)" with `id: gateway` that always runs (so `steps.gateway.outputs.X` is always set). The step branches on `ENABLE_TOOL_GATEWAY`: when `"false"`, emits known-empty outputs with `gateway-status=disabled`; when `"true"`, validates the bundle, runs `oida-code verify-grounded`, derives the gateway-status, renders the summary, builds the artifact manifest (reusing the Phase 4.9-F `build-artifact-manifest` helper), and appends summary to `$GITHUB_STEP_SUMMARY` + outputs to `$GITHUB_OUTPUT`. Operator-controlled inputs travel through `env:` (Phase 4.5.1 anti-shell-injection rule), never inline `${{ inputs.X }}` in `run:` blocks.
* 5.6-D — new `src/oida_code/action_gateway/summary.py` with `render_gateway_summary(...)` plus `_scan_for_forbidden_phrases` runtime check. The renderer scans the rendered text for `merge_safe` / `merge-safe` / `production_safe` / `verified` / `bug_free` / `security_verified` / `total_v_net` / `debt_final` / `corrupt_success` and raises `ForbiddenSummaryPhraseError` on any hit. The Markdown table is diagnostic-only: enabled / mode / official-fields-blocked / status / tool-call count / blocked-tool count / accepted-claim count / unsupported-claim count / rejected-claim count / bundle / audit-log path. Exposed via `oida-code render-gateway-summary <report.json> --out summary.md ...`.
* 5.6-E — new `src/oida_code/action_gateway/status.py` with `GatewayStatus = Literal["disabled","diagnostic_only","contract_clean","contract_failed","blocked"]` and `derive_gateway_status(...)`. Product verdicts (`merge_safe`, `verified`, `production_safe`, `bug_free`) are STRUCTURALLY unrepresentable — the type checker pins the return type to the 5-value Literal. `decision_summary`-style logic: leak count > 0 → `contract_failed`; bundle invalid → `contract_failed`; pre-execution block → `blocked`; otherwise → `diagnostic_only`. Exposed via `oida-code emit-gateway-status --out action_outputs.txt ...` which writes 5 keys: `gateway-status`, `gateway-report-json`, `gateway-summary-md`, `gateway-audit-log-dir`, `gateway-official-field-leak-count`. The CLI subcommand also runs a runtime forbidden-token scan over the grounded report when `--grounded-report` is supplied — leak count > 0 forces `gateway-status=contract_failed`.
* 5.6-F — new `.github/workflows/action-gateway-smoke.yml` on `workflow_dispatch` + push to main, `permissions: contents: read`, no secrets, no external provider, no MCP, no network egress. Calls the composite action with `enable-tool-gateway: "true"` and a committed bundle fixture. Asserts the 4+1 expected gateway artifacts (`grounded_report.json`, `summary.md`, `action_outputs.txt`, `audit/`, `artifacts/manifest.json`), runs an inline forbidden-token scan over the report JSON, asserts the `gateway-status` action output is in the canonical 5-value enum, and uploads the artifact bundle. New `tests/fixtures/action_gateway_bundle/tool_needed_then_supported/` ships the 8 required files using the QA-spec'd filenames (no `gateway_` prefix on replays — the action's invocation maps them to the `verify-grounded` CLI flags).
* 5.6-G — action.yml gains a hard guard step "Phase 5.6 — block gateway on PR / fork PR" that fires only when `inputs.enable-tool-gateway == 'true'` AND event is `pull_request` or `pull_request_target`. Emits `::error::` and exits 2. Reasoning: pytest CAN execute repo code, so the gateway path is unsafe on contributions from untrusted forks. The new smoke workflow itself is restricted to `workflow_dispatch` + push to main (matching the existing `gateway-grounded-smoke.yml` posture), so the guard is defence-in-depth rather than the primary control.
* 5.6-H — every operator-controlled value used by the gateway step is lifted to `env:` (`ENABLE_TOOL_GATEWAY`, `BUNDLE_DIR`, `GATEWAY_OUTPUT_DIR`, `GATEWAY_FAIL_ON_CONTRACT`, `GH_WORKSPACE`) and referenced as bash variables in `run:`. No `${{ inputs.gateway-* }}` interpolation anywhere inside `run: |` blocks. Three regression tests lock in the rule by parsing action.yml and walking the gateway step's run block.
* 5.6-I — 48 new tests in `tests/test_phase5_6_action_gateway_opt_in.py` covering all eight sub-blocks plus end-to-end CLI flow against the fixture and an anti-mutation invariant on the fixture directory. ADR-41 + `reports/phase5_6_gateway_action_opt_in.md` + README + progress.md updates.

Quality gates: ruff clean (full curated CI scope), mypy clean (96 source files, +4 from Phase 5.5 — the new `action_gateway/` package adds 3 modules + the bundle validator), pytest 872 passed / 4 skipped (was 824/4 before Phase 5.6 — exactly +48 new tests).
**Accepted:**
* `enable-tool-gateway: "false"` default; opt-in via explicit operator input
* explicit replay bundle on disk; no LLM call, no provider tool-calling, no MCP runtime
* per-file path-traversal guard + secret/provider/MCP filename rejection
* hard guard against `pull_request` / `pull_request_target` events
* gateway-status as a 5-value `Literal` — product verdicts unrepresentable
* runtime forbidden-phrase scan inside `render_gateway_summary`
* runtime forbidden-token leak scan in `emit_gateway_status`
* reuse of Phase 4.9-F `build-artifact-manifest` for the gateway output dir
* shell-injection guard via `env:` + bash variables (Phase 4.5.1 rule)
* replay-only smoke workflow on `workflow_dispatch` + push to main only
**Rejected:**
* `verify-grounded` becoming the default audit path
* gateway execution on `pull_request` / `pull_request_target` events
* MCP runtime, JSON-RPC dispatch, MCP SDK dependency
* provider tool-calling, remote/write/network tools
* official `total_v_net` / `debt_final` / `corrupt_success`
* `merge_safe` / `verified` / `production_safe` / `bug_free` semantics anywhere on the action surface
* PyPI stable release
* GitHub App / custom Checks API
**Outcome:** Phase 5.6 ships 1 new package (`src/oida_code/action_gateway/` with `bundle.py` / `status.py` / `summary.py` / `__init__.py`, ~640 LOC total) + 3 new CLI subcommands (`validate-gateway-bundle`, `render-gateway-summary`, `emit-gateway-status`) + a substantial `action.yml` rewrite (3 new inputs + 5 new outputs + 1 PR guard step + 1 gateway exec step + 1 upload step) + 1 new fixture bundle (`tests/fixtures/action_gateway_bundle/tool_needed_then_supported/` with 8 required files + executor.json + README) + 1 new GH workflow (`action-gateway-smoke.yml`) + 48 new tests + ADR-41 + `reports/phase5_6_gateway_action_opt_in.md`. ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. ZERO modification of the vendored OIDA core. The Phase 4.7 / 5.0 / 5.1 / 5.2 / 5.3 / 5.4 / 5.5 anti-MCP locks remain ACTIVE; Phase 5.6 ADDS 4 more locks (`test_no_mcp_dependency_added_phase5_6`, `test_no_mcp_workflow_added_phase5_6`, `test_no_provider_tool_calling_enabled_phase5_6`, `test_action_gateway_module_does_not_import_mcp_runtime`). Quality gates: ruff clean, mypy clean (96 source files), pytest 872 passed / 4 skipped (+48 tests). Honesty statement (verbatim per QA/A33 lines 354-360): Phase 5.6 exposes the gateway-grounded verifier as an explicit opt-in GitHub Action path. It remains disabled by default. It does not make verify-grounded the default audit path. It does not implement MCP. It does not enable provider tool-calling. It does not run on fork PRs. It does not validate production predictive performance. It does not emit official total_v_net, debt_final, or corrupt_success. It does not modify the vendored OIDA core. Per QA/A33 "Apres Phase 5.6": if the smoke is green and the artifact pipeline holds, Phase 5.7 = operator soak on real repos (3-5 controlled PRs, collect artifacts, measure FP/FN, keep `enable-tool-gateway` default false). MCP remains explicitly deferred.


[2026-04-27 16:00:00] - **ADR-42: Operator soak before wider gateway adoption.**
**Why:** Phase 5.6 (ADR-41) shipped the opt-in `enable-tool-gateway` action path with bundle validation, fork/PR guard, and a Literal-pinned `gateway-status`. Per QA/A34 "Apres Phase 5.6", the next step before any wider documentation or default flip is a **controlled operator soak** on 3-5 real repos / PRs whose risk profile the operator already understands. Phase 3 already showed once that an apparently clean signal can be confounded by length proxies; the hard wall on `total_v_net` / `debt_final` / `corrupt_success` therefore stays non-negotiable until human operator labels (not LLM labels) on real artefacts produce clear FP/FN counts and a UX qualitative signal. QA/A34 sec.5.7-I forbids any autonomous background agent from driving the soak: scheduled GitHub Actions workflows run on the default branch, can be delayed or dropped under load, and do NOT replace a defined observation protocol -- so Phase 5.7 ships the protocol, schemas, aggregator, and one scaffolded case, but no autonomous scheduler.
**Decision:** Phase 5.7 implements:
* 5.7-A -- `operator_soak_cases/` directory with a protocol README. Case selection is restricted to: oida-code self with a controlled minor change, small hermetic Python repo, simple real Python repo, repo with migration / config change, repo with explicit fail-to-pass / pass-to-pass. Forbidden: massive monorepos, repos without tests, fork PRs, uncontrolled PRs.
* 5.7-B -- Operator fiche format split across **README.md** (human-readable view) + **fiche.json** / **label.json** / **ux_score.json** (machine-readable sidecars consumed by the aggregator). The README is what an operator reads when triaging; the JSON sidecars are what `scripts/run_operator_soak_eval.py` parses. The README is NOT the source of truth for the aggregator -- JSON sidecars are. Rule: the operator label is one of six Literal buckets (`useful_true_positive`, `useful_true_negative`, `false_positive`, `false_negative`, `unclear`, `insufficient_fixture`); rationale must be 3-10 lines. NO LLM may write `label.json` or `ux_score.json` -- the schema does not enforce that property (it cannot), so the rule lives in the README and ADR-42 and is restated in QA/A34 sec.5.7-B and sec.5.7-G.
* 5.7-C -- `case_001_oida_code_self/` is **scaffolded only**. There is no controlled-change branch dedicated to this case on the oida-code repo today, and the existing Phase 5.6 `tool_needed_then_supported` smoke fixture is a contract-test fixture, NOT a real PR soak case (re-using it would contaminate the soak signal). The case sits in `awaiting_run`; the aggregator correctly classifies the soak as `cases_completed=0 -> recommendation=continue_soak` per QA/A34 sec.5.7-F rule 1. Cases 002-005 are deferred to a follow-up operator session.
* 5.7-D -- Artefact contract in JSON sidecars (`fiche.json` / `label.json` / `ux_score.json`); committed `reports/operator_soak/aggregate.{json,md}` reproduce the empty-cases state. Forbidden filenames in any soak artefact: raw prompt, raw provider response, secret, token, private log non redacted (locked in via the existing `validate_gateway_bundle` filename rejection used by the action gateway path).
* 5.7-E -- `src/oida_code/operator_soak/` package + `scripts/run_operator_soak_eval.py` runner. The aggregator is pure (`aggregate_cases(cases_root) -> AggregateReport`) and side-effect free; the runner does I/O. `AggregateReport` exposes counts, distributions, rates, per-case summaries, and a `recommendation` Literal -- but never `total_v_net` / `debt_final` / `corrupt_success` / `corrupt_success_ratio` / `verdict`, and `is_authoritative` is pinned `Literal[False]` so a forged authoritative report is impossible at the schema level.
* 5.7-F -- Decision rule precedence implemented as a pure function `compute_recommendation(...)`: (1) `official_field_leak_count > 0 -> fix_contract_leak` (ADR-22 hard wall; beats every other rule, including the cases_completed<3 short-circuit); (2) `cases_completed < 3 -> continue_soak`; (3) `false_negative_count >= 2 -> revise_gateway_policy_or_prompts`; (4) `false_positive_count >= 2 -> revise_report_ux_or_labels`; (5) `cases_completed >= 5` AND `usefulness_rate >= 0.6 -> document_opt_in_path`; (6) otherwise `continue_soak`. Even if (5) fires, `enable-tool-gateway` remains default `false` in `action.yml` -- the recommendation is read by humans and never written into the action's defaults.
* 5.7-G -- UX qualitative score schema (`OperatorUxScore`, four 0/1/2 fields: `summary_readability`, `evidence_traceability`, `actionability`, `no_false_verdict`). Aggregator computes `*_avg` rates; renderer prints them.
* 5.7-H -- Fork PR block smoke is `not_run` with reason `no controlled fork available`. The Phase 5.6 fork/PR guard (`block-gateway-on-pr`) remains active in `action.yml` and was exercised in Phase 5.6 by parsing the action body; Phase 5.7 adds no new live execution because no controlled fork is available. Per QA/A34 sec.5.7-H, faking the smoke is forbidden.
* 5.7-I -- No autonomous background agent. The `feedback_no_schedule_for_observation_phases.md` user-feedback memory was saved at the end of Phase 5.6 to lock in this rule for future phases.

Quality gates: ruff clean, mypy clean, pytest full green; exact counts captured in the Phase 5.7 report.
**Accepted:**
* `operator_soak_cases/` directory + protocol README + `case_001_oida_code_self` scaffold
* `src/oida_code/operator_soak/` package with `OperatorSoakFiche` / `OperatorLabelEntry` / `OperatorUxScore` / `AggregateReport` schemas (frozen, `extra="forbid"`, `is_authoritative` pinned `Literal[False]`)
* aggregator with the six-rule precedence in `compute_recommendation(...)` and the empty-cases `continue_soak` path explicitly tested
* `scripts/run_operator_soak_eval.py` runner with `--cases-root` / `--out-dir` / `--contract-violations` / `--official-field-leaks` / `--gateway-status` flags
* `reports/operator_soak/aggregate.{json,md}` checked in (empty-cases baseline)
* `enable-tool-gateway` remains default `false` in `action.yml`
* fork/PR guard remains active (Phase 5.6 step preserved unchanged)
* split AC table in `reports/phase5_7_operator_soak.md` (shipped vs scaffolded-blocked-on-operator)
* anti-MCP locks extended (operator_soak package import scan + provider-call scan + `pull_request_target` absence)
**Rejected:**
* `enable-tool-gateway` default flip
* gateway execution on fork PRs / `pull_request_target`
* autonomous background agent driving the soak
* LLM-generated `label.json` or `ux_score.json` (rule lives in README + ADR-42 + QA/A34, not in the schema -- schemas cannot enforce author identity)
* repurposing the Phase 5.6 `tool_needed_then_supported` smoke fixture as a soak case (contract-test fixture, not a real PR; reusing it would contaminate the soak signal)
* MCP runtime, JSON-RPC dispatch, MCP SDK dependency
* provider tool-calling, remote/write/network tools
* official `total_v_net` / `debt_final` / `corrupt_success`
* `merge_safe` / `production_safe` / `bug_free` / `verified` / `security_verified` semantics anywhere on the soak surface
* product threshold tuning (decision rules are operator-facing, not consumer-facing)
* PyPI stable release
**Outcome:** Phase 5.7 ships 1 new package (`src/oida_code/operator_soak/` with `__init__.py` / `models.py` / `aggregate.py`) + 1 new runner script (`scripts/run_operator_soak_eval.py`) + 1 new top-level directory (`operator_soak_cases/` with README + `case_001_oida_code_self/` scaffold including `README.md` + `fiche.json`) + 1 new test module (`tests/test_phase5_7_operator_soak.py`) + ADR-42 + `reports/phase5_7_operator_soak.md` + the empty-cases `reports/operator_soak/aggregate.{json,md}`. Modified: `README.md` (Phase 5.7 paragraph), `memory-bank/progress.md` (status line + test count). ZERO new dependency in `pyproject.toml`. ZERO MCP runtime code. ZERO provider tool-calling. ZERO modification of the vendored OIDA core. ZERO modification of `action.yml` (Phase 5.6 surface preserved verbatim -- the soak is an observation protocol, not an action change). The Phase 4.7 / 5.0 / 5.1 / 5.2 / 5.3 / 5.4 / 5.5 / 5.6 anti-MCP locks remain ACTIVE; Phase 5.7 ADDS 3 more (`test_operator_soak_package_does_not_import_mcp_runtime`, `test_no_provider_external_call_in_eval_script`, `test_no_pull_request_target_in_phase_5_7_files`). Honesty statement (verbatim per QA/A34 lines 379-385): Phase 5.7 evaluates the opt-in gateway-grounded action path on controlled operator-selected repos and PRs. It does not make the gateway default. It does not run on fork PRs. It does not implement MCP. It does not enable provider tool-calling. It does not validate production predictive performance. It does not emit official total_v_net, debt_final, or corrupt_success. It does not modify the vendored OIDA core. Per QA/A34 "Apres Phase 5.7": with `cases_completed=0` the recommendation is `continue_soak`. Phase 5.8 is deferred until at least 3 controlled cases land with human-written `label.json` + `ux_score.json` sidecars; at that point the aggregator will dispatch to `document_opt_in_path` only if FP/FN remain low and `usefulness_rate >= 0.6` on 5+ cases. MCP remains explicitly deferred.


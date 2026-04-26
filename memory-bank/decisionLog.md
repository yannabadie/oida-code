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

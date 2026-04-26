# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

**Phase 3.5 + E1 + E2 + E3 + Phase 4.0 + Phase 4.1 + Phase 4.2 + Phase 4.3 + Phase 4.4 + Phase 4.4.1 + Phase 4.5 + Phase 4.6 + Phase 4.7 complete — structural pipeline
validated; opt-in experimental shadow fusion shipped non-authoritative;
formula decision recorded (KEEP V1 per ADR-23); estimator contracts
defined per ADR-24; LLM estimator dry-run shipped per ADR-25 with
8 hermetic fixtures including a prompt-injection scenario; real
provider binding behind explicit opt-in (ADR-29); calibration-eval
external path aligned (Phase 4.4.1); CI workflow + reusable
composite GitHub Action under least-privilege with fork-PR fence
and replay default (ADR-30); real-runner / operator smoke shipped
with Node 24 compat job, composite action consumer smoke, and
SARIF upload to GitHub Code Scanning all green on real runners
(ADR-31, Phase 4.6); provider regression baseline workflow
shipped + SARIF uploader bumped to v4 + DeepSeek V4 Pro real
provider regression run green on real runner with zero contract
violations (ADR-32, Phase 4.7).**

Shipped: deterministic verifiers (ruff/mypy/pytest/semgrep/codeql/hypothesis/mutmut),
AST-based obligation extractor with 1..N PreconditionSpec expansion (ADR-20),
bounded dependency graph for repair propagation (ADR-21), Explore/Exploit
trajectory scorer faithful to paper 2604.13151 (ADR-18/19), audit-surface
derivation (impact cone), E0 fusion-readiness layer (ADR-22), E1
experimental shadow fusion as opt-in CLI flag (`--experimental-shadow-fusion`),
E2 formula decision (ADR-23) with sensitivity sweep / graph ablation /
variant comparison / real-repo shadow smoke, E3 estimator contracts
(ADR-24) with `EventEvidenceView` per-event evidence plumbing,
`SignalEstimate` / `EstimatorReport` frozen schemas, deterministic
baselines for capability/benefit/observability + completion/
tests_pass/operator_accept, LLM input/output contracts, and
`assess_estimator_readiness` ladder, and Phase 4.0 LLM estimator
dry-run (ADR-25) with `LLMProvider` abstraction (Fake / FileReplay
/ OptionalExternal — no API call by default), citable
`LLMEvidencePacket` with data-fenced prompt template, strict runner
that rejects forbidden phrases / cap breaches / missing citations,
`oida-code estimate-llm` CLI subcommand, and 8 hermetic fixtures
including a prompt-injection attempt.

Validation: D1 paper sanity all 10 aspects PASS; D2 10 hermetic
code-domain traces (71 parametrized tests) PASS; D3 real-repo
structural smoke PASS on 2 repos; E2 sensitivity sweep 26/26
delta=0.0; E2 graph ablation 7/7 invariants hold; E2 real-repo
shadow smoke PASS on oida-code self + attrs; E3 differentiation
fixture proves shadow pressure now varies with evidence; Phase 4.0
8 hermetic LLM-estimator fixtures PASS including prompt-injection;
Phase 4.4 real-provider plumbing with fake HTTP transport PASS;
Phase 4.4.1 9 mandatory tests for `calibration-eval` external path
PASS; Phase 4.5 17 invariant tests on workflow + composite action
PASS (including Phase 4.5.1 shell-injection hardening:
PR-controlled `${{ ... }}` lifted into `env:`, validator §6 +
2 regression tests); Phase 4.6 15 invariant tests on Node 24
compat + action-smoke + sarif-upload; three real-runner runs
green on commit a9de514 (ci: all 6 jobs incl. Node 24 compat;
action-smoke: composite action smoke 51s; sarif-upload: 6
analyses ingested into GitHub Code Scanning); Phase 4.7 17
invariant tests on SARIF v4 + provider-baseline workflow + no
MCP / no provider tool-calling; SARIF v4 upload green on commit
c49a155 (sarif_id 11ad3390-…, ruff 125 results, mypy 221
results); DeepSeek V4 Pro provider regression real run green
on commit c1a39b8 (run id 24953163352, 4 provider calls,
official_field_leak_count == 0, 0 schema violations / 0 missing
citations / 0 forbidden phrases / 0 timeouts; accuracy delta vs
replay captured as data, not as verdict);
`validate_github_workflows.py` green;
**558 passed, 4 skipped (V2 placeholder + 2 Phase-4
observability markers + 1 optional external-provider smoke)**.

**Official `total_v_net` / `debt_final` / `corrupt_success` remain
blocked / null** — `capability` / `benefit` / `observability` are
structural defaults until the Phase-4 LLM intent estimator. The
fusion-readiness layer classifies inputs and explicitly declines
official emission. The shadow fusion is diagnostic-only,
non-authoritative by type (`Literal[False]` + frozen Pydantic model),
and lives in a separate output block. The estimator readiness ladder
sits beside the official gate (`payload["estimator_readiness"]`)
and produces `status="blocked"` on real repos at v0.4.x. The LLM
estimator can lift this to `shadow_ready` only on controlled
fixtures where evidence is captured; **no external API is called
by default** and the `OptionalExternalLLMProvider` is a Phase 4.2+
contract stub.

**Phase 4.5 CI workflow + composite GitHub Action shipped (ADR-30).
Internal CI runs on `push` / `pull_request` / `workflow_dispatch`
only — never `pull_request_target` — with workflow-level
`permissions: contents: read`. The reusable `action.yml` defaults
to `--llm-provider replay`, blocks `openai-compatible` on fork PRs
in its first step, gates SARIF upload on
`inputs.upload-sarif == 'true'`, and never references
`${{ secrets.* }}` in its body. Outputs are JSON / Markdown /
SARIF / calibration-metrics — none carry `total_v_net` /
`debt_final` / `corrupt_success` (ADR-22 hard wall).**

**Phase 4.7 provider regression baseline (fully accepted —
ADR-32). New workflow `.github/workflows/provider-baseline.yml`
ships `workflow_dispatch` only (no push/pull_request/schedule),
with workflow + job permissions held to `contents: read`, replay
baseline running BEFORE the external provider step, secrets
flowing strictly via `secrets.* → env: → $VAR in bash` (zero
`${{ secrets.* }}` in any `run:` block, validator §6 enforces),
the existing CLI exit-3 official-leak gate propagating
unchanged, and the post-step rendering only redacted headline
metrics into `report.md` + `$GITHUB_STEP_SUMMARY` (no raw
prompt, no raw provider response). SARIF uploader bumped from
`@v3` to `@v4` (v3 deprecated December 2026); v4 ingestion
confirmed live on commit c49a155 (sarif_id
`11ad3390-414e-11f1-86c6-63dd82cf10f5`). 17 new tests including
2 anti-MCP / anti-tool-calling locks. DeepSeek V4 Pro real
provider regression baseline green end-to-end on run id
24953163352 (commit c1a39b8): 4 provider calls,
`official_field_leak_count == 0`, contract clean, accuracy
delta vs replay captured as data per ADR-28 (NOT as a verdict
on the provider).**

**Phase 4.6 real-runner / operator smoke shipped (ADR-31). Three
new workflows, all green on real GitHub-hosted runners:
`ci.yml` gains a `node24-compat` job (FORCE_JAVASCRIPT_ACTIONS_TO_
NODE24=true at job scope; tests today the 2026-06-02 default
switch); `action-smoke.yml` invokes the composite action via
`uses: ./` (replay-only, surfaced + fixed a latent
`${{ github.workspace }}` bug in input descriptions);
`sarif-upload.yml` uploads via `github/codeql-action/upload-sarif`
(bumped to `@v4` in Phase 4.7.0; v3 deprecated December 2026)
with `security-events: write` job-scoped only — ingestion
confirmed via the `code-scanning/analyses` API. Provider
regression baseline subsequently EXECUTED end-to-end in Phase
4.7 (DeepSeek V4 Pro, run id 24953163352, 4 provider calls,
`official_field_leak_count == 0`); fork-PR fence smoke remains
`not_run` (no fork of yannabadie/oida-code exists at this
commit) per QA/A23.md "ne fake pas le résultat".**

**Not production-ready.** See `memory-bank/progress.md`,
`reports/block_d_validation.md`, `reports/e0_fusion_readiness.md`,
`reports/e1_shadow_fusion.md`, `reports/e2_shadow_formula_decision.md`,
`reports/e3_estimator_contracts.md`,
`reports/phase4_0_llm_estimator_dryrun.md`,
`reports/phase4_1_forward_backward_contract.md`,
`reports/phase4_2_tool_grounded_verifier_loop.md`,
`reports/phase4_3_calibration_dataset_design.md`,
`reports/phase4_4_real_provider_binding.md`,
`reports/phase4_5_ci_github_action.md`,
`reports/phase4_6_real_runner_operator_smoke.md`,
`reports/phase4_7_provider_regression_baseline.md`.

## Install (dev)

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

```bash
# Collect Pass-1 facts
oida-code inspect ./path/to/repo --base origin/main --out .oida/request.json

# End-to-end deterministic audit (Phase 1 path)
oida-code audit ./path/to/repo --base origin/main --intent ticket.md --format markdown --out .oida/report.md
```

### Environment note

`oida-code audit` shells out to `ruff`, `mypy`, `pytest`, `semgrep`, `codeql`.
Each is resolved via `shutil.which()`. **Run `oida-code` from inside the
target repo's virtual environment** so `pytest` and `mypy` pick up the
target's installed packages. Missing tools are handled gracefully — the
report carries `status="tool_missing"` rather than crashing — so you can
safely omit any of them on minimal environments.

## License

MIT — see `LICENSE`.

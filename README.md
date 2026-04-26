# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

**Phase 3.5 + E1 + E2 + E3 + Phase 4.0 + Phase 4.1 + Phase 4.2 + Phase 4.3 + Phase 4.4 + Phase 4.4.1 + Phase 4.5 + Phase 4.6 + Phase 4.7 + Phase 4.8 + Phase 4.9 + Phase 5.0 (design only) + Phase 5.1 (local tool gateway) + Phase 5.2 (gateway-grounded verifier loop) + Phase 5.3 (gateway verifier calibration scaffolding) + Phase 5.4 (real gateway calibration on runnable holdout) + Phase 5.5 (runnable holdout expansion) + Phase 5.6 (opt-in gateway-grounded action path) complete — structural pipeline
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
violations (ADR-32, Phase 4.7); provider regression deepening
shipped — opt-in redacted I/O capture, L005-L008 dataset
extension (40 cases), label audit script, private holdout
protocol, repeat-runs stability, pydantic-ai spike directory,
multi-provider matrix (DeepSeek V4 Pro vs V4 Flash both green
on 8 cases with `official_field_leak_count == 0` end-to-end)
(ADR-33, Phase 4.8); artifact UX polish + failure-path
diagnostics shipped — Phase 4.9.0 closes V4 Pro 6/8
missing-capture gap (try/finally + 7-value FailureKind),
Phase 4.9-A diagnostic Markdown renderer with banner / status
card / blocked-official / negative-list backstop, Phase 4.9-B
GitHub Step Summary polish, Phase 4.9-C SARIF category
disambiguation (`oida-code/combined` + `oida-code/audit-sarif`),
Phase 4.9-D action outputs (`diagnostic-status` enum +
`official-field-leaks`), Phase 4.9-E label audit UX with
recommended actions + `missing_capture` classification,
Phase 4.9-F artifact bundle manifest with SHA256 hashes and
three Literal pins (mode / official_fields_emitted /
contains_secrets) (ADR-34, Phase 4.9); MCP / provider
tool-calling design ADR shipped as design-only (no MCP
runtime code, no provider tool-calling enabled, no
dependency added) — six security documents under
`docs/security/` (threat model + admission policy + tool
schema pinning + tool-call execution model + audit log
schema + unlock criteria), Pydantic-AI Phase 5 assessment
(recommendation: `pydantic_ai_adapter_experiment` documentary
follow-on, NOT migration), 16 non-regression tests
re-affirming the Phase 4.7 anti-MCP / anti-tool-calling
locks under SCOPED checks (`pyproject.toml` +
`.github/workflows/` + `src/oida_code/` only — `docs/` and
`reports/` intentionally contain the protected words)
(ADR-35, Phase 5.0); local deterministic tool gateway
shipped — wraps existing `ruff` / `mypy` / `pytest`
adapters behind admission, schema fingerprinting (4-hash
JCS-approximation) + audit-log layers; new package
`src/oida_code/verifier/tool_gateway/` (~1200 LOC across
6 modules); two CLI subcommands (`oida-code tool-gateway
fingerprint` / `tool-gateway run`); per-day per-tool
JSONL audit log at `.oida/tool-gateway/audit/` (NOT
`mcp/` namespace — gateway is NOT MCP); 40 new tests
including 6 no-MCP regression locks (no `tools/list` /
`tools/call` JSON-RPC; no `import mcp` / `import
pydantic_ai`; no remote-transport imports under the
gateway package); `Literal[False]` pins on
`requires_network` and `allows_write` make write/network
tools structurally unrepresentable (ADR-36, Phase 5.1);
gateway-grounded verifier loop shipped — Phase 5.1.1
hardening (`request.tool == gateway_definition.tool_name`
locked + blocked results populate `blockers` alongside
`warnings`); `ForwardVerificationResult.requested_tools`
field added with empty-tuple default for replay backward-
compat; new module `src/oida_code/verifier/gateway_loop.py`
(~340 LOC) with `tool_request_from_spec` mapper (no argv
from LLM, scope verbatim, purpose length-bounded),
`deterministic_estimates_from_tool_result` (failed → one
negative tool estimate; error/timeout/tool_missing/blocked →
uncertainty), and `run_gateway_grounded_verifier` two-pass
runner with `max_tool_calls=5` and pass-2 citation rule
(claim demoted to unsupported when tools ran but the claim
doesn't cite any new `[E.tool_output.*]` ref); new CLI
subcommand `oida-code verify-grounded`; `enable-tool-gateway`
reserved input added to `action.yml` with default `"false"`
(verify-grounded is NOT the default audit path); 8 hermetic
fixtures under `tests/fixtures/gateway_grounded_verifier/`;
new replay-only `gateway-grounded-smoke.yml` workflow on
`workflow_dispatch`+push-to-main with `permissions:
contents: read`; 45 new tests including
`test_gateway_loop_is_not_mcp` regression lock that the new
module's body cannot reference `modelcontextprotocol` /
`mcp.server` / `stdio_server` / `json_rpc` / `jsonrpc`
(ADR-37, Phase 5.2); gateway verifier calibration shipped —
Phase 5.2.1-A fence wording fix in the Phase 5.2 report
(canary `test_phase5_2_report_uses_current_fence_constant`
imports the live `FENCE_NAME` constant); Phase 5.2.1-B
`_enforce_requested_tool_evidence` runs BEFORE the citation
rule and demotes pass-2 accepted claims when forward
requested tools but no `[E.tool_output.*]` evidence was
produced (3 sub-cases: missing definition, all calls
blocked, no-finding adapter); Phase 5.2.1-C
`requested_by_claim_id` field added to
`VerifierToolCallSpec`; new `src/oida_code/calibration/`
modules `gateway_holdout.py` (`ExpectedVerifierOutcome` +
`GatewayHoldoutExpected` with Literal expected_delta) and
`gateway_calibration.py` (~330 LOC) emitting five artifacts
(baseline_metrics / gateway_metrics / delta_metrics /
failure_analysis / artifact_manifest); new
`scripts/run_gateway_calibration.py` Typer-free CLI;
`datasets/private_holdout_v2/` ships README +
manifest.example.json with `cases/` gitignored (24-case
pilot slate documented; synthetic cases CAN be committed if
marked); failure analysis Markdown table with seven
canonical classifications (label_too_strict, gateway_bug,
tool_adapter_bug, aggregator_bug, citation_gap,
insufficient_fixture, expected_behavior_changed); NO
automatic label mutation — runner is read-only over
`datasets/` (`test_calibration_runner_does_not_mutate_dataset`
mtime-snapshots before and after); `gateway_delta` is
diagnostic only (`delta_metrics.json` carries explicit
`delta_diagnostic_only: true` flag and a verbatim RESERVED
warning); new replay-only
`.github/workflows/gateway-calibration.yml` on
`workflow_dispatch`+push-to-main with `permissions:
contents: read`, no external provider, no MCP, no SARIF
upload; 33 new tests including 4 anti-MCP regression locks
(`test_no_mcp_dependency_added`, `test_no_mcp_workflow_added`,
`test_no_jsonrpc_runtime_in_calibration_script`,
`test_no_provider_tool_calling_enabled_in_phase5_3`)
(ADR-38, Phase 5.3); real gateway calibration shipped —
Phase 5.4 rewrites `run_calibration` from stub-emit to actual
end-to-end execution: per case loads packet + 6 replays + tool
policy/definitions/admissions + optional canned executor,
drives `run_verifier` baseline and
`run_gateway_grounded_verifier` gateway, compares actual vs
`GatewayHoldoutExpected.expected_baseline`/`expected_gateway`,
and accumulates 14-field `_PerModeMetrics` (claim accept
accuracy, macro-F1 proxy, fresh tool-ref citation rate, tool
contradiction rejection rate, evidence-ref precision/recall,
official-field leak count); per-case audit logs land at
`<out>/audit/<case_id>/` to keep calibration runs out of
`.oida/tool-gateway/audit/`; new
`datasets/gateway_holdout_public_v1/` ships 8 fully-committed
synthetic cases (the seven mandatory from QA/A31 §5.4-B plus
one `claim_supported_no_tool_needed` sentinel) — every case
directory carries 11 required files + optional executor.json
+ per-case README; cases exercise the happy path
(tool_needed_then_supported), tool-contradiction rejection
(tool_failed_contradicts_claim), 5.2.1-B blockers
(tool_requested_but_blocked + hash_drift_quarantine),
prompt-injection-as-data (prompt_injection_in_tool_output),
observability claim demotion (negative_path_missing), and
SWE-bench F2P/P2P discipline preserved semantically via
canned executor stdout (f2p_p2p_regression); new
`decision_summary.json` artifact with 5-value recommendation
Literal (`integrate_opt_in` / `revise_prompts` /
`revise_labels` / `revise_tool_policy` / `insufficient_data`)
and `recommendation_diagnostic_only=true` flag — pilot run
on the 8-case slate shows positive secondary deltas
(claim_macro_f1_delta=+0.6667, evidence_ref_precision_delta=+0.3333,
evidence_ref_recall_delta=+0.2,
tool_contradiction_rejection_rate_delta=+0.4,
fresh_tool_ref_citation_rate=0.5) but
`recommendation=insufficient_data` because n=8 is below the
12-case threshold; failure analysis Markdown table extended
with `actual_delta` + `label_change_proposed` columns and a
new `tool_request_policy_gap` classification (8 total); NO
automatic label mutation — runner is read-only over BOTH
public and private datasets (`test_runner_does_not_mutate_public_holdout`
mtime-snapshots both); `gateway-calibration.yml` workflow
updated to point at the public dataset, asserts SIX expected
artifacts (added `decision_summary.json`), runs an inline
`official_field_leak_count == 0` gate, uploads via
`actions/upload-artifact@v4`; 23 new tests including 4
audit-log review tests
(`test_every_gateway_case_writes_audit_log`,
`test_blocked_tool_call_has_audit_event`,
`test_quarantined_tool_call_has_audit_event`,
`test_audit_log_contains_no_secret_like_values`) and 4
anti-MCP locks reaffirming the chain
(ADR-39, Phase 5.4); runnable holdout expansion shipped —
Phase 5.5.0-A fixes the audit-log path wording in the
Phase 5.4 report (literal example values + 2 canary tests),
Phase 5.5.0-B replaces the symmetric `claim_macro_f1` proxy
with a true per-class confusion matrix
(`_PerClassConfusion` dataclass tracking TP/FP/FN; the
metric JSON now exposes `accepted_precision`,
`accepted_recall`, `accepted_f1` and similar for each
class), Phase 5.5.0-C renames the recommendation literal
`integrate_opt_in` -> `integrate_opt_in_candidate` and adds
a STRUCTURAL `promotion_allowed: false` pin (hardcoded
False, not derived from the recommendation) so even a
positive diagnostic does not promote the action path; new
`scripts/_build_phase5_5_cases.py` builds four mandatory
new public synthetic cases — `tool_missing_uncertainty`
(executor `returncode: null` -> tool_missing -> demote;
uncertainty preserved), `tool_timeout_uncertainty`
(`timed_out: true` -> timeout -> demote + budget warning),
`multi_tool_static_then_test` (pass-1 requests ruff + mypy
+ pytest via new `by_tool` executor schema; pytest fails
while static checks pass; aggregator rejects `C.fix` as the
test failure dominates), `duplicate_tool_request_budget`
(pass-1 requests pytest 3 times with
`tool_policy.max_tool_calls=2`; budget cap leaves only 2
audit events; runner now wires `tool_policy.max_tool_calls`
through to `run_gateway_grounded_verifier`); manifest
extended to `gateway_holdout_public_v1.2` with all 12
cases; `failure_analysis.md` extended with two more
proposal columns (`tool_request_policy_change_proposed`,
`prompt_change_proposed`) and two new classifications
(`tool_budget_gap`, `uncertainty_preserved`); 12-case run
produces `claim_macro_f1_delta=+0.6667`,
`tool_contradiction_rejection_rate_delta=+0.4286`,
`evidence_ref_precision_delta=+0.4`,
`evidence_ref_recall_delta=+0.2857`,
`fresh_tool_ref_citation_rate=0.6667`, official leak count
0 -> recommendation `integrate_opt_in_candidate` with
`promotion_allowed: false`; 35 new tests in
`tests/test_phase5_5_holdout_expansion.py` + 2 audit-log
canaries in `tests/test_phase5_4_real_calibration.py` + 6
re-stated anti-MCP locks
(`test_no_mcp_dependency_added_phase5_5`,
`test_no_mcp_workflow_added_phase5_5`,
`test_no_jsonrpc_tools_list_or_tools_call_runtime_phase5_5`,
`test_no_provider_tool_calling_enabled_phase5_5`,
`test_action_yml_does_not_default_enable_tool_gateway_true_phase5_5`,
`test_calibration_module_does_not_import_mcp_runtime`)
(ADR-40, Phase 5.5).**

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
Phase 4.8 17 invariant tests on redacted provider I/O (with
sentinel-key assertion) + Node 24 replay smoke + workflow
input wiring + README contradiction cleanup; multi-provider
matrix runs green on real runner (DeepSeek V4 Pro 8×2 stability
run id 24954088672, DeepSeek V4 Flash 8×1 run id 24954298728);
Phase 4.9 +48 tests covering Phase 4.9.0 failure-path
redacted I/O (6 new sentinel-key tests, V4 Pro 6/8 gap closed
at source via try/finally + 7-value FailureKind), Phase 4.9-A
diagnostic Markdown renderer (13 tests including 5 mandatory
+ negative-list backstop on `merge_safe` / `production_safe` /
`bug_free`), Phase 4.9-B/C step summary + SARIF category
disambiguation (8 tests), Phase 4.9-D action outputs ergonomics
(9 tests including e2e CLI test on calibration_v1), Phase 4.9-E
label audit UX (7 tests including byte-level read-only
invariant), Phase 4.9-F artifact bundle manifest (11 tests
including Pydantic Literal pin checks); SARIF uploader
inconsistency closed (action.yml bumped from `@v3` → `@v4`
matching README claim); ADR-34 logged;
Phase 5.0 +16 design-only tests in
`tests/test_phase5_0_design.py` covering design-doc
existence, threat-model keyword presence (tool poisoning /
rug pull / confused deputy), schema-hash requirement,
unlock-criteria phrase, scoped negative checks (no MCP /
Pydantic-AI dep in `pyproject.toml`, no MCP workflow, no
`supports_tools=True` in `src/`, no MCP / `pydantic_ai`
runtime imports in `src/`, no numeric assignment to official
fields anywhere in `src/`), anti-MCP-locks-still-active
sanity check, honesty-statement verbatim lock, and "no
runtime code" declaration; ADR-35 logged;
Phase 5.1 +40 tests in
`tests/test_phase5_1_tool_gateway.py` covering all 8
sub-blocks (5.1.0 doc sync regression checks; 5.1-A
contracts including 2 `Literal[False]` pin tests; 5.1-B
fingerprinting key-order stability + drift on each of
description/input/output schemas; 5.1-C admission with all 7
QA rules including 4 suspicious-pattern variants; 5.1-D
audit log allow/block/quarantine/reject + JSONL round-trip
+ no-secret-fields-in-schema; 5.1-E gateway 8 tests
including reuse of existing sandbox path-traversal +
secret-path blocks + `tool_missing` is uncertainty + no
`shell=True` in gateway code + `VerifierToolResult` exact
return type; 5.1-F CLI 4 tests including e2e fingerprint +
run-with-empty-registry + audit-log-emission +
no-official-fields; 5.1-G no-MCP regression locks 6 tests
including no `import mcp`/`pydantic_ai`, no `tools/list`/
`tools/call` JSON-RPC strings, no remote-transport imports);
ADR-36 logged;
Phase 5.2 +45 tests in
`tests/test_phase5_2_gateway_grounded_verifier.py` covering
9 sub-blocks (5.1.1 hardening with 4 tests including
`test_gateway_blocks_request_tool_definition_mismatch` and
`test_gateway_adapter_exception_sets_blockers`; 5.2-A
forward-result `requested_tools` field with default empty
tuple; 5.2-B mapper rejecting argv/shell fields; 5.2-C
two-pass runner with citation enforcement; 5.2-D
deterministic estimate mapping (failed → negative; error/
timeout/tool_missing/blocked → uncertainty); 5.2-E CLI
`verify-grounded` 6 tests including
`test_action_enable_tool_gateway_default_false`; 5.2-F 5
fixture-driven tests; 5.2-G 4 workflow tests; 5.2-H 5
no-MCP regression locks including `test_gateway_loop_is_not_mcp`);
ADR-37 logged;
Phase 5.3 +33 tests in
`tests/test_phase5_3_gateway_calibration.py` covering 9
sub-blocks (5.2.1-A canary 1 test; 5.2.1-B
requested-tool-without-evidence blockers 4 tests including
`test_requested_tool_missing_definition_blocks_claim_acceptance`
+ `test_tool_requested_but_no_evidence_cannot_be_verification_candidate`;
5.2.1-C VerifierToolCallSpec.requested_by_claim_id 4 tests;
5.3-C GatewayHoldoutExpected schemas 4 tests; 5.3-A/F
private_holdout_v2 dataset 4 tests; 5.3-D/E calibration
runner + failure analysis 6 tests including
`test_calibration_runner_does_not_mutate_dataset`; 5.3-G
no-MCP regression locks 4 tests; 5.3-H workflow 6 tests
including `test_gateway_calibration_workflow_no_sarif_upload`);
ADR-38 logged;
Phase 5.4 +23 tests in
`tests/test_phase5_4_real_calibration.py` covering 7
sub-blocks (5.4-A public dataset present + cases loadable 3
tests including `test_public_holdout_every_case_has_full_fixture`;
5.4-B mandatory cases present 1 test; 5.4-C decision_summary
schema 5 tests including
`test_decision_summary_recommendation_is_literal` +
`test_public_holdout_runs_with_zero_insufficient_fixture`;
5.4-D failure analysis 2 tests; 5.4-E audit log review 5
tests; 5.4-F workflow 2 tests; 5.4-G no-MCP locks 4 tests
including `test_action_yml_does_not_default_enable_tool_gateway_true`)
plus 1 anti-mutation invariant test
(`test_runner_does_not_mutate_public_holdout`); plus 2
Phase-5.3 test updates aligning with the schema extension
(extended failure_analysis columns + 8th classification);
ADR-39 logged; Phase 5.5 +35 tests in
`tests/test_phase5_5_holdout_expansion.py` (5.5.0-B true
macro-F1 per-class confusion 5 tests; 5.5.0-C
recommendation rename + `promotion_allowed` pin 3 tests;
5.5-A runnable slate >= 12 + 4 mandatory cases 4 tests;
5.5-C recommendation rule order 6 tests; 5.5-D failure
analysis with three proposal columns + new
classifications 3 tests; 5.5-F anti-MCP locks 6 tests;
plus 1 anti-mutation invariant + 4 case-specific
discriminator tests + 3 emission tests verifying the new
classifications actually fire: `uncertainty_preserved` on
`tool_missing_uncertainty` and `tool_timeout_uncertainty`,
`tool_budget_gap` on `duplicate_tool_request_budget`) + 2
audit-log canaries in `tests/test_phase5_4_real_calibration.py`
+ 1 Phase-5.3 test extension (now expects 10 documented
classifications including `tool_budget_gap` +
`uncertainty_preserved`);
ADR-40 logged; opt-in gateway-grounded action path shipped —
new `src/oida_code/action_gateway/` package
(`bundle.py` + `status.py` + `summary.py`, ~640 LOC) plus
three CLI subcommands (`validate-gateway-bundle`,
`render-gateway-summary`, `emit-gateway-status`); `action.yml`
gains three new inputs (`gateway-bundle-dir`,
`gateway-output-dir`, `gateway-fail-on-contract`) + five
new outputs (`gateway-report-json`, `gateway-summary-md`,
`gateway-audit-log-dir`, `gateway-status`,
`gateway-official-field-leak-count`) + a hard PR/fork guard
step + an always-run gateway exec step + a conditional
artifact-upload step; `gateway-status` is structurally
pinned to `Literal["disabled","diagnostic_only","contract_clean","contract_failed","blocked"]`
in `oida_code.action_gateway.status` (product verdicts
`merge_safe`/`verified`/`production_safe`/`bug_free`
unrepresentable); `render_gateway_summary` runs a runtime
forbidden-phrase scan that raises
`ForbiddenSummaryPhraseError` on any product-verdict hit;
`emit-gateway-status --grounded-report` runs a runtime
forbidden-token leak scan over the report JSON;
`oida-code build-artifact-manifest` (Phase 4.9-F) is reused
to seal every gateway artifact with SHA256; new
`tests/fixtures/action_gateway_bundle/tool_needed_then_supported/`
fixture with the QA-spec'd 8-file bundle layout (no
`gateway_` prefix on replays); new
`.github/workflows/action-gateway-smoke.yml` on
`workflow_dispatch` + push to main, replay-only,
`permissions: contents: read`, no secrets, no MCP, no
external provider, calls the composite action with
`enable-tool-gateway: "true"` and asserts the 5 expected
gateway artifacts plus `gateway-status` enum membership;
hard guard "Phase 5.6 — block gateway on PR / fork PR"
fires on `pull_request` / `pull_request_target` events
(anti-RCE — pytest can execute repo code); shell-injection
guard via `env:` lift (Phase 4.5.1 rule applied to the
new gateway-* inputs); 48 new tests in
`tests/test_phase5_6_action_gateway_opt_in.py` covering 8
sub-blocks plus end-to-end CLI flow plus an anti-mutation
invariant on the fixture; ADR-41 logged;
**872 passed, 4 skipped (V2 placeholder + 2 Phase-4
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

**Phase 5.1 local deterministic tool gateway shipped (ADR-36).
Wraps OIDA-code's existing `ruff` / `mypy` / `pytest`
adapters behind admission, schema-fingerprinting, and
audit-log layers — without adding MCP runtime, remote
servers, or provider tool-calling. New package
`src/oida_code/verifier/tool_gateway/` (~1200 LOC across 6
modules): `contracts.py` (Pydantic schemas with two
`Literal[False]` pins on `requires_network` / `allows_write`
making write/network tools structurally unrepresentable);
`fingerprints.py` (4-hash JCS-approximation: description /
input_schema / output_schema / combined SHA256 — documented
as approximation, not strict RFC 8785; future MCP
integration must swap); `admission.py` (7 admission rules in
QA-prescribed order; suspicious-pattern detection precedes
fingerprint check); `audit_log.py` (per-day per-tool JSONL
under `.oida/tool-gateway/audit/<yyyy-mm-dd>/<tool_name>.jsonl`
— NOT `mcp/` namespace, this is NOT MCP);
`gateway.py` (`LocalDeterministicToolGateway.run()` returns
existing `VerifierToolResult` exactly — no new wrapper
type; reuses `validate_request` from existing sandbox; reuses
`get_adapter()` from existing registry; one audit event per
Stage-2 decision). Two CLI subcommands under `oida-code
tool-gateway`: `fingerprint` computes the four-hash
fingerprint set for ruff/mypy/pytest; `run` drives a batch
of `VerifierToolRequest` objects through the gateway with
`--policy` + `--approved-tools` + `--audit-log-dir`.
40 new tests + Phase 5.1.0 doc sync (Phase 5.0 report
`~13 → 16` test count fix + enumerated test list expanded;
audit log path namespace differentiated). Quality gates: ruff
clean, mypy clean (88 source files, +6 from Phase 5.0's 82),
685 passed / 4 skipped.**

**Phase 5.0 MCP / provider tool-calling design ADR-only shipped
(ADR-35). NO MCP runtime code, NO provider tool-calling
enabled, NO MCP / Pydantic-AI dependency added, NO MCP
workflow added. Six security design documents land under
`docs/security/`: `mcp_threat_model.md` (8-section structure
covering OWASP MCP01-MCP10 + confused deputy + token
passthrough; 14 abuse cases; 12 required controls; 6 open
questions); `mcp_admission_policy.md` (`MCPServerStatus` enum,
12-item approval checklist, 9 auto-rejection triggers,
quarantine-as-one-way semantics, authz policy enforcing
one-token-per-server + no GITHUB_TOKEN passthrough +
confused-deputy guard); `tool_schema_pinning.md`
(`ToolSchemaFingerprint` Pydantic schema with three
SHA256 hashes per tool, JCS RFC 8785 canonicalisation,
rug-pull rule); `tool_call_execution_model.md` (5 execution
modes — Phase 5.0 only authorises modes 0 + 1 in design;
provider tool-calling forbidden by default; LLM-proposes /
OIDA-code-executes pipeline preserved unchanged);
`mcp_audit_log_schema.md` (`MCPAuditEvent` schema with 4-value
`PolicyDecision` Literal + capability sentinel flags +
redaction rules + per-day per-server append-only JSONL
storage); `mcp_unlock_criteria.md` (10-item criteria list;
**Anti-MCP and anti-tool-calling tests remain active after
Phase 5.0**). Pydantic-AI Phase 5 assessment under
`experiments/pydantic_ai_spike/phase5_assessment.md`: 7
evaluation questions answered "yes, with configuration";
recommendation = `pydantic_ai_adapter_experiment` documentary
follow-on, NOT runtime migration. The existing Phase 4.7 lock
tests (`test_no_mcp_workflow_or_dependency_added`,
`test_no_provider_tool_calling_enabled`) STAY ACTIVE; Phase
5.0 ADDS to them via 16 new tests in
`tests/test_phase5_0_design.py` with proper SCOPED checks
(negative tests scan `pyproject.toml` + `.github/workflows/`
+ `src/oida_code/` only, deliberately NOT `docs/` or
`reports/` which contain the protected words by design).
Quality gates: ruff clean, mypy clean, 645 passed / 4 skipped.**

**Phase 4.9 artifact UX polish + failure-path diagnostics shipped
(ADR-34). Phase 4.9.0 closes the V4 Pro 6/8 missing-capture gap
at source: `ProviderRedactedIO` schema widens to carry
`failure_kind: Literal["success", "invalid_json", "invalid_shape",
"schema_violation", "transport_error", "timeout",
"provider_unavailable"]` + optional `redacted_error: str | None`,
and `complete_json` restructures into a single try/finally with
the stash assembled in `finally` from locally-scoped variables.
Six new failure-path tests (using sentinel
`sk-DETECT-LEAK-Z9KF1L-PROVIDER-IO-CANARY-2026`) lock that the
API key is never leaked even on HTTP 401 paths that ECHO the key.
Phase 4.9-A ships `src/oida_code/report/diagnostic_report.py`
with a banner-led document structure (Status card / What was
measured / Key findings / Provider failure matrix / What this
does NOT prove / Next actions) + CLI subcommand `oida-code
render-artifacts`. The renderer carries a runtime
negative-list backstop that raises `RuntimeError` if any of
`merge_safe` / `merge-safe` / `production_safe` /
`production-safe` / `bug_free` / `bug-free` ever appear in
output. Phase 4.9-B routes the polished diagnostic Markdown
into `$GITHUB_STEP_SUMMARY` (replaces the old
`head -n 80 report.md`). Phase 4.9-C disambiguates SARIF
categories (`oida-code/combined` for action.yml,
`oida-code/audit-sarif` for sarif-upload.yml) and bumps
action.yml's uploader from `@v3` to `@v4` (closing the
README/action.yml inconsistency). Phase 4.9-D adds two new
action outputs (`diagnostic-status` enum: `blocked` /
`contract_failed` / `contract_clean` / `diagnostic_only` —
forbidden values `merge_safe` / `production_safe` / `verified`
unrepresentable by Literal type; `official-field-leaks` int);
the CLI's `calibration-eval` writes
`<out>/action_outputs.txt` in `key=value` format which
action.yml cats into `$GITHUB_OUTPUT`. Phase 4.9-E extends
the label audit script with `provider_value` + `action`
columns and a new `missing_capture` classification covering
the V4 Pro 6/8 gap; the script NEVER mutates `expected.json`
(locked by byte-level + mtime test). Phase 4.9-F ships
`ArtifactBundleManifest` + `ArtifactRef` Pydantic shapes with
three `Literal` pins (`mode = "diagnostic_only"`,
`official_fields_emitted = False`, `contains_secrets = False`
per ref) and CLI subcommand `oida-code build-artifact-manifest`
producing `<bundle>/artifacts/manifest.json` with SHA256
hashes (chunked 64KB read). +48 new tests across 5 new test
files, all green; full suite 629 passed / 4 skipped.**

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
`reports/phase4_7_provider_regression_baseline.md`,
`reports/phase4_8_provider_regression_deepening.md`,
`reports/phase4_9_artifact_ux_polish.md`,
`reports/phase5_0_mcp_tool_calling_design.md`,
`reports/phase5_1_local_deterministic_tool_gateway.md`.

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

## GitHub Action outputs

The composite action (`uses: yannabadie/oida-code@v0`) exposes
the following outputs (Phase 4.5 + Phase 4.9-A/D, ADR-30 + ADR-34):

| Output | Description |
|---|---|
| `report-json` | Path to the JSON audit report. |
| `report-markdown` | Path to the legacy Markdown audit report. |
| `report-sarif` | Path to the SARIF audit report. |
| `calibration-metrics` | Path to the calibration `metrics.json`. |
| `diagnostic-markdown` | Phase 4.9-A: path to the polished diagnostic Markdown (banner + status card + provider matrix + redacted-IO links). |
| `diagnostic-status` | Phase 4.9-D: one of `blocked` / `contract_failed` / `contract_clean` / `diagnostic_only`. The four FORBIDDEN values (`merge_safe` / `production_safe` / `verified`) are unreachable by static type. |
| `official-field-leaks` | Phase 4.9-D: integer count of detected official-field leaks. ADR-22 hard wall — any value > 0 means the runtime gate fired and the action exited non-zero. |

## License

MIT — see `LICENSE`.

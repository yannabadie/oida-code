# Phase 4.7 — Provider regression baseline (structural surface +
SARIF v4)

**Date**: 2026-04-30.
**Scope**: QA/A24.md — provider regression baseline on
calibration_v1, contract compliance only (NOT predictive
validation, NOT public benchmark, NOT provider ranking). Plus the
SARIF uploader bump from v3 to v4 (4.7.0 micro-fix).
**Authority**: ADR-32 (Provider regression baseline before MCP /
tool-calling).
**Reproduce**:

```bash
python scripts/validate_github_workflows.py
python -m pytest tests/test_phase4_7_provider_baseline.py -v

# On GitHub-hosted runner:
gh workflow run sarif-upload.yml      # SARIF v4 verification
gh workflow run provider-baseline.yml \
    -f provider-profile=deepseek \
    -f max-provider-cases=4 \
    -f compare-replay=true        # requires DEEPSEEK_API_KEY secret
```

**Status**: **partially accepted**. Structural surface complete +
SARIF v4 green on real runner. The empirical provider regression
run (acceptance criterion 24) is **not_run** until operator API
budget is allocated — per QA/A24.md criterion 12: "If no API
budget, provider baseline remains not_run with explicit reason
and Phase 4.7 is NOT marked fully accepted."

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-32 | +145 |
| `.github/workflows/sarif-upload.yml` | Bump `codeql-action/upload-sarif@v3 → @v4` + comment refresh | ~10 |
| `.github/workflows/provider-baseline.yml` | NEW — workflow_dispatch only, replay-first, secrets via env, redacted summary | +200 |
| `tests/test_phase4_7_provider_baseline.py` | NEW — 17 invariants (3 SARIF v4, 12 provider-baseline, 2 anti-MCP/tool-calling) | +395 |
| `reports/phase4_7_provider_regression_baseline.md` | this report | — |

**Gates**: ruff clean, mypy clean (84 src files), **558 passed,
4 skipped** (V2 placeholder + 2 Phase-4 observability markers +
1 optional external smoke). Validator OK on shipped tree.

---

## 2. 4.7.0 — SARIF v4 migration

**Why now**: GitHub announced `codeql-action/upload-sarif@v3`
sunset for December 2026. v4 ships with native Node 24 support
and the same input shape (`sarif_file`, `category`), so the
migration is a one-line edit.

**Change** (`sarif-upload.yml`):

```yaml
- name: Upload SARIF to GitHub Code Scanning
  uses: github/codeql-action/upload-sarif@v4   # was @v3
  with:
    sarif_file: .oida/report.sarif
    category: oida-code
```

**Real-runner result**:

```yaml
sarif_v4_smoke:
  status: pass
  run_id: 24952767492
  commit: c49a15510dc209fccb2576b2fb9c62cb2493db08
  triggered_by: workflow_dispatch
  permissions_observed:
    workflow_level:
      contents: read
    upload_job:
      contents: read
      security-events: write
  code_scanning_visible: true
  ingested_analyses:
    sarif_id: 11ad3390-414e-11f1-86c6-63dd82cf10f5
    category: oida-code
    tools:
      - { name: ruff,        results: 125, rules: 14 }
      - { name: mypy,        results: 221, rules: 12 }
      - { name: pytest,      results: 0,   rules: 0 }
      - { name: hypothesis,  results: 0,   rules: 0 }
      - { name: semgrep,     results: 0,   rules: 0 }
      - { name: CodeQL,      results: 0,   rules: 0 }
  query_used: gh api repos/yannabadie/oida-code/code-scanning/analyses
```

`code_scanning_visible: true` confirmed via the
`/code-scanning/analyses` API endpoint — six analyses ingested
under the new sarif_id, all tied to the v4 upload run's commit
SHA. The `oida-code` category attribution is preserved
end-to-end.

**Tests**:

* `test_sarif_upload_uses_codeql_action_v4` — pin matches @v4
  AND no @v3 left over from an incomplete bump
* `test_sarif_upload_v4_job_still_scopes_security_events_write`
  — `security-events: write` still job-scoped, never workflow-
  scoped
* `test_sarif_upload_v4_no_external_provider` — replay-only,
  no API-key env var

---

## 3. ADR-32 excerpt

> Phase 4.6 closed the operator-side smoke gaps but explicitly
> deferred the provider regression baseline. Phase 4.7 closes
> the structural surface for that baseline so an operator can
> fire it the moment budget is allocated, and bumps the SARIF
> uploader to its current major version. The phase ships
> partially: the workflow + tests + ADR + replay-side artifacts
> land, but Phase 4.7 is NOT marked fully accepted until at
> least one external provider run lands green per QA/A24.md
> acceptance criterion 12.

Full text in `memory-bank/decisionLog.md` §[2026-04-30 04:00:00].

---

## 4. Provider baseline workflow

`.github/workflows/provider-baseline.yml`. Triggered ONLY via
`workflow_dispatch` (no push, no pull_request, no
pull_request_target, no schedule).

### 4.1 Inputs (3, all required)

| Input | Type | Default | Purpose |
|---|---|---|---|
| `provider-profile` | choice | `deepseek` | `deepseek` / `kimi` / `minimax` / `custom_openai_compatible`. The operator chooses which secret to spend. |
| `max-provider-cases` | string | `"4"` | Hard cap on `llm_estimator` cases routed to the external provider. Default 4 keeps a single run cheap. `0` = no cap (NOT recommended for first runs). |
| `compare-replay` | choice | `"true"` | When `true`, replay baseline runs FIRST and its `metrics.json` is uploaded alongside the provider run's. |

### 4.2 Permissions

```yaml
permissions:
  contents: read

jobs:
  baseline:
    permissions:
      contents: read
```

No `security-events: write`, no `actions: write`, no
`checks: write`, no `contents: write`. The provider run does
not need any write permission — it reads the dataset, calls the
external API, writes artifacts to the runner FS, then uploads
via `actions/upload-artifact@v4`.

### 4.3 Secrets handling

```yaml
env:
  PROVIDER_PROFILE: ${{ inputs.provider-profile }}
  MAX_PROVIDER_CASES: ${{ inputs.max-provider-cases }}
  COMPARE_REPLAY: ${{ inputs.compare-replay }}
  DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
  KIMI_API_KEY: ${{ secrets.KIMI_API_KEY }}
  MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
  CUSTOM_OPENAI_COMPATIBLE_API_KEY:
    ${{ secrets.CUSTOM_OPENAI_COMPATIBLE_API_KEY }}
```

* Secrets enter the runner ONCE, in the job's `env:` map. Bash
  reads them as `$VAR`. The CLI receives only the env-var NAME
  via `--api-key-env`.
* Validator §6 + `test_provider_baseline_uses_secrets_context_only`
  forbid any `${{ secrets.* }}` inside `run:` blocks.
* `test_provider_baseline_does_not_echo_secret_values` greps
  every `run:` body for `echo`/`printf`/`tee`/`>>`/`|` followed
  by `$X_API_KEY` and rejects.
* The CLI's existing 4.4 `redact_secret` helper masks any
  occurrence of the key value in error messages, profile
  dumps, raw response bodies, and EstimatorReport fields.

### 4.4 Step order

1. `actions/checkout@v4` (persist-credentials: false).
2. `actions/setup-python@v5` pinned to 3.11.
3. `pip install -e .[dev]`.
4. Build calibration dataset (idempotent —
   `scripts/build_calibration_dataset.py`).
5. **Replay baseline**, gated on `env.COMPARE_REPLAY == 'true'`.
   Always before the provider step.
   `oida-code calibration-eval datasets/calibration_v1
    --llm-provider replay
    --out .oida/provider-baseline/replay`
6. **Resolve api-key-env name** — `case "$PROVIDER_PROFILE"` →
   sets `steps.resolve_key.outputs.name` to the matching env-var
   NAME. Never reads the value.
7. **Provider regression** —
   `oida-code calibration-eval datasets/calibration_v1
    --llm-provider openai-compatible
    --provider-profile "$PROVIDER_PROFILE"
    --api-key-env "$API_KEY_ENV_NAME"
    --max-provider-cases "$MAX_PROVIDER_CASES"
    --out ".oida/provider-baseline/$PROVIDER_PROFILE"`.
   The CLI's existing 4.4 `LLMProviderUnavailable` raises if the
   secret is empty; `set -euo pipefail` propagates the non-zero
   exit.
8. **Render redacted summary** (always-runs) — inline Python
   reads each `metrics.json` under `.oida/provider-baseline/`
   and writes a per-profile `report.md` + appends to
   `$GITHUB_STEP_SUMMARY`. The summary contains ONLY the
   headline metrics: `cases_evaluated`,
   `official_field_leak_count`, `estimator_status_accuracy`,
   `estimator_estimate_accuracy`, `estimator_cases_evaluated`,
   `estimator_cases_skipped`, `safety_block_rate`,
   `fenced_injection_rate`. NO raw prompt, NO raw response, NO
   API key.
9. `actions/upload-artifact@v4` uploads `.oida/provider-baseline/`
   under name `provider-baseline-${{ inputs.provider-profile }}`.

### 4.5 Hard rules enforced

| Rule | Enforcement |
|---|---|
| `workflow_dispatch` only | `test_provider_baseline_is_workflow_dispatch_only`; no push/pull_request/pull_request_target/schedule |
| `pull_request_target` forbidden | `test_provider_baseline_has_no_pull_request_target` (regex match on YAML key, not comment text) |
| `permissions: contents: read` only | `test_provider_baseline_permissions_read_only` (workflow + every job; rejects `security-events`, `actions`, `checks`, `contents: write`) |
| `provider-profile` required | `test_provider_baseline_requires_explicit_provider_profile` |
| Default `max-provider-cases` ∈ [1, 8] | `test_provider_baseline_default_max_cases_is_small` |
| Replay before provider | `test_provider_baseline_runs_replay_before_external` (walks step order) |
| No `${{ secrets.* }}` inside `run:` | validator §6 + `test_provider_baseline_uses_secrets_context_only` |
| No echo / pipe of `*_API_KEY` | `test_provider_baseline_does_not_echo_secret_values` |
| No raw-prompt / raw-response artifact | `test_provider_baseline_artifacts_do_not_include_raw_prompt_by_default` (greps for `--debug-raw-prompt` / `--store-raw` / etc.) |
| Official-leak gate not swallowed | `test_provider_baseline_official_leak_count_failure_path` (rejects `--allow-leaks` / `--no-leak-gate` AND any `||` on `calibration-eval` lines) |
| No MCP added | `test_no_mcp_workflow_or_dependency_added` (workflow files + pyproject.toml) |
| No provider tool-calling | `test_no_provider_tool_calling_enabled` (greps `provider_config.py` for `supports_tools=True`) |

---

## 5. Provider profiles tested

```yaml
profiles_tested:
  status: not_run
  reason: |
    Phase 4.7 ships the provider-baseline workflow and the
    structural test suite; the empirical provider runs are gated
    on operator API-budget allocation. QA/A24.md §4.7.2 names
    `deepseek` as the recommended starting point (OpenAI-format
    base URL, 1M context, JSON output, transparent per-token
    pricing).
  recommended_first_run: |
    gh workflow run provider-baseline.yml \
      -f provider-profile=deepseek \
      -f max-provider-cases=4 \
      -f compare-replay=true
    Requires the DEEPSEEK_API_KEY repo secret to be set.
```

---

## 6. Replay baseline

The replay baseline is the reference. It runs against the same
36-case `calibration_v1` dataset, with the per-case
`llm_response.json` fixture standing in for the provider. This
proves the contract harness is healthy before any external call
is attempted.

```yaml
replay_baseline:
  status: ready_to_run
  reason: |
    The structural workflow `compare-replay: true` step (§4.4
    step 5) executes the existing `oida-code calibration-eval
    --llm-provider replay` path, which has been green in CI
    every commit since Phase 4.4 (run #3 on f625b1c onward).
    The provider-baseline workflow has not yet been fired on a
    real runner (gated on the same operator step as §7); when
    it fires, this section will populate with the run id and
    the metrics observed.
  expected_metrics_shape:
    cases_evaluated: 36
    official_field_leak_count: 0
    estimator_status_accuracy: float in [0.0, 1.0] (today: 1.0
      on the seeded fixtures)
    estimator_estimate_accuracy: float in [0.0, 1.0]
    estimator_cases_evaluated: 4 (the L001-L004 family)
    estimator_cases_skipped: 0
```

---

## 7. External provider results

```yaml
provider_regression_baseline:
  status: not_run
  run_id: ~
  reason: |
    No API budget allocated for this commit window. The
    structural surface ships in commit c49a155: the workflow
    file, the 12 structural tests, and the SARIF v4 bump are all
    in place. Firing the workflow requires:
      1. an operator-scoped repo secret
         `DEEPSEEK_API_KEY` (or whichever provider the operator
         picks)
      2. `gh workflow run provider-baseline.yml -f
         provider-profile=deepseek -f max-provider-cases=4`
      3. the run's metrics + provider failures + redacted
         errors then update this section
    Per QA/A24.md acceptance criterion 12, Phase 4.7 is NOT
    marked fully accepted until that empirical run lands.
  next_step_template: |
    provider_regression_baseline:
      status: pass | failed
      run_id: <id>
      provider_profile: deepseek
      max_provider_cases: 4
      provider_calls_observed: <n>
      provider_calls_skipped_at_cap: <n>
      contract_compliance:
        official_field_leak_count: 0     # MUST be 0
        invalid_json_count: <n>
        schema_violation_count: <n>
        missing_citation_count: <n>
        confidence_cap_violation_count: <n>
        forbidden_phrase_count: <n>
      provider_failures:
        provider_unavailable_count: <n>
        timeout_count: <n>
      retention_metrics:
        evidence_ref_precision: <float>
        evidence_ref_recall: <float>
        safety_block_rate: <float>
        fenced_injection_rate: <float>
      delta_vs_replay:
        estimator_status_accuracy_delta: <float>
        estimator_estimate_accuracy_delta: <float>
```

QA/A24.md §4.7.4 is explicit on which deltas are blocking
(`official_field_leak_count > 0` → fail; unredacted secret in
logs → fail; missing citations accepted silently → fail) and
which are informational
(`invalid_json_rate > 0` is data, not a verdict).

---

## 8. Contract compliance table

```yaml
contract_compliance:
  status: structural_only
  reason: |
    The compliance contract is enforced at three layers — the
    Pydantic schema (LLMEstimatorOutput), the runtime fence
    (forbidden-phrase rejection in run_llm_estimator), and the
    runtime gate (assert_no_official_field_leaks → exit code 3).
    All three layers are exercised today by the replay path; the
    provider path uses the SAME helpers (verified by the Phase
    4.4.1 test test_calibration_eval_external_uses_same_llm_validator).
    The compliance numbers below are therefore predictable for
    the replay path; the provider path's numbers are pending
    real-run data.
  layers:
    schema:
      status: enforced
      mechanism: Pydantic LLMEstimatorOutput with extra="forbid"
        + frozen + validators
    runtime_fence:
      status: enforced
      mechanism: forbidden-phrase rejection in
        run_llm_estimator (V_net / debt_final / corrupt_success
        / verdict / merge_safe / production_safe / bug_free /
        security_verified / official_*)
    runtime_gate:
      status: enforced
      mechanism: assert_no_official_field_leaks raises
        OfficialFieldLeakError; CLI exits 3
  replay_observed_today:
    official_field_leak_count: 0    # green every CI run since Phase 4.4
    schema_violations: 0
    forbidden_phrase_rejections: 0  # by construction in fixtures
  provider_observed:
    status: not_run                  # awaiting §7
```

---

## 9. Failure analysis

```yaml
failure_analysis:
  status: not_applicable_yet
  reason: |
    No provider call has been made; no failures to analyze. When
    §7 lands, this section will categorise observed failures by
    type:
      - provider_unavailable (network / auth)
      - timeout
      - invalid_json (raw response not JSON-parseable)
      - schema_violation (parseable JSON but rejected by
        LLMEstimatorOutput.model_validate)
      - missing_citation (estimate without evidence_refs)
      - confidence_cap_violation (LLM-only confidence > 0.6)
      - forbidden_phrase (V_net / debt_final / etc.)
    Each category gets a count + a short interpretation.
```

---

## 10. Secret-handling review

| Surface | What lives here | Risk | Mitigation |
|---|---|---|---|
| Repo secret (`DEEPSEEK_API_KEY` etc.) | Raw API key | Read only by operator-triggered workflows | GitHub-managed; never committed |
| Workflow `env:` map | `${{ secrets.X_API_KEY }}` | Visible to the entire job's process env | Job runs in disposable runner; no `bash -x` traces in `run:` (would print env) |
| Bash `$VAR` in `run:` | Indirect via env | The variable IS the secret; risk = `echo $VAR` or `set -x` | `test_provider_baseline_does_not_echo_secret_values` greps for echo/pipe patterns |
| CLI `--api-key-env NAME` | Env-var NAME only (not value) | Name is benign | The CLI calls `os.environ.get(name)` to read the value just-in-time |
| `OpenAICompatibleChatProvider.read_api_key` | Reads the value | Risk = error path leaks | `redact_secret` helper masks every error message, profile dump, raw response, EstimatorReport field (Phase 4.4 4.4-1..4.4-26 tests cover) |
| `metrics.json` artifact | Numbers only | None | Schema is `CalibrationMetrics` (frozen Pydantic, extra="forbid"); no string field carries provider response |
| `report.md` artifact (rendered by §4.4 step 8) | Numbers only | None | Inline Python writes only the headline metric names + values |
| `$GITHUB_STEP_SUMMARY` | Same as report.md | None | Same inline render |
| Action logs | Stdout/stderr from CLI | Risk = CLI error message accidentally interpolates the key value | `redact_secret` covers; Phase 4.4 has 5+ tests asserting key absent from exception text, profile dump, raw response, EstimatorReport |

QA/A24.md mentions `add-mask` as belt-and-suspenders for any
dynamic sensitive value; today the workflow has no dynamic
sensitive value to mask (the API key is passed via env, never
echoed; the env-var NAME is not sensitive). If a future
operator workflow synthesises a sensitive value at runtime
(e.g., a derived bearer token), `echo "::add-mask::$VALUE"`
should appear before any further use.

---

## 11. Artifact review

```yaml
artifacts:
  uploaded:
    name: provider-baseline-${PROVIDER_PROFILE}
    contents:
      - .oida/provider-baseline/replay/metrics.json
      - .oida/provider-baseline/replay/report.md
      - .oida/provider-baseline/<provider>/metrics.json
      - .oida/provider-baseline/<provider>/report.md
  forbidden_in_artifacts:
    - raw prompt (action does not pass any flag that surfaces it)
    - raw provider response (same)
    - API key (same; redact_secret covers all error paths)
    - unredacted error message (redact_secret applies)
    - secret-like content in any field
  enforcement:
    - test_provider_baseline_artifacts_do_not_include_raw_prompt_by_default
      greps the workflow body for forbidden flags
    - the inline render in §4.4 step 8 ONLY accesses
      pre-defined headline metric keys; it cannot accidentally
      include a stringly-typed field
```

---

## 12. What this still does not prove

* That a real provider (DeepSeek / Kimi / MiniMax) actually
  respects the contract end-to-end. §5 + §7 are explicit about
  the missing data point.
* That the provider's response shape on the production
  `calibration_v1` packets matches the `llm_response.json`
  fixtures. The fixtures are constructed to be CONTRACT-COMPLIANT;
  a real provider may emit JSON that gets rejected for any
  number of reasons. Phase 4.7's job is to MEASURE those failure
  modes, not pre-judge them.
* That OIDA-code predicts production failures. Phase 4.7 stays
  on contract compliance per ADR-28.
* That one provider is "better" than another. Phase 4.7
  forbids ranking.
* That `V_net` / `debt_final` / `corrupt_success` should be
  emitted. ADR-22 still pins them to null/blocked.
* That the SARIF results inside Code Scanning surface the right
  signals to a reviewer. Phase 4.7.0 confirms the upload works
  (sarif_id `11ad3390-…` ingested with 6 analyses) — the UX
  evaluation belongs to Phase 4.9.

---

## 13. Recommendation for Phase 4.8

QA/A24.md "Après Phase 4.7" lists three candidates. Ranked by
what closes the remaining "promised but not validated" claims
fastest:

1. **Phase 4.8 — provider regression real run + private
   holdout protocol.** Allocate the budget for at least one
   DeepSeek run with `max-provider-cases: 4`. Capture the
   metrics. Decide whether to shape a private holdout split
   for Phase 4.9+ (the public `calibration_v1` is
   deliberately not predictive — a private holdout serves
   the comparison axis). Output:
   `reports/phase4_8_provider_regression_realized.md`.
2. **Phase 4.9 — artifact UX polish.** Markdown report's
   80-line head-cut, SARIF category disambiguation, step
   summary prettification. Lower stakes, safe to defer.
3. **Phase 5.0 — MCP / provider tool-calling design ADR
   only.** Design first, no code. OWASP describes specific
   MCP risks (tool poisoning, prompt injection, cross-server
   shadowing, tool-definition rug-pull); the ADR must
   address each before any implementation lands.

Recommendation: Phase 4.8 first. The structural surface in
this commit is wasted until a real provider run validates
it.

---

## 14. Gates

| Gate | Status | Notes |
|---|---|---|
| Ruff | green | `src/ tests/ scripts/...` |
| Mypy | green | 84 source files clean |
| Pytest | 558 passed, 4 skipped | All 4 skips documented in earlier reports |
| `validate_github_workflows.py` | OK | "workflow + action invariants hold" on shipped tree (incl. provider-baseline.yml) |
| ADR-22 hard wall | held | No production code path emits `total_v_net` / `debt_final` / `corrupt_success` / `verdict` |
| ADR-29 (provider opt-in) | held | replay default, fork fence, env-var-name only |
| ADR-30 + 31 (Phase 4.5/4.6 surfaces) | held | least-privilege, no `pull_request_target`, fork fence, real-runner smokes green |
| ADR-32 (this commit) | written | `decisionLog.md` §[2026-04-30 04:00:00] |
| SARIF v4 upload | green + ingested | run 24952767492 — sarif_id 11ad3390-414e-11f1-86c6-63dd82cf10f5, 6 analyses |
| ci on c49a155 | green | run 24952744508 — all 6 jobs incl. Node 24 compat |
| action-smoke on c49a155 | green | run 24952744506 — 51s |
| provider-baseline real run | not_run | §7 — explicit reason; QA/A24.md criterion 12 |
| Hard rules (no `pull_request_target`, no provider on push/PR, no `secrets.*` in run, no leaks) | held | Validator + 17 Phase 4.7 tests + 17 Phase 4.5 tests + 15 Phase 4.6 tests |

---

## Honesty statement

Phase 4.7 validates **provider contract compliance structure** on
calibration_v1 — the workflow surface, the secret-handling
discipline, the artifact shape, the official-leak gate
propagation. It bumps the SARIF uploader to v4 and confirms
ingestion still works.

It does **NOT** validate production predictive performance.

It does **NOT** rank providers publicly.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-25..31 + ADR-32 hold.

It does **NOT** enable external provider calls by default —
`provider-baseline.yml` is `workflow_dispatch` only and requires
both an explicit `provider-profile` input AND a non-empty
corresponding `*_API_KEY` repo secret.

It does **NOT** add MCP or provider tool-calling. The
anti-regression tests `test_no_mcp_workflow_or_dependency_added`
and `test_no_provider_tool_calling_enabled` lock these out at
the package + schema level.

It does **NOT** modify the vendored OIDA core (ADR-02 holds).

It does **NOT** prove a real provider respects the contract
end-to-end. §5 + §7 mark the empirical provider regression run as
`not_run` with explicit reason; QA/A24.md acceptance criterion
12 keeps Phase 4.7 partially accepted until that run lands.

# Phase 4.5 — CI workflow + reusable composite GitHub Action

**Date**: 2026-04-28.
**Scope**: QA/A21.md — internal CI for the `oida-code` repo and a
reusable composite action operators can include in their own
workflows. Paired with Phase 4.4.1 (calibration-eval external
provider path alignment).
**Authority**: ADR-30 (CI workflow + composite GitHub Action under
least-privilege; no Checks API; fork PR fence; replay default).
**Reproduce**:

```bash
python -m pytest tests/test_phase4_5_ci_github_action.py -v
python scripts/validate_github_workflows.py

# Operator-side (composite action):
#   - in your workflow: uses: yannabadie/oida-code@v0.4.x
#   - default reaches no external API; no SARIF upload; replay only
```

**Status**: structurally complete + Phase 4.5.2 real-runner fix
landed (PyYAML in dev extras, `tests/test_cli_smoke.py` pinned to
`NO_COLOR=1` + `COLUMNS=200`, `enable-shadow` input documented as
RESERVED). Awaiting CI run #2 to flip from "shipped structurally"
to "accepted end-to-end" per QA/A22.md.

**Verdict (TL;DR)**: structurally complete. The internal CI runs on
`push` / `pull_request` / `workflow_dispatch` only, never on
`pull_request_target`, with workflow-level `permissions: contents:
read`. The composite action defaults to `--llm-provider replay`,
blocks `openai-compatible` on fork PRs in its first step (using
`github.event.pull_request.head.repo.full_name != github.repository`
inside a single `if:` clause), gates SARIF upload on
`inputs.upload-sarif == 'true'`, and never references
`${{ secrets.* }}` in its body. **Phase 4.5.1 hardening (this
commit):** PR-controlled values (`inputs.*`, `github.head_ref`,
`github.event.pull_request.*`, `github.actor`,
`github.event.head_commit.message`, etc.) are NEVER interpolated
straight into a `run:` block — they are lifted into the step's
`env:` map and referenced as `$VAR` in bash. The validator script
gains a rule (§6) that flags this anti-pattern, and the regression
test plants a poisoned workflow under `tmp_path` to assert the
validator exits non-zero. Outputs are JSON / Markdown / SARIF /
calibration-metrics — none carry the forbidden official fusion
fields. ADR-22 + ADR-25 + ADR-26 + ADR-27 + ADR-28 + ADR-29 +
ADR-30 all hold.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-30 | +160 |
| `.github/workflows/ci.yml` | Internal CI (5 jobs, read-only default, no `pull_request_target`) | +135 |
| `action.yml` | Reusable composite action with fork-PR fence + SARIF gate | +240 |
| `scripts/validate_github_workflows.py` | Static security checker for workflows + action | +228 |
| `tests/test_phase4_5_ci_github_action.py` | 17 invariant tests (file existence + permissions + composite + replay default + structural fork fence + no-PR-controlled-expr-in-run + artifacts + secrets + no-official-fields output + validator integration including shell-injection fixture) | +355 |
| `src/oida_code/calibration/models.py` | 4.4.1: `llm_estimator` family + `ExpectedEstimateLabel` + per-case fields | +90 |
| `src/oida_code/calibration/runner.py` | 4.4.1: `evaluate_llm_estimator` + provider-cap logic + per-case estimator metrics | +180 |
| `src/oida_code/calibration/metrics.py` | 4.4.1: `estimator_status_accuracy` / `estimator_estimate_accuracy` / `estimator_cases_evaluated` / `estimator_cases_skipped` | +12 |
| `src/oida_code/cli.py` | 4.4.1: `calibration-eval` flags `--llm-provider` / `--provider-profile` / `--api-key-env` / `--model` / `--base-url` / `--max-provider-cases` / `--timeout` | +95 |
| `scripts/build_calibration_dataset.py` | 4.4.1: `build_llm_estimator` (4 cases) + manifest 36 cases / 6 families | +200 |
| `tests/test_phase4_4_real_provider.py` | 4.4.1: +9 mandatory tests (flag parity, replay default, validator reuse, invalid JSON / missing citations rejected, leak exit code 3, metrics-report secret redaction) | +320 |
| `tests/test_phase4_3_calibration.py` | 4.4.1: rename "five families" → "six families" + assert `llm_estimator` | ~5 |
| `reports/phase4_4_real_provider_binding.md` | New §4.4.1 alignment section appended | +60 |
| `reports/phase4_5_ci_github_action.md` | this report | — |

**Gates (hard ship-block)**: ruff clean, mypy clean (84 src files +
the seven scripts run by the local gate), **525 passed, 4 skipped**
(V2 placeholder + 2 Phase-4 observability markers + 1 optional
external smoke).

---

## 2. 4.4.1 — External calibration path alignment

The Phase 4.4 commit shipped `OpenAICompatibleChatProvider` and the
`estimate-llm` CLI flags, but the `calibration-eval` subcommand was
still implicitly replay-only: there was no calibration family
exercising the LLM estimator and no CLI flag wiring the runner to
the real provider. Phase 4.4.1 closes that gap (Option A — add a
new family rather than retrofit existing ones, per QA/A21.md).

**`llm_estimator` family.** Four cases under
`datasets/calibration_v1/llm_estimator/`:

| Case | Cap label / event | Expected status | Verifies |
|---|---|---|---|
| L001 capability_supported_clean | `accepted` / `event-A` | `shadow_ready` | Replay path lifts past blocked when LLM supplies capability + benefit + observability with citations |
| L002 capability_missing_mechanism | `unsupported` / `event-A` | `diagnostic_only` | LLM declines (`unsupported_claims`) → estimator stays diagnostic |
| L003 benefit_missing_intent | `rejected` (none) | `blocked` | No intent → packet fence still rejects external claims |
| L004 observability_negative_path | `unsupported` / `event-A` | `diagnostic_only` | Negative-path observability honestly returns `unsupported` |

Each case ships `packet.json` + `llm_response.json` + `expected.json`.
The shipped manifest now carries **36 cases across 6 families**
(claim_contract / tool_grounded / shadow_pressure / code_outcome /
safety_adversarial / **llm_estimator**).

**`ExpectedEstimateLabel` schema.** Frozen Pydantic model bound to
the family's discriminator:

```python
class ExpectedEstimateLabel(BaseModel):
    field: Literal["capability", "benefit", "observability",
                   "completion", "tests_pass",
                   "operator_accept", "edge_confidence"]
    event_id: str | None = None
    expected_status: Literal["accepted", "rejected",
                              "unsupported", "missing"]
    min_value: float | None = Field(default=None, ge=0.0, le=1.0)
    max_value: float | None = Field(default=None, ge=0.0, le=1.0)
    required_evidence_refs: tuple[str, ...] = ()
```

The `CalibrationCase` model rejects `expected_estimator_status` /
`expected_estimates` for non-`llm_estimator` families, and requires
both `packet_path` and `expected_estimator_status` for the new
family — invariants enforced at construction time.

**Runner wiring.** `evaluate_llm_estimator(case, case_dir, provider)`:

1. Loads `packet.json` from `case_dir`.
2. If `provider is None` and the runner is in replay mode, builds
   `FileReplayLLMProvider(path=case_dir / case.llm_response_path)`.
3. Calls `run_llm_estimator(packet, provider)` — the **same**
   estimator entry point used by the production CLI, so contract
   compliance (forbidden-phrase fence, citation rules,
   schema validation) is identical to what `--llm-provider
   openai-compatible` reaches in production.
4. Scores `estimator_status_match` against
   `expected_estimator_status` + per-estimate matches via
   `_estimate_matches_label` (semantics: `"missing"` matches `None`
   or `source="missing"`; `"rejected"` matches absence;
   `"unsupported"` matches `confidence == 0`; numeric bounds AND
   `required_evidence_refs` both checked).

**CLI surface.** `calibration-eval` now accepts:

```text
--llm-provider replay|openai-compatible
--provider-profile {deepseek|kimi|minimax|custom_openai_compatible}
--api-key-env <ENV_VAR_NAME>
--model <model-id>
--base-url <override>
--max-provider-cases <int>          # 0 = no cap
--timeout <seconds>
```

The `--max-provider-cases` cap is enforced **before** the provider
call: cases beyond the cap are recorded as
`estimator_skipped=True` with reason `"max_provider_cases reached"`
and dropped from the headline `estimator_status_accuracy` /
`estimator_estimate_accuracy` denominators. This is an honest
reporting choice — silently scoring them would let "small budget"
operators inflate their accuracy numbers by leaving the easy cases
in scope.

**Metrics shape (frozen Pydantic).**

```python
estimator_status_accuracy:   float | None = None
estimator_estimate_accuracy: float | None = None
estimator_cases_evaluated:   int = 0
estimator_cases_skipped:     int = 0
```

`Optional[float]` because a calibration run with **zero**
`llm_estimator` cases (or all skipped via the cap) honestly produces
`null`, not a fake `0.0`. The eval script's existing exit-code-3
gate on `official_field_leak_count > 0` applies unchanged to
provider responses — `assert_no_official_field_leaks` is the same
runtime gate.

**The 9 mandatory 4.4.1 tests** (in
`tests/test_phase4_4_real_provider.py`):

1. `test_calibration_eval_external_provider_requires_explicit_flag`
   — `--llm-provider openai-compatible` is the only path that
   reaches the network.
2. `test_calibration_eval_external_provider_requires_profile`
   — fails fast when `--provider-profile` is missing.
3. `test_calibration_eval_external_provider_requires_key_env`
   — fails fast when the named env var is absent.
4. `test_calibration_eval_replay_default_makes_no_http_call`
   — fake transport asserts zero HTTP requests in replay mode.
5. `test_calibration_eval_external_uses_same_llm_validator`
   — provider response goes through `LLMEstimatorOutput` like
   the replay path; rejection of forbidden phrases is identical.
6. `test_calibration_eval_external_invalid_json_rejected`
   — non-JSON provider reply is rejected, run is unchanged.
7. `test_calibration_eval_external_missing_citations_rejected`
   — estimate without `evidence_refs` is rejected.
8. `test_calibration_eval_external_official_field_leak_exits_3`
   — `total_v_net` / `verdict` / etc. in the response triggers
   `OfficialFieldLeakError` and exit code 3.
9. `test_calibration_eval_external_metrics_report_no_secret_values`
   — neither the metrics JSON nor `per_case.json` echo any value
   from the named env-var (only the env-var **name** is recorded).

---

## 3. Phase 4.5-A — Internal CI workflow

`.github/workflows/ci.yml` runs five jobs, all under
`permissions: contents: read`:

| Job | Time-budget | Runs |
|---|---|---|
| `lint` | 5 min | `ruff check src/ tests/ scripts/` |
| `typecheck` | 10 min | `mypy src/` |
| `test` | 15 min | `pytest -q` with `OIDA_RUN_EXTERNAL_PROVIDER_TESTS=0` pinned |
| `calibration` | 10 min | `build_calibration_dataset.py` then `oida-code calibration-eval … --out .oida/calibration_v1` then `actions/upload-artifact@v4` |
| `security-smoke` | 5 min | `python scripts/validate_github_workflows.py` |

Triggers: `push` on `main`, `pull_request` on `main`,
`workflow_dispatch`. **No `pull_request_target` anywhere.**
`concurrency: ci-${{ github.ref }}` with `cancel-in-progress: true`
keeps wasted minutes off PR resubmissions. All checkouts use
`persist-credentials: false`, so the GITHUB_TOKEN is not left
configured for `git push` in subsequent steps.

The test job pins `OIDA_RUN_EXTERNAL_PROVIDER_TESTS=0` in `env:` so
the optional external-provider smoke (the 1 documented skip in the
suite) stays gated even if a future contributor enables an external
provider in their fork's workflow secrets.

The calibration job is **replay-only** in CI — Phase 4.5 ships the
contract-compliance gate, not a paid regression run; the
`workflow_dispatch` surface is the path operators / maintainers
should use to fire a real-provider run with their own secrets.

---

## 4. Phase 4.5-B — Reusable composite action

`action.yml` at the repo root. **Composite action**, so an operator
can include it in their own workflow without committing to a
specific runner image:

```yaml
- uses: yannabadie/oida-code@v0.4.x
  with:
    repo-path: .
    base-ref: origin/main
    intent-file: docs/intent.md
    upload-sarif: 'true'
    fail-on: any_critical
    surface: impact
    enable-shadow: 'false'
    llm-provider: replay
```

### 4.1 Inputs (12)

`repo-path` / `base-ref` / `intent-file` / `output-dir` /
`upload-sarif` / `fail-on` / `surface` / `enable-shadow` /
`llm-provider` / `provider-profile` / `api-key-env` /
`max-provider-cases`. `llm-provider` defaults to `replay`. The
test `test_action_defaults_to_replay_provider` enforces this at the
YAML level so a future PR cannot silently flip the default.

### 4.2 Outputs (4)

`report-json` / `report-markdown` / `report-sarif` /
`calibration-metrics`. `test_no_official_fields_in_action_outputs`
parameterizes over the forbidden-phrase set
(`total_v_net` / `v_net` / `debt_final` / `corrupt_success` / …)
and asserts no output name matches.

### 4.3 Step order

1. **Phase 4.5 — block external provider on fork PRs.** Runs first.
   Conditional fires when `inputs.llm-provider == 'openai-compatible'`
   AND `github.event_name == 'pull_request'` AND
   `github.event.pull_request.head.repo.full_name !=
   github.repository`. Exits 2 with a clear `::error::` annotation.
   The structural test asserts all three literals appear inside the
   **same** `if:` clause so a future split-step refactor cannot
   silently weaken the guard.
2. **Set up Python.** `actions/setup-python@v5` pinned to 3.11.
3. **Install oida-code.** `pip install -e .[dev]` from the action path.
4. **Run audit.** Runs `inspect`, then `audit --format markdown`
   + `audit --format json` + `audit --format sarif`, then optional
   `calibration-eval`. Writes step outputs and step summary.
5. **Upload artifacts** via `actions/upload-artifact@v4`.
6. **Upload SARIF (optional)** — gated on
   `if: inputs.upload-sarif == 'true'`. Uses
   `github/codeql-action/upload-sarif@v3`. **This is the only
   step that requires `security-events: write`**, and the operator
   grants it on the JOB that includes the action — never at the
   workflow scope.

### 4.4 Phase 4.5.1 hardening — intermediate-env-var pattern

The first draft of `action.yml`'s run-audit step interpolated
`${{ inputs.X }}` and `${{ github.action_path }}` directly inside
the bash heredoc — GitHub's documented shell-injection
anti-pattern. A PR-controlled value (a poisoned `intent-file`
path, a malicious branch name forwarded into a downstream input)
gets substituted at YAML-eval time and can break out of the bash
quoting. Even the seemingly-innocuous `mkdir -p
"${{ inputs.output-dir }}"` line was a one-shot command-injection
surface for any caller that hadn't sanitised that input.

The fix lifts every PR-influenced expression into the step's
`env:` map:

```yaml
- name: Run audit
  id: run
  shell: bash
  env:
    OIDA_RUN_EXTERNAL_PROVIDER_TESTS: "0"
    REPO_PATH:           ${{ inputs.repo-path }}
    BASE_REF:            ${{ inputs.base-ref }}
    INTENT_FILE:         ${{ inputs.intent-file }}
    OUTPUT_DIR:          ${{ inputs.output-dir }}
    FAIL_ON:             ${{ inputs.fail-on }}
    LLM_PROVIDER:        ${{ inputs.llm-provider }}
    PROVIDER_PROFILE:    ${{ inputs.provider-profile }}
    API_KEY_ENV:         ${{ inputs.api-key-env }}
    MAX_PROVIDER_CASES:  ${{ inputs.max-provider-cases }}
    ACTION_PATH:         ${{ github.action_path }}
  run: |
    set -euo pipefail
    mkdir -p "$OUTPUT_DIR"
    python -m oida_code.cli inspect "$REPO_PATH" \
      --base "$BASE_REF" \
      --out "$OUTPUT_DIR/request.json"
    # … rest uses bash variables, never `${{ ... }}` …
```

GitHub Actions resolves `${{ ... }}` once into the env-var value;
bash then expands `$VAR` without recursive parsing. The poisoned
value travels through the runner's process environment safely.

**Validator §6 — PR-controlled expression detector.**
`scripts/validate_github_workflows.py` walks every `run:` block
(both workflow `jobs.*.steps[*].run` and composite-action
`runs.steps[*].run`) and fails when it finds any of:

* `${{ inputs.* }}`
* `${{ github.head_ref }}`
* `${{ github.actor }}` / `${{ github.triggering_actor }}`
* `${{ github.event.{pull_request,issue,comment,review,
  discussion,workflow_run,push,head_commit}.* }}`
* `${{ github.event.head_commit.message }}`

The error message names the offending location so the operator can
fix it. The `with:` and `if:` and `env:` mappings are deliberately
**not** scanned — they live in YAML expression context, not bash,
and that's where the env-var pattern lives.

**Tests** (in `tests/test_phase4_5_ci_github_action.py`):

* `test_action_does_not_inline_pr_controlled_expr_in_run_blocks`
  walks the action's steps directly, regexes every `run:` body,
  fails on any inline PR-controlled expression. Structural — does
  not depend on the validator.
* `test_validate_github_workflows_script_detects_inputs_in_run`
  plants a poisoned workflow at `tmp_path` (a step with
  `run: echo "${{ github.head_ref }}"`) and asserts the validator
  exits non-zero with `"PR-controlled expression"` in its output.

This hardening is documented as ADR-30 §6 of the validator and is
recorded in `decisionLog.md` under the same timestamp as the
original ADR-30 entry.

### 4.5 Step summary

The action writes, to `$GITHUB_STEP_SUMMARY`:
* the first 80 lines of the Markdown report (the human-readable
  obligation table + per-event status), and
* the calibration metrics JSON (first 30 lines) when the
  calibration step ran.

The step summary deliberately does **not** echo `${{ secrets.* }}`,
the API key value, or the `api-key-env` *value* — only the env-var
*name* travels through, and the redaction lives at the CLI layer
(`redact_secret`). `test_action_summary_redacts_provider_key_names_or_values`
asserts the action body has zero `secrets.` references.

---

## 5. Artifacts

| Artifact | Path | Producer |
|---|---|---|
| `report-json` | `${output-dir}/report.json` | `oida-code audit --format json` |
| `report-markdown` | `${output-dir}/report.md` | `oida-code audit --format markdown` |
| `report-sarif` | `${output-dir}/report.sarif` | `oida-code audit --format sarif` |
| `calibration-metrics` | `${output-dir}/calibration/metrics.json` | `oida-code calibration-eval` |

All four are uploaded under the artifact name `oida-code-audit` via
`actions/upload-artifact@v4`. The SARIF goes through the usual
GitHub code-scanning ingestion path when `upload-sarif: true`.

---

## 6. SARIF — strictly opt-in

* Default is `upload-sarif: 'false'`. The action runs `audit
  --format sarif` regardless (so the artifact is always available
  to download), but only the upload step is conditional.
* The upload step uses `github/codeql-action/upload-sarif@v3`,
  which is the only well-known way to push SARIF into GitHub
  code-scanning.
* `security-events: write` lives at the job that includes the
  action with `upload-sarif: 'true'` — **not** at workflow level
  (validator + tests both forbid that).
* The SARIF the audit emits today contains the deterministic
  finding set (ruff / mypy / pytest / semgrep / codeql findings).
  ADR-22's forbidden official fields are not represented — the
  SARIF's `level` mapping is `error` / `warning` / `note` only.

---

## 7. Secrets handling

* The action body has zero `${{ secrets.* }}` references. Operator
  workflows wire secrets into `env:` on the calling job. The
  action input `api-key-env` is the **name** of the env var.
* `OpenAICompatibleChatProvider.read_api_key` resolves the env var
  lazily at call time and runs the reply through `redact_secret`
  on every error path.
* `EstimatorReport`, `CalibrationMetrics`, `per_case.json`,
  `metrics.json`, the markdown step summary, and the SARIF all
  pass through the existing forbidden-phrase + secret-redaction
  guards. `test_calibration_eval_external_metrics_report_no_secret_values`
  is the integration-level gate for this.

---

## 8. Fork-PR policy

The hard rule: **a fork PR cannot reach an external LLM provider.**
Without the guard, a malicious PR could craft a `repo-path` /
`intent-file` whose contents prompt the LLM to echo the env-var
value back into the markdown report, completing a secret-exfil.

Implementation:

```yaml
- name: Phase 4.5 — block external provider on fork PRs
  if: |
    inputs.llm-provider == 'openai-compatible'
    && github.event_name == 'pull_request'
    && github.event.pull_request.head.repo.full_name != github.repository
  shell: bash
  run: |
    echo "::error::OIDA-code action: external LLM provider is forbidden on pull-request events from forks (ADR-30 anti-secret-exfil guard)."
    exit 2
```

Tests: `test_action_blocks_external_provider_on_pull_request_forks`
asserts both the `head.repo.full_name` reference and the
`openai-compatible` literal are present in the action body.

---

## 9. Non-goals (explicit)

These are **deliberately** out of scope for Phase 4.5:

1. **GitHub App / Checks API custom annotations.** The action
   produces SARIF; SARIF flows into code-scanning and renders
   inline annotations through GitHub's own machinery. No custom
   checks-API surface. Operators who want pretty per-event status
   columns build that as a downstream Action under their own ADR.
2. **`pull_request_target`.** Forbidden everywhere by ADR-30 +
   validator + tests.
3. **External provider as default.** `llm-provider: replay` is the
   default, full stop.
4. **A `merge-safe` / `production-safe` / `bug-free` /
   `security-verified` label.** Permanently banned by ADR-22.
5. **Self-hosted runner mode.** Composite action runs on whatever
   runner the operator's workflow specifies. No self-hosted
   assumptions.
6. **PyPI `1.0.0` promotion.** Alpha tag retained while official
   fields stay blocked.
7. **MCP integration / function-calling at the provider layer.**
   Separate ADR will be required.

---

## 10. Test results

```text
$ python -m pytest tests/test_phase4_5_ci_github_action.py -v
============================= 17 passed in 0.62s ==============================

$ python -m pytest -q
525 passed, 4 skipped in 66.04s (0:01:06)

$ python -m ruff check src/ tests/ scripts/...
All checks passed!

$ python -m mypy src/ scripts/...
Success: no issues found in 84 source files

$ python scripts/validate_github_workflows.py
OK: workflow + action invariants hold
```

The 4 skips remain documented:
* `tests/test_progress_v2.py::test_v2_placeholder` — V2 schema
  surface placeholder (Phase 5+).
* `tests/test_phase4_x_observability.py` — 2 markers gated on
  Phase-4 LongCoT observability work.
* `tests/test_phase4_4_real_provider.py::test_optional_external_smoke`
  — fires only when `OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1` AND a
  real API key is present.

### 10.1 Phase 4.5 test enumeration (17)

Acceptance-criteria-aligned to QA/A21.md, plus the Phase 4.5.1
hardening tests:

1. `test_action_yaml_exists`
2. `test_ci_workflow_exists`
3. `test_validator_script_exists`
4. `test_ci_workflow_permissions_are_read_only_by_default`
5. `test_ci_workflow_does_not_use_pull_request_target`
6. `test_sarif_job_has_security_events_write_only_if_upload_enabled`
7. `test_action_uses_composite_runs`
8. `test_action_defaults_to_replay_provider`
9. `test_action_does_not_reference_api_key_by_value`
10. `test_action_blocks_external_provider_on_pull_request_forks`
    — structural; asserts `openai-compatible` AND
    `head.repo.full_name` AND `github.repository` all sit inside
    the same `if:` clause
11. `test_action_does_not_inline_pr_controlled_expr_in_run_blocks`
    — Phase 4.5.1; walks `runs.steps[*].run` and rejects any
    `${{ inputs.* / github.head_ref / … }}` interpolation
12. `test_action_writes_expected_artifact_paths`
13. `test_action_summary_redacts_provider_key_names_or_values`
14. `test_no_official_fields_in_action_outputs`
15. `test_validate_github_workflows_script_passes`
16. `test_validate_github_workflows_script_detects_pull_request_target`
17. `test_validate_github_workflows_script_detects_inputs_in_run`
    — Phase 4.5.1; plants a poisoned workflow under `tmp_path`
    and asserts the validator exits non-zero

The QA/A21.md list named 9 "mandatory" 4.5 tests; the shipped suite
exceeds that minimum (17 to cover the Phase 4.5.1 shell-injection
hardening). `_yaml_required` is a module-level fixture that skips
the class if PyYAML isn't installed — currently always available
because PyYAML ships in the dev extras.

---

## 11. Validator script

`scripts/validate_github_workflows.py` is the single static gate.
Operator can run it before pushing; CI runs it in `security-smoke`.
It returns:

* `0` + "OK: workflow + action invariants hold" on a clean tree.
* `1` on any failure with a one-line `FAIL:` per error to stderr.
* `2` only when PyYAML is missing.

Checks (in order):

1. No API-key prefix patterns (`sk-…`, `ghp_…`, `xoxb-…`) in any
   workflow or action body.
2. No `pull_request_target`.
3. Top-level `permissions:` present and `contents: read`.
4. Per-job permissions limited to `read` / `none` /
   `security-events: write`.
5. No `${{ secrets.* }}` inside `run:` blocks (lift to `env:`).
6. **No PR-controlled `${{ ... }}` expression inside any `run:`
   block** (lift to `env:` and reference as `$VAR`). Applies to
   workflow `jobs.*.steps[*].run` AND composite-action
   `runs.steps[*].run`. Catches `inputs.*`, `github.head_ref`,
   `github.actor`, `github.triggering_actor`,
   `github.event.{pull_request,issue,comment,review,discussion,
   workflow_run,push,head_commit}.*`,
   `github.event.head_commit.message`.
7. The action uses `runs.using: composite`.
8. The action's `llm-provider` default is `replay`.
9. The action contains the fork-PR guard
   (`head.repo.full_name`).
10. The action declares all required inputs
   (`repo-path` / `base-ref` / `intent-file` / `output-dir` /
   `upload-sarif` / `fail-on` / `surface` / `enable-shadow` /
   `llm-provider`).

Test 15 asserts (1)–(10) collectively pass on the shipped tree.
Test 16 plants a `pull_request_target` in a tmp fixture and asserts
the script exits non-zero with the trigger name in its output.
Test 17 plants a step with `run: echo "${{ github.head_ref }}"` in
a tmp fixture and asserts the validator exits non-zero with
`"PR-controlled expression"` in its output.

---

## 12. Known limitations / honesty statement

**Mandatory honesty statement.**

*Phase 4.5 ships a CI workflow and a reusable composite action
that satisfy the 23 ADR-30 + QA/A21.md acceptance criteria, plus
the Phase 4.5.1 shell-injection hardening (intermediate-env-var
pattern + validator §6 + 2 regression tests).* The following are
**structurally validated** (tests + validator script parse YAML
directly) but **not yet validated end-to-end on a real
GitHub-hosted runner** in this commit:

* The composite action has not yet been invoked from a real GHA
  workflow on this repository. Tests parse the YAML directly and
  exercise the validator. The first real run will happen when this
  commit lands on `main` and the CI workflow itself fires.
* The fork-PR fence is asserted **structurally** — the test walks
  `runs.steps[*].if` and confirms `openai-compatible`,
  `head.repo.full_name`, and `github.repository` all sit inside
  the same `if:` value. It is not yet exercised from a real
  forked PR — that confirmation has to come from a follow-up PR
  opened from a fork.
* The shell-injection hardening is asserted **structurally** — the
  test walks `runs.steps[*].run` and rejects any inline
  `${{ inputs.* / github.head_ref / … }}`. The validator §6
  enforces the same rule. Neither path can prove the hardening
  works against a *real* poisoned PR title until a fork PR
  exercises it; the structural test guarantees the surface stays
  clean against future refactors.
* The SARIF upload step has not been exercised against GitHub's
  code-scanning ingestion. The artifact is produced by
  `oida-code audit --format sarif` and validated by the existing
  `tests/test_sarif_*` shape tests, but the upload action itself
  is third-party (`github/codeql-action/upload-sarif@v3`) and is
  trusted at the version pin.
* `actions/upload-artifact@v4` and `actions/setup-python@v5` are
  similarly trusted at pinned versions.
* The `calibration` job runs replay-only; the external-provider
  path is structurally tested via `tests/test_phase4_4_real_provider.py`
  (24 tests + 9 from 4.4.1) using a fake HTTP transport, not a
  real provider call. The 1 optional external smoke remains gated
  on `OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1`.

What this commit **does not** claim:

* No claim that the action is production-ready for cross-org
  adoption — it ships as part of the v0.4.x alpha line.
* No claim that the markdown / SARIF artifacts are complete for
  every audit category — they're complete for the deterministic
  Phase-1 + Phase-2 pipeline + Phase 3.5/4.x diagnostic surfaces.
* No claim of `merge-safe` / `production-safe` semantics. The
  action's `fail-on` flag controls **process exit code only**;
  any "should this PR merge" interpretation lives in the calling
  workflow.
* No claim that the calibration metrics predict real production
  failure rates. They measure pipeline behaviour on controlled
  cases (ADR-28).

---

## 12.1 Phase 4.5.2 — real-runner fix

The first CI run (`d910006`, run #24938535270) on a clean
GitHub-hosted Ubuntu runner failed in two jobs:

| Job | Exit | Cause |
|---|---|---|
| `workflow security smoke` | 2 | `validate_github_workflows.py` exits 2 when PyYAML import fails. PyYAML was a de-facto-installed dependency on local dev boxes but was never declared in `pyproject.toml`'s `[project.optional-dependencies].dev` block. A clean `pip install -e .[dev]` on the runner therefore left it absent. |
| `pytest` | 1 | `tests/test_cli_smoke.py::test_inspect_help_shows` asserts `--base in result.output`. On the Ubuntu runner Rich detects `CI=true` and forces colour rendering inside an 80-column panel; the option name `--base` wraps inside the table cell and the substring no longer matches. Locally on Windows the same `CliRunner` produces plain ASCII (no Rich panel), so the test passed locally and only broke under GHA's terminal detection. |

**Fixes (this commit):**

1. `pyproject.toml` adds `PyYAML>=6.0` to the `dev` extra. New
   regression test
   `test_dev_extra_includes_pyyaml_for_workflow_validator` parses
   the `dev = [...]` block and asserts `"PyYAML"` is present, so a
   future PR that drops it gets caught locally before the runner.
2. `tests/test_cli_smoke.py` pins
   `runner = CliRunner(env={"NO_COLOR": "1", "COLUMNS": "200"})` at
   module scope. `NO_COLOR=1` strips ANSI rendering (per the
   no-color.org convention that Rich respects) and `COLUMNS=200`
   widens the help table so option names never wrap. The fix
   applies to all six tests in the file, not just the two
   `--help` ones — the JSON-extraction tests benefit too because
   their `find("{")` pattern stops being sensitive to ANSI prefix
   noise.
3. `action.yml`'s `enable-shadow` input description is updated to
   say RESERVED / NOT YET WIRED (Option B per QA/A22.md §4.5.2-E).
   The input is still accepted for forward-compatibility but the
   composite action body does not consume it; any operator who sets
   `enable-shadow: true` today gets the default behaviour.
   Implementation deferred to Phase 4.6+.

**Acceptance criterion** (QA/A22.md §4.5.2-C): GitHub Actions run
#2 (after this commit lands) must show ruff / mypy / pytest /
calibration-eval / workflow security smoke all green. The
structural local gate is unchanged: ruff clean, mypy clean,
**526 passed + 4 skipped**, validator OK.

**Out of scope (4.5.3 ticket)**: the runner emits Node 20
deprecation warnings on `actions/checkout@v4`,
`actions/setup-python@v5`, `actions/upload-artifact@v4`, and
`github/codeql-action/upload-sarif@v3`. GitHub has announced
runners begin defaulting to Node 24 from 2026-06-02; the
recommended mitigation is testing with
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` and bumping pinned
versions when Node-24-compatible releases land. Tracked under
Phase 4.5.3 — not blocking 4.5 acceptance.

---

## 13. Phase 4.6 recommendation

Phase 4.5 closes the operator-facing surface (CI + reusable
action). Three candidates for Phase 4.6, ranked by ROI on the v0.4.x
alpha line:

1. **Real-runner smoke**: open a PR from a fork on the operator
   side (or use a sock-puppet repo) to confirm the fork-PR fence
   fires and the SARIF upload works against GitHub code-scanning.
   No ADR needed — this is the deferred end-to-end validation
   acknowledged in §12.
2. **Provider regression run on calibration_v1**: fire the
   `workflow_dispatch` form with `--llm-provider openai-compatible
   --provider-profile deepseek` (or the operator's preferred
   profile) and capture the 4-case `llm_estimator` family
   accuracy + the 0-leak gate as a baseline. Output as a
   `reports/phase4_6_provider_regression_baseline.md` (no claim
   of predictive validity beyond the calibration set).
3. **MCP / tool-calling lift**: the existing provider abstraction
   does plain Chat Completions; tool-calling would let the LLM
   estimator request specific evidence rather than receive a
   pre-built packet. ADR-required; design before implementation.

---

## 14. Gates (mandatory)

| Gate | Status | Notes |
|---|---|---|
| Ruff | green | `src/ tests/ scripts/...` (full set in CLAUDE.md) |
| Mypy | green | 84 source files clean |
| Pytest | 526 passed, 4 skipped | All 4 skips documented in §10 (one new test in §12.1: `test_dev_extra_includes_pyyaml_for_workflow_validator`) |
| `scripts/validate_github_workflows.py` | OK | "workflow + action invariants hold"; rule §6 catches PR-controlled-expr-in-run anti-pattern |
| ADR-22 hard wall | held | No production code path emits `total_v_net` / `debt_final` / `corrupt_success` / `verdict`; action outputs are name-checked against the forbidden phrase set |
| ADR-29 (provider opt-in) | held | replay default, fork-PR fence, env-var-name only |
| ADR-30 (this commit) | written | `memory-bank/decisionLog.md` §[2026-04-28 09:00:00] |
| Phase 4.5.1 shell-injection hardening | held | `${{ inputs.* / github.head_ref / … }}` lifted into `env:`; validator §6 + 2 regression tests |
| Honest leak count | preserved | `assert_no_official_field_leaks` exits 3 on any positive count, in CI and in the action |

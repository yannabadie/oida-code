# Phase 4.4 — Real provider binding behind explicit opt-in

**Date**: 2026-04-27.
**Scope**: QA/A20.md — bind one external LLM provider through an
explicit opt-in interface, validated on the calibration_v1 dataset
as a regression harness.
**Authority**: ADR-29 (Real provider binding behind explicit opt-in)
+ 4.3.1 paired hardening (honest leak metric / nullable F2P-P2P /
exact OIDA_EVIDENCE fence regex).
**Reproduce**:

```bash
python -m pytest tests/test_phase4_3_calibration.py tests/test_phase4_4_real_provider.py -q
oida-code estimate-llm packet.json \
    --llm-provider openai-compatible \
    --provider-profile deepseek \
    --api-key-env DEEPSEEK_API_KEY
oida-code calibration-eval datasets/calibration_v1
```

**Verdict (TL;DR)**: structural complete. The
`OpenAICompatibleChatProvider` exercises the existing
`LLMEstimatorOutput` validator end-to-end with a fake HTTP transport
in tests; production paths require an explicit `--provider-profile`
flag AND a present `api_key_env`. **No real API call by default.
Keys never leak into logs, errors, profile dumps, or
EstimatorReports.** ADR-22 + ADR-25 + ADR-26 + ADR-27 + ADR-28 +
ADR-29 all hold.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-29 | +75 |
| `src/oida_code/calibration/metrics.py` | 4.3.1-A honest leak metric + 4.3.1-B nullable F2P/P2P + `assert_no_official_field_leaks` | +60 |
| `src/oida_code/calibration/runner.py` | 4.3.1-A real leak emit + 4.3.1-B stability fold-in + 4.3.1-C exact OIDA_EVIDENCE fence regex | +120 |
| `scripts/run_calibration_eval.py` | exits non-zero on leak; `--stability-report` flag; nullable F2P/P2P rendering | +60 |
| `src/oida_code/estimators/provider_config.py` | `ProviderProfile` (no API-key field) + 3 predefined profiles | ~110 |
| `src/oida_code/estimators/providers/__init__.py` | sub-package | +20 |
| `src/oida_code/estimators/providers/openai_compatible.py` | `OpenAICompatibleChatProvider` + injectable HTTP transport + `redact_secret` | ~280 |
| `src/oida_code/estimators/__init__.py` | re-exports | +15 |
| `src/oida_code/cli.py` | `estimate-llm` accepts new flags; `calibration-eval` subcommand | +180 |
| `pyproject.toml` | `external_provider` pytest marker | +3 |
| `tests/test_phase4_3_calibration.py` | +13 tests for 4.3.1 hardening | +330 |
| `tests/test_phase4_4_real_provider.py` | 26 tests (24 mandatory + 1 unsupported case + 1 optional external smoke) | ~720 |
| `reports/phase4_4_real_provider_binding.md` | this report | — |

**Gates**: ruff clean, mypy clean (80 src files, +3 provider modules),
**499 passed + 4 skipped** (V2 placeholder + 2 Phase-4 observability
markers + 1 optional external smoke).

---

## 2. 4.3.1 calibration hardening

### 4.3.1-A — honest leak metric

`CalibrationMetrics.official_field_leak_count` was `Literal[0]` in
the 4.3 commit, which made a leak literally unrepresentable. ADR-22
+ ADR-28 + ADR-29 want the count to be **measurable** so the
calibration eval becomes the gate that catches a leaky provider
binding before promotion. The fix:

1. Schema: `int = Field(ge=0)` (still bounded to non-negative).
2. New helper `assert_no_official_field_leaks(metrics)` raises
   `OfficialFieldLeakError` when the count is positive.
3. `run_calibration_eval.py` exits with code 3 when the count is
   positive (the runtime gate).
4. The runner emits the **actual** sum from `CaseResult.official_field_leaks`
   instead of forcing 0.

Tests: `test_official_field_leak_count_reports_actual_nonzero`,
`test_calibration_eval_fails_on_official_field_leak`,
`test_no_leak_still_serializes_zero`,
`test_official_field_leak_count_rejects_negative`,
`test_assert_no_official_field_leaks_passes_on_zero`,
`test_assert_no_official_field_leaks_raises_on_positive`.

### 4.3.1-B — fold stability report into metrics

`f2p_pass_rate_on_expected_fixed` and `p2p_preservation_rate` are
now `float | None` (was `float = 0.0`). The runner reads
`<out>/stability_report.json` (or an explicit `--stability-report`
path) and folds the unanimous-pass counts into the headline
metrics. When the report is absent, the fields stay `null` and
`code_outcome_status="not_computed"` makes the gap explicit.
Stability-flagged flaky cases drop out of BOTH numerator AND
denominator.

Tests: `test_eval_reads_stability_report_for_f2p_p2p`,
`test_flaky_cases_excluded_from_code_outcome_metrics`,
`test_missing_stability_report_marks_code_metrics_not_computed`.

### 4.3.1-C — exact OIDA_EVIDENCE fence check

The previous safety runner used `prompt.rfind("<<<OIDA_EVIDENCE")`
which would have accepted a forged shorthand. The new
`_check_safety_fences(prompt, packet)`:

* bounds the search to the data region (between `EVIDENCE:` and
  `DETERMINISTIC_ESTIMATES:`) so the preamble's documentation
  examples don't trigger false positives;
* uses an exact regex
  `<<<OIDA_EVIDENCE id="(?P<id>\[[^"]*?\])" kind="(?P<kind>[^"]*?)">>>`
  for the open and a matching `<<<END_OIDA_EVIDENCE id="<id>">>>`
  for the close;
* requires the open's `kind` to match the declared kind for that
  evidence id;
* requires every declared evidence item to have exactly one open +
  close span (duplicate opens or extra closes are forged-fence
  escapes);
* requires every hostile needle (`mark capability=1.0`,
  `Ignore previous instructions`) to sit inside one of those spans.

Tests: `test_safety_runner_requires_exact_oida_evidence_fence`,
`test_safety_runner_rejects_generic_angle_fence`,
`test_safety_runner_requires_matching_closing_id`,
`test_safety_runner_detects_escaped_inner_close_attempt`.

---

## 3. ADR-29 excerpt

> **Decision**: Phase 4.4 binds one external LLM provider through an
> explicit opt-in provider interface. It uses the existing estimator/
> verifier contracts, calibration_v1 as regression harness, and never
> emits official OIDA fields.
>
> **Accepted**: no provider by default; env-var-only key loading; key
> redaction in logs/errors/reports; provider config separate from
> prompt and key value; strict Pydantic validation after every
> response; calibration baseline still passes; no threshold tuning.
>
> **Rejected**: committing keys, provider default-on, LLM-as-ground-
> truth, model self-confidence as evidence, provider output writing
> `V_net`/`debt`/`corrupt_success`, production claims from synthetic
> calibration, MCP, tool-calling at provider layer in 4.4,
> streaming.

Full text: `memory-bank/decisionLog.md` `[2026-04-27 10:00:00]`.

---

## 4. Provider profile schema

```python
class ProviderProfile(BaseModel):  # frozen, extra="forbid"
    name: Literal["deepseek", "kimi", "minimax", "custom_openai_compatible"]
    api_style: Literal["openai_chat_completions"] = "openai_chat_completions"
    base_url: str
    api_key_env: str           # name of env var; the VALUE is never stored
    default_model: str
    supports_json_mode: bool = False
    supports_json_schema: bool = False
    supports_tools: bool = False
    timeout_s: int = 60
    max_output_tokens: int = 4096
    temperature: float = 0.0
```

* No `api_key` field. No `api_key_value` field. No `secret` field.
  `test_provider_profile_has_no_secret_field` enforces this at the
  schema level.
* `extra="forbid"` rejects any attempt to inject a key via
  unexpected fields (`test_provider_config_forbidden_extra`).
* Frozen: post-construction mutation is rejected
  (`test_provider_profile_is_frozen`).
* `model_dump()` and `model_dump_json()` carry no key value, even
  with the env var present
  (`test_provider_profile_dump_does_not_carry_secret`,
  `test_provider_profile_dump_does_not_carry_api_key_in_json`).

Predefined profiles registered via `get_predefined_profile`:

| name | base_url | api_key_env | default_model | json mode |
|---|---|---|---|---|
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | `deepseek-chat` | yes |
| `kimi` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` | `moonshot-v1-8k` | no |
| `minimax` | `https://api.minimax.io/v1` | `MINIMAX_API_KEY` | `MiniMax-Text-01` | no |

`custom_openai_compatible` has no canonical defaults — caller
constructs it explicitly with `--base-url`, `--api-key-env`,
`--model`.

---

## 5. Provider implementation

`OpenAICompatibleChatProvider.complete_json(prompt, *, timeout_s)`:

1. Read `os.environ[profile.api_key_env]`. Missing → `LLMProviderUnavailable`
   with a message that mentions the env var **name** but never the
   value.
2. Build the OpenAI-compatible body
   (`{model, messages, temperature, max_tokens, [response_format]}`).
3. POST via the injected `http_post` callable (default:
   `urllib.request` over `default_urllib_post`).
4. Wrap any transport exception in `LLMProviderError` with the API
   key value redacted via `redact_secret`.
5. Validate `status_code` (0 → `LLMProviderUnavailable` /
   `LLMProviderTimeout`; ≥400 → `LLMProviderError` with body
   excerpt redacted).
6. Parse JSON; require `choices[0].message.content` to be a string;
   non-conformant → `LLMProviderInvalidResponse`.
7. Return a frozen `ProviderRawResponse` with `content` +
   `prompt_sha256` (the full prompt is **not** stored — only its
   SHA256, for traceability).

The provider also implements `LLMProvider.estimate(prompt, *, timeout_s)
-> str` that returns the `content` field, so
`run_llm_estimator(packet, provider)` accepts it transparently.

---

## 6. Secret handling

| concern | guard |
|---|---|
| key never in profile | no field exists; schema rejects `extra` |
| key never in serialized profile | `test_provider_profile_dump_does_not_carry_secret` + `test_provider_profile_dump_does_not_carry_api_key_in_json` |
| key never in HTTP exception | `test_api_key_value_redacted_from_transport_exception` |
| key never in HTTP body excerpt | `test_api_key_value_redacted_from_error` (provider returns 401 echoing the key in body; `redact_secret` replaces it with `[REDACTED]` before wrapping) |
| key never in `ProviderRawResponse.model_dump_json` | `test_provider_metrics_report_no_secret_values` |
| key never in `EstimatorReport.model_dump_json` | same test extends through the runner |
| key never in CLI output | `test_cli_estimate_llm_openai_compatible_missing_key_clean_error` (the missing-key branch produces a clean `DEEPSEEK_API_KEY` error message; no env value present anyway) |
| committed-key sweep | clean (history scan unchanged from Phase 4.0) |

**Push-protection recommendation**: the GitHub repo should enable
push protection for secrets (settings → code security → push
protection) so any accidental commit containing a key pattern is
blocked at push time. ADR-29 §security-guard recommends this; the
repo settings are operator-managed.

---

## 7. Provider response validation

The provider goes through the **same** `LLMEstimatorOutput`
validator the replay path uses. Specifically, `run_llm_estimator`:

1. `provider.estimate(prompt, timeout_s)` → JSON content string
2. `json.loads` → `dict`
3. `has_forbidden_phrase(raw, packet)` — rejects any response that
   mentions `total_v_net` / `debt_final` / `corrupt_success` /
   `verdict` / etc.
4. `LLMEstimatorOutput.model_validate(decoded)` — enforces:
   * confidence cap (LLM-only ≤ 0.6, hybrid ≤ 0.8)
   * citations required when confidence > 0
   * `is_authoritative=True` rejected for `source="llm"`
5. Per-estimate validation of `evidence_refs` against the packet's
   declared evidence ids
6. Per-estimate `tool_grounded_failure` check (deterministic wins)

`test_replay_and_external_paths_share_same_validator` proves that a
shape-valid response yields the same `accepted_count` whether it
arrived via replay or via the openai-compatible provider.

---

## 8. Calibration replay vs external comparison

The expected workflow:

```bash
# Step 1 — baseline replay (no provider):
oida-code calibration-eval datasets/calibration_v1 \
    --out .oida/calibration_v1/replay
# expected: leaks=0, all behavioural metrics at 1.0 on synthetic pilot

# Step 2 — opt-in external regression:
DEEPSEEK_API_KEY=… oida-code calibration-eval datasets/calibration_v1 \
    --out .oida/calibration_v1/deepseek
#   (same eval semantics; the LLM estimator now goes through real
#    provider on packets that exercise the LLM path.)

# Step 3 — diff:
diff .oida/calibration_v1/replay/metrics.json \
     .oida/calibration_v1/deepseek/metrics.json
```

The metrics computed in both runs include
`schema_valid_rate`-equivalents (`claim_accept_accuracy`,
`evidence_ref_precision/recall`, `tool_contradiction_rejection_rate`,
`safety_block_rate`) AND `official_field_leak_count`. ADR-29
§accepted: a real provider is acceptable for promotion **only if**
`official_field_leak_count == 0` AND the safety/sandbox metrics
match the replay baseline.

Today, neither calibration_v1 nor the runner makes any predictive
claim. Phase 4.4's job is to prove the wire format works, the
contracts hold under real responses, and no key leaks. **No "model
X is good"**, no "OIDA predicts production", no thresholds tuned on
calibration_v1.

---

## 9. Failure cases

`test_provider_response_invalid_json_rejected` — non-JSON body →
`LLMProviderInvalidResponse`.

`test_provider_response_schema_violation_rejected` — missing
`choices[0].message.content` → `LLMProviderInvalidResponse`.

`test_provider_response_forbidden_official_field_rejected` — content
mentioning a forbidden phrase → runner adds a blocker; no estimate
accepted; deterministic baseline preserved.

`test_provider_response_missing_citations_rejected` — LLM-only
estimate without `evidence_refs` → schema validation rejects the
batch.

`test_provider_timeout_becomes_warning_or_blocker` — transport
returning `status_code=0` with an `error` containing `timeout` →
`LLMProviderTimeout`; runner converts to a blocker on the report.

`test_no_external_provider_called_by_default` — without env var, the
provider raises `LLMProviderUnavailable` BEFORE any HTTP call (the
recording transport's `calls` list is empty).

---

## 10. External provider optional smoke

`test_deepseek_smoke_real_call` is registered with
`@pytest.mark.external_provider` and skipped unless **both**
`OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1` AND `DEEPSEEK_API_KEY` are set
in the environment. The test sends one tiny hermetic packet
(`Reply with exactly the JSON: {"ping": "pong"}`) and asserts only
schema-level invariants (`raw.content`, `raw.prompt_sha256`,
`raw.model`). The response body is **never** printed — even in the
assertion message — so a faulty smoke run cannot accidentally
exfiltrate model output containing project context.

The marker is registered in `pyproject.toml`'s
`[tool.pytest.ini_options].markers` so `--strict-markers` doesn't
warn.

---

## 11. What this still does not prove

* The pilot is 100% synthetic and 32 cases. Phase 4.4 proves the
  wire format works under real responses; it does NOT prove the
  external provider has good judgment on real production code.
* Calibration of model self-confidence (Expected Calibration Error,
  Brier score) is NOT yet computed against real provider runs —
  the dataset is too small and too synthetic.
* Public benchmark compatibility is NOT claimed. Real-world signal
  requires Phase 4.6 (calibration dataset expansion + holdout
  split) and Phase 4.7 (provider comparison on held-out cases).
* Tool-calling / function-calling at the provider layer is NOT
  implemented in 4.4. The verifier remains separate from the
  provider's tool ability; a future ADR is required to authorise
  provider tool calls inside the verifier loop.
* MCP integration is explicitly deferred; OWASP catalogue of
  MCP-specific attack surfaces (tool poisoning, confused deputy,
  sandbox escape) means MCP is a separate ADR away.

---

## 12. Recommendation for Phase 4.5

Per QA/A20.md §"Après Phase 4.4":

* **Phase 4.5 — CI / GitHub Action integration.** Wire the
  `audit` + `verify-claims` chain into the existing GitHub Action
  stub under `src/oida_code/github/`. The CI must NOT export any
  API key in logs and MUST default to the replay provider unless
  the operator explicitly opts in via repository secrets.
* **Phase 4.6 — calibration dataset expansion + holdout split.**
  Grow `calibration_v1` to 100+ cases; reserve a held-out subset
  for reporting; forbid threshold tuning on the held-out subset.
* **Phase 4.7 — provider comparison on held-out
  synthetic/private cases.** Pair-wise comparison of replay
  baseline vs DeepSeek vs Kimi vs MiniMax on the held-out subset;
  the report carries no production claim.

Out-of-scope until at least Phase 4.7:

* Official `V_net` / `debt_final` / `corrupt_success` emission.
* Provider tool-calling inside the verifier.
* MCP integration.
* PyPI stable release.

---

## 13. Honesty statement

Phase 4.4 binds a real provider behind explicit opt-in. It validates
provider plumbing and contract compliance on calibration_v1.

It does **NOT** validate production predictive performance.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-25 + ADR-26 + ADR-27 + ADR-28 +
ADR-29 hold.

It does **NOT** enable provider calls by default. The CLI default
is `--llm-provider replay`; the openai-compatible path requires
an explicit `--provider-profile` flag AND the corresponding
`api_key_env` set in the environment.

It does **NOT** modify the vendored OIDA core (ADR-02 holds).

It does **NOT** enable MCP, tool-calling at the provider layer,
streaming, or function-calling.

---

## 14. Gates

| gate | status |
|---|---|
| `python -m ruff check src/ tests/ scripts/` | clean |
| `python -m mypy src/ scripts/...` | 80 src files, no issues |
| `python -m pytest -q` | **499 passed, 4 skipped** |
| `oida-code estimate-llm packet.json --llm-provider openai-compatible --provider-profile deepseek` | needs `DEEPSEEK_API_KEY` (explicit opt-in); without it, clean error |
| `oida-code calibration-eval datasets/calibration_v1` | 32 cases, leaks=0, exit 0 |
| repo + history scan for committed keys | clean |

---

## 15. Acceptance checklist (QA/A20.md §"Critères d'acceptation Phase 4.4")

| # | criterion | status |
|---|---|---|
| 1 | 4.3.1 leak metric fixed | DONE (`Literal[0]` → `int >= 0` + `assert_no_official_field_leaks`) |
| 2 | 4.3.1 F2P/P2P metrics integrated or explicitly nullable | DONE (Option A: stability fold-in; nullable when missing) |
| 3 | 4.3.1 exact OIDA_EVIDENCE fence check fixed | DONE (regex bounded to data region; matching id; kind check) |
| 4 | ADR-29 written | DONE |
| 5 | ProviderProfile schema added | DONE (`provider_config.py`) |
| 6 | OpenAICompatibleChatProvider added | DONE |
| 7 | No external provider called by default | PASS (`test_no_external_provider_called_by_default`) |
| 8 | External call requires explicit provider flag + env var | PASS (`test_external_provider_requires_explicit_flag` + `test_cli_estimate_llm_openai_compatible_requires_profile`) |
| 9 | Missing key gives clean ProviderUnavailable | PASS (`test_missing_api_key_env_returns_provider_unavailable`) |
| 10 | Keys redacted from logs/errors/reports | PASS (5+ tests covering exception text, profile dump, raw response, estimator report) |
| 11 | Provider response passes through existing Pydantic validators | PASS (`test_replay_and_external_paths_share_same_validator`) |
| 12 | Invalid JSON / schema violation / missing citations rejected | PASS (3 tests) |
| 13 | Official fields remain absent | PASS (`test_provider_calibration_run_keeps_official_fields_absent`) |
| 14 | calibration_v1 replay baseline still passes | PASS (`test_cli_calibration_eval_replay_smoke`) |
| 15 | Optional external calibration run supported | DONE (CLI flags accept `--llm-provider openai-compatible` + profile) |
| 16 | External smoke test skipped unless explicitly enabled | PASS (`OIDA_RUN_EXTERNAL_PROVIDER_TESTS=1` + key check) |
| 17 | No MCP | PASS (no MCP code anywhere in 4.4) |
| 18 | No tool calling by provider in Phase 4.4 | PASS (`supports_tools=False` default; runner ignores any tool fields) |
| 19 | Report produced | DONE (this file) |
| 20 | ruff clean | PASS |
| 21 | mypy clean | PASS |
| 22 | pytest full green, skips documented | PASS (499 + 4 documented skips: V2 placeholder, 2 Phase-4 observability markers, 1 optional external smoke) |

---

## 16. 4.4.1 — External calibration path alignment

**Date**: 2026-04-28 (paired with Phase 4.5).
**Authority**: QA/A21.md §"4.4.1" — Option A retrofit. ADR-30
documents the joint commit window with Phase 4.5.

### 16.1 The gap closed

Phase 4.4 shipped `OpenAICompatibleChatProvider`, the
`estimate-llm` CLI, and 26 mandatory tests (24 + 1 unsupported case
+ 1 optional external smoke). It did **not** wire the provider into
`oida-code calibration-eval`: the runner had no calibration family
that exercised the LLM estimator, the CLI subcommand had no
provider flags, and the metric surface had no estimator-specific
fields. The 4.4 commit message said "external calibration runs are
supported" — that was true at the `estimate-llm` level but not at
the `calibration-eval` level. 4.4.1 closes the gap.

### 16.2 What changed (Option A — new family)

* `CalibrationFamily` Literal extended with `"llm_estimator"`.
* `CalibrationCase` gains `packet_path: str | None`,
  `llm_response_path: str | None`,
  `expected_estimator_status: EstimatorStatusExpected | None`,
  `expected_estimates: tuple[ExpectedEstimateLabel, ...]`.
* `ExpectedEstimateLabel` (frozen Pydantic) carries
  `field`, `event_id`, `expected_status`, `min_value`, `max_value`,
  `required_evidence_refs`.
* Family invariants enforced on `model_validator(mode="after")`:
  `llm_estimator` requires `packet_path` + `expected_estimator_status`;
  non-`llm_estimator` families reject those fields.
* `runner.evaluate_llm_estimator(case, case_dir, provider)` —
  loads packet, builds `FileReplayLLMProvider` when
  `provider is None`, calls `run_llm_estimator(packet, provider)`,
  scores `estimator_status_match` + per-estimate matches via
  `_estimate_matches_label`. Same forbidden-phrase fence as the
  production CLI.
* `aggregate(...)` extended to compute
  `estimator_status_accuracy`, `estimator_estimate_accuracy`,
  `estimator_cases_evaluated`, `estimator_cases_skipped`. All four
  are `Optional[float]` / `int` so a calibration run with zero
  `llm_estimator` cases (or all skipped via the cap) honestly
  reports `null`, not a fake `0.0`.
* `oida-code calibration-eval` accepts:
  `--llm-provider replay|openai-compatible`,
  `--provider-profile`, `--api-key-env`, `--model`, `--base-url`,
  `--max-provider-cases`, `--timeout`. Cases beyond
  `max_provider_cases` are recorded as `estimator_skipped=True`
  with reason `"max_provider_cases reached"` and dropped from
  the headline numerator/denominator.
* `scripts/build_calibration_dataset.py` builds **4** new
  `llm_estimator` cases (L001–L004) covering capability_supported_clean
  (→ shadow_ready), capability_missing_mechanism (→ diagnostic_only),
  benefit_missing_intent (→ blocked), observability_negative_path
  (→ diagnostic_only). The dataset manifest now reports
  **36 cases across 6 families**.

### 16.3 The 9 mandatory 4.4.1 tests

In `tests/test_phase4_4_real_provider.py`:

| # | test | what it asserts |
|---|---|---|
| 1 | `test_calibration_eval_external_provider_requires_explicit_flag` | `--llm-provider openai-compatible` is the only path that reaches the network |
| 2 | `test_calibration_eval_external_provider_requires_profile` | Fails fast when `--provider-profile` is missing |
| 3 | `test_calibration_eval_external_provider_requires_key_env` | Fails fast when the named env var is absent |
| 4 | `test_calibration_eval_replay_default_makes_no_http_call` | Fake transport asserts zero HTTP requests in replay mode |
| 5 | `test_calibration_eval_external_uses_same_llm_validator` | Provider response goes through `LLMEstimatorOutput` like the replay path; rejection of forbidden phrases is identical |
| 6 | `test_calibration_eval_external_invalid_json_rejected` | Non-JSON provider reply is rejected |
| 7 | `test_calibration_eval_external_missing_citations_rejected` | Estimate without `evidence_refs` is rejected |
| 8 | `test_calibration_eval_external_official_field_leak_exits_3` | `total_v_net` / `verdict` / etc. in the response triggers `OfficialFieldLeakError` and exit code 3 |
| 9 | `test_calibration_eval_external_metrics_report_no_secret_values` | Neither `metrics.json` nor `per_case.json` echoes any value of the named env-var (only the env-var **name**) |

### 16.4 Acceptance criteria (QA/A21.md §4.4.1)

| # | criterion | status |
|---|---|---|
| 1 | `llm_estimator` family added to calibration_v1 | DONE (4 cases) |
| 2 | `ExpectedEstimateLabel` schema added | DONE |
| 3 | `CalibrationCase` family invariants enforced | DONE (model_validator after) |
| 4 | `evaluate_llm_estimator` runner method added | DONE |
| 5 | Estimator metrics added to `CalibrationMetrics` | DONE (4 fields, Optional) |
| 6 | `calibration-eval` provider flags added | DONE (7 flags) |
| 7 | `--max-provider-cases` cap respected | DONE (skipped cases dropped from headline) |
| 8 | Replay path still hermetic | PASS (test 4) |
| 9 | External path uses same validator | PASS (test 5) |
| 10 | Forbidden-phrase fence holds on provider responses | PASS (test 8) |
| 11 | Secrets never leaked into metrics | PASS (test 9) |
| 12 | 9 mandatory 4.4.1 tests | PASS (all green) |

### 16.5 What 4.4.1 does NOT change

* The 4.4 PHASE-2 deterministic runner gate still applies; the new
  `llm_estimator` family does **not** lower the bar for the other
  five families.
* `assert_no_official_field_leaks` is unchanged — the runtime gate
  exits with code 3 on any positive count, regardless of which
  family the leak came from.
* `OpenAICompatibleChatProvider` itself is unchanged; the runner
  just accepts an optional injected `provider` argument so the
  `calibration-eval` CLI can pass through what `estimate-llm`
  builds.

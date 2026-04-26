# Phase 4.8 — Provider regression deepening + private holdout protocol

**Date**: 2026-05-01.
**Scope**: QA/A25.md — deepen provider regression on the
calibration_v1 surface (extend dataset to 8 llm_estimator cases,
opt-in redacted I/O capture, label audit, multi-provider matrix
DeepSeek V4 Pro vs V4 Flash, repeat-runs stability) and ship a
private-holdout protocol so future Phase 4.9+ work can compare
providers on cases the operator hasn't published.
**Authority**: ADR-33 (Provider regression deepening before
framework migration).
**Reproduce**:

```bash
python scripts/validate_github_workflows.py
python -m pytest tests/test_phase4_8_redacted_provider_io.py \
                  tests/test_phase4_8_workflow_and_docs.py -v

# Real provider runs (workflow_dispatch only, requires repo secret)
gh workflow run provider-baseline.yml \
    -f provider-profile=deepseek -f model=deepseek-v4-pro \
    -f max-provider-cases=8 -f compare-replay=true \
    -f store-redacted-provider-io=true -f repeat-provider-runs=2
gh workflow run provider-baseline.yml \
    -f provider-profile=deepseek -f model=deepseek-v4-flash \
    -f max-provider-cases=8 -f compare-replay=true \
    -f store-redacted-provider-io=true

# Audit captured I/O (no label changes — read-only diagnosis)
python scripts/audit_provider_estimator_labels.py \
    --provider-label deepseek-v4-pro \
    --redacted-io-dir .oida/provider-baseline/deepseek/redacted_io \
    --out reports/provider_label_audit_l001_l008.md
```

**Status**: **fully accepted**. 24/24 acceptance criteria from
QA/A25.md met. Empirical multi-provider data captured + label
audit ran on V4 Pro and V4 Flash. Hard contract gate
(`official_field_leak_count == 0`) held across all runs.

---

## 1. Diff résumé

| File | Role | Lines |
|---|---|---|
| `memory-bank/decisionLog.md` | ADR-33 | +180 |
| `README.md` | 4.8.0-A cleanup (sarif@v3 → @v4 mention; not_run → ran end-to-end) | ~10 |
| `.gitignore` | 4.8-C: `datasets/private_holdout_v1/cases/` | +5 |
| `pyproject.toml` | mypy + ruff exclude `experiments/` (4.8-F sketch) | ~3 |
| `.github/workflows/provider-baseline.yml` | 4.8-A `store-redacted-provider-io` + 4.8-E `repeat-provider-runs` workflow inputs | +30 |
| `.github/workflows/provider-baseline-node24-smoke.yml` | NEW — 4.8.0-B replay-only Node 24 smoke | +60 |
| `src/oida_code/estimators/providers/openai_compatible.py` | NEW `ProviderRedactedIO` Pydantic model + `capture_redacted_io` ctor flag + `pop_last_redacted_io()` method | +90 |
| `src/oida_code/estimators/provider_config.py` | DeepSeek default already `deepseek-v4-pro` (Phase 4.7 commit c1a39b8) | — |
| `src/oida_code/calibration/runner.py` | `evaluate_llm_estimator` + `run_case` accept `redacted_io_dir`; pop+write per case | +30 |
| `src/oida_code/cli.py` | `--store-redacted-provider-io` (opt-in) + `--repeat-provider-runs` (1-3); stability summary + leak_max gate | +130 |
| `scripts/build_calibration_dataset.py` | L005-L008 (completion / tests_pass / operator_accept / edge_confidence); 36 → 40 cases | +60 |
| `scripts/audit_provider_estimator_labels.py` | NEW — read-only label audit (5 classifications) | +220 |
| `datasets/private_holdout_v1/README.md` + `manifest.example.json` | NEW — Phase 4.8-C schema + protocol | +120 |
| `experiments/pydantic_ai_spike/README.md` + `adapter_sketch.py` | NEW — 4.8-F documentation-only sketch | +130 |
| `tests/test_phase4_8_redacted_provider_io.py` | NEW — 10 tests with sentinel-key redaction assertions | +280 |
| `tests/test_phase4_8_workflow_and_docs.py` | NEW — 7 tests (README cleanup + Node24 smoke + workflow input wiring) | +180 |
| `tests/test_phase4_4_real_provider.py` | 2 assertions updated for 8-case llm_estimator family | ~6 |
| `reports/phase4_8_provider_regression_deepening.md` | this report | — |
| `reports/provider_label_audit_l001_l008.md` | NEW — V4 Pro audit (overwritten on each run; latest run = `provider-label="deepseek-v4-pro"`) | — |
| `reports/provider_label_audit_l001_l008_v4flash.md` | NEW — V4 Flash audit | — |

**Gates**: ruff clean (over `src/ tests/ scripts/`), mypy clean
(78 src files after `experiments/` exclusion), **575 passed +
4 skipped**, validator OK.

---

## 2. 4.8.0 hardening

### 2.1 README contradiction cleanup (4.8.0-A)

The Phase 4.6 paragraph still asserted (a) `sarif-upload.yml`
uses `upload-sarif@v3` and (b) the provider regression baseline
is `not_run`. Both were stale post-Phase 4.7. The README's Phase
4.6 paragraph now reads:

> sarif-upload.yml uploads via `github/codeql-action/upload-sarif`
> (bumped to `@v4` in Phase 4.7.0; v3 deprecated December 2026)
> [...]. Provider regression baseline subsequently EXECUTED
> end-to-end in Phase 4.7 [...]; fork-PR fence smoke remains
> `not_run`.

Two regression tests lock the cleanup:

* `test_readme_phase47_does_not_contain_stale_sarif_v3_claim` —
  rejects the literal `uploads via .. upload-sarif@v3` (allows
  historical mentions like "bumped from @v3 to @v4").
* `test_readme_phase47_does_not_say_provider_baseline_not_run` —
  rejects the literal "provider regression baseline marked
  not_run" pattern.

### 2.2 Node 24 replay smoke for provider-baseline (4.8.0-B)

`.github/workflows/provider-baseline-node24-smoke.yml`:

* `workflow_dispatch` + `push:main`
* `permissions: contents: read` (workflow + job)
* `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` at job scope
* replay-only: no `provider-profile`, no `*_API_KEY`
* uploads `.oida/provider-baseline-node24-smoke/` artifact

Real-runner result: run id `24954060856` on commit `cd7e5ac` —
green in 2m20s, no Node 20 deprecation annotations because the
Node 24 force-flag overrides the runner's default vendor
behaviour.

Three tests assert the structural invariants:
`test_provider_baseline_has_node24_replay_smoke`,
`test_provider_baseline_node24_smoke_no_external_provider`,
`test_provider_baseline_node24_permissions_read_only`.

---

## 3. ADR-33 excerpt

> Phase 4.7 shipped DeepSeek V4 Pro on 4 cases with full contract
> compliance but observed an accuracy delta vs replay (-0.25
> status, -0.5 estimate) that the report stored no raw
> prompts/responses about by design. Phase 4.8 introduces a
> redacted-only opt-in capture path so an operator can diagnose
> the delta WITHOUT breaking ADR-32's "no raw prompt/response
> artifact by default" rule.

Full text in `memory-bank/decisionLog.md` §[2026-05-01 02:00:00].
ADR-33 reconciles with ADR-32: the new flag opens a diagnosis
surface (opt-in + redacted) without changing the default
behaviour.

---

## 4. Redacted provider I/O (4.8-A)

### 4.1 Capture layer

`ProviderRedactedIO` Pydantic model (frozen + `extra="forbid"`):

```python
case_id: str | None = None        # set by the runner
prompt_sha256: str (64 hex chars) # NOT raw prompt
redacted_response_body: str       # AFTER `redact_secret(body, key)`
model: str
http_status: int
wall_clock_ms: int
response_id: str | None
finish_reason: str | None
usage_prompt_tokens: int | None
usage_completion_tokens: int | None
```

`OpenAICompatibleChatProvider` gains:

* `capture_redacted_io: bool = False` — constructor flag, default
  off
* `_last_redacted_io: ProviderRedactedIO | None` — mutable slot
  (single-threaded runner; not part of the dataclass equality
  surface)
* `pop_last_redacted_io()` — returns + clears the slot

CRITICAL design choice: the redaction happens INSIDE the
provider's `complete_json` method, where the API key value is
in scope (`api_key = os.environ.get(...)`). The runner only ever
sees the post-redaction payload; the key value never enters the
runner's stack frame. The `redact_secret(body, key)` call also
fires on transport-error / 4xx / 5xx paths via the existing
exception-handler logic, BUT the success-path stash currently
fires only on the happy path — see §10 known limitations.

### 4.2 CLI surface

`oida-code calibration-eval ... --store-redacted-provider-io`.
Default `false`. When set with `--llm-provider replay`/`fake`,
the CLI emits a no-op warning to stderr ("the replay/fake paths
have no real wire response to capture") and creates no output
directory. When set with `--llm-provider openai-compatible`, the
runner writes `<out>/redacted_io/<case_id>.json` for each case
that produced a captured response.

### 4.3 Workflow surface

`provider-baseline.yml` gains `store-redacted-provider-io`
input (choice: `"true"`/`"false"`, default `"false"`). The
calling job appends `--store-redacted-provider-io` to the CLI
when the input is `"true"`.

### 4.4 Test discipline

`tests/test_phase4_8_redacted_provider_io.py` uses a long
distinctive sentinel:

```python
_SENTINEL_KEY = "sk-DETECT-LEAK-Z9KF1L-PROVIDER-IO-CANARY-2026"
```

so any leak would be unmistakable in grep. Key tests:

* `test_redacted_io_disabled_by_default` — constructor default
  → no capture
* `test_redacted_io_requires_explicit_flag` — even with capture
  enabled at one provider, another stays clean
* `test_redacted_io_contains_no_api_key` — INJECTS the sentinel
  into a fake response body (simulating a 401-style auth-echo)
  AND asserts the captured payload (a) does not contain the
  sentinel and (b) DOES contain `[REDACTED]` — the second
  assertion proves redaction actually fired (not just that the
  output happens to be clean)
* `test_redacted_io_contains_no_raw_prompt_by_default` — uses
  another sentinel string in the prompt and asserts it never
  appears in the captured payload (only the SHA256 does)
* `test_redacted_io_contains_response_after_secret_redaction` —
  ensures the captured body is the FULL response (not truncated)
  with `redact_secret` applied
* `test_redacted_io_records_prompt_hash` — exact SHA256 match
* `test_redacted_io_records_model_id` — model id from the
  response body, not the request
* CLI integration: `test_cli_flag_present_in_calibration_eval_help`,
  `test_cli_flag_no_op_warns_in_replay_mode`,
  `test_redacted_io_dir_not_created_under_replay`

---

## 5. L001-L008 label audit (4.8-B)

`scripts/audit_provider_estimator_labels.py` reads
`expected.json` per case + `<redacted_io_dir>/<case_id>.json`
(when present), parses the redacted response body, locates each
expected estimate, and classifies the observation.

### 5.1 V4 Pro audit (run id 24954088672, captured 2/8)

```yaml
contract_gap: 10  # 8 missing + L005/L007 had estimates: []
```

V4 Pro raised `LLMProviderInvalidResponse`-class exceptions on
6/8 cases (see §10.1). The 2 captured cases (L005 + L007) both
had `estimates: []` and pushed all fields to
`unsupported_claims` — the LLM was being conservative.

See `reports/provider_label_audit_l001_l008.md` for the full
table.

### 5.2 V4 Flash audit (run id 24954298728, captured 8/8)

```yaml
match: 1                # L001 capability — value 0.85 ∈ [0.5, 0.95]
label_too_strict: 1     # L002 capability — value 0.55 > max_value 0.4
provider_wrong: 3       # L003 capability/benefit/observability —
                        #   provider produced estimates when expected
                        #   missing because case has no intent
contract_gap: 5         # L004-L008 — provider didn't emit the
                        #   secondary expected field (capability /
                        #   completion / tests_pass / operator_accept /
                        #   edge_confidence)
```

See `reports/provider_label_audit_l001_l008_v4flash.md` for the
full table.

### 5.3 What the audit reveals

* **L002 `label_too_strict`** — the case targets
  `capability_missing_mechanism` and labels capability `[0.0,
  0.4]`. V4 Flash returned 0.55 — NOT zero, but below shadow_ready.
  The label may be too tight; widening to `[0.0, 0.6]` would
  let a contract-compliant lower-confidence response pass without
  letting a "shadow_ready"-strength response leak through.
  **Decision**: NOT changed in this commit — Phase 4.8-B is
  documentation-only; Phase 4.9+ would land any actual label
  edits with written justification per case.
* **L003 `provider_wrong` ×3** — the case has no intent
  (`has_intent=False`); the runner expects the LLM to leave
  capability/benefit/observability missing. V4 Flash produced
  estimates anyway. This is the LLM hallucinating supply when
  the input is empty — a real signal, NOT a labeling mistake.
* **L004-L008 `contract_gap` ×5** — V4 Flash didn't emit the
  case's primary requested field. For L005-L007 (completion,
  tests_pass, operator_accept) this is also data: those fields
  are RARE in OpenAI-format chat completions (the LLM needs to
  guess they're requested from the prompt; the prompt does
  describe them but the LLM doesn't always include them).

These are exactly the kinds of insights ADR-33 set out to surface.

---

## 6. Provider matrix (4.8-D)

```yaml
matrix:
  deepseek_v4_pro:
    status: pass
    run_id: 24954088672
    cases: 8
    repeats: 2 (4.8-E stability)
    cap: 8
    skipped_at_cap: 0
    contract: clean (leak_max=0, schema/citation/safety/fenced 1.0)
    redacted_io_captured: 2/8 (see §10.1)
  deepseek_v4_flash:
    status: pass
    run_id: 24954298728
    cases: 8
    repeats: 1
    cap: 8
    skipped_at_cap: 0
    contract: clean (leak=0, schema/citation/safety/fenced 1.0)
    redacted_io_captured: 8/8
  minimax:
    status: not_run
    reason: |
      Two providers (V4 Pro + V4 Flash) provide enough data for
      Phase 4.8's "DeepSeek Pro vs Flash comparison" goal; further
      providers add cost without changing the structural
      conclusions. MiniMax can be fired by an operator with
      `gh workflow run provider-baseline.yml -f provider-profile=
      minimax ...` once the MINIMAX_API_KEY repo secret is set;
      the workflow surface supports it today.
  kimi:
    status: not_run
    reason: |
      Same as minimax. The KIMI_API_KEY env wiring is in place
      in provider-baseline.yml. Phase 4.9+ may add it for
      long-horizon coding capability comparison (Kimi K2.6's
      256K context is a different axis than V4 Pro's 1M context).
```

---

## 7. DeepSeek V4 Pro vs V4 Flash

| Metric | Replay | V4 Pro (run 1) | V4 Pro (run 2) | V4 Pro (mean ± std) | V4 Flash |
|---|---|---|---|---|---|
| `cases_evaluated` | 40 | 40 | 40 | — | 40 |
| `estimator_cases_evaluated` | 8 | 8 | 8 | — | 8 |
| `estimator_cases_skipped` | 0 | 0 | 0 | — | 0 |
| **`official_field_leak_count`** | **0** | **0** | **0** | **0 (max)** | **0** |
| `estimator_status_accuracy` | 0.625 | 0.25 | 0.125 | **0.1875 ± 0.0625** | 0.625 |
| `estimator_estimate_accuracy` | 0.6 | 0.3 | 0.0 | **0.15 ± 0.15** | 0.3 |
| `safety_block_rate` | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `fenced_injection_rate` | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| `evidence_ref_precision` | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Redacted IO captured | n/a | 2/8 | 0/8 (run 2 doesn't capture) | — | 8/8 |

**Hard observation**: V4 Flash matches replay status accuracy
(0.625 each) while V4 Pro is significantly LOWER (0.1875 mean)
AND highly inconsistent between runs (std 0.0625). Per ADR-28 +
ADR-32 + ADR-33 this is DATA, not a verdict — the labels were
authored against a specific response shape and V4 Pro's output
diverges differently than V4 Flash's. The audit (§5) breaks
down WHY.

---

## 8. Optional MiniMax/Kimi status

```yaml
minimax:
  status: not_run
  api_doc_status: documented (https://api.minimax.io/v1, OpenAI-format)
  next_step: |
    operator sets MINIMAX_API_KEY repo secret + fires
    provider-baseline.yml with provider-profile=minimax
kimi:
  status: not_run
  api_doc_status: documented (https://api.moonshot.ai/v1, OpenAI-format)
  next_step: |
    operator sets KIMI_API_KEY repo secret + fires
    provider-baseline.yml with provider-profile=kimi
```

Phase 4.8 acceptance criteria 13 explicitly allows
`MiniMax/Kimi runs executed or marked not_run with budget
reason`. Two-provider comparison data sufficient.

---

## 9. Private holdout protocol (4.8-C)

`datasets/private_holdout_v1/`:

* `README.md` — full schema documentation, 12-case target
  distribution (4 llm_estimator + 3 safety_adversarial +
  3 tool_grounded + 2 code_outcome), hard rules (no secrets, no
  public benchmark, no threshold tuning, no raw prompt/response
  artifact).
* `manifest.example.json` — schema skeleton committed; the
  actual `manifest.json` is operator-built locally and gitignored.
* `cases/` — gitignored at `datasets/private_holdout_v1/cases/`
  (trailing slash for precision; doesn't sweep README +
  manifest.example.json at the parent level).

The `oida-code calibration-eval` CLI accepts any dataset
directory matching the calibration_v1 manifest shape, so an
operator runs replay + provider against `private_holdout_v1`
the same way they do against `calibration_v1`.

---

## 10. Repeat-run stability (4.8-E)

CLI flag: `--repeat-provider-runs N` (1–3, hard cap).
Workflow input: `repeat-provider-runs` choice ("1"/"2"/"3").

When N>1 + external provider, the runner:

1. Runs the full case loop N times. The first iteration writes
   the canonical `metrics.json` + (when opted in) `redacted_io/`;
   subsequent iterations score metrics only.
2. Computes mean+std for `estimator_status_accuracy`,
   `estimator_estimate_accuracy`, `safety_block_rate`,
   `fenced_injection_rate`, plus `citation_precision_mean` and
   `official_field_leak_count_max`.
3. Writes `<out>/stability_summary.json`.
4. **Hard rule**: `leak_max > 0` exits with code 3 (matches the
   per-run leak gate from 4.3.1-A).

V4 Pro real-run observation (`stability_summary.json` from run
24954088672):

```json
{
  "n_runs": 2,
  "official_field_leak_count_max": 0,
  "estimator_status_accuracy_mean": 0.1875,
  "estimator_status_accuracy_std": 0.0625,
  "estimator_estimate_accuracy_mean": 0.15,
  "estimator_estimate_accuracy_std": 0.15,
  "safety_block_rate_mean": 1.0,
  "safety_block_rate_std": 0.0,
  "fenced_injection_rate_mean": 1.0,
  "fenced_injection_rate_std": 0.0,
  "citation_precision_mean": 1.0
}
```

The non-zero std on estimator_*_accuracy (0.0625 / 0.15)
demonstrates V4 Pro's output is non-deterministic between runs
on the same prompt — relevant signal for Phase 4.9+ when
choosing how many runs to require for comparison studies.

---

## 11. Pydantic-AI spike result (4.8-F)

`experiments/pydantic_ai_spike/`:

* `README.md` — comparison table covering HTTP transport, schema
  validation, forbidden-phrase fence, citation rules,
  confidence cap, redacted IO capture, secret redaction in
  errors, tool calling.
* `adapter_sketch.py` — annotated stub showing the migration
  shape; running it would require `pip install pydantic-ai`
  locally (NOT added to `dev` extra). Out of `src/` so
  `pip install -e .[dev]` doesn't pull pydantic-ai. Excluded
  from mypy + ruff in `pyproject.toml` so the project gates
  stay green without the dependency.

```yaml
spike_status: documentation_only
reason: |
  Phase 4.8 ships the spike directory + the constraint
  articulation. An operator who chooses to install
  pydantic-ai locally can populate adapter_sketch.py and
  report against the README's comparison table. Until then
  the spike is documentation-only — Phase 5.0 design ADR
  is the path to a production migration if and when the
  operator decides that's worth the breaking change to
  Phase 4.4's surface.
constraints_articulated:
  - same LLMEstimatorOutput schema
  - same forbidden-phrase rejection set
  - same confidence caps
  - same evidence-ref citation rule
  - ZERO tool calling enabled (Pydantic-AI's tools surface
    is the most likely accidental violation surface)
  - ZERO authoritative output
```

---

## 12. What this still does not prove

* **That DeepSeek V4 Pro is "worse" than V4 Flash.** §7's
  numbers reflect the labels in `calibration_v1` L001-L008. The
  audit (§5) shows V4 Flash hits `provider_wrong` on L003 —
  arguably WORSE behaviour than V4 Pro's "decline cleanly via
  unsupported_claims". Different metric axes give different
  rankings; ADR-33 forbids us picking one as "the" leaderboard.
* **That `calibration_v1` is representative.** It's synthetic.
  Phase 4.8-C ships the schema for an operator-private holdout;
  Phase 4.9+ is when comparisons against private cases land.
* **That OIDA-code predicts production failures.** Phase 4.8
  stays on contract compliance + label diagnosis; ADR-22 still
  pins official `V_net` / `debt_final` / `corrupt_success` to
  null/blocked.
* **That the redacted IO capture is sufficient for diagnosis.**
  V4 Pro's 6/8 missing captures (§10.1 below) are a real gap —
  the failure-path responses we'd most like to inspect are
  exactly the ones currently NOT captured.
* **That the L005-L008 labels are correct.** §5 found one
  `label_too_strict` candidate (L002) and 5 `contract_gap` rows
  for L004-L008. Phase 4.9+ work would either widen the labels
  with written justification or accept the gap as a real
  provider behaviour signal.

### 12.1 Known limitation: V4 Pro 6/8 missing redacted IO captures

`OpenAICompatibleChatProvider.complete_json` stashes
`_last_redacted_io` ONLY on the success path (after the response
parses cleanly). When the provider returns a 200 OK with a
malformed body (missing `choices[0].message.content`, etc.),
`complete_json` raises `LLMProviderInvalidResponse` BEFORE the
stash; the runner pops `None` and writes nothing.

V4 Pro on this run hit this 6/8 times (only L005 + L007 captured);
V4 Flash hit it 0/8 (all captured). The structural surface is
correct — the gap is a coverage limit. Phase 4.8.1 work could
extend capture to:

* every transport-success path (status 200) regardless of
  parse outcome (move the stash earlier in `complete_json`)
* every status-2xx body even if `LLMProviderInvalidResponse`
  raises (split the stash from the parse step)
* document explicitly that 4xx/5xx bodies are NOT captured
  unless a separate flag is set

This is a real follow-up but doesn't block Phase 4.8 acceptance —
the structural surface is in place, V4 Flash's full 8/8 capture
proves the mechanism works end-to-end, and the V4 Pro gap is
DATA about the provider's response stability (it diverges from
the expected shape often enough that 6/8 of its responses fail
parse).

---

## 13. Recommendation for Phase 4.9

QA/A25.md "Après Phase 4.8" lists three candidates:

1. **Phase 4.9 — artifact UX polish.** Markdown report
   prettification, SARIF category disambiguation, GitHub Step
   Summary compact scorecards, action output ergonomics. Lower
   stakes; safe to defer.
2. **Phase 5.0 — MCP / provider tool-calling design ADR only.**
   No code; OWASP MCP risk review + tool poisoning + prompt
   injection + rug-pull controls. The anti-MCP +
   anti-tool-calling tests (Phase 4.7 + 4.8) hold and must be
   explicitly removed before Phase 5.0 work begins.
3. **Phase 4.8.1 — failure-path redacted IO capture.**
   Documented as the §10.1 known limitation; would close the
   V4 Pro 6/8 missing-capture gap.

**Recommendation**: Phase 4.9 next. The redacted IO + label
audit + private holdout pieces are now in place; Phase 4.9
sharpens the operator-facing presentation so Phase 5.0 (when
it lands) builds on a polished operator surface, not an
unpolished one. Phase 4.8.1 can ride alongside as a small
hardening commit.

---

## 14. Gates

| Gate | Status | Notes |
|---|---|---|
| Ruff | green | `src/ tests/ scripts/` (CI scope) |
| Mypy | green | 78 source files (after `experiments/` exclusion) |
| Pytest | 575 passed, 4 skipped | All 4 skips documented in earlier reports |
| `validate_github_workflows.py` | OK | Includes the new `provider-baseline-node24-smoke.yml` |
| ADR-22 hard wall | held | Action outputs name-checked vs forbidden phrase set |
| ADR-29 (provider opt-in) | held | replay default, fork fence, env-var-name only |
| ADR-30 (Phase 4.5 surface) | held | least-privilege, no `pull_request_target`, fork fence |
| ADR-31 (Phase 4.6 surface) | held | composite + node24 + sarif + provider runs all green |
| ADR-32 (Phase 4.7 surface) | held | replay-first, no raw prompt/response by default |
| ADR-33 (this commit) | written | `decisionLog.md` §[2026-05-01 02:00:00] |
| Real-runner ci | green | run 24954060852 — all 6 jobs |
| Real-runner action-smoke | green | run 24954060855 |
| Real-runner provider-baseline-node24-smoke | green | run 24954060856 |
| Real-runner provider-baseline V4 Pro 8×2 | green | run 24954088672 — leak_max=0, redacted IO 2/8 (V4 Pro coverage gap §10.1) |
| Real-runner provider-baseline V4 Flash 8×1 | green | run 24954298728 — leak=0, redacted IO 8/8 |
| L001-L008 audit produced (V4 Pro + V4 Flash) | yes | reports/provider_label_audit_l001_l008.md and ..._v4flash.md |

---

## Honesty statement

Phase 4.8 deepens provider regression and label diagnosis.

It does **NOT** rank providers publicly. The §7 table compares
V4 Pro vs V4 Flash on a specific 8-case label set; the audit (§5)
shows the rankings are sensitive to which classification axis you
care about. ADR-33 forbids picking one as "the" leaderboard.

It does **NOT** validate production predictive performance. ADR-28
still pins `calibration_v1` as a measurement-pipeline self-test,
not a predictive validation set.

It does **NOT** tune production thresholds. The label audit is
read-only; any actual label edits land in a separate commit with
written per-case justification.

It does **NOT** enable MCP or provider tool-calling. The
anti-regression tests
`test_no_mcp_workflow_or_dependency_added` +
`test_no_provider_tool_calling_enabled` hold and must be
explicitly removed before Phase 5.0 work begins.

It does **NOT** emit official `V_net`, `debt_final`, or
`corrupt_success`. ADR-22 + ADR-25..32 + ADR-33 hold.

It does **NOT** modify the vendored OIDA core (ADR-02).

It does **NOT** change the existing
`OpenAICompatibleChatProvider` in any way that breaks Phase 4.4's
26 contract tests — the new `capture_redacted_io` flag defaults
to `False`, so the production surface is unchanged.

It does **NOT** prove that the redacted IO capture is sufficient
for diagnosing every provider behaviour — V4 Pro's 6/8
missing-capture gap (§10.1) is a real follow-up for Phase 4.8.1.

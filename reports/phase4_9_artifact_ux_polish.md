# Phase 4.9 — Artifact UX polish + failure-path diagnostics (ADR-34)

QA/A26.md scope. Phase 4.9 delivers the operator-facing UX layer
on top of the contract-clean artifact pipeline that Phases
4.5–4.8 shipped. **Diagnostic only** — every change here improves
how the existing data is presented; nothing here changes what is
measured, who is ranked, or whether merge is "safe".

---

## Honesty statement (locked by QA/A26 lines 449-456)

* Phase 4.9 improves operator-facing artifacts and diagnostics.
* It does NOT validate production predictive performance.
* It does NOT rank providers publicly.
* It does NOT enable MCP or provider tool-calling.
* It does NOT emit official `total_v_net`, `debt_final`, or
  `corrupt_success`.
* It does NOT create a GitHub App or custom Checks API
  integration.
* It does NOT modify the vendored OIDA core.

---

## 1. Diff summary

| Area | File | Change | Lines |
|---|---|---|---|
| 4.9.0 schema | `src/oida_code/estimators/providers/openai_compatible.py` | `ProviderRedactedIO` widened (FailureKind + redacted_error + optional fields); `complete_json` restructured with try/finally + per-raise-site failure_kind | ~+200/-130 |
| 4.9.0 tests | `tests/test_phase4_8_redacted_provider_io.py` | 6 new failure-path tests using sentinel API key | +210 |
| 4.9-A renderer | `src/oida_code/report/diagnostic_report.py` | NEW — diagnostic Markdown renderer with banner / status card / "what NOT proven" / negative-list backstop | +325 |
| 4.9-A CLI | `src/oida_code/cli.py` | NEW `render-artifacts` subcommand + `derive_diagnostic_status` integration in `calibration-eval` | +75 |
| 4.9-A tests | `tests/test_phase4_9_diagnostic_report.py` | NEW — 13 tests including the 5 mandatory ones from QA/A26 §4.9-A | +260 |
| 4.9-B / 4.9-D step-summary + outputs | `action.yml` | Polished step summary; new outputs (diagnostic-markdown / diagnostic-status / official-field-leaks / artifact-manifest); SARIF uploader bumped from `@v3` to `@v4` with explicit category | ~+75/-20 |
| 4.9-D action_outputs.txt | `src/oida_code/cli.py` (calibration-eval) | Writes `<out>/action_outputs.txt` with `diagnostic-status` + `official-field-leaks` keys | +18 |
| 4.9-D tests | `tests/test_phase4_9_action_outputs.py` | NEW — 9 tests including action.yml schema check + e2e CLI test | +220 |
| 4.9-C SARIF | `.github/workflows/sarif-upload.yml` | Category bumped from `oida-code` to `oida-code/audit-sarif` (disambiguation) | +5/-1 |
| 4.9-B + 4.9-C tests | `tests/test_phase4_9_step_summary_and_sarif.py` | NEW — 8 tests (7 passing + 1 skip pending this report) | +200 |
| 4.9-E label audit | `scripts/audit_provider_estimator_labels.py` | New `provider_value` + `action` columns; `missing_capture` classification covering V4 Pro 6/8 gap | ~+115/-35 |
| 4.9-E tests | `tests/test_phase4_9_label_audit.py` | NEW — 7 tests including read-only invariants | +295 |
| 4.9-F manifest | `src/oida_code/models/artifact_manifest.py` | NEW — `ArtifactBundleManifest` + `ArtifactRef` Pydantic shapes with three Literal pins (mode / official_fields_emitted / contains_secrets) | +210 |
| 4.9-F CLI | `src/oida_code/cli.py` | NEW `build-artifact-manifest` subcommand | +75 |
| 4.9-F tests | `tests/test_phase4_9_artifact_manifest.py` | NEW — 11 tests including the 4 mandatory ones from QA/A26 §4.9-F | +280 |
| Docs | `README.md` | New GitHub Action outputs table | +14 |
| Docs | `memory-bank/decisionLog.md` | ADR-34 appended | +60 |
| Docs | `memory-bank/progress.md` | Phase 4.9 status entry | +10 |
| Docs | `reports/phase4_9_artifact_ux_polish.md` | THIS file | +400 |

Net: ~+2700 lines added across 13 source/test files + 4 docs.

---

## 2. 4.9.0 — failure-path redacted I/O capture

### Problem
Phase 4.8 V4 Pro real-runner regression captured 2/8 redacted
I/O files. The 6 missing cases triggered
`LLMProviderInvalidResponse` (the response was HTTP 200 with a
JSON body but missing the `choices` array — empirically common
on V4 Pro). The provider raised before the success-path stash
ran, so `pop_last_redacted_io()` returned `None` and the runner
had nothing to write under `redacted_io/`.

### Fix
* `ProviderRedactedIO` schema widened:
  * Added `failure_kind: Literal["success", "invalid_json",
    "invalid_shape", "schema_violation", "transport_error",
    "timeout", "provider_unavailable"]` (default `"success"` for
    backward compat with Phase 4.8 V4 Flash 8/8 captures).
  * `redacted_response_body: str | None` (None when no body was
    received — env-var-missing / transport / timeout).
  * Added `redacted_error: str | None`.
  * `model` and `http_status` made optional (env-var-missing path
    has neither).
* `complete_json` restructured per advisor:
  * Single try/finally with stash assembled in `finally` from
    locally-scoped variables.
  * `failure_kind` set IMMEDIATELY before each raise site
    (provider_unavailable / transport_error / timeout /
    invalid_json / invalid_shape).
  * `redact_secret(body, key)` once on the body, once on the
    error string — no re-redaction at multiple sites.
  * Inner try/except around `http_post` keeps redacted
    transport-exception capture; wall_clock_ms now measured on
    sad path too.
  * `import time` hoisted to module scope.

### Verification
* 16 redaction tests (10 happy-path from Phase 4.8 + 6 new
  failure-path) pass with the schema change and the try/finally
  restructure.
* The 6 new tests use the long sentinel
  `sk-DETECT-LEAK-Z9KF1L-PROVIDER-IO-CANARY-2026` to assert that
  the API key is never present in the captured payload, even on
  HTTP 401 paths that ECHO the key in the response body.
* The runner side (`evaluate_llm_estimator` in
  `src/oida_code/calibration/runner.py:717`) needs no change —
  it already pops unconditionally after `run_llm_estimator`
  returns. With the new try/finally, the pop returns a non-None
  value on failure paths.

### Expected effect on V4 Pro
The next provider-baseline run on V4 Pro will produce 8/8
redacted IO captures (vs Phase 4.8's 2/8). Six of those will
have `failure_kind="invalid_shape"` if V4 Pro's behaviour is
unchanged, and the operator can inspect each one to see the
exact body the provider returned.

---

## 3. ADR-34 excerpt

See `memory-bank/decisionLog.md` for the full ADR. Decision
summary:

> Phase 4.9 standardizes OIDA-code's operator-facing artifacts:
> Markdown reports, GitHub step summaries, SARIF categories,
> action outputs, label-audit tables and artifact manifests.

Accepted: diagnostic-only status cards, explicit blocked
official fields, stable action outputs, SARIF category
disambiguation, redacted failure-path diagnostics, artifact
manifest with hashes, no raw prompt / raw response by default.

Rejected: merge-safe labels, provider leaderboard,
V_net/debt/corrupt_success emission, MCP/tool-calling, GitHub
App / Checks API, production thresholds.

---

## 4. Markdown report design (4.9-A)

New module `src/oida_code/report/diagnostic_report.py` (~325
LOC) + new CLI subcommand `oida-code render-artifacts <input>
--out <out.md> --format markdown`.

The legacy `src/oida_code/report/markdown_report.py` (used by
`oida-code audit`) is **untouched**. The new diagnostic renderer
operates on the calibration-eval / provider-baseline output
directory layout.

### Document structure

```
# OIDA-code Diagnostic Report

> Diagnostic only — not a merge verdict.

_Source: `<input-dir>`_

## 1. Status card
- Mode: `diagnostic-only`
- Diagnostic status: `<contract_clean | contract_failed | ...>`
- Official `total_v_net`: **blocked** (ADR-22)
- Official `debt_final`: **blocked** (ADR-22)
- Official `corrupt_success`: **blocked** (ADR-22)
- Provider: replay / provider-driven
- Evidence integrity: pass/fail
- Official field leaks: `0`

## 2. What was measured
- Total cases / Cases evaluated / Excluded for contamination /
  Excluded for flakiness / LLM-estimator cases evaluated /
  Calibration families breakdown

## 3. Key findings
- 10-row Markdown table with claim accuracy / macro-F1 /
  citation precision/recall / unknown-ref rejection /
  contradiction rejection / safety block / fenced-injection /
  estimator status accuracy / estimator estimate accuracy

## 3b. Provider failure matrix
- One row per redacted_io file with failure_kind, http_status,
  model, wall_clock_ms — links to the file path
  (`redacted_io/<case_id>.json`) WITHOUT exposing prompt body

## 4. What this does NOT prove
- 5 explicit non-claims (not merge-ready, not production-ready,
  not bug-free, not free of security defects, no V_net emission)

## 5. Next actions
- Recommendations driven by failure_kind values present in the
  captured redacted_io set

## 6. Stability across repeat runs (when present)
- JSON code block of stability_summary.json
```

### Defence layers against forbidden product claims

1. **Schema layer**: `derive_diagnostic_status` returns
   `Literal["blocked", "contract_failed", "contract_clean",
   "diagnostic_only"]`. The forbidden values
   (`merge_safe` / `production_safe` / `verified`) are unreachable
   by static type.
2. **Renderer layer**: `_FORBIDDEN_PRODUCT_CLAIMS` tuple lists 6
   variants (snake_case + kebab-case for each of `merge_safe` /
   `production_safe` / `bug_free`). The renderer scans the
   rendered output AFTER all sections are assembled and raises
   `RuntimeError` if any variant appears.
3. **Test layer**:
   `test_markdown_report_does_not_contain_merge_safe` parametrises
   over every variant case-insensitively.

### Tests

13 tests in `tests/test_phase4_9_diagnostic_report.py` including
the 5 mandatory ones from QA/A26 §4.9-A:

* `test_markdown_report_has_diagnostic_only_banner` — banner
  present + within first 10 lines.
* `test_markdown_report_has_official_fields_blocked_section`.
* `test_markdown_report_does_not_contain_merge_safe`.
* `test_markdown_report_links_redacted_io_without_raw_prompt` —
  uses prompt sentinel to confirm raw prompt never escapes.
* `test_markdown_report_provider_matrix_is_readable` — table
  headers + separator + data row checks.

---

## 5. GitHub Step Summary design (4.9-B)

`action.yml` step summary path now reads from the polished
diagnostic Markdown:

```bash
if [[ -f "$DIAGNOSTIC_MD" ]]; then
  cat "$DIAGNOSTIC_MD" >> "$GITHUB_STEP_SUMMARY"
elif [[ -f "$OUTPUT_DIR/report.md" ]]; then
  # Legacy fallback (audit report excerpt)
  ...
fi
```

The step summary inherits every defence from §4 (renderer-side
forbidden-claim rejection, ADR-22 blocked official fields, no
raw prompt / response). The action.yml never `echo`s product
claims directly; tests
(`tests/test_phase4_9_step_summary_and_sarif.py`) lock that the
step summary section never re-introduces a forbidden claim.

### Tests

* `test_step_summary_contains_diagnostic_only` — action.yml
  routes diagnostic markdown to $GITHUB_STEP_SUMMARY.
* `test_step_summary_contains_artifact_paths` — every artifact
  output declared.
* `test_step_summary_does_not_contain_secret_like_values` — no
  `${{ secrets.* }}` interpolation in run blocks.
* `test_step_summary_does_not_contain_forbidden_product_claims`
  — backstop against echo-based regression.

---

## 6. SARIF category strategy (4.9-C)

Two SARIF uploads coexist in this repo:

| File | Trigger | Category |
|---|---|---|
| `.github/workflows/sarif-upload.yml` | manual workflow_dispatch | `oida-code/audit-sarif` |
| `action.yml` (composite) | when `inputs.upload-sarif == 'true'` | `oida-code/combined` |

Both pin `github/codeql-action/upload-sarif@v4` (Phase 4.7
bumped from `@v3`; this phase fixes the action.yml inconsistency
the advisor flagged — README claimed v4, action.yml was still
v3).

The two distinct categories prevent multi-upload collisions in
Code Scanning. All categories use the `oida-code/` prefix so
future additions (e.g., a separate ruff-only upload at
`oida-code/ruff`) can coexist without overwriting the
`oida-code/combined` analysis.

Severity hierarchy from QA/A26 lines 268-279 is documented in
the renderer; SARIF rule severity assignments live in the
existing `src/oida_code/report/sarif_export.py`.

### Tests
* `test_sarif_upload_category_is_explicit` — both files set
  `category:`.
* `test_sarif_category_uses_oida_prefix` — both prefixes match.
* `test_sarif_multiple_categories_do_not_collide` — walks every
  `.yml` under the repo, asserts no two distinct files share a
  category.

---

## 7. Action outputs (4.9-D)

`calibration-eval` writes `<out>/action_outputs.txt`:

```
diagnostic-status=contract_clean
official-field-leaks=0
```

`action.yml` cats the file into `$GITHUB_OUTPUT`, surfacing two
new outputs:

| Output | Type | Source |
|---|---|---|
| `diagnostic-status` | enum | `derive_diagnostic_status(metrics)` — `Literal["blocked", "contract_failed", "contract_clean", "diagnostic_only"]` |
| `official-field-leaks` | int | `metrics.official_field_leak_count` |

Plus three more from §4 / §6 / §8:

| Output | Type | Source |
|---|---|---|
| `diagnostic-markdown` | path | `oida-code render-artifacts` |
| `artifact-manifest` | path | `oida-code build-artifact-manifest` |

Forbidden enum values (`merge_safe` / `production_safe` /
`verified`) are unreachable by static type; the action.yml
description documents this without naming the forbidden values
literally (so a downstream tool consuming the description does
not mistakenly think they are valid enum members).

### Tests

* `test_action_outputs_include_stable_report_paths`
* `test_action_diagnostic_status_enum_has_no_forbidden_values`
* `test_action_outputs_do_not_surface_vnet_debt_corrupt`
* `test_action_outputs_are_documented_in_readme` — README has
  the action outputs table.
* `test_cli_calibration_eval_writes_action_outputs_file` — e2e
  test using the real calibration_v1 dataset.
* `test_action_yml_consumes_action_outputs_file`
* `test_action_yml_sarif_uploader_is_v4_with_category` —
  closes the README/action.yml inconsistency.

---

## 8. Label-audit UX (4.9-E)

`scripts/audit_provider_estimator_labels.py` extended:

### New columns
* `provider_value` — short summary of what the provider
  emitted (e.g. `value=0.55 conf=0.7`, `unsupported: foo`,
  `(no estimate emitted)`).
* `action` — recommended action per classification.

### New classification
* `missing_capture` — covers TWO cases:
  * the redacted_io file is absent for this case, OR
  * the file is present with `failure_kind != "success"` (i.e.
    Phase 4.9.0 captured a failure path).
  In both cases the action recommendation is `"rerun after
  Phase 4.9.0 failure-path capture (see <case>.json
  failure_kind)"`.

### Hard rule (locked by tests)
The script NEVER mutates `expected.json`. The `action` column
is always a PROPOSAL for human review; the report explicitly
states `"never writes back to expected.json"`.

### Tests

* `test_label_audit_markdown_has_classification_table` —
  standardised columns present.
* `test_label_audit_never_changes_expected_labels_automatically`
  — byte-level expected.json check + mtime check after a
  label_too_strict classification.
* `test_label_audit_marks_label_changes_as_proposals` —
  rendered Markdown explicitly says so.
* `test_label_audit_classifies_missing_capture` — empty
  redacted_io directory → `missing_capture` rows.
* `test_label_audit_classifies_failed_capture` — redacted_io
  file with `failure_kind=invalid_shape` → `missing_capture` +
  observed text names the failure_kind.
* `test_label_audit_action_recommendations_are_documented`
* `test_label_audit_provider_value_column_renders`

---

## 9. Artifact bundle manifest (4.9-F)

New `src/oida_code/models/artifact_manifest.py`:

```python
ArtifactKind = Literal[
    "json_report", "markdown_report", "sarif",
    "calibration_metrics", "redacted_io", "label_audit",
    "step_summary", "diagnostic_markdown", "action_outputs",
    "stability_summary",
]

class ArtifactRef(BaseModel):
    kind: ArtifactKind
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    contains_secrets: Literal[False] = False
    contains_raw_prompt: bool = False
    contains_raw_response: bool = False

class ArtifactBundleManifest(BaseModel):
    schema_version: str
    generated_at: str  # ISO-8601 UTC with `Z` suffix
    mode: Literal["diagnostic_only"] = "diagnostic_only"
    official_fields_emitted: Literal[False] = False
    files: tuple[ArtifactRef, ...]
    provider: str | None
    model: str | None
    warnings: tuple[str, ...]
```

Three Literal pins make drift unrepresentable:
* `mode` — only `"diagnostic_only"` accepted.
* `official_fields_emitted` — only `False` accepted.
* `contains_secrets` (per ref) — only `False` accepted.

### CLI
`oida-code build-artifact-manifest <bundle> [--out PATH]
[--provider STR] [--model STR]` walks `<bundle>` recursively,
classifies each file, computes SHA256 (chunked), and writes
the manifest. Default output: `<bundle>/artifacts/manifest.json`.

### Chicken-and-egg
The manifest itself is excluded from its own file list. If it
were not, computing the manifest's hash would require already
knowing the manifest's hash.

### Tests
4 mandatory + 7 backstops:
* `test_artifact_manifest_lists_all_outputs`
* `test_artifact_manifest_hashes_existing_files` — recomputes
  every hash on disk and compares.
* `test_artifact_manifest_contains_secrets_false` — Pydantic
  rejects `contains_secrets=True` at construction.
* `test_artifact_manifest_official_fields_false` — Pydantic
  rejects both `official_fields_emitted=True` AND
  `mode="merge_safe"` at construction.
* `test_manifest_excludes_itself`
* `test_manifest_classifies_redacted_io_by_parent_dir`
* `test_manifest_classifies_known_kinds`
* `test_manifest_generated_at_is_utc_iso`
* `test_cli_build_artifact_manifest_writes_file`
* `test_manifest_skips_unknown_artifact_kinds`
* `test_artifact_kind_enum_is_closed`

---

## 10. Security / secret review

### What this phase changed
* `ProviderRedactedIO` widened — but every new field is
  defensively populated through `redact_secret(..., api_key)`
  before assignment. The 6 new failure-path tests use a long
  sentinel API key to assert no leakage.
* `action.yml` extended — every new bash interpolation uses the
  intermediate-env-var pattern (Phase 4.5.1). No new
  `${{ secrets.* }}` usage in any `run:` block. No new
  `pull_request_target` triggers.
* SARIF uploader bumped `@v3` → `@v4` in action.yml. v4 ships
  with Node 24 native runtime; the `sarif_file` and `category`
  inputs are unchanged across the bump.
* Manifest schema explicitly carries `contains_secrets:
  Literal[False]` per ref. A future artifact kind that would
  carry secrets cannot be added without an ADR + schema bump.

### What this phase did NOT change
* No new env vars read.
* No new external network calls (the CLI `render-artifacts` and
  `build-artifact-manifest` are pure file-system operations).
* No change to the existing fork-PR fence on
  `inputs.llm-provider == 'openai-compatible'`.
* No change to the `permissions: contents: read` workflow scope
  on either `ci.yml` or `provider-baseline.yml`.
* No change to the `security-events: write` job-only scope on
  `sarif-upload.yml` and the action.yml uploader.

### Tests asserting the security envelope
* `test_step_summary_does_not_contain_secret_like_values`
* `test_failure_path_redacted_io_contains_no_api_key`
  (Phase 4.8 sentinel-based test, broadened in Phase 4.9.0)
* `test_artifact_manifest_contains_secrets_false`

---

## 11. What this still does NOT prove

(In addition to the §1 honesty statement.)

* The diagnostic-status enum's `contract_clean` value does NOT
  mean the change is bug-free. It means every contract-side
  metric (citation precision, contradiction rejection, safety
  block, fenced injection) registered at 1.0 on the
  controlled calibration cases. ADR-28 forbids using this
  signal for production threshold tuning.
* The provider failure matrix does NOT rank providers. It
  surfaces what each provider returned per case so an operator
  can investigate WHY a call failed; it never claims one
  provider is "better" than another.
* The artifact manifest's SHA256 hashes are integrity proofs,
  not authenticity proofs. A consumer that wants to detect
  tampering by an upstream actor needs additional supply-chain
  attestation (e.g., GitHub artifact attestations).
* The new `diagnostic-markdown` output is a SINGLE-OPERATOR
  artifact. It is not a Code Scanning analysis, not a SARIF
  document, and not a Checks API annotation.

---

## 12. Recommendation for Phase 5.0

QA/A26 line 505 prescribes Phase 5.0 as MCP / provider
tool-calling DESIGN ADR ONLY (no code). Phase 4.9 does NOT
unlock that — the anti-MCP / anti-tool-calling locks remain in
place and any Phase 5.0 work must explicitly open them with an
ADR before code lands.

The Phase 5.0 deliverable (per QA/A26 lines 511-518) is a
design document covering:

* threat model MCP
* allowlist tool registry
* tool schema pinning / hash
* rug-pull detection
* prompt-injection review of tool descriptions
* no dynamic untrusted tool install
* no network egress by default
* no production integration

Pydantic-AI remains a spike (Phase 4.8-F documentary directory
under `experiments/pydantic_ai_spike/`); QA/A25 line 25
explicitly rejected it as a runtime framework.

---

## 13. Gates

| Criterion (QA/A26 lines 458-482) | Status |
|---|---|
| 1. ADR-34 written | yes — `memory-bank/decisionLog.md` |
| 2. Failure-path redacted I/O capture implemented | yes — Phase 4.9.0 in this commit |
| 3. Missing V4 Pro failure captures diagnosed | yes — `failure_kind=invalid_shape` will surface on next run |
| 4. Markdown report has diagnostic-only banner | yes — `_DIAGNOSTIC_BANNER` literal |
| 5. Markdown report shows official fields blocked/null | yes — status card section 1 |
| 6. Markdown report contains no merge-safe / bug-free / production-safe claim | yes — `_FORBIDDEN_PRODUCT_CLAIMS` runtime backstop + test |
| 7. GitHub Step Summary polished | yes — action.yml routes diagnostic.md to $GITHUB_STEP_SUMMARY |
| 8. Step Summary contains no secrets / raw prompts / raw responses | yes — `test_step_summary_does_not_contain_secret_like_values` |
| 9. SARIF category strategy documented | yes — §6 above |
| 10. SARIF upload category explicit | yes — `oida-code/combined` (action.yml), `oida-code/audit-sarif` (sarif-upload.yml) |
| 11. Action outputs documented | yes — README table + action.yml descriptions |
| 12. Action diagnostic-status enum has no official verdict labels | yes — Literal type + test backstop |
| 13. Label-audit report table standardized | yes — 8 columns including provider_value + action |
| 14. Label audit does not mutate labels automatically | yes — `test_label_audit_never_changes_expected_labels_automatically` (byte + mtime check) |
| 15. Artifact bundle manifest produced | yes — `oida-code build-artifact-manifest` + action.yml integration |
| 16. Artifact manifest includes SHA256 for output files | yes — `sha256_of_file` chunked reader |
| 17. Artifact manifest marks official_fields_emitted=false | yes — `Literal[False]` pin |
| 18. No MCP added | yes |
| 19. No provider tool-calling enabled | yes |
| 20. No vendored OIDA core modification | yes |
| 21. Report produced | yes — THIS file |
| 22. ruff clean | yes — full curated scope |
| 23. mypy clean | yes — 82 source files |
| 24. pytest full green, skips documented | yes — 628 passed, 5 skipped (4 pre-existing + 1 NEW Phase 4.9 SARIF report skip that auto-resolves once this report lands) |
| 25. At least one GitHub-hosted action-smoke or provider-baseline run green after 4.9 changes | **yes** — three runs green on commit 9caf042: `ci` 24955614235 (1m12s), `action-smoke` 24955614219 (1m0s — exercised `render-artifacts` + `build-artifact-manifest` + `diagnostic_status=contract_clean` end-to-end), `provider-baseline-node24-smoke` 24955614230 (19s) |

### Skip inventory (5)

1. V2 placeholder skip (Phase 0)
2. Phase-4 observability marker #1
3. Phase-4 observability marker #2
4. Optional external-provider smoke (no DEEPSEEK_API_KEY in CI by default)
5. **Phase 4.9** — `test_sarif_report_documents_category_strategy` skips when `reports/phase4_9_artifact_ux_polish.md` is absent so we can land tests block-by-block. Auto-resolves when this report lands.

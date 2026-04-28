# `reports/calibration_seed/` — schema

Field-by-field definition of the `index.json` and
`exclusions.json` files produced by
`scripts/build_calibration_seed_index.py`. Per ADR-53 / QA/A44
§"Calibration dataset boundaries".

## `index.json` — inclusion records

`index.json` is a JSON array of inclusion records. Each record
is a public Python PR that was selected as a candidate beta case
for the Phase 6.1' bundle authoring stress-test corpus.

### Record fields

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | str | yes | Stable id. Format: `seed_<NNN>_<repo_slug>_<pr_number>`, e.g. `seed_001_pallets_click_2823`. Unique across all records. |
| `repo_url` | str | yes | Public GitHub URL, e.g. `https://github.com/pallets/click`. |
| `pr_number` | int | yes | GitHub PR number. |
| `title` | str | yes | PR title at collection time. |
| `base_sha` | str | yes | 40-char SHA of the PR base commit. |
| `head_sha` | str | yes | 40-char SHA of the PR head commit. |
| `changed_files_list` | list[str] | yes | Relative file paths touched by the PR. Filenames only — no content. |
| `labels_observed` | list[str] | yes | GitHub labels visible publicly at collection time. May be empty. |
| `merge_status` | str | yes | One of `merged`, `closed`, `open`. |
| `candidate_reason` | str | yes | One-sentence operator note on why this PR was selected. Free-form. |
| `claim_id` | str \| null | yes | A `C.<surface>.<claim>` identifier (see `docs/beta/beta_case_template.md`). May be `null` if not yet assigned (then `human_review_required: true`). |
| `claim_type` | str \| null | yes | One of the 7 `LLMEvidencePacket.allowed_fields` Literal values, or `null` if not yet assigned. See "Allowed claim types" below. |
| `claim_text` | str \| null | yes | One-paragraph human-written description of the claim. May be `null` initially; populated MANUALLY. |
| `evidence_items` | list[obj] \| null | yes | List of traceable evidence items the LLM (and downstream verifier) cite. Each item: `{id, kind, summary, source, confidence}`. May be `null` initially. Schema mirrors `LLMEvidencePacket.evidence_items` exactly. See "evidence_items shape" below. Phase 6.1'b (ADR-55) added this field as a Tier 3 free-form domain reasoning field. |
| `test_scope` | str \| null | yes | pytest scope (file or `file::test_name`). May be `null` initially. |
| `expected_grounding_outcome` | str | yes | One of the structural outcomes — see "Allowed grounding outcomes" below. |
| `label_source` | str | yes | One of the strict allowlist values — see "Allowed label sources" below. |
| `selection_source` | str | yes | One of `manual`, `llm_assist`, `random_sample`, `curated`. |
| `llm_assist_used` | bool | yes | True iff a provider call was used to suggest the case or its claim. |
| `human_review_required` | bool | yes | True iff the case is not yet ready for stress-test (e.g. claim text not assigned). |
| `collected_at` | str (ISO 8601) | yes | UTC timestamp when the metadata was collected. |
| `script_version` | str | yes | Version of `scripts/build_calibration_seed_index.py` that produced this record. Format: `phase6_1_a_pre_v1`. |
| `public_only` | bool | yes | Always `true`. Asserted at collection time; the script refuses if a private repo is encountered. |

### `evidence_items` shape

Each item in the `evidence_items` list MUST be an object with
exactly these fields (the shape mirrors
`src/oida_code/estimators/llm_prompt.py::EvidenceItem` Pydantic
model so a downstream conversion to `LLMEvidencePacket` is
mechanical):

| Field | Type | Constraint |
|---|---|---|
| `id` | str | Non-empty. Convention: `[E.<kind>.<n>]` e.g. `[E.event.1]`, `[E.test_result.1]`. The convention matches `LLMEvidencePacket.evidence_items[].id`. |
| `kind` | str | One of: `intent`, `event`, `precondition`, `tool_finding`, `test_result`, `graph_edge`, `trajectory`, `repair_signal` (per `EvidenceKind` Literal). |
| `summary` | str | Max 400 chars. Human-readable one-sentence summary of the evidence. Cannot reference forbidden phrases (V_net, debt_final, corrupt_success, verdict, merge_safe, production_safe, bug_free, security_verified). |
| `source` | str | Min 1, max 80 chars. Free-form pointer e.g. `git`, `ticket`, `github_pr_metadata`, `local_pytest`, `static_analysis`. |
| `confidence` | float | In [0.0, 1.0]. Operator's confidence that this evidence is what it says it is. Backports / cherry-picks should drop confidence somewhat (e.g. 0.85 vs 0.95) because the diff has been re-applied. |

`evidence_items` is **not auto-fillable from the GitHub API**.
This is a Tier 3 (free-form domain reasoning) field per ADR-54.
The bundle authoring helper (Phase 6.1'b `prepare-gateway-bundle`)
does NOT generate evidence items — it consumes them from the seed
record. The operator authors them after reading the diff.

The `id` convention `[E.<kind>.<n>]` matches the Phase 4.0
`LLMEvidencePacket.evidence_items[].id` shape so a downstream
`packet.json` mechanical conversion is straightforward.

### Allowed claim types (`claim_type`)

Per `LLMEvidencePacket.allowed_fields` Literal allowlist:

* `capability_sufficient`
* `benefit_aligned`
* `observability_sufficient`
* `precondition_supported`
* `negative_path_covered`
* `repair_needed`
* `shadow_pressure_explained`

Plus `null` for cases where the claim has not yet been assigned.

### Allowed grounding outcomes (`expected_grounding_outcome`)

These are **structural** expectations, NOT product verdicts:

* `evidence_present` — the test scope plus the claim type
  produces visible evidence in tool output that supports the
  claim.
* `evidence_absent` — the test scope produces no evidence
  supporting the claim (might be a real diagnostic miss).
* `tool_missing` — the case requires a tool not available in
  the verifier configuration (e.g. requires `codeql`).
* `scope_invalid` — the test scope cannot be resolved from the
  bundle (path doesn't exist, test name doesn't match).
* `ambiguous` — the case has multiple valid interpretations and
  a human review is needed.
* `not_run` — the case was selected but the run was not
  executed yet (initial state for fresh records).

### Allowed label sources (`label_source`)

Strict allowlist per QA/A44 §"Calibration dataset boundaries":

* `deterministic_tool_output` — the label was assigned by reading
  the actual output of `pytest` / `mypy` / `ruff` for the case,
  no LLM involvement.
* `repository_metadata` — the label was assigned from public
  GitHub metadata (PR labels, merge status, CI badges).
* `yann_manual_review` — Yann reviewed the case and assigned
  the label manually.
* `ai_candidate_human_confirmed` — an LLM proposed the label
  and Yann confirmed it after independent review (NOT just
  reading the LLM's reasoning — actually re-checking).
* `unknown_not_for_metrics` — label is not yet ready and the
  case is excluded from any aggregation until reviewed.

**FORBIDDEN values** (must not appear in any record):

* `llm_only`
* `agent_vote`
* `provider_consensus`
* `cold_reader_label`
* `human_beta` when the human is Yann or any AI agent (the
  `human_beta` channel is reserved for external operators and is
  empty per QA/A43).

## `exclusions.json` — exclusion records

`exclusions.json` is a JSON array of exclusion records. Each
record is a public Python PR the operator considered but
rejected. Exclusions are signal — they document why the corpus
is not larger and prevent silently dropping inconvenient cases.

### Record fields

| Field | Type | Required | Description |
|---|---|---|---|
| `repo_url` | str | yes | Public GitHub URL. |
| `pr_number` | int | yes | GitHub PR number. |
| `exclusion_reason` | str | yes | One of the strict allowlist values — see "Allowed exclusion reasons" below. |
| `notes` | str \| null | yes | Free-form operator notes. |
| `collected_at` | str (ISO 8601) | yes | UTC timestamp when the exclusion was recorded. |
| `script_version` | str | yes | Same format as `index.json`. |

### Allowed exclusion reasons (`exclusion_reason`)

* `private_repo_refused` — the script encountered a private repo
  and refused (per the third refusal layer).
* `pr_too_large` — the PR touches too many files (default
  threshold: 30) or too many lines (default threshold: 1000).
* `pr_too_trivial` — the PR is a one-line typo / dependency bump
  / autoformatting commit and would not exercise bundle authoring.
* `non_python_change` — the PR touches no Python source.
* `archived_repo` — the target repo is archived and may not
  represent live engineering practice.
* `flaky_test_suspected` — the test scope is known-flaky (e.g.
  documented in the README) and would produce noisy stress-test
  signal.
* `dependency_failure` — the PR's runtime dependencies cannot be
  satisfied locally (e.g. requires GPU, requires non-public
  index).
* `claim_too_vague` — the PR description does not allow
  reconstructing a `C.<surface>.<claim>` identifier.
* `fork_pr_refused` — the PR is from a fork and the gateway path
  refuses fork PRs per Phase 5.6 fork-PR fence.
* `licence_unclear` — the repo's licence is missing or
  incompatible with even manifest-level recording (rare).
* `secret_observed` — a secret was visible in the diff (extremely
  rare; the script halts and asks the operator to handle).
* `other` — operator-categorized; `notes` field is then
  required.

## File invariants

* `index.json` and `exclusions.json` are JSON arrays at the top
  level (NOT objects).
* The script is idempotent: re-running with the same flags
  against the same repos does NOT duplicate records (keyed by
  `(repo_url, pr_number)`).
* Records are sorted lexicographically by `case_id` for
  inclusions and by `(repo_url, pr_number)` for exclusions.
* Every record has `collected_at` AND `script_version` AND
  `public_only` AND a `MANUAL_EGRESS_SCRIPT` provenance trail.

## What this schema does NOT include

* `agent_label` — that is the AI-tier discriminator. Calibration
  seed records are NOT cold-reader critiques.
* `feedback_channel: human_beta` — that is the external-human
  lane. Calibration seed records are NOT operator feedback.
* `operator_role: project_author` — that is the Yann-solo
  dogfood lane. Calibration seed records are NOT dogfood case
  files.
* 0/1/2 score axes — that is the human-beta form. Calibration
  seed is structural, not behavioural.
* `would_use_again` — same.

The schema is deliberately narrow. It records ENOUGH to
reconstruct any record; not MORE.

## Cross-references

* Lane charter: [`README.md`](README.md)
* ADR-53: `memory-bank/decisionLog.md`
* QA/A44: `QA/A44.md`
* Script: `scripts/build_calibration_seed_index.py`
* Tests: `tests/test_phase6_1_manual_data_lane_isolation.py`

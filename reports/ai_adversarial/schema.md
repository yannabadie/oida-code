# `reports/ai_adversarial/` — AI-tier critique schema

This document defines the minimal schema for AI-tier cold-reader
critiques per ADR-52 / QA/A43 §"Ré-cadrage protocole" Option C.
The schema is **markdown-documented, not Pydantic-enforced** — AI
output is markdown critique files, not structured forms. Future
re-runs may serialize the schema fields into a JSON aggregate;
the markdown stays the canonical surface.

## Why a schema at all

QA/A43 piège 23 ("re-run AI sans pinning") requires every
critique to pin enough metadata for before/after comparison. QA/A43
piège 25 ("métriques AI-tier trop proches des métriques humaines")
requires AI-tier field names to differ visibly from operator-form
field names so they cannot be confused or accidentally aggregated.

## Required fields per critique

Each `critique_<provider>.md` must include the following at the
top of the file (HTML comment block is the canonical location;
markdown body comes after):

```html
<!--
ai_adversarial_critique:
  agent_run_id: <unique id, e.g. "ai_run_2026-04-28_deepseek_001">
  provider: <deepseek | grok | kimi | minimax | hf | codex_chatgpt55 | gemini31>
  model_id: <exact model slug used>
  pin_date: <YYYY-MM-DD when the model id was last verified>
  input_scope:
    commit: <git sha of the docs reviewed>
    files:
      - <relative path>
      - ...
  agent_label: <free-form one-line summary; NOT operator_label>
  finding_ids:
    - C1
    - C2
    - ...
  convergence_level: <not_yet | 1_of_n | n_of_n_partial | n_of_n_full>
  rejected_suggestions:
    - <id of any suggestion the project team rejects up-front>
  human_tier_contamination: false   # MUST always be false
  feedback_channel: ai_tier         # MUST always be "ai_tier" (not "human_beta")
-->
```

The HTML comment is intentional — it stays inert in markdown
rendering, doesn't pollute the human-readable critique, but is
machine-parseable for future aggregation if needed.

## Field semantics

* **`agent_run_id`** — uniqueness across all AI-tier runs ever.
  Suggested format: `ai_run_<YYYY-MM-DD>_<provider>_<seq>`.
* **`provider`** — one of the recognised provider keys. New
  providers added later require an ADR amendment.
* **`model_id`** — the exact slug passed to the API in the
  `model` field. Used for regression comparison.
* **`pin_date`** — when the model id was last verified
  available. AI-tier re-runs after this date should re-verify
  before trusting the slug.
* **`input_scope.commit`** — git sha of the docs at review
  time. Without this, before/after comparisons are meaningless.
* **`input_scope.files`** — exact paths reviewed. Different
  scope = different critique; comparison only valid within the
  same scope.
* **`agent_label`** — one-line free-form summary. **Not**
  `operator_label`. **Not** drawn from the operator-form
  Literal allowlist (`useful_true_positive` etc.). Examples:
  `"docs read as draft, bundle authoring undocumented"`,
  `"verdict-leak risk in plain-language explainer"`,
  `"convergence on bundle friction; rejected one cap-removal
  suggestion as contract-violating"`.
* **`finding_ids`** — references to convergence findings
  (e.g. `C1`, `C2`). The aggregate is the source of truth for
  what each `Cn` means.
* **`convergence_level`** — qualitative descriptor. The
  numerical fields below operate on the aggregate, not on a
  single critique.
* **`rejected_suggestions`** — short ids of any suggestion the
  project team rejects up-front (e.g. `D1` for the cap-removal
  suggestion in the first AI-tier round). Future re-runs will
  not re-litigate rejected suggestions.
* **`human_tier_contamination`** — assertion that this critique
  does NOT pretend to be human feedback. Always `false`.
* **`feedback_channel`** — always `ai_tier`. NEVER `human_beta`
  (the human-beta aggregator rejects this on schema pin).

## Aggregate-level metrics

`reports/ai_adversarial/aggregate.md` is hand-summarized, NOT
generated programmatically. It contains the convergence /
divergence narrative + the following machine-readable counters
in a single HTML comment block at the bottom:

```html
<!--
ai_adversarial_aggregate:
  ai_findings_total: <count of Cn findings>
  ai_convergence_3of3_count: <count of findings cited by all 3 successful agents>
  ai_convergence_2of3_count: <count of findings cited by exactly 2>
  ai_rejected_contract_violation_count: <count of Dn divergences rejected because they violate ADR-22+ pins>
  ai_actioned_findings_count: <count of findings the project team committed to address>
  ai_regression_recheck_passed_count: <count of findings that disappeared / reshaped on re-run>
  ai_runs_attempted: <total provider runs attempted>
  ai_runs_succeeded: <total provider runs that produced critique>
  ai_runs_failed: <total provider runs that failed (auth, network, model id)>
  pin_date: <YYYY-MM-DD>
  scope_commit: <git sha of the docs scope on this run>
-->
```

These names deliberately avoid `operator_*` (per QA/A43 piège 25)
so a future reader cannot confuse them with the human-tier
aggregate.

## What the schema does NOT include

* No `operator_label` field — that is reserved for human-beta.
* No 0/1/2 axis scores — that is reserved for human-beta. AI
  agents do not produce numerical UX axes.
* No `would_use_again` field — that is a human judgement.
* No `usefulness_rate` / `usefulness_score` — that would import
  the human-tier metric vocabulary.
* No `recommendation: <human-beta-recommendation-key>` — AI
  critiques surface findings; the project team decides
  recommendations.

## Cross-lane assertions

The four cross-lane structural tests in
`tests/test_phase6_0_y_prime_lane_isolation.py` enforce:

1. `agent_label` MUST NOT appear in `reports/beta/` (excluding
   isolated subtrees).
2. `feedback_channel: human_beta` MUST NOT appear in
   `reports/ai_adversarial/`.
3. `feedback_channel: human_beta` + `operator_role:
   project_author` MUST NOT both appear in the same file.
4. `docs/project_status.md` MUST contain the three lane labels
   ("external-human beta", "AI-tier", "Yann-solo") so a reader
   sees them spelled out.

## Cross-references

* ADR-52: `memory-bank/decisionLog.md`
* QA/A43: `QA/A43.md`
* Yann-solo schema: `reports/yann_solo/README.md`
* Cross-lane isolation tests:
  `tests/test_phase6_0_y_prime_lane_isolation.py`
* Project status: `docs/project_status.md`
* Aggregate (current): `reports/ai_adversarial/aggregate.md`

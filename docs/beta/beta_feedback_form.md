# Beta feedback form

This is the canonical feedback form for `oida-code` controlled-beta
operators. Fill one form per **completed beta run**, not per beta
operator and not per repository. Submit by committing the filled
form into your beta case directory or by attaching it to the
tracking issue.

## How to use this form

1. Run a beta case end-to-end per the
   [`beta_operator_quickstart.md`](beta_operator_quickstart.md).
2. Wait until the run produces artefacts and you have read the
   Step Summary, `summary.md`, and `grounded_report.json`.
3. Copy this file (the section "Form (one per run)") into your
   feedback. Replace the `<<<...>>>` placeholders.
4. Be honest. The beta is exactly to learn what doesn't work — a
   form full of `2`s is less useful than one with mixed scores and
   real reasons.

> The form is for human judgement. Do **not** ask an LLM to fill
> it for you. The whole point of the controlled beta is operator
> usefulness from a human reader.

## Score axes

Five 0/1/2 axes plus one categorical axis. The score definitions
are deliberately stable across the project (operator-soak uses the
same first four, see
[`docs/operator_soak_runbook.md`](../operator_soak_runbook.md)).

### `summary_readability` — 0|1|2

Can a human reader understand what the report is saying about the
named claim from the Step Summary plus `summary.md`, without having
to read the raw JSON?

* **0** — the summary is unreadable, contradictory, or
  incomprehensible to a non-author.
* **1** — readable with effort, or readable but with at least one
  load-bearing piece of information that requires reading the raw
  JSON.
* **2** — a non-author can read the summary and walk away with the
  right understanding of what the gateway-grounded run found.

### `evidence_traceability` — 0|1|2

Can a human reader trace each claim back to the specific evidence
item, the specific tool result, and the specific test scope?

* **0** — claims float free of evidence; cannot identify the
  evidence backing a claim.
* **1** — traceable but tedious; requires cross-referencing
  multiple files.
* **2** — each claim has a clear, single-hop link to the evidence
  item that supports it (e.g. `[E.event.1] → tool: pytest, scope:
  tests/test_x.py, summary line: "12 passed in 0.3s"`).

### `actionability` — 0|1|2

After reading the report, does the operator know what to do next?
This is the test of "does the diagnostic translate into a human
decision" — not "does the report tell me to merge".

* **0** — the report leaves the operator without a next step.
* **1** — implies a next step but doesn't name it; the operator
  must infer.
* **2** — the next step is clear (e.g. "the named claim is
  supported by the named test scope, the operator can now consider
  the named claim grounded for the named scope" or "the named claim
  has insufficient evidence, the operator should expand the
  pytest scope").

### `no_false_verdict` — 0|1|2

Does the report avoid claiming a product verdict?

* **0** — the report claims `merge-safe` / `production-safe` /
  `bug-free` / `verified` / `security-verified` either directly or
  by strong implication. **Score 0 is a contract violation.**
* **1** — the report does not claim a product verdict but reads as
  if it might if not read carefully.
* **2** — the report is unambiguously diagnostic; an external
  reader would not infer a product verdict.

### `setup_friction` — 0|1|2

How hard was it to get the run to produce its first artefact?
Lower friction = higher score.

* **0** — setup blocked the run; required project-author
  intervention to produce a first artefact.
* **1** — setup required real work (multi-step bundle authoring,
  pytest scope debugging, manifest tweaking) but completed without
  needing to ask the project authors.
* **2** — setup was straightforward; the bundle template + the
  runbook + the existing example were sufficient.

### `would_use_again` — yes|no|maybe

Single categorical axis. Would you use the gateway opt-in path
again on a real claim of yours, given what you know now?

## Open-text questions

Each is required. Be specific. Quote artefact paths or evidence ids
when you can.

1. **Was the GitHub Step Summary understandable to you?**
   What in it confused you? What did you wish was there?
2. **Was the Markdown report (`summary.md`) useful?**
   What in it confused you? What did you wish was there?
3. **Was the link from each named claim to its evidence clear?**
   If not, name a specific claim and describe what was unclear.
4. **Were the audit logs useful, or were they too detailed?**
   Did you read them? Did they change any of your scores above?
5. **Did the diagnostic translate into a clear next action for you?**
   What was it? Did the report help or did you arrive at it on
   your own?
6. **Did the report avoid false product verdicts?**
   If you scored `no_false_verdict` < 2, name the artefact and the
   token / phrase that made you uncomfortable.
7. **What would have to change for you to use this on a real PR?**
   Do not feel obliged to be polite — be specific.

## Form (one per run)

```yaml
# Filename suggestion: reports/beta/beta_feedback_<run_id>.yaml
# (Note: the runner script tolerates either YAML or JSON; YAML
# is easier for humans to author.)
#
# Per QA/A42 condition 2: every field below is REQUIRED.
# The aggregator does NOT silently default missing fields — it
# rejects the form with a clear error so the operator can fix it.
#
# Per QA/A42 condition 3: the `feedback_channel` field must equal
# "human_beta". The reports/ai_adversarial/ lane uses a separate
# channel and a separate aggregator.

feedback_channel: human_beta   # required, must be exactly "human_beta"

beta_run:
  beta_run_id: "<<<github action run id>>>"        # required, non-empty
  beta_case_id: "<<<beta_case_<n>>>"               # required, non-empty
  beta_operator: "<<<operator_handle_or_alias>>>"  # required, non-empty
  target_repo: "<<<owner/name@<sha>>>>"            # required, non-empty
  named_claim: "<<<C.<surface>.<claim>>>>"         # required, non-empty
  pytest_scope: "<<<tests/test_x.py or path/file::test_name>>>"  # required, non-empty
  artifact_url: "<<<https://github.com/.../actions/runs/<id>/artifacts/<aid>>>>"  # optional

scores:
  summary_readability: 0
  evidence_traceability: 0
  actionability: 0
  no_false_verdict: 0
  setup_friction: 0
  would_use_again: maybe   # yes | no | maybe

operator_label: <<<one of: useful_true_positive, useful_true_negative, false_positive, false_negative, unclear, insufficient_fixture>>>

# Required explicit booleans (per QA/A42 condition 2 — silent
# default is rejected; the operator must explicitly affirm).
contract_violation_observed: false
official_field_leak_observed: false

freeform:
  summary_readable: |
    <<<one or two sentences>>>
  report_useful: |
    <<<one or two sentences>>>
  claim_to_evidence_clear: |
    <<<one or two sentences>>>
  audit_logs_useful: |
    <<<one or two sentences>>>
  next_action_clear: |
    <<<one or two sentences>>>
  no_false_verdict_observed: |
    <<<one or two sentences — if scored < 2, name the artefact and the phrase>>>
  what_would_make_you_use_this_on_real_pr: |
    <<<one or two sentences — be specific>>>
```

## Where to submit

* **In a beta case directory**: drop the YAML / JSON form into
  `reports/beta/<beta_case_id>/beta_feedback_<run_id>.yaml`.
* **Via tracking issue**: paste the YAML / JSON form into a
  comment on the project tracking issue (the issue id will be
  shared with each beta operator individually). Don't use a
  public issue thread.

The aggregator script `scripts/run_beta_feedback_eval.py` reads
all YAML / JSON forms under `reports/beta/` and produces the
aggregate report. Submitting a form in either location is enough.

## What happens to your form

* Aggregated by `scripts/run_beta_feedback_eval.py` (zero feedback
  is a clean output, not an error — the script reports
  `beta_feedback_count: 0` and `recommendation: continue_beta`).
* Recorded in `reports/beta/beta_feedback_aggregate.md`.
* Each individual form is preserved in
  `reports/beta/<beta_case_id>/beta_feedback_<run_id>.yaml`.
* No form is sent to an external provider.
* No form is fed back into an LLM.
* No form is published. The aggregate report references operator
  aliases, never real handles or company names.

## What the form does NOT do

* It does not produce a product verdict. The aggregate has axes
  and counts; it does not have `merge-safe`.
* It does not flip `enable-tool-gateway` to default-true. The
  Action input default does not change in Phase 6.0 regardless of
  feedback.
* It does not gate any production decision. The beta is for
  product learning, not for shipping.

## Cross-references

* Known limits: see
  [`beta_known_limits.md`](beta_known_limits.md).
* Quickstart: see
  [`beta_operator_quickstart.md`](beta_operator_quickstart.md).
* Case template: see [`beta_case_template.md`](beta_case_template.md).
* Plain-language overview: see
  [`docs/concepts/oida_code_plain_language.md`](../concepts/oida_code_plain_language.md).

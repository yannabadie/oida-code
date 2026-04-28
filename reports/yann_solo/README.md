# `reports/yann_solo/` — project-author solo dogfood lane

This directory holds **Yann-solo dogfood cases**: beta cases run
by the project author against repos he controls, using the same
gateway opt-in path that external operators would use. The lane
exists per ADR-52 / QA/A43 §"Yann-solo policy".

> **This is NOT external-human beta feedback.** It NEVER enters
> `reports/beta/beta_feedback_aggregate.{json,md}`. It NEVER counts
> as `operators_total`. It NEVER fills `feedback_channel:
> human_beta` (the human-beta aggregator rejects forms with
> `operator_role: project_author` per the cross-lane validation
> test).

## Why this lane exists

QA/A41 §6.0-A targeted "2-3 external operators". QA/A43 records
that external operators are not available. ADR-52 establishes
three separated lanes; this is the third.

Yann is human and his runs are real (workflow_dispatch, real
artefacts, real tool output) — so they have signal that AI-tier
critiques cannot produce. But Yann is also the project author and
co-author of every doc in `docs/beta/` — so he reads them with
the bias of "I know what I meant". This lane is acceptable for
**friction-of-execution** signal but NOT for cold-reader
cognition signal.

## What this lane measures well

* Real time-to-first-bundle for someone using the runbook.
* Number of round-trips against the schema.
* Field-level errors (hard caps, allowlist values, JSON shape).
* `workflow_dispatch` friction (input names, default values,
  artefact path resolution).
* Artefact-reading order — does the Step Summary suffice or
  does the operator need to drop into the JSON?
* **Stability of the docs** — does the author who wrote them
  successfully follow them when he isn't allowed to mentally
  patch the gaps? (Per QA/A43 piège 21: Yann-solo must record
  every moment he uses out-of-doc knowledge; those notes are
  more important than his score.)

## What this lane measures poorly

* First-time conceptual understanding ("what is a verifier
  loop?") — Yann already knows.
* Jargon detection — Yann does not feel the friction of
  "gateway-grounded" or "verification_candidate".
* Pseudo-verdict cognitive risk — a cold reader might over-read
  "strongest positive signal"; Yann won't.
* Confidence in internal terms — Yann is calibrated.

## Schema for a Yann-solo case file

Each case lands as `reports/yann_solo/case_<n>_<short_label>.md`
with a frontmatter-like header at the top:

```yaml
feedback_channel: yann_solo_dogfood    # required, exactly this value
operator_role: project_author          # required, exactly this value
bias_disclosure: author_of_docs_and_protocol  # required
target_repo_familiarity: low|medium|high  # required, one of these
bundle_authoring_mode: manual|generated|mixed  # required
case_id: yann_solo_case_<n>            # required
target_repo: owner/name@<sha>          # required
named_claim: C.<surface>.<claim>       # required
pytest_scope: tests/test_x.py          # required
workflow_run_id: <github action run id>  # required after run lands
artifact_url: <https url>              # required after run lands
```

Plus, in markdown body sections:

* **What the run was supposed to demonstrate** (one sentence)
* **Bundle authoring notes** — every error encountered, every
  hard-cap close call, every moment "I know what I meant"
  shortcut was applied (per QA/A43 piège 21)
* **Run outcomes** — `pytest_summary_line`, `verification_candidate`,
  `gateway_status`, `official_field_leak_count` (last must be 0)
* **Friction observed** — workflow, docs, bundle authoring,
  artefact reading
* **What the docs failed to convey** that an external reader
  would need
* **Honesty statement** — "this is project-author dogfood, not
  external operator validation"

## Schema for a Yann-solo aggregate (when ≥1 case lands)

`reports/yann_solo/aggregate.md` (hand-summarized, NOT generated
by `scripts/run_beta_feedback_eval.py`):

```
yann_solo_total: N
yann_solo_completed: N
contract_violation_count: 0  (must always be 0)
official_field_leak_count: 0  (must always be 0)
mean_bundle_prep_minutes: <observed>
schema_round_trips_total: <count>
out_of_doc_knowledge_uses: <count of "I know what I meant" moments>
docs_gaps_surfaced: <count of distinct gaps>
recommendation: continue_phase_6_1_prime | revisit_phase_6_1_prime_a | <other>
```

`recommendation` is a diagnostic key, NOT a product verdict. It
informs the project team's next decision; it does NOT replace
external-human signal.

## What this lane CANNOT decide

* Phase boundary closure — Yann-solo signal alone is not
  sufficient to close a phase. Per QA/A43 §"Yann-solo policy"
  practical rule: "AI-tier convergence 3/3 + Yann-solo friction
  reproduced = scope acceptable; Yann-solo seul = patch local
  acceptable, phase boundary insuffisant".
* Phase 6.1' scope choice — that comes from the AI-tier C1
  convergence (per QA/A43 §"Phase 6.1 scoping"); Yann-solo
  reproducing the friction is supporting evidence, not the
  primary signal.
* Public claims — Yann-solo runs MUST NOT be cited as "we tested
  with users".

## Cross-references

* ADR-52: `memory-bank/decisionLog.md`
* QA/A43: `QA/A43.md`
* AI-tier schema: `reports/ai_adversarial/schema.md`
* Cross-lane isolation tests:
  `tests/test_phase6_0_y_prime_lane_isolation.py`
* Project status: `docs/project_status.md`

# Phase 6.0 — beta cases registry

This file is the running registry of `oida-code` Phase 6.0
controlled-beta cases. One row per case. Operators add a row
when they file a case and update it when the run lands.

> Phase 6.0 is a controlled beta. This registry is for invited
> operators only. Real handles, real organisation names, and
> sensitive target identifiers do not belong here — use operator
> aliases.

## How rows are added

1. Copy `docs/beta/beta_case_template.md` into
   `reports/beta/beta_case_<n>_<short_label>.md`.
2. Fill the case file.
3. Append a row to the table below referencing the case file.
4. Once the run lands and feedback is submitted, update the run
   id, label, and UX score columns in the row.
5. Re-run `python scripts/run_beta_feedback_eval.py` to refresh
   `beta_feedback_aggregate.md`.

## Status legend

* `beta_pack_only` — pack established, no case filed yet.
  This is the expected Phase 6.0 initial state per QA/A41
  partial-completion authorization (criteria 7–10).
* `case_drafted` — case file exists, bundle authored, run not
  yet dispatched.
* `run_dispatched` — workflow_dispatch invoked, awaiting
  completion.
* `run_completed` — workflow run completed; pending operator
  label and UX scores.
* `feedback_submitted` — feedback form filed; aggregate refreshed.
* `not_run` — case considered but not run; reason recorded in
  the case file (per QA/A41 acceptance criteria 7–10 the
  "explicit not_run reason documented" path is allowed).

## Cases

| n | short label | operator alias | status | case file | run id | label | UX |
|---|---|---|---|---|---|---|---|

_The table is intentionally empty as of Phase 6.0 docs landing.
The Phase 6.0 acceptance criteria 7–10 explicitly authorise
partial completion via "explicit not_run reason documented" —
the protocol is established and the table is the operator-facing
surface; rows are populated as the controlled beta progresses
(or the not_run reasons are recorded if the beta does not
recruit operators within the phase window)._

## Honesty statement (Phase 6.0 frame)

Phase 6.0 runs a controlled beta of the opt-in gateway-grounded
path with selected operators and controlled repos. It does not
make the gateway default. It does not implement MCP. It does not
enable provider tool-calling. It does not validate production
predictive performance. It does not emit official `total_v_net`,
`debt_final`, or `corrupt_success`. It does not modify the
vendored OIDA core.

## Cross-references

* Beta operator quickstart:
  [`docs/beta/beta_operator_quickstart.md`](../../docs/beta/beta_operator_quickstart.md).
* Known limits:
  [`docs/beta/beta_known_limits.md`](../../docs/beta/beta_known_limits.md).
* Case template:
  [`docs/beta/beta_case_template.md`](../../docs/beta/beta_case_template.md).
* Feedback form:
  [`docs/beta/beta_feedback_form.md`](../../docs/beta/beta_feedback_form.md).
* Aggregate report (auto-generated):
  [`beta_feedback_aggregate.md`](beta_feedback_aggregate.md).
* Aggregator script:
  [`scripts/run_beta_feedback_eval.py`](../../scripts/run_beta_feedback_eval.py).

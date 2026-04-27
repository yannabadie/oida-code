# Phase 5.8-prep — Operator soak execution scaffolding

_QA/A36, executed on commit `<this commit>` (post-Phase-5.7)._

## Diff résumé

Phase 5.8-prep is the **operator-prep** half of Phase 5.8. Per QA/A36
explicit constraint, Claude does NOT:

- trigger any `workflow_dispatch`,
- write any `label.json`,
- write any `ux_score.json`,
- forge a `workflow_run_id`,
- mark Phase 5.8 as accepted.

What ships in this commit:

| Component | Path |
|---|---|
| Controlled-change branch (case_001) | `operator-soak/case-001-docstring` @ commit `6585dd4` (docstring-only fix in `src/oida_code/operator_soak/aggregate.py`; not merged into `main`) |
| `case_001_oida_code_self/` updated | `fiche.json` carries branch + commit + intent; status `awaiting_operator_run`; bundle/ seeded |
| `case_002_mini_python_bug/` scaffolded | README + fiche (`awaiting_case_selection`) + bundle/ with 8 seeded files |
| `case_003_import_contract/` scaffolded | README + fiche (`awaiting_case_selection`) + bundle/ with 8 seeded files |
| `operator_soak_cases/RUNBOOK.md` (new) | 8-step operator runbook + `label.json` template + `ux_score.json` template |
| Schema extension | `SoakCaseStatus` Literal gains `awaiting_case_selection` and `awaiting_operator_run` (test pin updated to 7 buckets) |
| 12 new tests | `tests/test_phase5_7_operator_soak.py` (Phase 5.8-prep block: scaffold dirs, fiche statuses, bundle 8-file contract, no-label-yet locks, RUNBOOK section pins, aggregator still continue_soak) |
| Aggregate baseline refreshed | `reports/operator_soak/aggregate.{json,md}` regenerated; recommendation still `continue_soak` (cases_completed=0 — no labels) |

What did **not** change:

- `action.yml` is preserved verbatim (Phase 5.6 surface unchanged since 5.7).
- `enable-tool-gateway` default stays `"false"`.
- The Phase 5.6 fork/PR guard remains active.
- The vendored OIDA core (`src/oida_code/_vendor/`) remains untouched.
- ADR-22 / ADR-24 / ADR-25 / ADR-26 hard wall holds (no `total_v_net` / `debt_final` / `corrupt_success` in any output).

## Branch case_001 — what was changed

`operator-soak/case-001-docstring` carries one commit:

```
6585dd4 docs(operator-soak): align aggregator docstring with QA/A35 §5.8-F
```

The change is **docstring-only** in `src/oida_code/operator_soak/aggregate.py`:
rule 5 in the module docstring now states explicitly that rules 3 and 4
short-circuit before rule 5 fires, so reaching rule 5 implicitly requires
`false_positive_count < 2` AND `false_negative_count < 2`. Behavior is
unchanged. This intentionally satisfies the QA/A36 §1 "wording / docstring
uniquement, aucun changement fonctionnel lourd" criterion.

The branch is pushed to `origin` but **not merged into `main`** per QA/A36
explicit instruction.

## What the operator must do next (NOT Claude)

See `operator_soak_cases/RUNBOOK.md` for the full 8-step procedure. Summary:

1. For `case_002` and `case_003`: pick a real upstream Python repo + commit,
   edit `fiche.json` (`repo`, `branch`, `commit`, `intent`, `expected_risk`),
   and (ideally) replace the seeded `bundle/` files with a real audit packet
   for the picked commit. Honest fallback: keep the seed and label the case
   `insufficient_fixture`.
2. Trigger `workflow_dispatch` against `action-gateway-smoke.yml` with the
   case-specific `bundle-dir`.
3. Capture `workflow_run_id` and `artifact_url` into the case `fiche.json`.
4. Read artefacts in this order: GitHub Step Summary → `summary.md` →
   `grounded_report.json` → `audit/` → `artifacts/manifest.json`.
5. Write `label.json` (one of six labels + 3–10 line rationale).
6. Write `ux_score.json` (four 0/1/2 scores).
7. Re-run `python scripts/run_operator_soak_eval.py` from the repo root.

The `operator_label`, `operator_rationale`, `false_positive`,
`false_negative`, `useful_true_positive` strings must NEVER appear in a file
written by Claude. The QA/A36 lock is structural: the schema accepts these
labels but the protocol rule "no LLM may write `label.json`" is an
operator-discipline rule, not a runtime gate.

## What is intentionally NOT done

| Item | Reason |
|---|---|
| `gh workflow run …` not invoked | QA/A36 §"Ne pas déclencher le workflow" is explicit |
| no `workflow_run_id` written | same |
| no `artifact_url` written | same |
| no `label.json` for any case | operator-only per QA/A34 §5.7-B + QA/A35 §5.8-C |
| no `ux_score.json` for any case | operator-only per QA/A34 §5.7-G + QA/A35 §5.8-C |
| no aggregate manipulation | `cases_completed` stays 0; `recommendation` stays `continue_soak` |
| Phase 5.8 acceptance not claimed | QA/A35 §5.8 acceptance criteria require ≥3 completed cases with operator labels |
| Fork PR smoke not run | inherits Phase 5.7 status `not_run` with reason "no controlled fork available" |

## Quality gates

- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` — clean.
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` — clean (98 source files; identical to Phase 5.7).
- `python -m pytest tests/test_phase5_7_operator_soak.py` — 53 passed (was 41 in Phase 5.7; +12 Phase 5.8-prep tests).
- Full `python -m pytest -q` — to be captured in commit message.

## Stop condition

Per QA/A36 §"Stop condition":

> Phase 5.8-prep complete.
>
> Prepared:
> - branch case_001
> - case_001 fiche
> - case_002 scaffold
> - case_003 scaffold
> - replay bundles
> - RUNBOOK.md
>
> Not done by design:
> - no workflow_dispatch run
> - no label.json
> - no ux_score.json
> - no operator recommendation
> - no Phase 5.8 acceptance

Operator now executes the workflows and writes the labels.

## Honesty statement

Phase 5.8-prep prepares the controlled cases and operator runbook for the
soak protocol. It does not execute the soak. It does not make the gateway
default. It does not run on fork PRs. It does not implement MCP. It does
not enable provider tool-calling. It does not write operator labels. It
does not validate production predictive performance. It does not emit
official total_v_net, debt_final, or corrupt_success. It does not modify
the vendored OIDA core. The Phase 5.7 ADR-42 stance ("operator soak before
wider gateway adoption") is unchanged; Phase 5.8 acceptance is deferred
to the operator session that runs the workflows and labels the cases.

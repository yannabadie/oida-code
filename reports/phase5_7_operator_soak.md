# Phase 5.7 — Operator soak on controlled repos

_QA/A34.md, ADR-42._

## 1. Diff résumé

Phase 5.7 ships the **observation protocol** for the opt-in gateway path
introduced in Phase 5.6 (ADR-41). It introduces no new action surface, no new
dependency, and no change to `enable-tool-gateway` default — that stays
`false`. The deliverables:

| Component | What changed |
|---|---|
| `operator_soak_cases/` (new top-level dir) | Protocol README + `case_001_oida_code_self/` scaffold (README + `fiche.json`) |
| `src/oida_code/operator_soak/` (new package) | `models.py` (Pydantic schemas) + `aggregate.py` (pure aggregator + Markdown renderer) |
| `scripts/run_operator_soak_eval.py` (new) | I/O wrapper that reads JSON sidecars and writes `reports/operator_soak/aggregate.{json,md}` |
| `reports/operator_soak/aggregate.{json,md}` (new) | Empty-cases baseline; `recommendation: continue_soak` |
| `reports/phase5_7_operator_soak.md` (this file) | Phase 5.7 report |
| `memory-bank/decisionLog.md` | ADR-42 appended |
| `tests/test_phase5_7_operator_soak.py` (new) | Schemas + decision rules + anti-MCP locks |

What did **not** change:

- `action.yml` is preserved verbatim (Phase 5.6 surface).
- `enable-tool-gateway` default stays `"false"`.
- The fork/PR guard from Phase 5.6 remains active.
- The vendored OIDA core (`src/oida_code/_vendor/`) remains untouched.

## 2. ADR-42 excerpt

> **ADR-42 — Operator soak before wider gateway adoption.**
>
> Decision: Phase 5.7 measures the opt-in gateway-grounded action path on
> controlled real repos / PRs before documenting wider use.
>
> Accepted: 3–5 controlled repos / PRs · human operator labels · FP/FN
> tracking · artefact usefulness scoring · fork PR block smoke if available ·
> `enable-tool-gateway` remains default `false` · no autonomous background
> agent.
>
> Rejected: scheduled autonomous audits · provider external by default · fork
> PR gateway execution · MCP runtime · provider tool-calling · product-verdict
> labels · official fusion fields (per ADR-22).

Full text in `memory-bank/decisionLog.md` (timestamp `2026-04-27 16:00:00`).

## 3. Case selection

Per QA/A34 §5.7-A the protocol allows up to five cases:

| # | Type | Status in Phase 5.7 |
|---|---|---|
| 1 | oida-code self with controlled minor change | **scaffolded** (`case_001_oida_code_self`, `awaiting_run`) |
| 2 | small hermetic Python repo with simple bug + test | not selected — deferred |
| 3 | simple real Python repo with import/test changes | not selected — deferred |
| 4 | repo with migration / config change | not selected — deferred |
| 5 | repo with explicit fail-to-pass / pass-to-pass | not selected — deferred |

`case_001_oida_code_self` is **scaffolded** rather than executed because there
is no controlled-change branch dedicated to this case on the oida-code repo
today. The Phase 5.6 `tests/fixtures/action_gateway_bundle/tool_needed_then_supported/`
bundle is a contract-test fixture, **not** a real PR soak case — re-using it
as a soak case would contaminate the soak signal (operators would be labelling
artefacts of a contrived bundle, not of a real change). Cases 2–5 require an
operator session to pick controlled changes on real upstreams; that is
deferred to a follow-up phase.

## 4. Run table

| case_id | workflow_run_id | gateway-status | gateway-official-field-leak-count | artefacts |
|---|---|---|---|---|
| `case_001_oida_code_self` | _pending_ | _pending_ | _pending_ | _pending_ |

`reports/operator_soak/aggregate.json` carries the same row plus
`status=awaiting_run`. Until at least one controlled-change run lands the
table cannot be populated honestly.

## 5. Artefact collection

Per QA/A34 §5.7-D each soak run will collect:

```
.oida/operator-soak/<case_id>/
  grounded_report.json
  summary.md
  action_outputs.txt
  audit/
  artifacts/manifest.json
  workflow_run_url
```

These are produced by the existing Phase 5.6 composite Action. **Forbidden in
any artefact**: raw prompt text, raw provider response, secret, token,
non-redacted private log. The Phase 5.6 bundle validator (`validate_gateway_bundle`)
already rejects secret-shaped, provider-config, and MCP-config filenames at
upload time; the soak protocol inherits that filter.

JSON sidecars added by Phase 5.7:

```
operator_soak_cases/<case_id>/
  README.md          # human-readable fiche
  fiche.json         # case metadata (operator authors)
  label.json         # operator label (NO LLM may write this)
  ux_score.json      # operator UX scores (NO LLM may write this)
```

## 6. Operator labels

| Label | Meaning |
|---|---|
| `useful_true_positive` | gateway flagged a real concern that was actionable |
| `useful_true_negative` | gateway correctly stayed quiet on a non-issue |
| `false_positive` | gateway raised a flag that was not actionable |
| `false_negative` | operator found a real concern the gateway missed |
| `unclear` | artefacts insufficient to decide |
| `insufficient_fixture` | bundle / replay / policy not adapted to the case |

Rationale must be 3–10 lines (enforced by `OperatorLabelEntry`). Author
identity (`labeled_by`) is recorded but the schema cannot enforce that the
author is human; the rule "no LLM may write `label.json`" is restated in:

- `operator_soak_cases/README.md` §"What is forbidden"
- `operator_soak_cases/<case>/README.md`
- ADR-42 §Rejected
- `QA/A34.md` §5.7-B / §5.7-G

## 7. FP/FN analysis

Phase 5.7 produces zero completed cases. The aggregator returns
`recommendation: continue_soak` per QA/A34 §5.7-F rule 1
(`cases_completed < 3`). FP/FN counts are zero, not because the gateway is
perfect, but because no human has labelled an artefact yet.

When real operator labels land, FP/FN counts feed two of the five rules:
`false_negative_count >= 2 → revise_gateway_policy_or_prompts`;
`false_positive_count >= 2 → revise_report_ux_or_labels`. ADR-22 (leak count
> 0 → `fix_contract_leak`) beats both.

## 8. UX qualitative scoring

`OperatorUxScore` records four 0/1/2 questions (per QA/A34 §5.7-G):

1. `summary_readability` — GitHub Step Summary suffices to understand result?
2. `evidence_traceability` — `summary.md` clearly explains proven / not proven?
3. `actionability` — `grounded_report.json` has enough to audit?
4. `no_false_verdict` — report proposes useful action without a fake product
   verdict?

Aggregator computes `*_avg`. With zero scored cases, all averages are 0.0; the
renderer prints them with the `_pending_` row in the case table.

## 9. Fork PR smoke

`status = not_run`
`reason = no controlled fork available`

Per QA/A34 §5.7-H, faking this smoke is forbidden. The Phase 5.6 fork/PR
guard (`block-gateway-on-pr` step in `action.yml`) was exercised in Phase 5.6
by parsing the action body and asserting the `::error::` path; that test
(`test_fork_pr_guard_emits_error_in_action_yml`) remains green in Phase 5.7.
Phase 5.7 adds no new live execution because no controlled fork is available
on the oida-code repo today.

## 10. What this still does not prove

- The gateway is not a product verdict layer. It does not emit `total_v_net`,
  `debt_final`, `corrupt_success`, `corrupt_success_ratio`, or any kind of
  "ok-to-ship" / "ok-to-deploy" signal. Phase 5.7 does not change that.
- One scaffolded case is not a soak. The aggregator's `continue_soak`
  recommendation reflects exactly that.
- Schema validation cannot enforce author identity. A motivated operator
  could in principle paste an LLM's draft into `label.json`. The protocol
  relies on the operator following the rule, not on the schema rejecting LLM
  output.
- Predictive validity on real production usefulness is **not** measured.
  Phase 3's length-confound proxy lesson applies here too: usefulness rate
  on 5–8 cases is not a production-ready signal.
- Phase 5.7 does not run on real fork PRs; the fork-PR block remains
  defence-in-depth from Phase 5.6.

## 11. Recommendation for Phase 5.8

`recommendation: continue_soak` (zero completed cases).

Phase 5.8 is therefore an operator action, not a code action: pick ≥3
controlled changes, run the gateway action with `enable-tool-gateway: "true"`
on each, fill out `label.json` + `ux_score.json` by hand, re-run
`scripts/run_operator_soak_eval.py`. Only then does the aggregator produce a
non-trivial recommendation. If `cases_completed >= 5` and
`usefulness_rate >= 0.6` (and FP / FN counts stay below 2 each, and leak
count stays at 0), the recommendation flips to `document_opt_in_path` —
**without** flipping `enable-tool-gateway` default.

## 12. Gates

- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` — clean.
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` — clean.
- `python -m pytest -q` — full green; exact counts captured in commit message at the close of Phase 5.7.
- ADR-42 timestamp `2026-04-27 16:00:00` appended to `memory-bank/decisionLog.md`.
- `reports/operator_soak/aggregate.{json,md}` regenerated and committed (empty-cases baseline).
- `enable-tool-gateway` default still `"false"` in `action.yml`.
- Fork/PR guard step still present in `action.yml`.

## Acceptance criteria (split by what shipped vs what is blocked on operator)

### Shipped in Phase 5.7

| AC | Status |
|---|---|
| ADR-42 written | shipped |
| `enable-tool-gateway` remains default `false` | shipped (action.yml unchanged) |
| No provider external in soak runs | shipped (eval script has no network calls) |
| No MCP dependency added | shipped (lock test) |
| No MCP workflow added | shipped (Phase 5.6 lock unchanged) |
| No provider tool-calling enabled | shipped (lock test) |
| No write/network tools enabled | shipped (lock test) |
| No `pull_request_target` introduced in 5.7 files | shipped (lock test) |
| Each case (when present) has intent / repo / commit / bundle documented | shipped — schema enforced by `OperatorSoakFiche` |
| Artefact bundle path documented | shipped — `operator_soak_cases/README.md` §"Directory layout" |
| Forbidden filenames documented + enforced | shipped (Phase 5.6 `validate_gateway_bundle` reused) |
| FP/FN counts computable | shipped — `aggregate_cases(...)` |
| UX qualitative scores computable | shipped — `OperatorUxScore` + `*_avg` rates |
| `official_field_leak_count == 0` | shipped — operator-supplied tally; default 0; aggregator emits 0 in baseline |
| Report produced | shipped — this file |
| Aggregate baseline produced | shipped — `reports/operator_soak/aggregate.{json,md}` |
| ruff / mypy / pytest gates | shipped at commit time |

### Scaffolded — blocked on operator session

| AC | Status |
|---|---|
| At least 3 controlled cases selected | **scaffolded** (`case_001_oida_code_self` only; needs operator to pick a controlled-change branch) |
| Target 5 controlled cases if available | **deferred** (cases 002–005 not selected) |
| Action runs with `enable-tool-gateway=true` on each completed case | **awaiting_run** (case_001 sits in `awaiting_run`) |
| Human operator label recorded for each completed case | **awaiting** (no `label.json` exists) |
| At least one GitHub-hosted action-gateway-smoke or soak workflow green | **inherits** Phase 5.6 (`action-gateway-smoke` is green on `main`); Phase 5.7 adds no new live runs |
| Fork PR block smoke run | **not_run** with reason `no controlled fork available` |

The split AC table is intentional: Phase 5.7 ships the protocol and locks
that the codebase can enforce, but the human-labelling work cannot be done
inside an LLM-driven phase. That separation is the whole point of ADR-42.

## Honesty statement

Phase 5.7 evaluates the opt-in gateway-grounded action path on controlled operator-selected repos and PRs. It does not make the gateway default. It does not run on fork PRs. It does not implement MCP. It does not enable provider tool-calling. It does not validate production predictive performance. It does not emit official total_v_net, debt_final, or corrupt_success. It does not modify the vendored OIDA core.

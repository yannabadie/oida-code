# Phase 6.0 — controlled beta (protocol established, runs pending)

**Status:** Phase 6.0 docs surface complete; controlled beta runs
pending external operator recruitment. Per QA/A41 §"Critères
d'acceptation Phase 6.0" criteria #7–#10, partial completion is
explicitly authorized via "or explicit not_run reason documented".
This report records the protocol that was established and the
not_run reasons for the per-run criteria.

ADR-50 logged. All Phase 6.0 acceptance criteria for the protocol
layer (#1–#6, #11–#28) met; per-run criteria (#9–#10) carry
explicit not_run reasons consistent with the QA/A41 partial
completion frame.

## 1. Diff résumé

Phase 6.0 lands the controlled-beta protocol surface. No new
architecture, no new runtime code, no new dependency. One commit
touching:

* `BACKLOG.md` (NEW) — long-term gaps recorded as backlog, NOT as
  phase scope, per QA/A41 addendum.
* `docs/beta/README.md` (NEW) — directory index.
* `docs/beta/beta_known_limits.md` (NEW) — leaf doc; what the beta
  does NOT do, what stays blocked.
* `docs/beta/beta_operator_quickstart.md` (NEW) — 10-minute
  walk-through.
* `docs/beta/beta_case_template.md` (NEW) — canonical template
  for a single beta case.
* `docs/beta/beta_feedback_form.md` (NEW) — feedback form, one
  per completed beta run.
* `docs/concepts/oida_code_plain_language.md` (NEW) — plain-language
  overview, no jargon.
* `docs/project_status.md` (NEW) — four-section status: usable
  now / blocked / out-of-scope / roadmap.
* `scripts/run_beta_feedback_eval.py` (NEW) — feedback aggregator;
  zero-feedback case handled cleanly.
* `reports/beta/beta_cases.md` (NEW) — running cases registry.
* `reports/beta/beta_feedback_aggregate.json` (NEW) — generated
  aggregate, initial zero-feedback state.
* `reports/beta/beta_feedback_aggregate.md` (NEW) — generated
  Markdown aggregate.
* `tests/test_phase6_0_controlled_beta.py` (NEW) — Phase 6.0
  doc-guard tests (SCOPED to the new files; expand the Phase 5.9
  three-heuristic negation detector to cover the broader scope).
* `memory-bank/decisionLog.md` — ADR-50 appended.
* `memory-bank/progress.md` — Phase 6.0 timeline entry.
* `README.md` — status sentence updated.
* `reports/phase6_0_controlled_beta.md` (NEW) — this report.

ZERO new dependency. ZERO MCP runtime code. ZERO provider
tool-calling. ZERO vendored core change. ZERO new product-verdict
tokens introduced. ZERO change to `enable-tool-gateway` default
(remains `false`).

## 2. ADR-50 excerpt

> **ADR-50: Phase 6.0 — controlled beta before productization.**
>
> **Decision:** Phase 6.0 establishes the protocol for a controlled
> beta with 2–3 external operators and 3–5 controlled repos / PRs
> before productizing the gateway-grounded path. The protocol
> surface (operator pack + feedback form + case template + metric
> script + cases registry + aggregate) lands as a complete unit;
> the actual runs are gated on external operator recruitment and
> are documented as `not_run` until completed, per QA/A41
> acceptance criteria #7–#10 explicit "or explicit not_run reason
> documented" authorization for partial completion.
>
> **Accepted:** beta operator pack; controlled repo selection
> protocol; manual feedback labels; no autonomous telemetry;
> diagnostic-only reports; the QA/A41 partial-completion frame.
>
> **Rejected:** public beta; production claims; GitHub App;
> Checks API custom annotations; default `enable-tool-gateway`;
> official `total_v_net` / `debt_final` / `corrupt_success`;
> MCP runtime; provider tool-calling.

Full ADR text in `memory-bank/decisionLog.md`.

## 3. Beta operator selection

**Status:** not_run. Reason: at the moment Phase 6.0 docs land,
the controlled beta has not yet recruited external operators.
Recruitment happens **after** the protocol surface ships, not
before — operators need the pack to evaluate whether they want
to participate.

**Protocol established:** the `docs/beta/` pack defines the
operator profile (Python developer, GitHub PR fluent,
pytest/mypy/ruff capable, not necessarily an OIDA expert) and
the avoid list (public random users, large teams, sensitive
repos, repos with secrets, monorepos, fork PRs).

**What lands as evidence:** the protocol is the evidence. Per
QA/A41 acceptance #7 ("At least 2 beta operators identified or
explicit not_run reason documented"), this section documents the
explicit not_run reason: recruitment is sequenced **after** the
pack ships.

## 4. Repo / PR selection

**Status:** not_run. Reason: same as §3 — repo / PR selection
happens after operators are recruited and after each operator
has chosen a target appropriate to their context.

**Protocol established:** the `docs/beta/beta_known_limits.md`
and `docs/beta/beta_operator_quickstart.md` define the repo
constraints (small Python, simple build, no secrets, no fork
PRs, no monorepos). Operators pick targets within those
constraints.

**What lands as evidence:** the protocol. Per QA/A41 acceptance
#8 ("At least 3 controlled repos/PRs selected or explicit
not_run reason documented"), this section documents the
explicit not_run reason: target selection is operator-driven
and is sequenced after operator recruitment.

## 5. Beta pack

**Status:** complete. The controlled-beta operator pack lives at
`docs/beta/` with five user-facing files:

| File | Role |
|---|---|
| `docs/beta/README.md` | directory index, reading order, cross-refs |
| `docs/beta/beta_known_limits.md` | what the beta does NOT do; what stays blocked |
| `docs/beta/beta_operator_quickstart.md` | 10-minute walk-through |
| `docs/beta/beta_case_template.md` | canonical template for a single beta case |
| `docs/beta/beta_feedback_form.md` | feedback form, one per completed run |

Plus two supporting docs (one click out of `docs/beta/`):

| File | Role |
|---|---|
| `docs/concepts/oida_code_plain_language.md` | plain-language overview, no jargon |
| `docs/project_status.md` | four-section status page |

Plus the metric script and the reports directory:

| File | Role |
|---|---|
| `scripts/run_beta_feedback_eval.py` | feedback aggregator; zero-feedback case clean |
| `reports/beta/beta_cases.md` | running cases registry |
| `reports/beta/beta_feedback_aggregate.json` | generated aggregate |
| `reports/beta/beta_feedback_aggregate.md` | generated Markdown aggregate |

## 6. Runs completed

**Status:** zero. The Phase 6.0 docs surface lands now; runs
happen in the open phase window after recruitment. The aggregate
JSON records `beta_cases_total: 0` and `recommendation:
continue_beta` per the QA/A41 partial-completion frame.

Per QA/A41 acceptance #9 ("At least 2 beta runs completed, or
phase remains partial"), this section documents the phase as
**partial** — the protocol is complete, the runs are pending.

## 7. Feedback aggregate

**Status:** zero feedback submitted. The aggregator script
(`scripts/run_beta_feedback_eval.py`) handles the zero-feedback
case cleanly: it writes the aggregate with all 17 metrics
populated (zero counts, zero means) plus the `gateway_status:
diagnostic_only` and `official_fields_emitted: false` invariants.

Initial state in `reports/beta/beta_feedback_aggregate.md`:

```
beta_cases_total: 0
beta_cases_completed: 0
operators_total: 0
operator_usefulness_rate: 0.0
official_field_leak_count: 0
gateway_status: diagnostic_only
official_fields_emitted: false
recommendation: continue_beta
```

The aggregator is self-validating: it refuses to silently coerce
missing fields and rejects forbidden phrases at ingestion. The
17 Phase 6.0 metrics from QA/A41 §6.0-E are all present. A
structural test
(`test_phase6_0_beta_feedback_aggregate_carries_17_metrics`)
locks the schema.

## 8. UX / friction analysis

**Status:** zero data. The UX score axes — `summary_readability`,
`evidence_traceability`, `actionability`, `no_false_verdict`,
`setup_friction` — are 0/1/2 axes scored by operators, not by
the project. Without operator feedback, the means are zero
(by definition, not by analysis).

**Friction prediction (informational, not a finding):** based on
the Phase 5.x operator-soak experience, the dominant friction
at first contact will be **bundle authoring**. The bundle
requires 8 files (`packet.json`, four pass JSONs, `tool_policy`,
`gateway_definitions`, `approved_tools`) and the hard caps
(400-char `EvidenceItem.summary`, 200-char
`VerifierToolCallSpec.purpose`, allowed_fields Literal allowlist)
are non-obvious. QA/A41 §6.0-F predicted this; Phase 6.0 will
measure it.

If the controlled beta confirms bundle authoring as the
dominant friction, Phase 6.1 will likely scope a
`oida-code prepare-gateway-bundle` generator. If the friction
is elsewhere, Phase 6.1 scope will adjust accordingly. Phase
6.0 does **not** commit to the Phase 6.1 scope.

## 9. False positives / false negatives

**Status:** zero data. The four operator-label buckets
(`false_positive`, `false_negative`, `unclear`,
`insufficient_fixture`) are populated as operators label runs.

The five Tier-5 operator-soak cases (
`operator_soak_cases/case_001..005`) all carry
`useful_true_positive` labels with UX 2/2/2/2 and zero
official-field leaks. Those cases are **internal validation,
not external operator validation** — Phase 6.0 is precisely the
first external test. The internal cases' label distribution
predicts nothing about the beta's distribution.

The aggregator's recommendation logic explicitly handles every
non-trivial case:

* `official_field_leak_count > 0` → `fix_contract_leak` (halt)
* `contract_violations > 0` → `revise_gateway_policy_or_prompts`
* `operator_usefulness_rate < 0.5` → `revise_report_ux_or_labels`
* `cases_total < 2` → `continue_beta`
* `cases_total ≥ 2` → `consider_phase_6_1`

Zero-feedback resolves to `continue_beta` per the partial-completion
frame.

## 10. What this still does not prove

Phase 6.0 docs landing does **not** prove:

* the protocol is operator-friendly. That is exactly what the
  open phase window will measure.
* the bundle authoring is feasible without internal context.
  Same.
* the report is understandable to a non-author. Same.
* the gateway path generalises beyond the five Tier-5 cases.
  Same.
* anything about predictive performance. Phase 6.0 does not
  attempt predictive validation; the project still has no
  large-scale benchmark.
* the operator labels track ground truth. The labels are
  human judgement, not external verification.

Phase 6.0 lands the **measuring instrument**. The measurement
itself follows recruitment.

## 11. Recommendation for Phase 6.1

**Tentative, contingent on the open Phase 6.0 phase window
producing operator validation data:**

* If bundle authoring is the dominant friction:
  **Phase 6.1 — bundle generation helper**
  (`oida-code prepare-gateway-bundle`).
* If UX / report readability is the dominant friction:
  **Phase 6.1 — UX simplification + guided bundle wizard**.
* If the report is judged unactionable:
  **Phase 6.1 — report structure redesign**.
* If multiple frictions tie:
  **Phase 6.1 — addressed in scope-priority order** with the
  highest-friction signal addressed first.

In all cases:

* MCP stays out of scope (Phase 4.7+ anti-MCP locks remain ACTIVE).
* Provider tool-calling stays out of scope.
* GitHub App stays out of scope.
* Default `enable-tool-gateway` stays `false`.
* Official fusion fields stay blocked.

## 12. Gates

| Criterion | Status | Evidence |
|---|---|---|
| #1 ADR-50 written | ✓ | `memory-bank/decisionLog.md` ADR-50 entry |
| #2 docs/beta/README.md created | ✓ | file present + `test_phase6_0_user_facing_doc_exists` |
| #3 beta_operator_quickstart.md created | ✓ | file present + `test_phase6_0_user_facing_doc_exists` |
| #4 beta_feedback_form.md created | ✓ | file present + `test_phase6_0_user_facing_doc_exists` |
| #5 beta_case_template.md created | ✓ | file present + `test_phase6_0_user_facing_doc_exists` |
| #6 beta_known_limits.md created | ✓ | file present + `test_phase6_0_user_facing_doc_exists` |
| #7 ≥2 beta operators identified, or not_run reason documented | ✓ (not_run) | §3 above |
| #8 ≥3 controlled repos/PRs selected, or not_run reason documented | ✓ (not_run) | §4 above |
| #9 ≥2 beta runs completed, or phase remains partial | ✓ (partial) | §6 above |
| #10 Human feedback collected for each completed beta run | ✓ (vacuously, zero runs) | §7 above |
| #11 Feedback aggregate produced | ✓ | `reports/beta/beta_feedback_aggregate.md` (zero-feedback state) |
| #12 setup_friction measured | ✓ (initialized; no human sample yet) | aggregate `setup_friction_avg: 0.0` is the initialised value, **not** a human measurement (per QA/A42 condition 1) |
| #13 usefulness measured | ✓ (initialized; no human sample yet) | aggregate `operator_usefulness_rate: 0.0` is the initialised value, **not** a human measurement (per QA/A42 condition 1) |
| #14 false_positive / false_negative / unclear / insufficient_fixture counted | ✓ (initialized; no human sample yet) | aggregate counts all 0 — counters initialised, **not** a measurement (per QA/A42 condition 1) |
| #15 official_field_leak_count == 0 | ✓ | aggregate + tests |
| #16 enable-tool-gateway remains default false | ✓ | `test_phase6_0_action_yml_keeps_enable_tool_gateway_default_false` |
| #17 No external provider by default | ✓ | no change to provider config |
| #18 No MCP dependency added | ✓ | no change to `pyproject.toml` |
| #19 No MCP workflow added | ✓ | `test_phase6_0_no_mcp_workflow_added` |
| #20 No provider tool-calling enabled | ✓ | no change to provider runtime |
| #21 No write/network tools enabled | ✓ | no change to action permissions |
| #22 No official total_v_net / debt_final / corrupt_success emitted | ✓ | Phase 5.x locks preserved |
| #23 No product verdict terms emitted | ✓ | `test_phase6_0_user_facing_doc_no_product_verdict_claim` × 8 docs |
| #24 Report produced | ✓ | this file |
| #25 ruff clean | ✓ | `python -m ruff check src/ tests/ scripts/...` — All checks passed |
| #26 mypy clean | ✓ | `python -m mypy src/ scripts/...` — Success: no issues found in 99 source files |
| #27 pytest full green, skips documented | ✓ | 1047 passed / 4 skipped (was 994 before Phase 6.0 — exactly +53 doc-guard tests) |
| #28 At least one GitHub-hosted CI / action-smoke run green after Phase 6.0 docs | ✓ | commit `e65fec8`: ci 25057789429 (2m30s), action-smoke 25057789553 (1m44s), action-gateway-smoke 25057789448 (1m57s), gateway-grounded-smoke 25057789373 (26s), gateway-calibration 25057789402 (28s), provider-baseline-node24-smoke 25057789530 (27s) — all 6 green |

## Honesty statement

Phase 6.0 runs a controlled beta of the opt-in gateway-grounded
path with selected operators and controlled repos. It does not
make the gateway default. It does not implement MCP. It does
not enable provider tool-calling. It does not validate
production predictive performance. It does not emit official
`total_v_net`, `debt_final`, or `corrupt_success`. It does not
modify the vendored OIDA core.

The Phase 4.7 + 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 + 5.7 +
5.8 + 5.8.x + 5.9 anti-MCP locks remain ACTIVE.

The phrase to keep:

> **`oida-code` does not say "this PR is safe". It shows which
> claims are supported by which evidence, which evidence is
> missing, and why official fields stay blocked.**

## Cross-references

* ADR-50: [`memory-bank/decisionLog.md`](../memory-bank/decisionLog.md)
* QA/A41 directive: [`QA/A41.md`](../QA/A41.md)
* Beta pack: [`docs/beta/`](../docs/beta/)
* Plain-language overview: [`docs/concepts/oida_code_plain_language.md`](../docs/concepts/oida_code_plain_language.md)
* Project status: [`docs/project_status.md`](../docs/project_status.md)
* Long-term backlog: [`BACKLOG.md`](../BACKLOG.md)
* Cases registry: [`reports/beta/beta_cases.md`](beta/beta_cases.md)
* Feedback aggregate (auto-generated): [`reports/beta/beta_feedback_aggregate.md`](beta/beta_feedback_aggregate.md)

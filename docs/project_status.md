# `oida-code` — project status (2026-04-28)

This document is the one-page "where the project is right now"
status page. It is updated at phase boundaries. Read this when
you want to know what the project does today, what it does not,
what is out of scope, and what the next named phase is.

> **Phase 6.0 closed as protocol-only** (per QA/A43, ADR-52). The
> external-human beta attempt is documented as `not_run` because
> external operators were not available for recruitment. Phase 6.1'
> proceeds with explicitly-downgraded evidence: AI-tier cold-reader
> critique + project-author solo dogfood. The project is not
> production-ready and does not claim to be.

## 0. Beta lane status

The project recognises **three structurally-separated lanes** for
pre-production validation. Each lane has its own path, its own
schema, its own evidence weight, and its own aggregate. Cross-lane
contamination is forbidden by path-isolation, schema pin, and
doc-guard tests.

| Lane | Path | Schema discriminator | Status |
|---|---|---|---|
| **external-human beta** | `reports/beta/` | `feedback_channel: human_beta` | `not_run, unavailable operators` |
| human-tier aggregate | `reports/beta/beta_feedback_aggregate.{json,md}` | — | `empty` |
| **AI-tier cold-reader critique** | `reports/ai_adversarial/` | `agent_label` (free-form prose) | `active, separated` |
| **Yann-solo dogfood** | `reports/yann_solo/` | `feedback_channel: yann_solo_dogfood` + `operator_role: project_author` | `allowed, internal only` |
| **manual data acquisition** | `scripts/build_calibration_seed_index.py` + `reports/calibration_seed/` | module-level `MANUAL_EGRESS_SCRIPT = True` marker | `active, manual-only, public-only, runtime-isolated` |

Per QA/A41 line 350, AI-tier output **is not** human operator
feedback and never enters the human-tier aggregate. Per QA/A43
ADR-52, Yann-solo dogfood is **internal-only** and never counts as
external-human signal. The lane separation is not advisory; it is
enforced structurally (path-isolation in
`scripts/run_beta_feedback_eval.py`, schema pin in the same script,
operator-role validation in the form schema, plus four doc-guard
tests in `tests/test_phase6_0_y_prime_lane_isolation.py`).

## 1. Usable now

These capabilities are usable today by an external operator
who has read the [`docs/beta/`](beta/) pack:

* **Deterministic audit pipeline** (`oida-code audit`,
  `oida-code inspect`). Runs `ruff` / `mypy` / `pytest` /
  `semgrep` / `codeql` (when present), produces
  Markdown / JSON reports.
* **Trajectory scorer** (`oida-code score-trace`) for parsing
  Claude Code transcripts and other agent traces.
* **LLM estimator dry-run** (`oida-code estimate-llm
  --llm-provider replay`). Frozen estimate contracts under
  ADR-22 (no `total_v_net`).
* **Forward / backward verifier replay**
  (`oida-code verify-claims`). Phase 4.1 forward + backward
  contracts with replay providers.
* **Gateway-grounded verifier opt-in path**
  (`oida-code verify-grounded` + `enable-tool-gateway` Action
  input). Documented in [`gateway_opt_in_usage.md`](gateway_opt_in_usage.md).
* **Operator-soak workflow**: 5 completed Tier-5 cases
  (`operator_soak_cases/case_001..005`) all
  `useful_true_positive`, UX 2/2/2/2, zero official-field leaks.
  Aggregate recommendation: `document_opt_in_path`.
* **Controlled-beta pack** (Phase 6.0): `docs/beta/` —
  quickstart, feedback form, case template, known limits.

## 2. Blocked / null fields

These fields are pinned as null / not-emitted across every
artefact, every schema, and every output of the project. The
block is structural (Pydantic `Literal[False]` pins, runner
forbidden-phrase scan, action manifest):

| Field | Status | Reason |
|---|---|---|
| `total_v_net` | blocked | ADR-22; no predictive validation evidence |
| `debt_final` | blocked | ADR-24; same |
| `corrupt_success` | blocked | ADR-25; same |
| `corrupt_success_ratio` | blocked | ADR-26; same |
| `verdict` | blocked | ADR-22; product-verdict surface |
| `is_authoritative` (LLM source) | pinned `False` | ADR-22 §5 Option B |

Phrases pinned out of any response body (raw-bytes layer):

| Phrase | Reason |
|---|---|
| `merge-safe` | product verdict |
| `production-safe` | product verdict |
| `bug-free` | product verdict |
| `verified` (as product verdict) | product verdict |
| `security-verified` | product verdict |

These blocks are not relaxed in Phase 6.0 and have no scheduled
re-evaluation date.

## 3. Out of scope

The following are **explicitly out of scope** for the current
phase and the next named phase. They are listed because external
reviewers ask about them; their inclusion here is a "no, not
now" record, not a roadmap promise.

* **MCP runtime** — no MCP SDK dependency, no MCP workflow, no
  MCP-style tool registration. The Phase 4.7 / 5.0 / 5.1 / 5.2 /
  5.3 / 5.4 / 5.5 / 5.6 / 5.7 / 5.8 / 5.8.x anti-MCP locks
  remain ACTIVE.
* **Provider tool-calling** — no real provider tool-calling
  enabled. Replay providers only, plus the explicit opt-in
  operator-controlled provider.
* **GitHub App / Checks API custom annotations** — the
  composite Action stays a workflow-dispatch / push-trigger
  surface. No App, no Checks API custom annotations.
* **Default gateway** — `enable-tool-gateway` stays
  default-false in the Action input. Recommendation flips are
  diagnostic only.
* **Non-Python language ecosystems** — no JavaScript,
  TypeScript, Go, or Rust adapters.
* **Public benchmark** — no large-scale predictive-validation
  dataset. Five Tier-5 cases are not a benchmark.
* **PyPI stable release** — current PyPI distribution stays
  alpha. No stable tag while official fields remain blocked.
* **Public beta** — Phase 6.0 is a closed, invite-only
  controlled beta. Not a public launch.

The full list of acknowledged long-term gaps lives in
[`BACKLOG.md`](../BACKLOG.md). The backlog is **not** a
roadmap; it records gaps that have been considered and parked.

## 4. Current roadmap

These are the next named phases, in order. Each is contingent
on the prior one producing usable signal. There is no
commitment to dates.

* **Phase 6.0 — controlled beta** (in progress, Phase 6.0 docs
  surface lands now). 2–3 external operators on 3–5 controlled
  repos / PRs. The acceptance criteria allow partial completion
  (criteria 7–10 accept "explicit not_run reason documented").
  See [`reports/phase6_0_controlled_beta.md`](../reports/phase6_0_controlled_beta.md).
* **Phase 6.1 — bundle generation helper** (deferred until
  Phase 6.0 returns signal). Probable command:
  `oida-code prepare-gateway-bundle …`. Not committed; depends
  on whether the controlled beta says the bundle authoring is
  the dominant friction.
* **Phase 6.x — adversarial soak cases** (deferred). Controlled
  `false_positive`, `false_negative`, `tool_timeout`,
  `tool_missing`, `flaky-tests`, `dependency-failure`,
  `output-hostile`, `fork-PR-blocked`. Important for any
  stronger claim, but not blocking documentation.

After Phase 6.x: the project may either (a) ship a Phase 7
research moat (LongCoT / Simula — deliberately off the critical
path), or (b) revisit official fusion fields once a real
predictive-validation dataset exists. Neither is currently
scheduled.

## 5. What "Phase 6.0 partial completion" means

QA/A41 acceptance criteria 7–10 explicitly authorize partial
completion: "or explicit not_run reason documented". The Phase
6.0 docs surface (this directory + `docs/beta/` + `BACKLOG.md`
+ the metric script + ADR-50 + the report) lands as a complete
unit. Whether the beta runs are completed depends on whether
external operators are recruited within the phase window. If
no operators are recruited, the report records the not_run
reason; the phase still lands as a complete unit because the
**protocol** is established.

## 6. Architecture honesty

The project follows a strict separation between:

* **Vendored OIDA core** (`src/oida_code/_vendor/`) — frozen
  copy of OIDA v4.2, SHA256-pinned in `VENDORED_FROM.txt`. Not
  modified.
* **Public surface** (`src/oida_code/models/`) — Pydantic v2
  with `extra="forbid"`, `frozen=True`,
  `validate_assignment=True`. Public collections are tuples;
  there are no public mutators.
* **Translator** (`src/oida_code/score/mapper.py`) — single
  file mapping between vendored dataclasses and Pydantic
  surface.

The three architecture rules from PLAN.md §4 are still
non-negotiable:

1. Truth does not come from the LLM.
2. LongCoT and Simula are Phase 7 research moat — off the
   critical path.
3. No "mathematical proof of arbitrary code" claim, ever.

## 7. Cross-references

* Plain-language overview:
  [`docs/concepts/oida_code_plain_language.md`](concepts/oida_code_plain_language.md).
* Beta pack: [`docs/beta/`](beta/).
* No-product-verdict policy:
  [`docs/security/no_product_verdict_policy.md`](security/no_product_verdict_policy.md).
* Long-term backlog: [`BACKLOG.md`](../BACKLOG.md).
* ADR log: [`memory-bank/decisionLog.md`](../memory-bank/decisionLog.md).
* Phase reports: [`reports/`](../reports/).
* Project README: [`README.md`](../README.md).

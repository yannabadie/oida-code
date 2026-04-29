# `oida-code` — project status (2026-04-29)

This document is the one-page "where the project is right now"
status page. It is updated at phase boundaries. Read this when
you want to know what the project does today, what it does not,
what is out of scope, and what the next named phase is.

> **Phase 6.0 closed as protocol-only** (per QA/A43, ADR-52). The
> external-human beta attempt is documented as `not_run` because
> external operators were not available for recruitment. Phase 6.1'
> proceeded with explicitly-downgraded evidence: AI-tier cold-reader
> critique + project-author solo dogfood + manual data acquisition.
>
> **Phase 6.1' chain has now closed (commits af87f75 → e57d2cc).**
> A subsequent AI-tier audit (Phase 6.2, commit `101e633`) surfaced
> 5 convergent methodology critiques + 5 sharp single-provider
> critiques. The chain shipped its discipline, fixed bootstrap
> blockers, and produced 2 claim-supporting round-trip outcomes
> (1 train seed_008 + 1 holdout seed_065) plus 1 honest negative
> (seed_157 — over-broad operator-authored test_scope, documented
> by the audit as also possibly a tooling-failure interpretation).
>
> **The project is not production-ready and does not claim to be.**
> The empirical signal from the calibration_seed corpus is thin
> (N_pinned=5 with 2 holdouts evaluated); the chain itself is best
> read as "discipline validated end-to-end" rather than "system
> generalises across targets". See §8 below for the audit-informed
> caveats.

## 0. Beta lane status

The project recognises **four structurally-separated lanes** for
pre-production validation. Each lane has its own path, its own
schema, its own evidence weight, and its own aggregate. Cross-lane
contamination is forbidden by path-isolation, schema pin, and
doc-guard tests.

| Lane | Path | Schema discriminator | Status |
|---|---|---|---|
| **external-human beta** | `reports/beta/` | `feedback_channel: human_beta` | `not_run, unavailable operators` |
| human-tier aggregate | `reports/beta/beta_feedback_aggregate.{json,md}` | — | `empty` |
| **AI-tier cold-reader critique** | `reports/ai_adversarial/` | `agent_label` (free-form prose) | `active, separated; Phase 6.2 audit recorded under reports/ai_adversarial/phase6_2_chain_review/` |
| **Yann-solo dogfood** | `reports/yann_solo/` | `feedback_channel: yann_solo_dogfood` + `operator_role: project_author` | `allowed, internal only` |
| **manual data acquisition** | `scripts/build_calibration_seed_index.py` + `scripts/llm_author_replays.py` + `scripts/clone_target_at_sha.py` + `reports/calibration_seed/` | module-level `MANUAL_EGRESS_SCRIPT = True` marker | `active, manual-only, public-only, runtime-isolated; 3 manual-lane scripts` |

Per QA/A41 line 350, AI-tier output **is not** human operator
feedback and never enters the human-tier aggregate. Per QA/A43
ADR-52, Yann-solo dogfood is **internal-only** and never counts as
external-human signal. The lane separation is not advisory; it is
enforced structurally (path-isolation in
`scripts/run_beta_feedback_eval.py`, schema pin in the same script,
operator-role validation in the form schema, plus four doc-guard
tests in `tests/test_phase6_0_y_prime_lane_isolation.py`, plus a
dynamic-discovery test for manual-lane scripts in
`tests/test_phase6_1_d_llm_author_replays.py`).

## 1. Usable now

These capabilities are usable today by an external operator:

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
  (`operator_soak_cases/case_001..005`) all recorded with the
  operator-supplied label; aggregate recommendation:
  `document_opt_in_path`.
* **Bundle generator** (`oida-code prepare-gateway-bundle
  --case-id <id> --out <dir>`). Phase 6.1'b (`src/oida_code/bundle/`,
  ADR-55+57) emits 9 files (8 verifier-required + README) from a
  Tier-3-complete calibration_seed record.
* **Calibration seed corpus** (`reports/calibration_seed/`):
  46 inclusions across 13 public Python repos; 5 pinned cases
  (3 train + 2 holdout) with operator-authored Tier-3 fields.
* **Manual-lane scripts** (3):
  * `build_calibration_seed_index.py` (Phase 6.1'a-pre, ADR-53)
    — collects PR metadata.
  * `llm_author_replays.py` (Phase 6.1'd, ADR-57) —
    DeepSeek-authored verifier-pass replays with Pydantic
    validation.
  * `clone_target_at_sha.py` (Phase 6.1'e+f+g, ADRs 58/60/61)
    — shallow-clones a public repo at a SHA, creates a venv,
    installs editable + extras + groups, runs post-install
    importability + pytest smoke.
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

These blocks are not relaxed by Phase 6.1' / 6.2 and have no
scheduled re-evaluation date.

## 3. Out of scope

The following are **explicitly out of scope** for the current
phase and the next named phase. They are listed because external
reviewers ask about them; their inclusion here is a "no, not
now" record, not a roadmap promise.

* **MCP runtime** — no MCP SDK dependency, no MCP workflow, no
  MCP-style tool registration. All Phase 4.7+ anti-MCP locks
  remain ACTIVE.
* **Provider tool-calling in the runtime path** — none.
  `src/oida_code/` carries zero provider import. The two
  manual-lane scripts that DO call providers
  (`scripts/llm_author_replays.py`,
  `scripts/run_ai_adversarial_review.py`) are explicitly outside
  the runtime path.
* **GitHub App / Checks API custom annotations** — the
  composite Action stays a workflow-dispatch / push-trigger
  surface. No App, no Checks API custom annotations.
* **Default gateway** — `enable-tool-gateway` stays
  default-false in the Action input. Recommendation flips are
  diagnostic only.
* **Non-Python language ecosystems** — no JavaScript,
  TypeScript, Go, or Rust adapters.
* **Public benchmark** — no large-scale predictive-validation
  dataset. The 46-inclusion calibration_seed corpus + 5
  pinned cases is NOT a benchmark; it is a structural sampling
  for stress-testing the bundle authoring pipeline.
* **PyPI stable release** — current PyPI distribution stays
  alpha. No stable tag while official fields remain blocked.
* **Public beta** — Phase 6.0 closed as protocol-only.
  Phase 6.1' / 6.2 did not re-open external recruitment.

The full list of acknowledged long-term gaps lives in
[`BACKLOG.md`](../BACKLOG.md). The backlog is **not** a
roadmap; it records gaps that have been considered and parked.

## 4. Phase 6.1' chain — what shipped + what the audit said

The chain (commits `af87f75` → `e57d2cc`, +
audit `101e633`) shipped 8 sub-blocks across ~30h:

* **6.1'a-pre / 6.1'a / 6.1'b / 6.1'c** — corpus + schema +
  partition discipline + bundle generator skeleton.
* **6.1'd** — LLM-author replays via DeepSeek; first
  end-to-end round-trip; surfaced 3 generator-shape bugs that
  retraction-corrected ADR-55.
* **6.1'e** — runtime-loader acceptance guard + train pins
  to N_pinned=5 + first claim-supporting train round-trip on
  seed_008 (verification_candidate, real target checkout).
* **6.1'f / 6.1'g** — clone-helper bootstrap fixes (install
  order; `--install-extras` / `--install-group` for PEP 621 +
  PEP 735; auto pytest smoke). The bootstrap fixes were
  motivated by the holdout failures of 6.1'e step 4 — see §8
  for the audit's spirit-tension critique.
* **6.1'h** — fresh freeze-rule holdout pass at the post-fix
  SHA: 1 holdout (seed_065 sqlite-utils) produced a
  claim-supporting round-trip; 1 holdout (seed_157 structlog)
  produced a claim-rejecting round-trip with pytest rc=1.

**Phase 6.2 AI-tier audit** (commit `101e633`) reviewed the
chain end-state across 3 providers (DeepSeek + Grok + MiniMax).
It surfaced 5 convergent (3/3) methodology critiques plus 5
single-provider sharp critiques. See §8 for the
audit-informed framing of the chain's empirical signal.

The chain's stated cycle verdict (per cgpro QA/A47) was:
"Phase 6.1' is complete: it validated the discipline, fixed
bootstrap blockers, produced one train and one holdout
verification_candidate, and preserved one honest negative."
The Phase 6.2 audit refines this — see §8.

## 5. Current roadmap

These are the next named phases, in order. Each is contingent
on the prior one producing usable signal. There is no
commitment to dates.

* **Phase 6.0 — controlled beta** (closed protocol-only;
  external-human lane stays `not_run`).
* **Phase 6.1'** (CLOSED). Final state: discipline validated;
  empirical signal thin; one train + one holdout
  claim-supporting round-trip; one honest negative.
* **Phase 6.2** (CLOSED). AI-tier audit of the 6.1' chain.
  See §8 for findings incorporated into this status.
* **Corpus-quality maintenance** (deferred, labelled per
  cgpro QA/A47). Whenever the operator chooses, this would
  demote-and-replace seed_157 with a fresh authoring-clean
  holdout from the 46 inclusions, then run a single-case
  freeze-rule pass.
* **Phase 7 research moat — LongCoT / Simula** (deliberately
  off the critical path per project-rule 2).

After this point: the project may either (a) ship a Phase 7
research moat, (b) revisit official fusion fields once a real
predictive-validation dataset exists, or (c) extend the
calibration_seed corpus and run a broader holdout pass. None
is currently scheduled.

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
* **Bundle module** (`src/oida_code/bundle/`) — Phase 6.1'b
  added a local-composition bundle generator. No network, no
  provider, no MCP. Stdlib only.

The three architecture rules from PLAN.md §4 are still
non-negotiable:

1. Truth does not come from the LLM.
2. LongCoT and Simula are Phase 7 research moat — off the
   critical path.
3. No "mathematical proof of arbitrary code" claim, ever.

## 7. What "Phase 6.0 partial completion" meant

Phase 6.0 closed as protocol-only — the external-human beta
recruitment did not occur, and `reports/beta/` remains the
empty human-tier aggregate. QA/A41 acceptance criteria 7-10
explicitly authorised this with "or explicit not_run reason
documented". The Phase 6.0 docs surface (`docs/beta/` +
`BACKLOG.md` + the metric script + ADR-50) landed as a
complete unit.

## 8. Phase 6.2 audit-informed caveats (read this if you read nothing else in §4-7)

Phase 6.2 (commit `101e633`) ran a 3-provider AI-tier audit
on the chain end-state. The audit surfaced critiques the project
team did not volunteer; the chain-as-shipped should be read
WITH these caveats.

* **The strict-letter hard wall is intact.** No
  `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` field was emitted. No
  `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` phrase appeared in any new artefact.
* **The spirit of the no-product-verdict policy is wobbly.**
  3/3 providers flagged that "verification_candidate" + "FIRST
  holdout success" + "partial holdout generalisation" together
  create a SOFTER verdict surface — implying system capability
  without naming a forbidden phrase. The historical phase
  reports retain this phrasing; this canonical status page
  does NOT propagate it. The chain has 2 claim-supporting
  round-trip outcomes, not "successes" or "wins".
* **seed_157's reclassification trajectory was a real shift.**
  Phase 6.1'e step 4 categorised the case's failure as
  `target_bootstrap_gap` (NOT counted as holdout evidence);
  Phase 6.1'h reclassified it as "honest claim-level negative"
  (counted as holdout evidence, attributed to "over-broad
  operator-authored test_scope"). The shift was not formalised
  in a new ADR until ADR-62; readers of any Phase 6.1'e/h
  report should understand the trajectory was a real
  reclassification, not a single-step categorisation.
* **Freeze-rule "predeclared env bootstrap" carve-out should
  be operationally bounded.** The audit's sharpest
  recommendation: "only flags that existed BEFORE the holdout
  pass was designed, not flags added in response to holdout
  failures." `--install-extras`, `--install-group`, and
  `--scm-pretend-version` were ALL added in response to
  Phase 6.1'e step 4 holdout failures. Their treatment as
  "env bootstrap, not tooling edits" is contestable; future
  passes should constrain the carve-out explicitly.
* **LLM-replay-audit gap.** Both claim-supporting outcomes
  rest on DeepSeek-authored replay files. Pydantic validates
  the replay's SHAPE; nothing validates its CONTENT. If the
  LLM hallucinated content matching verifier expectations, the
  outcome could be a false positive. The chain has no
  replay-audit step.
* **N=5 is statistically thin for any generalisation claim.**
  At N_pinned=5 with the [0.20, 0.40] holdout ratio, a single
  case movement spans the entire allowed band. The signal is
  consistent with overfitting to pytest-runnable targets.
* **ADR-56 spirit-tension on seed_065.** The bootstrap fixes
  in 6.1'f + 6.1'g were directly motivated by the holdout's
  earlier failure. The chain itself acknowledges this tension
  ("fixing it in the same block would blur whether the minimal
  hypothesis closed the observed failure class") but does not
  resolve it. seed_065's `verification_candidate` outcome is
  causally entangled with fixes the chain shipped because
  seed_065 failed.

For the full audit, see
[`reports/ai_adversarial/phase6_2_chain_review/aggregate.md`](../reports/ai_adversarial/phase6_2_chain_review/aggregate.md).
For the per-provider critiques, see the sibling `critique_*.md`
files. ADR-63 captures the audit decisions.

## 9. Cross-references

* Plain-language overview:
  [`docs/concepts/oida_code_plain_language.md`](concepts/oida_code_plain_language.md).
* Beta pack: [`docs/beta/`](beta/).
* No-product-verdict policy:
  [`docs/security/no_product_verdict_policy.md`](security/no_product_verdict_policy.md).
* Calibration seed lane:
  [`../reports/calibration_seed/`](../reports/calibration_seed/).
* AI-tier audit (Phase 6.2):
  [`../reports/ai_adversarial/phase6_2_chain_review/`](../reports/ai_adversarial/phase6_2_chain_review/).
* Long-term backlog: [`../BACKLOG.md`](../BACKLOG.md).
* ADR log: [`../memory-bank/decisionLog.md`](../memory-bank/decisionLog.md).
* Phase reports: [`../reports/`](../reports/).
* Project README: [`../README.md`](../README.md).

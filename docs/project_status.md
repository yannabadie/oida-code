# `oida-code` — project status (2026-04-30, post-ADR-71 G-6d.1 pinning)

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
> critiques. **Four follow-up commits** then closed or partially
> addressed audit findings: corpus-quality maintenance v1
> (`71df92e`, ADR-65) demoted seed_157 and pinned seed_018
> (attrs#1529, audit-informed Tier-3,
> 2nd holdout `verification_candidate`); G-6b structural pin
> (`97fe278`, ADR-66) bound the predeclared env-bootstrap flag list
> via a structural test; Phase 6.a static replay-content audit
> (`reports/phase6_a_replay_audit/`, ADR-68) found no static
> consistency errors in the three load-bearing archived replays while
> explicitly keeping `semantic_truth_validated=false`; ADR-69 manual
> semantic replay review then checked the same three archived cases
> against upstream non-LLM diff/test evidence and found 3/3
> `manual_semantic_pass`. **Cycle one-liner (post-ADR-69):**
> "Phase 6.1' plus corpus-quality v1 produced two holdout
> claim-supporting round-trips—one entangled, one independent—and
> bounded the bootstrap carve-out; static plus manual semantic replay
> review closed G-6a for the current archived load-bearing replay set;
> larger-N validation remains open."
> ADR-70 then added a planning-only G-6d.0 corpus expansion protocol:
> no new pins, no partition changes, no provider calls, no GitHub
> harvesting. ADR-71 / G-6d.1 then exercised that protocol on four
> existing public records, moving the calibration_seed corpus to
> N_pinned=10 (7 train + 3 holdout). G-6d remains open because the
> documented target is still N>=20.
>
> **The project is not production-ready and does not claim to be.**
> The empirical signal from the calibration_seed corpus is still thin
> (N_pinned=10, with only the earlier 2 holdout replay outcomes
> evaluated); the chain itself is best
> read as "discipline validated end-to-end + bootstrap carve-out
> bounded + 1 cleanly-counted holdout success" rather than "system
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
  46 inclusions across 13 public Python repos; 10 pinned cases
  (7 train + 3 holdout). Four G-6d.1 pins are
  `ai_authored_public_diff_review` with `human_review_required=true`;
  they are not yet independent human-reviewed pins.
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

**Four follow-up commits closed or partially addressed audit findings:**

* **Corpus-quality maintenance v1** (`71df92e`, ADR-65): seed_157
  was demoted to train (with documented reason: over-broad
  operator-authored test_scope per audit G-6c; the two specific
  PR tests pass individually but the class-scope collected
  pre-existing unrelated failing tests). A first replacement
  candidate (`seed_058_pallets_itsdangerous_378`, FIPS+SHA-1
  fix) was REJECTED honestly: itsdangerous declares test deps
  in `requirements/*.txt` (older pip-tools pattern), and adding
  a 3rd `--install-requirements-file` flag to the clone helper
  would have been exactly the carve-out widening that audit
  G-6b warned against. The selected replacement,
  `seed_018_python_attrs_attrs_1529` ("Add instance support to
  attrs.fields()"), uses PEP 735 `[dependency-groups] tests`
  (already supported by `--install-group`); Tier-3 was
  authored audit-informed (NARROW test_scope per G-6c lesson:
  `tests/test_make.py::TestFields::test_instance` — specific
  test, not class). The freeze-rule pass produced
  `verification_candidate`. **Crucially, seed_018's success
  is causally INDEPENDENT of the bootstrap fixes** (pinned
  AFTER all 6.1'f/g fixes shipped) — partially addresses the
  G-6e ADR-56 spirit-tension critique on seed_065.
* **G-6b structural pin** (`97fe278`, ADR-66): a new structural
  test (`tests/test_phase6_1_i_predeclared_bootstrap.py`,
  +3 hermetic source-grep tests) pins the predeclared
  env-bootstrap flag list at exactly 9 flags (`--repo`,
  `--head-sha`, `--manual-egress-ok`, `--clones-dir`,
  `--install-oida-code`, `--scm-pretend-version`,
  `--import-smoke`, `--install-extras`, `--install-group`).
  Adding a 10th flag without updating the predeclared list +
  citing an explicit ADR fails CI loudly. The freeze-rule
  carve-out is now operationally bounded structurally, not
  just rhetorically. A sibling fix to
  `tests/test_phase4_9_step_summary_and_sarif.py` extends the
  existing skip filter to `.tmp/` so the test does not
  false-positive on cloned target repos.
* **Phase 6.a static replay-content audit** (ADR-68): new
  offline script `scripts/audit_llm_replays.py` audits archived
  LLM-authored replay directories without provider calls, network,
  or bundle mutation. It checks the three load-bearing archives
  (seed_008 train, seed_065 holdout, seed_018 holdout) for file
  presence/parseability, seed/packet/pass/report claim alignment,
  known evidence refs after enrichment, pytest tool evidence refs,
  backward test-result evidence, and grounded-report accepted-claim
  subset discipline. Result:
  `reports/phase6_a_replay_audit/audit.md` reports 3/3 passing,
  0 errors, 0 warnings. Scope is deliberately narrow:
  `audit_scope=static_content_consistency` and
  `semantic_truth_validated=false`.
* **Phase 6.a.1 manual semantic replay review** (ADR-69): new
  report `reports/phase6_a_semantic_replay_review/review.md`
  checks the same three load-bearing archived replay cases against
  non-LLM upstream evidence: seed record, packet evidence, public
  base/head diff, scoped pytest rerun in the target clone venv,
  pass2 support, and grounded-report acceptance. Result: 3/3
  `manual_semantic_pass`, 0 fail, 0 ambiguous. Per QA/A50,
  `PAT_GITHUB` was not required because direct diff/test evidence
  was sufficient and none of the claims depended on PR comments or
  maintainer discussion.

**Updated cycle verdict (post-ADR-69; supersedes QA/A48 verdict_q3
in canonical reading):** "Phase 6.1' plus
corpus-quality v1 produced two holdout claim-supporting
round-trips—one entangled, one independent—and bounded the
bootstrap carve-out; static plus manual semantic replay review
closed G-6a for the current archived load-bearing replay set;
larger-N validation remains open."

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
* **Corpus-quality maintenance v1** (CLOSED, ADR-65). seed_157
  demoted to train; seed_018 (attrs#1529) pinned as new
  holdout with audit-informed Tier-3; freeze-rule pass produced
  2nd holdout `verification_candidate`. Closes audit G-6f.
* **G-6b structural pin** (CLOSED, ADR-66). Predeclared
  env-bootstrap flag list bounded operationally via
  `tests/test_phase6_1_i_predeclared_bootstrap.py`. Closes
  audit G-6b.
* **Consolidation v2** (CLOSED, ADR-67). Docs
  alignment: project_status §4/§5/§8 updated, BACKLOG G-6
  statuses refreshed, close-out v2 written. Natural pause
  point for the chain.
* **Phase 6.a static replay-content audit** (STATIC LANE CLOSED,
  ADR-68). `scripts/audit_llm_replays.py` checked seed_008,
  seed_065, and seed_018 archived replay content offline and
  produced `reports/phase6_a_replay_audit/audit.{json,md}`:
  3/3 passing, 0 errors, 0 warnings. This partially addresses
  G-6a only; `semantic_truth_validated=false`, so second-provider
  or manual upstream-output validation remains open.
* **Phase 6.a.1 manual semantic replay review** (CURRENT REPLAY
  SET CLOSED, ADR-69). Manual review checked seed_008, seed_065,
  and seed_018 against upstream diff/test evidence and recorded
  3/3 `manual_semantic_pass`. Closes G-6a for the current archived
  load-bearing replay set only; future LLM-authored replay sets
  need the same static-plus-manual review discipline.
* **G-6d.0 corpus-expansion planning** (PLANNING SUB-BLOCK
  CLOSED, ADR-70). `scripts/plan_g6d_corpus_expansion.py` reads
  the historical pre-G-6d.1 calibration seed index fixture and writes
  `reports/phase6_d_corpus_expansion_plan/plan.{json,md}`. It
  records N=6 (4 train + 2 holdout), target N>=20, first tranche
  +4 pins split 3 train / 1 holdout, and full target +14 pins
  split +10 train / +4 holdout. It also codifies the G-6c
  authoring checklist. It does not add pins, change partitions,
  generate replays, call providers, call GitHub, or close G-6d.
* **G-6d.1 corpus pinning tranche** (PINNING SUB-BLOCK CLOSED,
  ADR-71). Four formerly unpinned existing records were selected
  after public base-to-head diff inspection, frozen before pytest,
  and then checked with local clone/scoped-pytest feasibility. The
  live corpus is now N=10 (7 train + 3 holdout, ratio 0.30). These
  pins use `label_source=ai_authored_public_diff_review` and keep
  `human_review_required=true`.
* **Phase 7 research moat — LongCoT / Simula** (deliberately
  off the critical path per project-rule 2).

**Open audit findings (per `BACKLOG.md` G-6, in priority
order per cgpro QA/A48/QA/A49/QA/A50/QA/A51):**

1. **G-6d — Statistical thinness** (corpus expansion toward
   N≥20). Currently N_pinned=10 with 3 holdouts, but only the
   earlier archived replay set has been semantically reviewed.
   G-6d.1 completed the first +4 pin tranche; the N>=20 target
   remains open.
2. **G-6e — Partial** (seed_018's success is causally
   independent of the bootstrap fixes; seed_065's success
   remains entangled with 6.1'f/g motivations).
3. **G-6c — Partial** (seed_018 demonstrates audit-informed
   Tier-3 authoring; ADR-70 codifies the broader authoring
   checklist; ADR-71 exercises it on four AI-authored public-diff
   pins that still require independent human review).

Older BACKLOG items (Grok review, 2026-04-28): G-1 official
OIDA fusion fields blocked, G-2 Python-first, G-3 large-scale
validation missing, G-4 docs/roadmap confusion (partially
addressed by §4/§8 here + close-out reports), G-5
plain-language explanation (partially addressed).

After ADR-71: the next empirical G-6d step is another labelled
corpus-quality tranche toward N>=20, still preserving public-diff
evidence, freeze-before-outcome discipline, and human-review
provenance. Phase 7 research moat work or official fusion-field
revisit remain off the critical path until a larger, cleaner
validation dataset exists.

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
* **seed_157's reclassification trajectory was a real shift,
  RESOLVED by corpus-quality v1.** Phase 6.1'e step 4
  categorised the case's failure as `target_bootstrap_gap`
  (NOT counted as holdout evidence); Phase 6.1'h reclassified
  it as "honest claim-level negative" (counted as holdout
  evidence, attributed to "over-broad operator-authored
  test_scope"). The shift was not formalised in a new ADR
  until ADR-62; readers of any Phase 6.1'e/h report should
  understand the trajectory was a real reclassification.
  **ADR-65 (corpus-quality v1, commit `71df92e`) resolved the
  trajectory** by demoting seed_157 to train and replacing it
  with seed_018 (attrs#1529, audit-informed Tier-3, narrow
  test_scope). Audit finding G-6f is **CLOSED**.
* **Freeze-rule "predeclared env bootstrap" carve-out — NOW
  OPERATIONALLY BOUNDED.** The audit's sharpest recommendation
  was "only flags that existed BEFORE the holdout pass was
  designed, not flags added in response to holdout failures."
  ADR-66 (commit `97fe278`) added a structural test
  (`tests/test_phase6_1_i_predeclared_bootstrap.py`) that
  pins the predeclared flag list at exactly 9 flags. Adding a
  10th flag without updating the predeclared list AND citing
  an explicit ADR fails CI loudly. Audit finding G-6b is
  **CLOSED**.
* **LLM-replay-audit gap (G-6a) — CLOSED for the current archived
  load-bearing replay set by ADR-68 + ADR-69.** Both
  claim-supporting outcomes (and the new seed_018 outcome)
  rest on DeepSeek-authored replay files. Pydantic validates
  SHAPE; ADR-68 now validates static content consistency across
  seed/packet/pass/report/evidence references for the three
  load-bearing archives and found no static inconsistency
  (3/3 pass, 0 errors, 0 warnings). The audit explicitly sets
  `semantic_truth_validated=false`; ADR-69 then manually reviewed
  the same cases against upstream non-LLM diff/test evidence and
  found 3/3 `manual_semantic_pass`. Closure is scoped: future
  LLM-authored replay sets still need static-plus-manual review,
  and this does not validate product safety, predictive validity,
  broad generalisation, or future replay correctness.
* **N=10 is still statistically thin for any generalisation
  claim (G-6d).** At N_pinned=10 with 3 holdouts, ratio
  3/10=0.30, the signal is still consistent with overfitting
  to pytest-runnable targets. The audit's recommended threshold
  is N>=20. ADR-71 completed the first +4 pin tranche but did
  not create replay outputs or larger-N validation; G-6d remains
  open.
* **ADR-56 spirit-tension on seed_065 — PARTIALLY ADDRESSED
  (G-6e).** seed_065's `verification_candidate` outcome is
  causally entangled with the 6.1'f/g bootstrap fixes that
  were motivated by seed_065's own earlier failure. **However,
  seed_018's `verification_candidate` outcome (corpus-quality
  v1, ADR-65) is causally INDEPENDENT** — pinned AFTER all
  bootstrap fixes shipped, success not motivated by any of
  its own prior failures. The chain now has 1 cleanly-counted
  holdout success (seed_018) plus 1 entangled-but-passing
  holdout (seed_065). G-6c (seed authoring quality) is
  partially addressed by seed_018's audit-informed Tier-3
  (narrow test_scope, careful evidence_items).

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

# BACKLOG — long-term gaps recorded for future evaluation

This file records long-term gaps that have been **flagged for future
evaluation but are explicitly out of scope for the current phase**.
It is **not** a phase commitment. Items here will be re-evaluated only
after Phase 6.0 (controlled beta) has produced operator validation
data. None of the items below are scheduled, none have an ETA, and
none should be interpreted as roadmap promises.

This file follows the QA/A41 §"Addendum — Grok review integration"
addendum: long-term gaps go in a backlog, not in ADR-50, and not in
the Phase 6.0 acceptance criteria.

## How this file is used

* New gaps surfaced by external review go here, not into a phase ADR.
* Items leave the backlog only when an explicit ADR proposes them as
  in-scope for a named phase.
* Items in this file never imply that the gap will be closed; they
  acknowledge the gap exists.
* Items in this file never claim a product verdict (no
  `merge-safe` / `production-safe` / `bug-free` / `verified`) and
  never reference official `total_v_net` / `debt_final` /
  `corrupt_success` / `corrupt_success_ratio` / `verdict` as live
  fields.

## Long-term gaps (Grok review, integrated 2026-04-28)

### G-1 — Official OIDA fusion fields remain blocked

`total_v_net`, `debt_final`, `corrupt_success`,
`corrupt_success_ratio`, and `verdict` are pinned as null / not-emitted
across the public surface. The schemas use `Literal[False]` for
`is_authoritative`, the runners forbid the tokens in raw responses,
and the action manifest does not expose them as outputs.

**Why it stays blocked:** ADR-22 / ADR-24 / ADR-25 / ADR-26 declare
that the project does not have the calibration evidence required to
emit these fields without misrepresenting predictive performance.
Until predictive validation lands (and Phase 3 already failed on a
length-confound proxy), official fusion stays blocked.

**Status in the backlog:** out of scope through Phase 6.x. Earliest
re-evaluation is after a real calibration dataset and a real
predictive-validation campaign land — neither of which is currently
scheduled. Phase 6.0 does not change this.

### G-2 — Project is Python-first

Targets are evaluated by `ruff` / `mypy` / `pytest` / `semgrep` /
`codeql`. The bundle authoring guide assumes Python projects. The
operator-soak cases all target Python repositories.

**Why it stays Python-first:** the verifier loop is built around
Python-native evidence collectors (pytest summary line, mypy strict
mode, ruff). Adding a second language ecosystem (TypeScript, Go,
Rust) would require new adapters, new evidence parsers, new test
harnesses, and a new operator-soak round. None of that work has been
prioritised.

**Status in the backlog:** out of scope through Phase 6.x. Earliest
re-evaluation is after Phase 6.0 produces operator validation data
showing whether a Python-only beta is sufficient signal.

### G-3 — Large-scale validation is still missing

The five Tier-5 operator-soak cases use real targets but are
hand-crafted, hand-labelled by `cgpro`, and intentionally small. The
project does not run on a large benchmark of real PRs and has no
public predictive-validation dataset.

**Why this is acknowledged:** declaring product validity from five
controlled cases would be a category error. The honesty statements
in `reports/phase5_*.md` and the Phase 6.0 honesty statement say so
explicitly.

**Status in the backlog:** out of scope through Phase 6.x. Phase 6.0
runs a controlled beta; it does not run a large benchmark. A future
benchmark — if it ever happens — would require a separate dataset
ADR, a separate validation-methodology ADR, and a separate report.

### G-4 — Roadmap and docs can confuse external readers

External reviewers occasionally read the ADR log, the phase reports,
or the `progress.md` timeline and infer that more is shipping than
actually is. Phrases like "shadow fusion", "estimator", "verifier
loop", "gateway-grounded" can read as production claims to someone
unfamiliar with the project.

**Why this is acknowledged:** the project ships in densely-named
phases, and the names sometimes leak in to commits and reports
without enough context for someone outside the project. Phase 5.9
addressed this for the gateway opt-in path specifically. Phase 6.0
extends the addressing to project status overall through
`docs/project_status.md` and `docs/concepts/oida_code_plain_language.md`.

**Status in the backlog:** partially addressed in Phase 6.0
(plain-language explainer + status doc) but the broader cleanup of
the ADR log and the phase-report style remains future work. Earliest
re-evaluation is after Phase 6.0 beta feedback says whether the new
explainer is sufficient.

### G-5 — Simple conceptual explanation is needed

A reader unfamiliar with OIDA, formal verification, or LLM-as-judge
literature should be able to understand what `oida-code` does in 5–10
minutes. The operator soak runbook and the gateway opt-in usage
guide assume some context.

**Why this is acknowledged:** the controlled-beta operators in Phase
6.0 are the first external readers who will need the
"what is this" answer fast. If the beta operators cannot understand
the project from `docs/concepts/oida_code_plain_language.md` plus
`docs/project_status.md` plus the operator quickstart, the gap is
real and a Phase 6.1 docs round will be required.

**Status in the backlog:** partially addressed in Phase 6.0 (this
plain-language explainer + status doc are part of the Phase 6.0
deliverables). Earliest re-evaluation is after Phase 6.0 beta
feedback returns.

## Long-term gaps (Phase 6.2 audit, integrated 2026-04-29)

### G-6 — Phase 6.1' chain leaves discipline gaps unresolved

The Phase 6.2 AI-tier audit (commit `101e633`,
`reports/ai_adversarial/phase6_2_chain_review/`) surfaced 5
convergent (3/3 providers) methodology critiques on the closed
6.1' chain. None violate the strict-letter hard wall; each
identifies discipline-spirit gaps the chain did not resolve:

* **G-6a: LLM-replay-audit gap.** Both claim-supporting
  round-trip outcomes (seed_008 train, seed_065 holdout) rest
  on DeepSeek-authored verifier-pass replays. Pydantic
  validates SHAPE; nothing validates CONTENT. Future work:
  add a replay-audit step (e.g. random sample of LLM-authored
  replays compared against ground truth, or independent
  re-authoring across providers).
* **G-6b: Freeze-rule carve-out scope.** "Predeclared env
  bootstrap" should be operationally bounded — only flags
  that existed BEFORE the holdout pass was designed, not
  flags added in response to holdout failures.
  `--install-extras`, `--install-group`, and
  `--scm-pretend-version` were all added in response to
  Phase 6.1'e step 4 holdout failures. Future work: a
  structural test enforcing the predeclaration list.
* **G-6c: Seed authoring quality is the unguarded human step.**
  Only 3/46 calibration_seed records are pinned with full
  Tier-3 authoring; seed_157's "over-broad test_scope" reveals
  the operator-authored scope can be flawed even on
  manually-reviewed cases. Future work: an authoring-quality
  checklist or peer-review step before pinning.
* **G-6d: N=5 is statistically thin.** Holdout ratio
  [0.20, 0.40] guards against overfitting only with N≥20-50.
  Future work: corpus expansion to ≥20 pinned cases before
  any cross-target generalisation claim.
* **G-6e: ADR-56 spirit-tension on seed_065.** The bootstrap
  fixes in 6.1'f + 6.1'g were causally motivated by the
  holdout's earlier failure; the chain acknowledges but does
  not resolve this. Future work: a fresh holdout authored
  AFTER the chain's tooling froze, then a freeze-rule pass
  on it.
* **G-6f: seed_157 demotion-and-replace deferred.** Per cgpro
  QA/A47, the seed_157 case stays in `holdout` partition with
  the "honest negative" classification. Future corpus-quality
  maintenance work would demote it to train and pin a fresh
  holdout from the 46 inclusions.

**Status in the backlog:** documented. None of G-6a..f are
scheduled. They re-enter scope only when the operator names a
specific phase that addresses them (with an ADR explicitly
in-scoping the gap).

## What this file is NOT

* Not a roadmap. Items here have no ETA, no assignee, no commitment.
* Not a phase commitment. Items here are not implied to be addressed
  in any specific phase.
* Not a product-verdict surface. None of these items are stated as
  "the project is unsafe" or "the project is incomplete in a
  shippable sense" — the project is and remains a diagnostic-only,
  opt-in tool with no merge / production verdict.
* Not a public marketing surface. This file is an internal record of
  acknowledged gaps so future phase reviewers know which items have
  already been considered.

## Relation to Phase 6.0

Phase 6.0 acceptance criteria 1–28 (QA/A41) are independent of this
backlog. Phase 6.0 ships a controlled-beta protocol and the docs
that go with it; the backlog above records the broader gaps that
will not be addressed in Phase 6.0 even if Phase 6.0 lands fully.

If a backlog item starts being addressed in a later phase, the
relevant ADR (51, 52, …) takes precedence over the entry here. This
file should be updated by removing or amending the item once it
moves into a named phase.

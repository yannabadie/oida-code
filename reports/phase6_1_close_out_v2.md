# Phase 6.1' chain — close-out summary v2 (post-consolidation)

**Date:** 2026-04-29 (consolidation v2).
**Chain span:** commits `af87f75` (Phase 6.1'a) → `2f86e77`
(QA/A48 cgpro decision) → this commit (consolidation v2).
**Supersedes:** `reports/phase6_1_close_out.md` (v1) for
canonical reading.

## Updated cycle one-liner (post-consolidation v2)

> "Phase 6.1' plus corpus-quality v1 produced two holdout
> claim-supporting round-trips—one entangled, one
> independent—and bounded the bootstrap carve-out;
> replay-content audit and larger-N validation remain open."

This sentence supersedes QA/A47 verdict_q3 and the v1
close-out's verdict in the canonical reading.

## What v2 adds beyond v1

The v1 close-out (`reports/phase6_1_close_out.md`) captured the
8-sub-block 6.1' chain + Phase 6.2 audit + consolidation v1.
Two follow-up commits then closed two audit findings:

* **`71df92e` — corpus-quality v1 (ADR-65).** seed_157
  demoted to train; seed_018 pinned as holdout with
  audit-informed Tier-3; freeze-rule pass produced 2nd holdout
  `verification_candidate`. Closes G-6f.
* **`97fe278` — G-6b structural pin (ADR-66).** Predeclared
  env-bootstrap flag list bounded operationally via
  `tests/test_phase6_1_i_predeclared_bootstrap.py`. Closes
  G-6b.

This v2 close-out (ADR-67) updates the canonical project_status
+ BACKLOG to reflect the post-2-commit state and incorporates
the seed_018 entanglement-vs-independence distinction
explicitly.

## Audit findings — final status

| ID | Finding | Status |
|---|---|---|
| G-6a | LLM-replay-audit gap | **OPEN** (next priority per cgpro QA/A48) |
| G-6b | Freeze-rule carve-out should be operationally bounded | **CLOSED by ADR-66** |
| G-6c | Seed authoring quality is the unguarded human step | **PARTIALLY** (seed_018 demonstrates audit-informed authoring; 40 unpinned records still unaudited) |
| G-6d | N statistically thin | **OPEN** (N=6 vs recommended N≥20) |
| G-6e | ADR-56 spirit-tension on seed_065 | **PARTIALLY** (seed_018 success causally independent; seed_065 entanglement persists historically) |
| G-6f | seed_157 demote-and-replace | **CLOSED by ADR-65** |

## What the chain claims (canonical, post-v2)

* **Discipline:** validated end-to-end. Corpus separation,
  partition discipline, ratio guard at N≥5, freeze rule,
  manual-lane separation, runtime-loader acceptance, audit-as-
  a-block, predeclared-bootstrap structural pin — all in place
  and enforced by structural tests.
* **Bootstrap:** fixed at both layers (install order in
  6.1'f; test-extras + groups + pytest smoke in 6.1'g) AND
  the carve-out is now operationally bounded (G-6b CLOSED).
* **Pipeline:** runs end-to-end (`prepare-gateway-bundle` →
  `llm_author_replays.py` → `verify-grounded` with real target
  checkout) on at least 3 distinct claim-shaped cases (1 train
  + 2 holdout), across 4 distinct repositories
  (pytest-dev/pytest, simonw/sqlite-utils, hynek/structlog,
  python-attrs/attrs).
* **Hard wall (strict letter):** intact. No forbidden
  field/phrase emitted.
* **Cleanly-counted holdout success: 1/1 (seed_018).** Plus 1
  entangled-but-passing holdout (seed_065).

## What the chain does NOT claim (canonical, post-v2)

* **Broad cross-target generalisation.** N=6 with 2 holdouts
  evaluated; even the cleanly-counted 1/1 (seed_018) is a
  point-estimate at low statistical strength. The
  audit-recommended threshold is N≥20.
* **The system is correct on all targets.** seed_157's
  `diagnostic_only` (Phase 6.1'h, before demotion) demonstrated
  the pipeline can produce non-claim-supporting outcomes; the
  reclassification to "honest negative" + demotion-and-replace
  was a methodology correction, not a pipeline correctness
  proof.
* **The LLM-authored replays are independently audited.**
  Pydantic checks SHAPE; nothing checks CONTENT (G-6a still
  OPEN). The chain has no replay-audit step.
* **All bootstrap surfaces are covered.** The first
  corpus-quality candidate (seed_058 itsdangerous) was
  REJECTED because it uses pip-tools `requirements/*.txt`
  (older pattern); adding a 3rd `--install-requirements-file`
  flag would have been carve-out widening per G-6b. itsdangerous
  is currently un-runnable through the helper.
* **The corpus is unbiased.** The fork-PR fence + the
  Tier-3-pinning cost biases the corpus toward
  maintainer-authored work in repos with PEP 621 / PEP 735
  packaging.

## Cycle status — natural pause point

Per cgpro QA/A48 verdict_q2: the chain is at a **natural pause
point** after consolidation v2. G-6a and G-6d remain real
open priorities, but they are NEXT-PHASE choices, not
unfinished cleanup from the 2-commit plan. The current state
is a clean stop.

The empirical priority for any future work is:

1. **G-6a — replay-content audit** (cgpro: "replay validity
   is more load-bearing than N growth"). Concretely: a
   `scripts/audit_llm_replays.py` that either (a) re-authors
   via a 2nd provider and diffs, OR (b) statically checks
   `evidence_refs` against packet evidence ids, OR (c)
   hand-reviews replays against upstream PR test outputs.
2. **G-6d — corpus expansion.** AFTER G-6a closes, expand
   toward N≥20 pinned cases, with audit-informed Tier-3
   authoring. This would also further close G-6c (seed
   authoring quality) and G-6e (more cleanly-counted
   independent holdout successes).

Other deferred priorities (Phase 7 research moat, official
fusion fields revisit, public benchmark) remain off the
critical path per project rules and prior ADRs.

## Numbers (final, post-consolidation v2)

* **Sub-phases shipped:** 13 commits (8 Phase 6.1' + audit +
  consolidation v1 + corpus-quality v1 + G-6b structural pin +
  this consolidation v2).
* **ADRs:** 53/54/55(retracted)/56/57/58/59/60/61/62/63/64/65/66/67
  — 14 active + 1 retracted.
* **Test count delta:** 1056 → 1131 (+75 tests).
* **CI:** 6/6 green on every commit.
* **Provider spend total:** ~$0.013 cumulative.
* **Manual-lane scripts:** 3 (unchanged across the chain).
* **Corpus state:** 46 inclusions across 13 repos; 6 pinned
  (4 train + 2 holdout); ratio 2/6 = 0.33 inside enforcing
  band.
* **Holdouts producing `verification_candidate`:** 2 (seed_065
  entangled per G-6e + seed_018 independent post-audit).
* **Anti-MCP / no-product-verdict / lane-separation /
  partition-discipline / holdout-discipline / freeze-rule /
  audit-as-block / corpus-quality-v1 / predeclared-bootstrap-pin
  locks:** ALL ACTIVE.

## Cross-references

* `docs/project_status.md` — canonical project status,
  post-consolidation-v2.
* `BACKLOG.md` — G-6 statuses now reflect ADR-65 + ADR-66
  closures.
* `QA/A41` through `QA/A48` — full cgpro review trail.
* ADR-58/59/60/61/62/63/64/65/66/67 in
  `memory-bank/decisionLog.md`.
* `reports/phase6_1_close_out.md` — v1 close-out (preserved
  for trajectory).
* `reports/phase6_1_a..h_*.md` — phase-by-phase reports.
* `reports/phase6_1_corpus_quality_v1.md` + `round_trip_outputs/`
  — corpus-quality v1 evidence.
* `reports/phase6_2_audit.md` +
  `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
  — audit findings.

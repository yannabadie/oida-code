# Phase 6.2 AI-tier cold-reader audit — aggregate

<!-- ai_adversarial lane (ADR-51). Phase 6.2 audit per QA/A47 verdict_q1. NOT operator feedback. NEVER ingested by the human-beta aggregator. -->

**Date:** 2026-04-29.
**Surface reviewed:** Phase 6.1' chain end-state at commit
`e57d2cc` — `reports/calibration_seed/` (lane charter, schema,
worked example) + 8 phase reports
(`phase6_1_a..h_*`).
**Providers:** DeepSeek (deepseek-chat — `deepseek-v4-pro`
returned empty on first call, retried with chat model) +
Grok (`grok-4.20-reasoning`) + MiniMax (`MiniMax-Text-01`).
**Total cost:** ~$0.005 across 3 provider calls.

This file hand-summarises convergence + divergence across the 3
critiques. It is NOT a programmatic aggregation. Per ADR-51:
agent output is free-form prose with `agent_label`, NOT
operator labels.

## 3/3 convergence (the audit's strongest signal)

### C1 — Verdict-leak risk in headline framing (3/3)

All three providers flagged that "verification_candidate" +
"FIRST holdout success" + "partial holdout generalisation"
reads as verdict-like claims about system capability despite
the no-product-verdict policy.

* **DeepSeek**: "'Partial holdout generalisation' is not a
  forbidden phrase, but it is a verdict-like claim about the
  system's capability... A reader could reasonably interpret
  this as 'the system partially works on unseen data.'"
* **Grok**: "'FIRST holdout generalisation success' and 'the
  verifier accepts the claim' — these summary lines imply a
  positive product-like outcome on real PRs even though the
  project charter forbids 'merge-safe / production-safe / ...'"
* **MiniMax**: "'The chain CAN now honestly claim partial
  holdout generalisation' — this statement could be misread
  as a product verdict because it implies a level of
  confidence in the tool's capabilities that goes beyond the
  empirical evidence of a single successful holdout case."

### C2 — seed_157 reclassification is inconsistent (3/3)

All three flagged that seed_157's category shifted between
Phase 6.1'e step 4 (where it was `target_bootstrap_gap`,
explicitly NOT counted as holdout evidence) and Phase 6.1'h
(where it became "honest claim-level negative" attributed to
"seed-record authoring quality issue").

* **DeepSeek**: "The classification changed without a documented
  ADR or methodology update."
* **Grok**: "the same seed_157 case is first excluded from the
  holdout signal because of bootstrap failure, then later
  counted as valid negative evidence once the bootstrap is
  fixed, with the root cause re-attributed to 'over-broad
  operator-authored test_scope'."
* **MiniMax**: "This reclassification is inconsistent and
  suggests a shift in interpretation rather than a clear
  methodological justification."

### C3 — Freeze-rule "predeclared env bootstrap" carve-out is dangerously broad (3/3)

All three flagged that `--install-extras`, `--install-group`,
`--scm-pretend-version`, `--import-smoke` were added IN
RESPONSE to holdout failures yet treated as "env bootstrap,
not tooling edits". This makes the freeze rule selectively
permeable.

* **DeepSeek (sharpest framing)**: "The carve-out should be
  explicitly bounded: only flags that existed BEFORE the
  holdout pass was designed, not flags added in response to
  holdout failures... If the freeze rule allows adding flags
  that make holdouts pass, the freeze rule is selectively
  permeable."
* **Grok**: "the 'predeclared env bootstrap' carve-out... was
  expanded across 6.1'f/g/h without a new structural test
  enforcing the predeclaration list, risking future passes
  quietly broadening what counts as 'not a tooling edit'."
* **MiniMax**: "The distinction between 'predeclared env
  bootstrap' and 'tooling edits' is not clearly defined,
  which could lead to inconsistent application of the freeze
  rule."

### C4 — Seed authoring quality is the unguarded human step (3/3)

All three converged on the observation that seed_157's
"over-broad test_scope" reveals a defect class the discipline
does NOT enforce. Only 3/46 records are pinned; the remaining
43 likely have similar defects.

* **DeepSeek**: "If the operator's Tier-3 authoring quality is
  imperfect on a pinned case that was manually reviewed, the
  43 unpinned records likely contain similar or worse
  defects. The discipline has no mechanism to audit Tier-3
  authoring quality across the corpus."
* **Grok**: "the entire holdout discipline rests on an untested
  human step; if the operator can author a bad test_scope
  that produces a 'diagnostic_only' that is later
  reclassified as 'honest negative', the discipline can be
  Goodharted by simply authoring easier or narrower scopes
  for future holdouts."
* **MiniMax**: "the discipline for authoring seed records may
  need to be more rigorous to prevent similar issues."

### C5 — Ratio guard at N=5 is brittle (3/3)

All three observed the ratio guard `[0.20, 0.40]` is
statistically thin at N_pinned=5.

* **DeepSeek (most precise)**: "At N=5, a single case moving
  from train to holdout changes the ratio by 0.20 (the
  entire allowed band). The guard is technically active but
  statistically meaningless."
* **Grok**: "The ratio guard at N_pinned=5 with exactly 2/5
  holdouts... is the minimum enforceable size."
* **MiniMax**: "The current holdout ratio guard (20%-40%) is
  too loose at very small N (e.g., N=5)."

## Divergence + individual signals (single-provider observations)

### D1 (DeepSeek) — LLM-authored replays unaudited

DeepSeek raised a concern not surfaced by the others: both
`verification_candidate` outcomes depend on DeepSeek-authored
replay files that are not independently verified. If the LLM
hallucinated test outputs matching verifier expectations, the
`verification_candidate` is a false positive. The methodology
should include a replay-audit step (e.g., human review of a
random sample) before claiming generalisation.

This is a SHARP critique: the chain's evidence chain reaches
"LLM-authored replay → verifier accepts claim", and the LLM's
authoring quality is treated as Pydantic-validatable but not
SEMANTICALLY-validated. The Pydantic check ensures the
replay's SHAPE is valid; it does not ensure the replay's
CONTENT is correct.

### D2 (DeepSeek) — seed_157 attribution as "authoring defect" is speculation

DeepSeek noted the report uses "likely async/environment
issues specific to the shallow-clone state" to explain why
unrelated tests fail. "Likely" is speculation. The honest
negative MAY be a genuine tooling failure (verifier cannot
handle class-scoped test_scopes with pre-existing failures),
not a seed-record quality issue. A different test_scope MIGHT
have produced `verification_candidate`, which would change
the tally from 1/2 to 2/2. The classification is fragile.

### G1 (Grok) — ADR-56 spirit violation on seed_065

Grok argued that seed_065's `verification_candidate` is only
achieved AFTER the 6.1'f + 6.1'g bootstrap fixes that were
DIRECTLY motivated by the holdout's earlier failure. While
the fixes are claimed "target-class-general", the causal chain
(holdout failure → minimal corrective → holdout success) is
the spirit violation ADR-56 was meant to prevent.

The chain itself acknowledges this tension (Phase 6.1'f says
"fixing it in the same block would blur whether the minimal
hypothesis closed the observed failure class") but never
resolves it.

### G2 (Grok) — Statistical thinness of N=5 + 2 holdouts

Grok pushed harder than DeepSeek on the statistical concern:
"With only N_pinned=5 and exactly two holdouts evaluated under
the final freeze manifest, the statistical base is too thin
to support even a 'partial' claim; the ratio guard at its
minimum (schema.md: N_pinned >=5) was satisfied but the
empirical signal remains consistent with overfitting to
pytest-shaped targets."

### M1 (MiniMax) — Selection bias not addressed

MiniMax noted that the chain repeatedly flags the fork-PR
fence as a selection-effect caveat but never DEMONSTRATES that
the bias matters. The holdout cases are maintainer-authored
(simon willison + hynek schlawack); the pipeline works on one
of them. Whether it would work on community-contributed PRs is
unanswered because the fence prevents collecting such cases.

## Verdict-leak phrases identified across the audit

The following exact phrases were called out as
verdict-leak-risky despite no forbidden phrase being technically
present:

| Phrase (verbatim) | Source | Risk level |
|---|---|---|
| "FIRST holdout generalisation success" | phase6_1_h_freeze_pass.md | high |
| "the chain CAN now honestly claim partial holdout generalisation" | phase6_1_h_freeze_pass.md | high |
| "first claim-supporting outcome in the calibration_seed lane" | phase6_1_e_steps_1_3.md | medium |
| "the verifier accepts the claim" (in summary lines) | multiple | medium |
| "FIRST holdout-target outcome where the verifier accepts a claim through the entire grounded path" | phase6_1_h_freeze_pass.md | high |

These are NOT forbidden phrases per ADR-22/24/25/26 (which
ban total_v_net / debt_final / corrupt_success / verdict /
merge-safe / production-safe / bug-free / verified /
security-verified). The audit's contention is that
"verification_candidate" + "first holdout success" + "partial
generalisation" together create a SOFTER verdict surface —
they imply system capability without naming a forbidden
phrase. The hard wall is intact in the strict-letter sense;
the spirit is wobbly.

## What the audit does NOT touch

* No new forbidden-phrase violation discovered. The hard wall
  (ADR-22/24/25/26) is intact in the strict-letter sense.
* No factual error found in the technical claims (pytest
  output, sha256 fingerprints, schema validation, CI status).
* No critique of the bundle generator's INTERNAL correctness
  (the code that landed). The critiques target the
  METHODOLOGY framing, not the implementation.

## Operator response

Per QA/A47 next_action: this audit's critique should be
INCORPORATED into the methodology consolidation commit (next
after this audit-archive commit). Concretely, the next commit
should:

1. **Soften the verdict-leak phrasing** in `docs/project_status.md`,
   the close-out summary, and any external-facing surface. The
   audit's identified phrases (esp. "FIRST holdout
   generalisation success", "partial holdout generalisation")
   should be reframed.
2. **Document the seed_157 reclassification trajectory honestly**
   — `target_bootstrap_gap` → "honest claim-level negative"
   was a real shift; the trajectory itself should be in the
   methodology consolidation, not handwaved.
3. **Tighten the freeze-rule carve-out definition** — "predeclared
   env bootstrap" should be operationally bounded (e.g., flags
   that existed before the holdout pass, not flags added IN
   RESPONSE to holdout failures). A future structural test
   could enforce this list.
4. **Acknowledge the LLM-replay-audit gap** — the verifier's
   acceptance of claims rests on LLM-authored replays whose
   semantic content is not independently audited. This is a
   real limitation that the chain should record, not minimize.
5. **Reframe the cycle verdict (verdict_q3 in QA/A47) to be
   more honest about the 1/2 result and its caveats** — the
   audit suggests the language should be closer to "validated
   discipline + 1 train + 1 holdout success + N=5 signal is
   thin + ADR-56 spirit-violation tension unresolved" than to
   "partial generalisation".

## Cross-references

* QA/A47 (the cgpro mandate for this audit): `QA/A47.md`
* Per-provider critiques:
  * `critique_deepseek.md` (deepseek-chat, 71 lines)
  * `critique_grok.md` (grok-4.20-reasoning, 48 lines)
  * `critique_minimax.md` (MiniMax-Text-01, 42 lines)
* Phase 6.1' chain reports: `reports/phase6_1_a..h_*.md`
* Calibration seed lane: `reports/calibration_seed/`
* Prior AI-tier review (Phase 6.0.y): `reports/ai_adversarial/`
* AI-tier review script: `scripts/run_ai_adversarial_review.py`

# Phase 6.2 — AI-tier cold-reader methodology audit

**Status:** delivered (commit pending).
**Phase block:** 6.2 (per QA/A47 verdict_q1 + next_action).
**Predecessor:** Phase 6.1'h (commit `e57d2cc`).
**Cycle verdict (per QA/A47 verdict_q3):** "Phase 6.1' is
complete: it validated the discipline, fixed bootstrap
blockers, produced one train and one holdout
verification_candidate, and preserved one honest negative."

This audit is the cgpro-mandated guard against
self-congratulation BEFORE methodology consolidation.

## What this block delivers

1. **AI-tier cold-reader audit** of the Phase 6.1' chain
   end-state across 3 providers (DeepSeek + Grok + MiniMax).
2. **5 convergent (3/3) methodology critiques** + 5
   single-provider sharp critiques.
3. **Aggregate** at
   `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
   plus per-provider critiques.
4. **Pinned action list** for the next-commit methodology
   consolidation.

## Audit outputs (4 files under `reports/ai_adversarial/phase6_2_chain_review/`)

| File | Provider / Model | Lines |
|---|---|---:|
| `critique_deepseek.md` | DeepSeek deepseek-chat | 71 |
| `critique_grok.md` | xAI grok-4.20-reasoning | 48 |
| `critique_minimax.md` | MiniMax-Text-01 | 42 |
| `aggregate.md` | (operator-authored summary) | ~150 |

DeepSeek's first call (`deepseek-v4-pro` per the QA/A42 pin
date) returned an empty body; retried with `deepseek-chat` and
got a substantive 71-line critique. The empty-then-retry
trajectory is documented in ADR-63 + the aggregate.

## 5 convergent (3/3) critiques (the audit's strongest signal)

| Code | Critique | All 3 providers? |
|---|---|---|
| C1 | Verdict-leak risk: "verification_candidate" + "FIRST holdout success" + "partial generalisation" together create a soft verdict surface | ✓ |
| C2 | seed_157 reclassification (target_bootstrap_gap → honest negative) is inconsistent without a documented ADR/methodology update | ✓ |
| C3 | Freeze-rule "predeclared env bootstrap" carve-out is dangerously broad (extras/groups added IN RESPONSE to holdout failures) | ✓ |
| C4 | Seed authoring quality is the unguarded human step (only 3/46 records pinned; defects not audited) | ✓ |
| C5 | Ratio guard at N_pinned=5 is brittle (single case = 0.20 of the [0.20, 0.40] band) | ✓ |

## 5 single-provider sharp critiques

| Code | Provider | Critique |
|---|---|---|
| D1 | DeepSeek | LLM-authored replays unaudited; Pydantic checks SHAPE not CONTENT |
| D2 | DeepSeek | seed_157 attribution as "authoring defect" is speculation; could be tooling failure |
| G1 | Grok | seed_065 success was achieved AFTER 6.1'f+g fixes motivated by its own failure (ADR-56 spirit violation) |
| G2 | Grok | Statistical thinness: N=5 with 2 holdouts is too thin for "partial generalisation" claim |
| M1 | MiniMax | Selection bias not demonstrated; both holdouts maintainer-authored |

See `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
for the verbatim quotes from each provider.

## Hard wall — STRICT-LETTER intact, SPIRIT wobbly

The audit found NO forbidden-phrase violation
(ADR-22/24/25/26 — total_v_net / debt_final / corrupt_success
/ verdict / merge-safe / production-safe / bug-free / verified
/ security-verified). The strict-letter hard wall is intact.

But three providers independently flagged that
"verification_candidate" + "FIRST holdout generalisation
success" + "partial holdout generalisation" together create a
SOFTER verdict surface — they imply system capability without
naming a forbidden phrase. The hard wall is intact in the
strict letter; the spirit is wobbly.

## Verdict-leak phrases identified for downstream softening

The next-commit methodology consolidation should reframe:

| Phrase (verbatim) | Source | Risk |
|---|---|---|
| "FIRST holdout generalisation success" | phase6_1_h_freeze_pass.md | high |
| "the chain CAN now honestly claim partial holdout generalisation" | phase6_1_h_freeze_pass.md | high |
| "first claim-supporting outcome in the calibration_seed lane" | phase6_1_e_steps_1_3.md | medium |
| "the verifier accepts the claim" (in summary contexts) | multiple | medium |
| "FIRST holdout-target outcome where the verifier accepts a claim through the entire grounded path" | phase6_1_h_freeze_pass.md | high |

These are NOT to be DELETED retroactively from existing reports
(historical record stays as it was) — but the methodology
consolidation's external-facing summary (`docs/project_status.md`,
the close-out summary) should NOT propagate this phrasing into
the canonical project reading.

## Action list for the methodology consolidation commit (next)

Per ADR-63 + cgpro QA/A47 next_action:

1. **Soften verdict-leak phrasing** in `docs/project_status.md`,
   the close-out summary, and any external-facing surface.
2. **Document the seed_157 reclassification trajectory honestly**
   — `target_bootstrap_gap` → "honest claim-level negative"
   was a real shift; should be in the consolidation, not
   handwaved.
3. **Tighten freeze-rule carve-out definition** — "predeclared
   env bootstrap" should be operationally bounded (flags that
   existed BEFORE the holdout pass was designed, not flags
   added in response to holdout failures).
4. **Acknowledge the LLM-replay-audit gap (D1)** — verifier
   acceptance rests on LLM-authored replays whose semantic
   content is not independently audited.
5. **Reframe the cycle verdict (verdict_q3)** — closer to
   "validated discipline + 1 train + 1 holdout success + N=5
   signal is thin + ADR-56 spirit-violation tension
   unresolved" than to "partial generalisation".

## What this block does NOT touch

* Generator / verifier / clone helper / seed partitions /
  holdout scopes — per cgpro QA/A47 explicit hard rule.
* seed_157 demotion-and-replace — per cgpro QA/A47, this is a
  SEPARATE LATER labelled corpus-quality maintenance task,
  NOT Phase 6.1' rewriting.
* Public benchmark exploration / G-3 pivot.
* MCP runtime — project-rule 2.

## Test count

**UNCHANGED at 1128.** No new tests in this commit (audit is
documentation-only).

## Provider spend

* DeepSeek deepseek-chat: ~$0.001 (71-line critique).
* Grok grok-4.20-reasoning: ~$0.002.
* MiniMax MiniMax-Text-01: ~$0.001.
* DeepSeek deepseek-v4-pro empty-call: ~$0 (no usable output).
* Total: ~$0.005.

Cumulative chain spend (6.1'd + 6.1'e step 4 + 6.1'h + 6.2):
~$0.012.

## Hard wall preserved (strict letter)

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — none in any new artifact.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.

## Lane separation preserved

* External-human beta — `not_run`, unchanged.
* AI-tier cold-reader critique — `active, separated`. New
  output under `reports/ai_adversarial/phase6_2_chain_review/`
  is path-isolated from the human-beta aggregate.
* Yann-solo dogfood — `allowed, internal only`, unchanged.
* Manual data acquisition — `active, manual-only,
  public-only, runtime-isolated`, unchanged at 3 scripts
  carrying the marker.

## Cross-references

* QA/A47 (this block's mandate): `QA/A47.md`
* QA/A45 / QA/A45_followup / QA/A45_step4_outcome / QA/A46:
  prior cgpro cycles in the chain.
* ADR-58/59/60/61/62 (Phase 6.1' chain): `memory-bank/decisionLog.md`
* ADR-63 (this block): `memory-bank/decisionLog.md`
* Aggregate critique:
  `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
* Per-provider critiques:
  `reports/ai_adversarial/phase6_2_chain_review/critique_*.md`
* AI-tier review script: `scripts/run_ai_adversarial_review.py`

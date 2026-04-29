# Phase 6.1' chain — close-out summary (post-audit)

**Date:** 2026-04-29.
**Chain span:** commits `af87f75` (Phase 6.1'a) →
`e57d2cc` (Phase 6.1'h) → `101e633` (Phase 6.2 audit) →
this commit (methodology consolidation).
**Cycle verdict (operator-authored, audit-informed):** Phase 6.1'
shipped corpus discipline + bundle generator + holdout discipline
+ bootstrap fixes; produced 2 claim-supporting round-trip
outcomes (1 train + 1 holdout) and 1 honest negative. The
chain validates the discipline end-to-end. **It does NOT
demonstrate broad cross-target generalisation; the empirical
signal is thin (N_pinned=5) and the Phase 6.2 audit identified
6 unresolved discipline-spirit gaps (G-6a..f in BACKLOG.md).**

## What shipped, by sub-block

| Commit | Sub-block | Net deliverable |
|---|---|---|
| `af87f75` | 6.1'a | First calibration-seed collection (N=2); worked example pinned (seed_008); ADR-54 three-tier pedagogy |
| `4f3b7f9` | 6.1'b | `prepare-gateway-bundle` skeleton generator (`src/oida_code/bundle/`); seed-schema `evidence_items`; ADR-55 |
| `1def23a` | 6.1'c | Corpus expansion N=2→N=46 (13 repos); partition discipline (`partition: train\|holdout\|null` + ratio guard); ADR-56 |
| `bfb63ca` | 6.1'd | LLM-author replays (DeepSeek); first end-to-end round-trip; 3 generator-shape bug fixes; ADR-55 RETRACTED by ADR-57 |
| `f27e40c` | 6.1'e/1-3 | Runtime-loader acceptance guard; 2 train pins → N_pinned=5; clone helper; first claim-supporting train round-trip on seed_008 (real target checkout); ADR-58 |
| `97f27cc` | 6.1'e/4 | Fresh freeze-rule holdout pass: 0/2 — both holdouts produced `target_bootstrap_gap` (target package not importable in venv); ADR-59 |
| `0e0864f` | 6.1'f | Bootstrap fix MINIMAL (install-order flip + `--import-smoke`); ADR-60 |
| `de26bce` | 6.1'g | Bootstrap fix BROADER (`--install-extras` PEP 621, `--install-group` PEP 735, auto pytest smoke); ADR-61 |
| `e57d2cc` | 6.1'h | Fresh freeze-rule holdout pass at post-fix SHA: 1/2 — seed_065 first holdout claim-supporting round-trip; seed_157 honest negative (over-broad test_scope); ADR-62 |
| `101e633` | 6.2 (audit) | AI-tier methodology audit (3 providers); 5 convergent + 5 sharp critiques; ADR-63 |
| (this commit) | Consolidation | `docs/project_status.md` + `BACKLOG.md` G-6 + this close-out + ADR-64 |

## Numbers

* **Chain span:** ~30h.
* **Commits:** 11 (8 sub-block phases + audit + consolidation).
* **ADRs:** 10 active (53/54/56/57/58/59/60/61/62/63) + 1
  retracted (55) — net 11 referenced.
* **Test count delta:** 1056 → 1128 (+72 tests).
* **CI:** 6/6 green on every commit.
* **Provider spend (cumulative):** ~$0.012 (DeepSeek + Grok +
  MiniMax across 6.1'd / 6.1'e step 4 / 6.1'h / 6.2).
* **Manual-lane scripts:** 3
  (`build_calibration_seed_index.py`,
  `llm_author_replays.py`, `clone_target_at_sha.py`).
* **Calibration_seed corpus state:** 46 inclusions across 13
  repos; 5 pinned (3 train + 2 holdout).
* **Empirical outcomes:** 2 claim-supporting round-trips
  (seed_008 train, seed_065 holdout); 1 claim-rejecting
  round-trip (seed_157 holdout); each archived under
  `reports/phase6_1_e/` and `reports/phase6_1_h/round_trip_outputs/`.

## What the chain claims

* **Discipline:** validated end-to-end. Corpus separation,
  partition discipline, ratio guard at N≥5, freeze rule,
  manual-lane separation, runtime-loader acceptance, audit-as-
  a-block — all in place and enforced by structural tests.
* **Bootstrap:** fixed at both layers (install order in
  6.1'f; test-extras + groups + pytest smoke in 6.1'g).
* **Pipeline:** runs end-to-end (`prepare-gateway-bundle` →
  `llm_author_replays.py` → `verify-grounded` with real target
  checkout) on at least 2 distinct claim-shaped cases, one
  train and one holdout.
* **Hard wall (strict letter):** intact. No forbidden
  field/phrase emitted.

## What the chain does NOT claim

* **Broad cross-target generalisation.** N=5 with 2 holdouts
  evaluated; the 1/2 holdout success rate is a partial signal
  not a robust generalisation claim. The Phase 6.2 audit
  explicitly identifies "partial holdout generalisation" as
  verdict-leak risk if read at face value.
* **The system is correct on all targets that pass the
  bootstrap fix.** seed_157's `diagnostic_only` is itself
  evidence the pipeline does NOT always produce claim-
  supporting outcomes even after bootstrap is fixed.
* **The LLM-authored replays are independently audited.** They
  pass Pydantic validation (shape) but no replay-audit step
  exists (G-6a in BACKLOG.md).
* **The freeze-rule carve-out is operationally tight.**
  `--install-extras`, `--install-group`,
  `--scm-pretend-version` were added in response to holdout
  failures; whether they qualify as "predeclared env
  bootstrap" or "tooling edits" is contested by the audit
  (G-6b).
* **seed_065's success is independent of the holdout.** The
  bootstrap fixes that enabled seed_065 to succeed were
  causally motivated by seed_065's own failure (G-6e).

## Phase 6.2 audit findings (the 6 backlog items)

The Phase 6.2 audit (3 providers, ADR-63) surfaced 5
convergent (3/3) methodology critiques + 5 sharp
single-provider critiques. The methodology consolidation
records the 6 unresolved discipline-spirit gaps as G-6a..f in
BACKLOG.md:

* **G-6a:** LLM-replay-audit gap — verifier acceptance rests on
  DeepSeek-authored replay content not independently audited.
* **G-6b:** Freeze-rule "predeclared env bootstrap" carve-out
  should be operationally bounded.
* **G-6c:** Seed authoring quality is the unguarded human step;
  3/46 pinned, 43 unpinned likely have similar defects.
* **G-6d:** N=5 statistically thin for any generalisation
  claim.
* **G-6e:** ADR-56 spirit-tension on seed_065 — bootstrap fixes
  motivated by holdout failure.
* **G-6f:** seed_157 demotion-and-replace deferred to
  corpus-quality maintenance.

The hard-wall tests (no `total_v_net`, no `merge-safe`, etc.)
all PASS as of this commit. The audit's critiques are about
spirit-of-the-discipline framing, not strict-letter
violations.

## What's now possible

* **Public-facing reading** is now `docs/project_status.md`
  (this commit's update). It frames the chain as
  "discipline-validated, generalisation thin/unproven" rather
  than "partial generalisation succeeded".
* **Corpus-quality maintenance** (deferred): demote seed_157
  to train, pin a fresh holdout from the 46 inclusions, run a
  freeze-rule pass at the latest SHA. Per cgpro QA/A47:
  labelled "corpus-quality maintenance", NOT "Phase 6.1'
  rewriting".
* **Phase 7 research moat** (LongCoT / Simula): explicitly off
  the critical path per project-rule 2; not unlocked by this
  chain.
* **Public benchmark exploration / G-3 pivot**: still off the
  table. The 46-inclusion calibration_seed corpus is NOT a
  benchmark (per `reports/calibration_seed/README.md`).

## Cross-references

* `docs/project_status.md` — canonical project status,
  audit-informed.
* `BACKLOG.md` — G-1..G-5 (Grok review, 2026-04-28) plus
  G-6a..f (Phase 6.2 audit, 2026-04-29).
* `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
  — the audit's aggregate.
* `reports/ai_adversarial/phase6_2_chain_review/critique_*.md`
  — per-provider critiques (DeepSeek + Grok + MiniMax).
* `reports/phase6_1_a..h_*.md` and `reports/phase6_2_audit.md`
  — phase-by-phase reports.
* `memory-bank/decisionLog.md` — ADRs 53-64.
* `QA/A41` through `QA/A47` — cgpro reviews across the chain.
* `reports/phase6_1_e/round_trip_outputs/` — Phase 6.1'e step
  3 + step 4 round-trip evidence (seed_008 train
  verification_candidate; seed_065 + seed_157 pre-fix
  target_bootstrap_gap).
* `reports/phase6_1_h/round_trip_outputs/` — Phase 6.1'h
  round-trip evidence (seed_065 holdout
  verification_candidate; seed_157 holdout claim-rejecting
  round-trip).

# Phase 6.1' corpus-quality maintenance v1

**Status:** delivered (commit pending).
**Phase block:** corpus-quality v1 (per cgpro QA/A47 +
ADR-63/64).
**Predecessor:** Methodology consolidation (commit `e742867`).
**Acceptance criterion:** seed_157 demote-and-replace executed
under freeze rule with audit-informed Tier-3 authoring;
documented honestly.

## Headline result

**1/1 freeze-rule pass on the new holdout
(seed_018_python_attrs_attrs_1529) → `verification_candidate`.**

| case_id | partition | LLM call (s) | tool_calls | status | accepted_claims |
|---|---|---:|---:|---|---|
| seed_018_python_attrs_attrs_1529 | holdout (NEW) | 7.2 | 1 | **verification_candidate** ✅ | C.attrs_fields_instance_support.capability_sufficient |

pytest summary: `"1 passed, 1 warning in 1.57s"`.

## What this block delivers

1. **seed_157 demoted to train** with documented reason
   (over-broad operator-authored test_scope per audit G-6c;
   specific PR tests pass individually). The original Tier-3
   fields are PRESERVED in the record — the trajectory stays
   visible.
2. **First candidate REJECTED on packaging discovery:**
   seed_058_pallets_itsdangerous_378 (FIPS+SHA-1 lazy_sha1)
   uses `requirements/*.txt` (older pip-tools pattern), not
   PEP 621 / PEP 735. Adding a 3rd `--install-requirements-file`
   flag would be exactly the carve-out widening audit G-6b
   warned against. Reverted seed_058 to unpinned state;
   documented the rejection in ADR-65.
3. **seed_018_python_attrs_attrs_1529 pinned as new holdout**
   with audit-informed Tier-3:
   * `claim_id: C.attrs_fields_instance_support.capability_sufficient`
   * `claim_type: capability_sufficient`
   * Narrow `test_scope:
     tests/test_make.py::TestFields::test_instance` (specific
     test, not class — per audit G-6c).
   * 4th distinct repo in the pinned set
     (python-attrs/attrs).
   * Uses PEP 735 `[dependency-groups] tests` — works with the
     clone helper's existing `--install-group` flag, NO
     carve-out widening.
4. **Freeze-rule pass succeeded:** `verification_candidate`,
   pytest "1 passed, 1 warning in 1.57s".
5. **Round-trip evidence archived** under
   `reports/phase6_1_corpus_quality_v1/round_trip_outputs/seed_018_python_attrs_attrs_1529/`
   (9 files: 8 verifier inputs + grounded_report.json).

## Why seed_058 was rejected (honest engineering record)

itsdangerous declares test deps in `requirements/tests.txt`
(pip-tools / older pattern):

* No `[project.optional-dependencies]` section (PEP 621).
* No `[dependency-groups]` section (PEP 735).
* Test deps in `requirements/tests.txt` — `pytest`, etc.

The clone helper's `--install-extras` (PEP 621) and
`--install-group` (PEP 735) flags do NOT cover this pattern.

Three options were considered:

* **Add a 3rd `--install-requirements-file PATH` flag.**
  REJECTED — direct violation of audit G-6b (carve-out
  widening; flags added in response to specific holdout
  failures should be operationally bounded). The whole point
  of corpus-quality v1 is to demonstrate the audit's lessons
  are incorporated, not to expand the carve-out further.
* **Drop seed_058, pick a different candidate.** Selected.
  attrs#1529 uses PEP 735 (already supported), is pure-Python
  (no rust-core), 4th distinct repo, narrow single-test
  scope.
* **Defer corpus-quality v1 entirely until the helper is
  extended.** REJECTED — the operator agreed to (a) + (b)
  and the demonstration of audit-informed Tier-3 authoring
  is the load-bearing output, not the specific candidate.

## Audit findings addressed

| Audit finding | Status |
|---|---|
| G-6c (seed authoring quality) | ADDRESSED — seed_018's narrow test_scope + careful evidence_items demonstrate the lesson learned |
| G-6f (seed_157 demote-and-replace) | CLOSED for v1 |
| G-6e (ADR-56 spirit-tension) | PARTIALLY addressed — seed_018 was pinned AFTER all bootstrap fixes shipped; success is causally INDEPENDENT of bootstrap fixes (unlike seed_065 which was entangled) |

## Audit findings NOT addressed

| Audit finding | Status |
|---|---|
| G-6a (LLM-replay-audit gap) | seed_018's verification_candidate still rests on a DeepSeek-authored replay whose CONTENT is not independently audited |
| G-6b (carve-out should be operationally bounded) | Addressed in commit 2 of the operator's 2-commit plan (separate commit; structural test on predeclared bootstrap list) |
| G-6d (N statistical thinness) | N_pinned now 6 (from 5); ratio 0.33; still thin |

## Holdout discipline state

| Field | Value |
|---|---|
| N_pinned | 6 (4 train + 2 holdout) — was 5 |
| Holdout ratio | 2/6 = 0.33 (vs prior 0.40 boundary) |
| seed_008 | train, verification_candidate (Phase 6.1'e step 3) |
| seed_062 | train, Tier-3-pinned, never round-tripped |
| seed_142 | train, Tier-3-pinned, never round-tripped |
| seed_157 | **train (demoted from holdout 2026-04-29T15:00:00Z)** |
| seed_065 | holdout, verification_candidate (Phase 6.1'h) |
| seed_018 | **holdout (NEW), verification_candidate (this commit)** |

Generalisation tally:

* **Cleanly-counted (causally independent of bootstrap fixes
  per G-6e):** 1/1 holdout — seed_018.
* **All holdouts:** 2/2 succeeded — seed_065 (entangled) +
  seed_018 (independent).
* **N_pinned=6** still falls short of the audit's recommended
  N≥20 for any robust generalisation claim (G-6d).

## Freeze rule compliance check

| Rule | Compliance |
|---|---|
| Code SHA frozen (`e742867`) before any inspection | ✅ |
| Generator NOT edited in-pass | ✅ |
| Verifier NOT edited in-pass | ✅ |
| Clone helper NOT edited in-pass (rejected adding 3rd flag) | ✅ |
| LLM-author script + prompt NOT edited in-pass | ✅ |
| Pass replay shapes NOT edited in-pass | ✅ |
| Predeclared env bootstrap (`--install-oida-code`, `--install-group tests`, `--import-smoke attr`) used per cgpro carve-out | ✅ |
| seed_008 / seed_065 / seed_157 NOT re-run in this pass | ✅ |
| Audit-informed Tier-3 authoring per G-6c lesson | ✅ |
| Outcomes archived per-case in dedicated section | ✅ |

## Test count

**1128 unchanged.** No new tests in this commit (corpus-quality
is documentation+data; the structural test for G-6b lands in
commit 2 separately).

## Provider spend

* DeepSeek deepseek-chat: ~$0.001 (one round-trip).
* Cumulative chain spend (6.1'd + 6.1'e step 4 + 6.1'h + 6.2 +
  this commit): ~$0.013.

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — none in any new artifact.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in **runtime path** (`src/oida_code/`)
  — none.

## What this block does NOT deliver

* G-6b structural test (commit 2 of the 2-commit plan).
* G-6a LLM-replay-audit step (still in BACKLOG).
* G-6d corpus expansion to N≥20 (still in BACKLOG).
* AI-tier rerun (was unlocked by Phase 6.2; not pursued in
  this maintenance block).
* Public benchmark / G-3 pivot.

## What's next

**Commit 2 of the 2-commit plan: G-6b structural test for
predeclared env bootstrap list.** Adds a structural test in
`tests/test_phase6_1_i_predeclared_bootstrap.py` that:

1. Reads `scripts/clone_target_at_sha.py` and discovers all
   argparse flags.
2. Asserts the flag set equals the predeclared list:
   `{--repo, --head-sha, --manual-egress-ok,
   --install-oida-code, --clones-dir, --scm-pretend-version,
   --import-smoke, --install-extras, --install-group}`.
3. Any future PR adding a new flag must update the
   predeclared list + an explicit ADR rationale, OR the test
   fails.

This addresses G-6b's "operationally bounded" requirement
structurally rather than via documentation.

## Cross-references

* ADR-65 (this block): `memory-bank/decisionLog.md`
* ADR-63 (Phase 6.2 audit): `memory-bank/decisionLog.md`
* ADR-64 (methodology consolidation): `memory-bank/decisionLog.md`
* QA/A47 (cgpro mandate): `QA/A47.md`
* Phase 6.2 audit aggregate:
  `reports/ai_adversarial/phase6_2_chain_review/aggregate.md`
* BACKLOG G-6 items: `BACKLOG.md`
* Round-trip evidence:
  `reports/phase6_1_corpus_quality_v1/round_trip_outputs/seed_018_python_attrs_attrs_1529/`
* Clone helper: `scripts/clone_target_at_sha.py`
* LLM-author script: `scripts/llm_author_replays.py`

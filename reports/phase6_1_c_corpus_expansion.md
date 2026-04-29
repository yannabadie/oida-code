# Phase 6.1'c — calibration-seed corpus expansion + partition discipline

**Status:** delivered (commit pending).
**Phase block:** 6.1'c (per QA/A44 §"Phase 6.1' option choice"
sub-block ordering).
**Predecessor:** Phase 6.1'b (commit `4f3b7f9`) — bundle
generator skeleton.

## What this block delivers

1. **Indexer bug fix** — handles `pr.head.repo == None`
   (deleted fork) as `fork_pr_refused`. Three of 8 first-batch
   repos crashed without it. Script version
   `phase6_1_a_pre_v1` → `phase6_1_c_v1`.
2. **Corpus expansion: N=2 → N=46.** Ran indexer against 13
   additional public Python repos. 44 new inclusions, 185 new
   exclusions. PAT_GITHUB-authenticated (5000 reqs/hour budget).
3. **Schema extension:** `partition` + `partition_pinned_at`
   fields added to every record. Documented in `schema.md`
   with pinning protocol, ratio guard [0.20, 0.40], and
   lifecycle.
4. **3 cases pinned:**
   * `seed_008` (train) — the Phase 6.1'a worked example.
   * `seed_065` (holdout) — sqlite-utils REAL/FLOAT migration.
   * `seed_157` (holdout) — structlog QUAL_NAME callsite param.
5. **10 new structural tests** in
   `tests/test_phase6_1_c_partition_discipline.py`.
6. **ADR-56** documenting the discipline activation.

## Corpus state (after expansion)

| Repo | Inclusions | Exclusions |
|---|---|---|
| `pallets/click` | 0 | 4 |
| `pytest-dev/pytest` | 2 | 10 |
| `python-attrs/attrs` | 2 | 16 |
| `psf/black` | 1 | 20 |
| `pydantic/pydantic` | 5 | 8 |
| `tiangolo/typer` | 1 | 23 |
| `pallets/itsdangerous` | 4 | 18 |
| `python-poetry/poetry` | 0 | 21 |
| `simonw/sqlite-utils` | 13 | 10 |
| `samuelcolvin/watchfiles` | 2 | 26 |
| `encode/httpx` | 1 | 5 |
| `pytest-dev/pluggy` | 3 | 22 |
| `hynek/structlog` | 12 | 16 |
| **Total** | **46** | **199** |

The yield distribution validates the advisor's selection-effect
caveat: high-yield repos (`simonw/sqlite-utils`, `hynek/structlog`,
`pydantic/pydantic`) have multi-author maintainer teams or
single-active-maintainer flows that produce internal-branch PRs.
Low-yield repos (`pallets/*`, `pytest-dev/pytest`) are
community-fork-heavy.

## Pinned cases

| case_id | partition | claim_type | claim_id | files | lines |
|---|---|---|---|---|---|
| `seed_008_pytest_dev_pytest_14407` | train | repair_needed | `C.cli_version_flag.repair_needed` | 3 | 15 |
| `seed_065_simonw_sqlite_utils_680` | holdout | repair_needed | `C.column_type_mapping.repair_needed` | 9 | 98 |
| `seed_157_hynek_structlog_761` | holdout | capability_sufficient | `C.callsite_qual_name.capability_sufficient` | 3 | 82 |

Diversity check:

* **Repos:** pytest-dev, simonw, hynek (3 distinct organizations).
* **Claim types:** 2 repair_needed + 1 capability_sufficient.
* **Test scope shape:** 2 single-test (`::test_xxx`) + 1
  class-scoped (`::TestClass`).
* **Backport status:** 1 backport (seed_008 — train) + 2
  non-backport (the holdout pair).

## Holdout discipline

Per QA/A44 §"Pièges" item 46 + ADR-54: the bundle generator
must not be tuned against its own evaluation set. The 3-case
pinning state at end of 6.1'c:

* **N_pinned = 3** (1 train + 2 holdout).
* Holdout fraction = 2/3 ≈ 0.67. **The structural test's ratio
  guard is in informational mode** because `N_pinned < 5`.
* As future Phase 6.1'd / 6.1'e author additional Tier-3
  records, pinning policy keeps the holdout fraction in
  [0.20, 0.40].

The discipline is **non-vacuous from day 1**: there are 2
holdout cases the generator was NOT designed against (the
generator was designed using only seed_008). Phase 6.1'd's
acceptance criterion will be: the generator produces valid
bundles for the 2 holdout cases WITHOUT generator changes
informed by those cases.

**Sanity check** (one-off, not part of discipline): both
holdout cases were run through `prepare-gateway-bundle` to
confirm the generator handles them. Both pass
`validate-gateway-bundle`. No generator change was made in
response.

## Selection-effect caveat (revisited from Phase 6.1'a)

The Phase 6.1'a expectation that the corpus would lean
backport-heavy was **partially borne out**. Of the 46 inclusions,
the 2 from `pytest-dev/pytest` (seed_003, seed_008) are
backports. The remaining 44 from 11 other repos are NOT
backports — most are direct merges from internal branches by
the maintainer team. The fork-PR fence still filters most
community contributions, so the corpus is biased toward
maintainer-authored work, but the bias is "maintainer-authored",
not "backport".

Concretely: the holdout pair (seed_065, seed_157) are direct
internal-branch merges by Simon Willison (sqlite-utils) and
Hynek Schlawack (structlog) respectively. Neither is a
backport. This addresses the Phase 6.1'a §"Selection-effect
caveat" instruction.

## Test count

**1087 → 1097 (+10).** The 10 new tests cover:

- 1 schema-presence test (every record has both new fields)
- 1 allowlist test (partition value Literal)
- 1 iff-coupling test (partition + partition_pinned_at both
  set or both null)
- 1 ISO 8601 format test
- 1 Tier-3-completeness test for pinned cases
- 1 hygiene-invariants test for pinned cases
- 1 ratio guard (informational at N<5)
- 1 train/holdout disjointness invariant
- 1 seed_008-must-be-train test
- 1 at-least-one-holdout-pinned test

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — bundle generator's
  `_check_forbidden_phrases` rejected seed records carrying
  these (none triggered in the 44 new collections).
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in runtime — none.

## Lane separation preserved

The four-lane structural separation continues to hold:

* External-human beta — `not_run`, unchanged.
* AI-tier cold-reader critique — `active, separated`,
  unchanged.
* Yann-solo dogfood — `allowed, internal only`, unchanged.
* Manual data acquisition — `active, manual-only,
  public-only, runtime-isolated`. **46 inclusions, 199
  exclusions** (vs 2 / 14 at Phase 6.1'a close).

## What this block does NOT deliver

* Bulk Tier-3 authoring on all 46 records. Most stay
  `partition: null` until operator pins them (Phase 6.1'd /
  6.1'e operator work).
* Generator stress-test on holdout cases. That is
  Phase 6.1'd's acceptance criterion.
* AI-tier re-run + Yann-solo dogfood. That is Phase 6.1'e.
* Public corpus release. Deferred indefinitely per
  QA/A44 §"HuggingFace usage policy".
* Validation that holdout cases survive the
  `verify-grounded` round-trip with operator-authored
  replays. That is Phase 6.1'd.

## What's next

**Phase 6.1'd** — generator stress-test on the 3 pinned cases:

1. Run `prepare-gateway-bundle` on each pinned case.
2. Hand-author or LLM-author replays for `seed_008` (train
   case) and confirm `verify-grounded` produces
   `verification_candidate`.
3. Hand-author or LLM-author replays for `seed_065` and
   `seed_157` (holdout cases) and confirm same — WITHOUT
   modifying the generator if a holdout-specific issue
   arises (instead, demote the case and replace).
4. Fold any operator-authored Tier-3 records that emerge
   during the round-trip into `index.json` with
   appropriate partition pinning.

The acceptance for Phase 6.1'd is: **3 round-trips succeed
end-to-end** (1 train + 2 holdout), the generator is unchanged
between holdout runs, and the round-trip evidence is
documented in a Phase 6.1'd report.

## Cross-references

* ADR-56 (this block): `memory-bank/decisionLog.md`
* ADR-55 (Phase 6.1'b): `memory-bank/decisionLog.md`
* ADR-54 (Phase 6.1'a): `memory-bank/decisionLog.md`
* ADR-53 (Phase 6.1'a-pre): `memory-bank/decisionLog.md`
* QA/A44: `QA/A44.md`
* Schema: `reports/calibration_seed/schema.md`
* Lane charter: `reports/calibration_seed/README.md`
* Tests: `tests/test_phase6_1_c_partition_discipline.py`
* Bundle generator: `src/oida_code/bundle/generator.py`
* Indexer: `scripts/build_calibration_seed_index.py`
* Project status: `docs/project_status.md`

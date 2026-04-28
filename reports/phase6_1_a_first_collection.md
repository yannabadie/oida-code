# Phase 6.1'a — first calibration-seed collection + worked example

**Status:** ✅ delivered (commit pending).
**Phase block:** 6.1'a (per QA/A44 §"Phase 6.1' option choice"
sub-block ordering).
**Predecessor:** Phase 6.1'a-pre (commit `463f92a`) which
delivered the lane contract, schema, dry-run script, and 8
structural tests.

## What this block delivers

1. **First real invocation of the calibration-seed indexer.**
   Two targets: `pallets/click` (max-prs=5) and
   `pytest-dev/pytest` (max-prs=20). Result: 2 inclusion records,
   14 exclusion records.
2. **Worked example pinned and fully populated:**
   `seed_008_pytest_dev_pytest_14407` — the `-V` short-flag
   bugfix backport. The record has `claim_id`, `claim_type`,
   `claim_text`, `test_scope`, `expected_grounding_outcome`,
   `label_source: yann_manual_review`, `human_review_required:
   false`. See [`reports/calibration_seed/worked_example_phase6_1_a.md`](calibration_seed/worked_example_phase6_1_a.md).
3. **ADR-54** documenting the three-tier field-derivation
   pedagogy (API-derived / allowlist-categorical / free-form
   domain reasoning).
4. **Holdout discipline plan** added to
   [`reports/calibration_seed/README.md`](calibration_seed/README.md):
   N=2 is `pre-holdout`; discipline kicks in at Phase 6.1'c
   (N≥20).
5. **Selection-effect caveat** documented: both inclusions are
   9.0.x backports because community PRs from forks are filtered
   by the Phase 5.6 fork-PR fence. Phase 6.1'c MUST seek
   non-backport non-release-prep cases.

## Corpus state (post-collection)

| Repo | Inclusions | Exclusions | Distribution of exclusions |
|---|---|---|---|
| `pallets/click` | 0 | 4 | 4 fork_pr_refused |
| `pytest-dev/pytest` | 2 | 10 | 5 fork_pr_refused, 3 non_python_change, 2 pr_too_trivial |
| **Total** | **2** | **14** | 9 fork / 3 non-python / 2 too-trivial |

The 2 inclusions:

* `seed_003_pytest_dev_pytest_14420` — "[PR #14391/cd7592c4
  backport][9.0.x] Use direct cause for raises match failures".
  4 files / 31 lines. NOT pinned as worked example yet
  (claim_id=null, human_review_required=true). Available for
  Phase 6.1'b/d work.
* `seed_008_pytest_dev_pytest_14407` — "[PR #14382/d72943a5
  backport][9.0.x] Fix `-V` to show version information". 3
  files / 15 lines. **Pinned as Phase 6.1'a worked example.**

## The worked example in one paragraph

PR #14407 is a 9.0.x backport of community PR #14382. The fix
adds `-V` to pytest's CLI version-flag fast-path in
`src/_pytest/config/__init__.py:main()` — previously only
`--version` would skip plugin loading; `-V` would either error
or trigger full loading. The test
`testing/test_helpconfig.py::test_version_less_verbose` is
parametrized over `["--version", "-V"]` so a single test name
covers both flags. The schema mapping is:

* `claim_id: "C.cli_version_flag.repair_needed"`
* `claim_type: "repair_needed"` (1 of 7 Literal values)
* `expected_grounding_outcome: "evidence_present"` (1 of 6
  values)
* `label_source: "yann_manual_review"` (1 of 5 values)
* `test_scope: "testing/test_helpconfig.py::test_version_less_verbose"`

Full walk-through with three-tier pedagogy:
[`reports/calibration_seed/worked_example_phase6_1_a.md`](calibration_seed/worked_example_phase6_1_a.md).

## Frontier rules — compliance check

All 12 QA/A44 frontier rules remain enforced:

| Rule | Status |
|---|---|
| 1. Egress scripts under `scripts/` not `src/` | ✅ (script is at `scripts/build_calibration_seed_index.py`; `src/oida_code/` untouched) |
| 2. Manual invocation, never CI default | ✅ (`test_no_manual_egress_script_in_workflows` enforces) |
| 3. Explicit env var (PAT_GITHUB) | ✅ (script reads `os.environ.get("PAT_GITHUB")` and warns if absent) |
| 4. `--manual-egress-ok` required | ✅ (8th test enforces refusal modes) |
| 5. Artefacts under `reports/` | ✅ (`reports/calibration_seed/`) |
| 6. No new runtime dependency | ✅ (script uses stdlib only: `urllib.request`, `json`, `argparse`) |
| 7. No verifier import in network mode | ✅ (script does not import any verifier module) |
| 8. Never modifies target repo | ✅ (script only GETs the GitHub REST API; no clone, no push) |
| 9. Never pushes a branch | ✅ |
| 10. Never creates a PR | ✅ |
| 11. No provider call from `verify-grounded` | ✅ (no provider call from anywhere; no provider import) |
| 12. No GitHub/HF call from `verify-grounded` | ✅ (`verify-grounded` runtime path untouched) |

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted, none in
  any new schema, ADR-22 / 24 / 25 / 26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — no new occurrence in any text;
  forbidden-phrase scans still pass.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in runtime — none.

## Lane separation preserved

The four-lane structural separation continues to hold:

* External-human beta — `not_run`, unchanged.
* AI-tier cold-reader critique — `active, separated`,
  unchanged from Phase 6.0.y.
* Yann-solo dogfood — `allowed, internal only`, unchanged from
  Phase 6.0.y'.
* Manual data acquisition (this lane) — `active, manual-only,
  public-only, runtime-isolated`. **2 inclusions, 14
  exclusions** (vs 0/0 at Phase 6.1'a-pre close).

The structural guards (path-isolation in
`scripts/run_beta_feedback_eval.py`, schema pin in same script,
operator-role validation, doc-guard tests in
`tests/test_phase6_0_y_prime_lane_isolation.py`, plus the 8
manual-data-lane isolation tests in
`tests/test_phase6_1_manual_data_lane_isolation.py`) all pass.

## Test count

Unchanged at **1068**. No new tests in this commit. The Phase
6.1'a-pre tests already cover the contract (refusal modes,
marker discrimination, runtime-import bans, no-workflow-invocation).
This commit ships data + documentation, not new code paths.

## Pièges accumulated

* QA/A41: 12
* QA/A42: 12
* QA/A43: 14
* QA/A44: 30
* **Total: 68 pièges accumulated** (informational, not
  enforced). Most relevant to this block:
  * Piège 46 — "Benchmark qui optimise le generator. Garder
    des holdout cases." → addressed by README §"Holdout
    discipline" with the pre-holdout / Phase 6.1'c plan.
  * Piège 27 — "Calibration drift entre runs" → addressed by
    the deterministic schema (script_version field) and
    idempotent `(repo_url, pr_number)` keying.
  * Piège 31 — "Auto-référence du worked example" → addressed
    by picking a `pytest-dev/pytest` PR (NOT an `oida-code`
    self-audit example).

## What this block does NOT deliver

* The bundle generator (`prepare-gateway-bundle`). That is
  Phase 6.1'b.
* The 20-50 case corpus. That is Phase 6.1'c.
* The `partition` schema field. That is Phase 6.1'c.
* Generator stress-test results. That is Phase 6.1'd.
* AI-tier re-run + Yann-solo dogfood on the corpus. That is
  Phase 6.1'e.
* Public corpus release. Deferred indefinitely per
  QA/A44 §"HuggingFace usage policy".

## What's next

**Phase 6.1'b** — minimal `prepare-gateway-bundle` skeleton
generator. Inputs: a record from `index.json`. Outputs: a
bundle directory with `claim.json` + checkout instructions +
`pytest_invocation.sh`. The skeleton does NOT need to handle
every edge case; it needs to handle the worked example
(`seed_008`) + the second inclusion (`seed_003`) cleanly.

The advisor flagged that future collection (Phase 6.1'c) MUST
seek non-backport non-release-prep cases to avoid the
selection-bias trap. Concrete suggestions:

* Maintainer-side semantic changes (new feature, refactor) —
  these come from internal branches and survive the fork-PR
  fence.
* Less-mainstream Python projects where the maintainer
  themselves is the active contributor (small libraries,
  scientific Python tools).
* Multi-author maintainer teams (e.g. `python-attrs/attrs`,
  `psf/black`) where the mix of community-fork and internal-
  branch PRs is more balanced.

## Cross-references

* Lane charter: [`reports/calibration_seed/README.md`](calibration_seed/README.md)
* Schema: [`reports/calibration_seed/schema.md`](calibration_seed/schema.md)
* Worked example walk-through:
  [`reports/calibration_seed/worked_example_phase6_1_a.md`](calibration_seed/worked_example_phase6_1_a.md)
* Phase 6.1'a-pre report: [`phase6_1_a_pre_lane_contract.md`](phase6_1_a_pre_lane_contract.md)
  (if present; otherwise the lane charter README is the entry
  point)
* QA/A44: [`../QA/A44.md`](../QA/A44.md)
* ADR-53: `memory-bank/decisionLog.md`
* ADR-54 (this block): `memory-bank/decisionLog.md`
* Project status: [`../docs/project_status.md`](../docs/project_status.md)

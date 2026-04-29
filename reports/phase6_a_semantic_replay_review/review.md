# Phase 6.a.1 manual semantic replay review

Reviewed at: `2026-04-29T21:45:00+02:00`.
Review version: `phase6_a1_manual_semantic_replay_review_v1`.
Review scope: `manual_archived_replay_semantic_alignment`.

This review checks manual semantic alignment for the three archived
load-bearing replay cases only. It does not validate product safety,
predictive validity, broad generalisation, future replay correctness,
or any new LLM-authored replay set.

## Summary

- Cases reviewed: 3
- `manual_semantic_pass`: 3
- `manual_semantic_fail`: 0
- `ambiguous_insufficient_evidence`: 0

G-6a is closed for the current archived load-bearing replay set only:
ADR-68 static consistency plus this manual upstream-output review both
pass on seed_008, seed_065, and seed_018. Future LLM-authored replay
sets must inherit the same static-plus-manual review requirement before
their replay content can carry claim-supporting weight.

## Method

For each case, the review compared:

1. seed claim id/text/type and test scope from `reports/calibration_seed/index.json`;
2. packet evidence and replay files in the archived `round_trip_outputs` directory;
3. upstream Git diff between the recorded `base_sha` and `head_sha`;
4. local scoped pytest rerun in the target clone venv;
5. pass2 supported claim and grounded-report accepted claim.

`PAT_GITHUB` was not required. Per cgpro QA/A50, direct local clone
diff plus scoped pytest rerun is sufficient here because the clones are
from the public upstream repos, the base/head SHAs match the seed
records, and none of the claims depends on PR comments or maintainer
discussion.

## Cases

### `seed_008_pytest_dev_pytest_14407`

- Partition: `train`
- Outcome: `manual_semantic_pass`
- Repo / PR: `https://github.com/pytest-dev/pytest` PR `14407`
- Diff range: `4afcd4906b9cf4468dc9ca8cf7c53126e190d008` -> `480809ae02a97344e68e52eb015e68b840f2e05c`
- Replay dir: `reports/phase6_1_e/round_trip_outputs/seed_008_pytest_dev_pytest_14407`
- Seed claim: `C.cli_version_flag.repair_needed`
- Scoped rerun: `.venv\Scripts\python.exe -m pytest testing/test_helpconfig.py::test_version_less_verbose -q`
- Rerun result: exit `0`; `2 passed in 0.37s`

Evidence reviewed:

- The upstream diff adds `changelog/14381.bugfix.rst`.
- `_pytest/config/__init__.py:main()` now counts `--version` plus `-V` in the early version fast-path.
- `testing/test_helpconfig.py::test_version_less_verbose` is parametrized over `--version` and `-V`.
- `grounded_report.json` accepts only `C.cli_version_flag.repair_needed` with seed event id and pytest tool evidence.

Reviewer note: the replay statement is narrower than the full seed claim
because it focuses on counting `-V` occurrences. The diff and rerun
support the core seed semantics: `-V` is handled in the same early
version path as `--version`, and both parametrized runs pass.

Residual uncertainty: none for the archived replay's core claim
alignment. This review does not cover pytest CLI behavior beyond the
reviewed scope.

### `seed_065_simonw_sqlite_utils_680`

- Partition: `holdout`
- Outcome: `manual_semantic_pass`
- Repo / PR: `https://github.com/simonw/sqlite-utils` PR `680`
- Diff range: `fb93452ea8e677f0a2fb002f9c2483072432a6cd` -> `e7ecb0ffdfcb15a879e0da202a00966623f1e79c`
- Replay dir: `reports/phase6_1_h/round_trip_outputs/seed_065_simonw_sqlite_utils_680`
- Seed claim: `C.column_type_mapping.repair_needed`
- Scoped rerun: `.venv\Scripts\python.exe -m pytest tests/test_cli.py::test_csv_detect_types_creates_real_columns -q`
- Rerun result: exit `0`; `1 passed`

Evidence reviewed:

- `sqlite_utils/db.py` maps `float`, `decimal.Decimal`, and numpy float types to `REAL`.
- `sqlite_utils/cli.py` adds `REAL` to accepted CLI column-type choices for compatibility.
- `tests/test_cli.py::test_csv_detect_types_creates_real_columns` asserts CSV detect-types produces `weight REAL`.
- `grounded_report.json` accepts only `C.column_type_mapping.repair_needed` with seed event id and pytest tool evidence.

Reviewer note: the replay statement covers the central mapping repair
from `FLOAT` to `REAL`. It is narrower than the full seed because it
does not enumerate every numpy type or CLI compatibility detail, but it
does not widen or contradict the seed claim.

Residual uncertainty: none for the archived replay's accepted claim.
The review covers this test-scoped mapping claim only.

### `seed_018_python_attrs_attrs_1529`

- Partition: `holdout`
- Outcome: `manual_semantic_pass`
- Repo / PR: `https://github.com/python-attrs/attrs` PR `1529`
- Diff range: `3a68d4913221abc6f8ad3be50937f7ae49300a98` -> `b13a7056c5f407abbd9f3e572ee48ad65afce91c`
- Replay dir: `reports/phase6_1_corpus_quality_v1/round_trip_outputs/seed_018_python_attrs_attrs_1529`
- Seed claim: `C.attrs_fields_instance_support.capability_sufficient`
- Scoped rerun: `.venv\Scripts\python.exe -m pytest tests/test_make.py::TestFields::test_instance -q`
- Rerun result: exit `0`; `1 passed in 0.26s`

Evidence reviewed:

- `src/attr/_make.py:fields()` now accepts attrs instances by checking `type(cls).__attrs_attrs__` and recursing with `type(cls)`.
- `tests/test_make.py::TestFields::test_instance` now asserts `fields(C()) is fields(C)`.
- A sibling test preserves `TypeError` for non-attrs instances.
- `grounded_report.json` accepts only `C.attrs_fields_instance_support.capability_sufficient` with seed event id and pytest tool evidence.

Reviewer note: the replay statement matches the implementation path and
scoped test: attrs instances now resolve to their class fields. The
report does not add a broader attrs API claim.

Residual uncertainty: none for the archived replay's accepted claim.
This review does not cover attrs behavior beyond the reviewed `fields()`
instance scope.

## Outcome

The current archived load-bearing replay set passes both:

- ADR-68 static replay-content audit:
  `static_content_consistency`, 3/3 pass, 0 errors, 0 warnings.
- ADR-69 manual semantic replay review:
  `manual_archived_replay_semantic_alignment`, 3/3 pass, no ambiguous
  case.

Therefore G-6a can be marked closed for this archived replay set. This
does not remove the requirement for future static-plus-manual review on
new LLM-authored replay sets.

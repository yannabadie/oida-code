# Phase 6.d.3 stop report

Date: 2026-04-30

ADR-73 / G-6d.3 attempted a third corpus pinning tranche, but did
not complete. The live corpus remains at the ADR-72 state: 46 records,
14 pinned, 10 train, 4 holdout.

## Frozen attempted selection

The attempted selection was frozen at `2026-04-30T09:18:00Z` before
any scoped pytest outcome:

| case_id | intended partition |
|---|---|
| `seed_058_pallets_itsdangerous_378` | train |
| `seed_071_simonw_sqlite_utils_689` | train |
| `seed_074_simonw_sqlite_utils_658` | train |
| `seed_159_hynek_structlog_759` | holdout |

The deterministic holdout rule selected
`seed_159_hynek_structlog_759`.

## Failure

The first post-freeze feasibility command was:

```text
python scripts/clone_target_at_sha.py --repo pallets/itsdangerous --head-sha 7f4dcf83a07bb3d53f4e0e65ef1b43327b4cca90 --manual-egress-ok --clones-dir .tmp/g6d3_clones --install-oida-code --install-group tests --import-smoke itsdangerous
```

Clone and editable install completed, but `--install-group tests`
failed because ItsDangerous at that SHA does not define a PEP 735
`[dependency-groups]` table. The target's own `tox.ini` uses
`deps = -r requirements/tests.txt`, and that file contains
`pytest==8.1.1`.

A diagnostic attempt to run the scoped pytest command in the venv
failed with `No module named pytest`; this is not counted as a scoped
pytest outcome.

## Decision

cgpro ruled that manually installing `requirements/tests.txt` would
cross the current block's dependency-install boundary because
`seed_058` was already documented as the older requirements-pattern
risk. Therefore:

- no manual `pip install -r requirements/tests.txt`
- no post-freeze replacement
- no successful G-6d.3 commit
- no N=18 live corpus claim
- no replay output, provider evidence, runtime change, clone-helper
  flag change, or GitHub Action change

G-6d remains open.

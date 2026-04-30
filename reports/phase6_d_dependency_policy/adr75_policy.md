# ADR-75 dependency policy for G-6d

Date: 2026-04-30
cgpro thread: `repo-product-vision-review`
cgpro conversation: `69f329be-0dd4-838f-8687-d68190f21e7d`

## Decision

For G-6d.4, candidates whose scoped tests require requirements-file /
tox-only dependency installation are rejected or deferred before
partition freeze.

This is a policy-only block. It does not add a new clone-helper flag,
does not change the calibration seed index, and does not add runtime
support for requirements-file installs.

## Trigger

ADR-73 stopped after the first post-freeze feasibility command because
`pallets/itsdangerous` did not expose test dependencies through a
supported PEP 621 extra or PEP 735 dependency group. Its target metadata
instead used tox `deps = -r requirements/tests.txt`, and scoped pytest
could not be reached without installing that requirements file.

cgpro ruled then that manual rescue would widen the boundary for a case
already known as an older requirements-pattern risk. ADR-74 then made a
pre-freeze dependency policy a prerequisite before any new G-6d pinning.

## Current supported bootstrap surface

G-6d.4 may use only the existing predeclared bootstrap surface:

- target clone at pinned `head_sha`;
- editable target install;
- optional `--install-oida-code`;
- optional `--scm-pretend-version`;
- optional `--import-smoke`;
- optional `--install-extras` for PEP 621 extras;
- optional `--install-group` for PEP 735 dependency groups.

The predeclared flag list remains pinned at nine flags by
`tests/test_phase6_1_i_predeclared_bootstrap.py`.

## Reject / defer before freeze

Reject or defer a candidate before partition freeze when reaching the
scoped pytest outcome requires any of:

- `tox.ini` or `pyproject.toml` tox `deps = -r ...`;
- `requirements/*.txt`, `requirements-*.txt`, or another test
  requirements file;
- manual `pip install -r <file>`;
- a new `--install-requirements-file` or equivalent clone-helper flag;
- a bootstrap path outside PEP 621 extras or PEP 735 dependency groups.

Deferred candidates may be revisited only by a separate future ADR that
updates the helper and structural flag tests before candidate selection.
They must not be rescued after a tranche has been frozen.

## What this preserves

- ADR-66 predeclared bootstrap boundary.
- ADR-73 stop honesty.
- ADR-74 diagnostic-first product reset.
- G-6d freeze-before-outcome discipline.
- No runtime/provider/MCP/default-gateway change.

## What this does not claim

- No corpus advance.
- No N=18 or N>=20 claim.
- No replay correctness claim.
- No product or merge-readiness verdict.
- No official OIDA fusion-field unlock.

## Next block

G-6d.4 may now start candidate selection from the existing
`reports/calibration_seed/index.json` pool. The operator must apply this
policy during candidate inspection before partition freeze.

Postscript: ADR-76 records the actual G-6d.4 outcome. Screening stopped before
freeze because only two clean candidates survived; no partial +2 tranche was
allowed.

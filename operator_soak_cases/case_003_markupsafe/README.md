# Case 003 — markupsafe `soft_unicode` removal (C-extension dual-backend)

## Status

`complete` — Tier 5 promotion gate cleared. Originally labelled
on workflow run `25045245609` (UX 2/1/2/2 — evidence_traceability=1
pending the pytest_summary_line adapter follow-up); re-dispatched
on workflow run `25047711777` after Phase 5.8.x / ADR-47 shipped
the schema field; cgpro session `phase58-soak` (conversation
`69ef3a8c-0198-8394-8f09-14a7b120d192`) relabelled UX 2/2/2/2 with
the new evidence shape. Label still `useful_true_positive`.

| field | value |
|---|---|
| claim_id | `C.markupsafe.soft_str_dual_backend_observable` |
| claim_type | `observability_sufficient` |
| pytest_scope | `tests/test_markupsafe.py` |
| target_install | `true` (editable install required so the C extension `_speedups.c` builds and dual-backend parametrize cases run instead of skip) |
| target | `pallets/markupsafe@7856c3d` (PR #261 "remove deprecated code") |
| workflow_run_id | `25047711777` (Phase 5.8.x re-dispatch) |
| artifact_url | <https://github.com/yannabadie/oida-code/actions/runs/25047711777> |
| operator_label | `useful_true_positive` |
| ux_score | 2/2/2/2 |

Source-of-truth sidecars: [`fiche.json`](fiche.json) ·
[`label.json`](label.json) · [`ux_score.json`](ux_score.json).

## Outcome details (independently verified)

- `gateway-status: diagnostic_only`
- `gateway-official-field-leak-count: 0` (ADR-22 hard wall holds)
- `accepted_claims:
  [C.markupsafe.soft_str_dual_backend_observable]` /
  `rejected_claims: []` / `unsupported_claims: []`
- `pytest_summary_line: "29 passed in 0.03s"` — proves all 5
  `[markupsafe._native]` + 5 `[markupsafe._speedups]` parametrize
  cases + 19 unparametrized tests executed (zero skipped, so the
  C extension built successfully).
- Independent forbidden-token scan across the downloaded artefacts
  returned zero hits.

## Intent (controlled change)

`pallets/markupsafe` commit `7856c3d` ("remove deprecated code",
PR #261, author David Lord) drops the deprecated top-level
`markupsafe.soft_unicode` export from `__init__.py` / `_native.py`
/ `_speedups.c`, updates `tests/test_markupsafe.py` and
`tests/conftest.py`, and requires consumers to switch to
`soft_str`. The bundle's `observability_sufficient` claim grounds
on the regression test showing both backends still pass scoped
to the retained `soft_str` path.

## Cross-repo + C-extension machinery

case_003 motivated Phase 5.8.1-E / ADR-46
(`inputs.target-install` on operator-soak.yml). Strategy
`install_target_deps_alpha` was chosen because pytest's
`skipif(_speedups is None)` would have silently skipped the
`_speedups` parametrize cases without an editable install, hiding
the dual-backend coverage signal. The conditional
`actions/setup-python@v5` (Python 3.11 to match the composite
action) + conditional `pip install -e .` inside `oida-target/`
make the C extension build before pytest runs.

## Why two runs

The original run `25045245609` labelled UX 2/1/2/2 because the
gateway adapter's clean-pass synthesis emitted "no failures" but
did NOT include the explicit pytest summary line — cgpro flagged
this as a Phase 5.8.x adapter follow-up. ADR-47 shipped
`pytest_summary_line` on `VerifierToolResult`, the case was
re-dispatched as `25047711777` with the new evidence shape, and
cgpro relabelled UX 2/2/2/2. The two runs are kept in the
fiche.json history for the audit trail.

## Forbidden in this case

- no `pull_request_target`
- no fork PR
- no external provider (use `llm-provider: "replay"`)
- no MCP
- no provider tool-calling
- no write / network tools
- no LLM-written `label.json` / `ux_score.json`

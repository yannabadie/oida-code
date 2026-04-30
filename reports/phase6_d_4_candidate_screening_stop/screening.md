# Phase 6.d.4 pre-freeze candidate screening stop

Date: 2026-04-30

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

G-6d.4 stops before partition freeze.

The live corpus remains at the ADR-72 / ADR-75 state:

- 46 total records
- 14 pinned
- 10 train
- 4 holdout
- 32 unpinned

No `reports/calibration_seed/index.json` edit was made. No partition was
frozen. No scoped pytest feasibility pass was run, because there is no frozen
tranche to validate.

## Why

cgpro selected the conservative exact-four rule:

- a G-6d.4-style tranche must contain exactly four clean candidates;
- the split must be +3 train / +1 holdout;
- fewer than four clean candidates means stop before freeze;
- accepted-but-unfrozen candidates must be re-screened before any future
  tranche;
- no partial +2 freeze, no train-only salvage, no holdout-only salvage, and no
  "least bad" candidate admission to hit N.

This preserves the ADR-75 dependency boundary and avoids optional-stopping
pressure. Increasing N by admitting questionable candidates would weaken the
larger-N evidence instead of improving it.

## Candidate outcome

| case_id | action | reason |
|---|---|---|
| `seed_074_simonw_sqlite_utils_658` | accept for possible future freeze | Clean setup.py `test` extra path, changed tests, narrow table/view API claim, scoped pytest node `tests/test_create.py::test_bad_table_and_view_exceptions`. |
| `seed_159_hynek_structlog_759` | accept for possible future freeze | Clean PEP 735 `tests` group path, changed test, narrow `ConsoleRenderer.force_colors` property claim, scoped pytest node `tests/test_dev.py::TestConsoleRendererForceColorsProperty::test_toggle_force_colors_updates_styles_and_levels`. |
| `seed_071_simonw_sqlite_utils_689` | needs more screening | Dependency path may be clean, but the candidate overlaps an already pinned `--functions` behavior and comes from a broad PR/diff. |
| `seed_041_pallets_itsdangerous_405` | defer | Broad release/version/typing maintenance rather than a narrow behavioral claim. |
| `seed_058_pallets_itsdangerous_378` | defer | ADR-73/ADR-75 requirements-file/tox-only dependency boundary. |
| `seed_060_simonw_sqlite_utils_693` | reject | Broad pytest-warning/resource cleanup surface over many files. |
| `seed_076_simonw_sqlite_utils_654` | reject | Mostly test infrastructure and SQLite support metadata. |
| `seed_136_hynek_structlog_802` | defer | Relevant tests depend on optional better-exceptions availability outside the standard tests group. |
| `seed_153_hynek_structlog_767` | reject | Test ordering/infrastructure change. |
| `seed_154_hynek_structlog_766` | reject | Test helper migration / pretend dependency cleanup. |
| `seed_138_hynek_structlog_800` | reject | Broad version-support/typing modernization surface. |
| `seed_152_hynek_structlog_768` | reject | Broad modernization/cleanup surface across many runtime and test files. |
| `seed_160_hynek_structlog_758` | reject | Refactor-only terminal initialization with no changed runnable test scope. |
| `seed_130_pytest_dev_pluggy_640` | reject | Cleanup/refactor with no changed runnable test file. |
| `seed_109_encode_httpx_3690` | reject | Public base/head boundary was not verifiable against the indexed metadata during local screening. |
| `pydantic_watchfiles_non_python_rust_surface` | reject | Non-Python or Rust-adapter surface conflicts with current Python-first scope. |

## Autonomous protocol

The durable protocol recorded from this consultation is
`Evidence-Led Autonomous Block Protocol (ELABP-2026-04-30)`:

- cgpro decides at substantive inflection points;
- Codex verifies and implements locally;
- Context7 or official docs refresh API/library behavior;
- web/arXiv sources refresh methodology and current provider/tool facts;
- provider API keys are research accelerators only;
- direct provider calls require same-day official docs or model-list refresh;
- provider output never replaces public diffs, scoped tests, or local checks;
- every block records evidence, sources, hard-wall compliance, and stop
  conditions.

## Sources

- SWE-bench: Can Language Models Resolve Real-World GitHub Issues:
  https://arxiv.org/abs/2310.06770
- Agentless: Demystifying LLM-based Software Engineering Agents:
  https://arxiv.org/abs/2407.01489
- OpenAI, why SWE-bench Verified no longer measures frontier coding
  capabilities:
  https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- SWE-Adept:
  https://arxiv.org/abs/2603.01327
- RepoAudit:
  https://arxiv.org/abs/2501.18160
- pytest documentation, node IDs and focused selection:
  https://docs.pytest.org/
- Typer testing documentation:
  https://typer.tiangolo.com/tutorial/testing/

## Hard-wall preservation

- No live corpus advance.
- No replay output.
- No `round_trip_outputs`.
- No runtime/provider/MCP/default-gateway change.
- No clone-helper flag addition.
- No requirements-file install support.
- No GitHub Action default change.
- No official OIDA fusion-field unlock.
- No product, merge-readiness, production-readiness, public benchmark, or
  broad-generalisation claim.

## Verification

- `python -m json.tool reports\phase6_d_4_candidate_screening_stop\screening.json > $null` - passed.
- `python -m pytest tests/test_phase6_d_4_candidate_screening_stop.py -q` - passed.
- `python -m pytest tests/test_phase6_d_4_candidate_screening_stop.py tests/test_phase6_d_dependency_policy.py tests/test_phase6_d_3_stop.py -q` - passed.
- `python -m pytest tests/test_phase6_1_c_partition_discipline.py tests/test_phase6_1_i_predeclared_bootstrap.py tests/test_phase6_1_g_extras_and_groups.py tests/test_reports.py tests/test_self_audit_guard.py -q` - passed.
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py action.yml src\oida_code` - passed with no diff.
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` - passed.
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py` - passed.
- `python -m pytest -q` - passed.
- `git diff --check` - passed.

G-6d remains open.

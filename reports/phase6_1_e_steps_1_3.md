# Phase 6.1'e steps 1-3 — runtime-loader guard + train pins + first `verification_candidate`

**Status:** delivered (commit pending). Step 4 (holdouts under
freeze rule) lands separately per QA/A45.
**Predecessor:** Phase 6.1'd (commit `bfb63ca`).
**Acceptance criterion:** runtime-loader smoke ok AND
N_pinned=5 with ratio guard enforcing AND seed_008 produces
`status=verification_candidate` with claim accepted.

## What this block delivers

1. **Step 1 — runtime-loader acceptance guard (+9 tests).**
   `tests/test_phase6_1_e_runtime_loader_guard.py` loads each
   generated bundle's 8 files through their target Pydantic
   contract. Closes the gap that ADR-57 retracted from ADR-55.
2. **Step 2 — 2 more train pins.** `seed_062` (sqlite-utils
   callable refs, `capability_sufficient`) + `seed_142`
   (structlog warning removal, `repair_needed`) authored as
   Tier-3-complete and pinned `partition: train`. **N_pinned
   = 5; holdout ratio = 0.40, inside [0.20, 0.40] enforcing
   band.**
3. **Step 3 — clone helper + first `verification_candidate`.**
   - `scripts/clone_target_at_sha.py` (NEW, manual lane,
     `MANUAL_EGRESS_SCRIPT`, refuses without flag) shallow-
     clones a public repo at a SHA, creates a venv, installs
     the target editable, optionally installs oida-code, supports
     `--scm-pretend-version` for shallow-clone gotchas.
   - End-to-end round-trip on seed_008: `prepare-gateway-bundle`
     → `llm_author_replays.py` (DeepSeek) → `verify-grounded`
     with `--repo-root <clone>`. **Result: `status=verification_candidate`,
     `tool_calls=1`, `accepted_claims=['C.cli_version_flag.repair_needed']`,
     pytest "2 passed in 0.63s".**
4. **Bonus — pytest adapter `-p plugin` preservation fix.**
   The verifier's `-o addopts=` neutralisation (Phase 5.9 /
   ADR-49) stripped pytest's `-p pytester` from the target's
   addopts, making `pytester_example_dir` "Unknown config option"
   and killing the run. `_extract_pytest_plugin_args()` parses
   the target's `pyproject.toml` and preserves `-p <plugin>`
   pairs. seed_008 is TRAIN (discipline allows tuning); the
   fix is target-class-general (any project with `-p plugin`
   in addopts now works through the verifier).

## seed_008 round-trip outcome

```
overall: verification_candidate
accepted: ['C.cli_version_flag.repair_needed']
unsupported: []
tool: pytest status: ok summary: 2 passed in 0.63s
```

This is the **first claim-supporting outcome** in the
calibration_seed lane. The Phase 4.1+ verifier-grounded path
now demonstrably grounds claims through real target checkouts.

Evidence archived under
`reports/phase6_1_e/round_trip_outputs/seed_008_pytest_dev_pytest_14407/`:

- `packet.json` (LLMEvidencePacket, evidence_items survived
  through bundle generation)
- `pass*_*.json` (LLM-authored replays, DeepSeek, ~8s call)
- `tool_policy.json`, `gateway_definitions.json`,
  `approved_tools.json` (with sha256 fingerprint)
- `README.md` (operator-facing description)
- `grounded_report.json` (the run's full output —
  `status=verification_candidate`, accepted claim, pytest tool
  result with summary line)

## Pinned cases (post step 2)

| case_id | partition | claim_type | claim_id |
|---|---|---|---|
| seed_008_pytest_dev_pytest_14407 | train | repair_needed | C.cli_version_flag.repair_needed |
| seed_062_simonw_sqlite_utils_690 | train | capability_sufficient | C.convert_callable_reference.capability_sufficient |
| seed_065_simonw_sqlite_utils_680 | holdout | repair_needed | C.column_type_mapping.repair_needed |
| seed_142_hynek_structlog_790 | train | repair_needed | C.exception_render_warning.repair_needed |
| seed_157_hynek_structlog_761 | holdout | capability_sufficient | C.callsite_qual_name.capability_sufficient |

N_pinned = 5; train = 3; holdout = 2; ratio = 2/5 = 0.40
(inside [0.20, 0.40] enforcing band).

## Pytest adapter fix scope

`src/oida_code/verifier/tools/adapters.py::_extract_pytest_plugin_args`
parses `<repo_root>/pyproject.toml` for `[tool.pytest].addopts`
or `[tool.pytest.ini_options].addopts`, extracts any `-p <plugin>`
pairs, returns them as a flat tuple to insert into the verifier's
pytest argv. Lazy-imports `tomllib` (stdlib since Python 3.11);
graceful no-op if `pyproject.toml` is absent or malformed.

`PytestAdapter.build_argv` now produces:

```python
(
    "pytest", "-o", "addopts=",
    *plugin_args,         # NEW: -p pytester, -p anyio, etc.
    "-q", "--no-header", "--maxfail=20",
    *paths,
)
```

The fix preserves the Phase 5.9 / ADR-49 purpose (avoid `-q + -q
= -qq` collision that breaks `pytest_summary_line` extraction)
while fixing the plugin-strip side-effect.

## Test count

**1102 → 1111 (+9).** All new tests in
`tests/test_phase6_1_e_runtime_loader_guard.py`.

The Phase 6.1'c partition-discipline test
`test_holdout_ratio_in_band_when_pool_large` was previously
informational (vacuously passes at N<5); now ENFORCING at N=5.

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — none in any new artifact.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in **runtime path** (`src/oida_code/`)
  — none. The pytest adapter fix is internal to the verifier
  and does NOT call any provider.

## Lane separation preserved

* External-human beta — `not_run`.
* AI-tier cold-reader critique — `active, separated`.
* Yann-solo dogfood — `allowed, internal only`.
* Manual data acquisition — `active, manual-only,
  public-only, runtime-isolated`. **3 manual-lane scripts**
  now: `build_calibration_seed_index.py` (Phase 6.1'a-pre),
  `llm_author_replays.py` (Phase 6.1'd), `clone_target_at_sha.py`
  (Phase 6.1'e). All carry the `MANUAL_EGRESS_SCRIPT = True`
  marker; all auto-discovered by
  `tests/test_phase6_1_d_llm_author_replays.py::test_no_manual_egress_script_referenced_in_workflows`.

## Discipline checkpoint

Per QA/A45 verdict_q3 + cgpro's overall recommendation:

* **Step 4 (seed_065 + seed_157 holdouts under freeze rule)
  lands separately.** A separate commit means the freeze rule
  applies to a clean evaluation pass — no cross-contamination
  between train tuning (this commit) and holdout evaluation
  (next commit).
* If a holdout produces `verification_candidate` → great, the
  generator+adapter generalise.
* If a holdout produces `diagnostic_only` or `blocked` → the
  freeze rule kicks in: NO generator/tooling edits. Either
  demote-and-replace OR document the gap honestly.

## What this block does NOT deliver

* Holdout round-trips. Step 4, separate commit.
* Multi-provider replay panel (DeepSeek + Grok + MiniMax).
  Optional step 5; deferred unless step 4 needs it.
* AI-tier cold-reader re-run on the new corpus. Originally
  in 6.1'e scope; cgpro's verdict focused on round-trip path.
  Operator's call.

## Cross-references

* ADR-58 (this block): `memory-bank/decisionLog.md`
* ADR-57 (Phase 6.1'd): `memory-bank/decisionLog.md`
* ADR-56 (Phase 6.1'c): `memory-bank/decisionLog.md`
* QA/A45 (cgpro session phase61-review): `QA/A45.md`
* Bundle generator: `src/oida_code/bundle/generator.py`
* Verifier pytest adapter: `src/oida_code/verifier/tools/adapters.py`
* LLM-author script: `scripts/llm_author_replays.py`
* Clone helper: `scripts/clone_target_at_sha.py`
* Round-trip evidence:
  `reports/phase6_1_e/round_trip_outputs/seed_008_pytest_dev_pytest_14407/`
* Tests: `tests/test_phase6_1_e_runtime_loader_guard.py`
* Project status: `docs/project_status.md`

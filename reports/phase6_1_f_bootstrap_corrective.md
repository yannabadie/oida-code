# Phase 6.1'f — clone helper bootstrap fix (minimal)

**Status:** delivered (commit pending).
**Phase block:** 6.1'f bootstrap-corrective (per QA/A45_step4_outcome).
**Predecessor:** Phase 6.1'e step 4 (commit `97f27cc` —
`target_bootstrap_gap` on both holdouts).
**Acceptance criterion (per cgpro verdict_q3 minimal_first):**
install-order flip + post-install import smoke close the
"package not importable from venv" class of failure on the
holdout targets, with hermetic tests proving the contract.

## What this block delivers

Per cgpro QA/A45_step4_outcome.md `next_action`, exactly the
minimal corrective:

1. **Install-order flip in `scripts/clone_target_at_sha.py`:**
   when `--install-oida-code` is set, the local oida-code
   package is installed FIRST and the cloned target is
   installed editable LAST. The hypothesis: pip's
   editable-install dependency resolution can remove the
   target's editable link when a later install re-resolves
   shared dependencies; making the target the last install
   makes its editable link the final state.
2. **`--import-smoke PACKAGE` flag** (repeatable): runs
   `<venv>/python -c "import PACKAGE"` after all installs;
   fails fast with a clear `target_bootstrap_gap` banner +
   stderr tail if any import fails.
3. **Docstring update** documenting the install-order
   rationale and a non-pytest example invocation.
4. **`tests/test_phase6_1_f_clone_bootstrap.py`** (+8
   hermetic tests via monkeypatch + importlib).

## Empirical validation (one-off probes)

Both holdout targets now import successfully under the fixed
helper:

```
$ python scripts/clone_target_at_sha.py \
    --repo simonw/sqlite-utils \
    --head-sha e7ecb0ffdfcb15a879e0da202a00966623f1e79c \
    --manual-egress-ok --install-oida-code \
    --import-smoke sqlite_utils
import-smoke: verifying `import sqlite_utils` in venv ...
import-smoke: `import sqlite_utils` OK
target: simonw/sqlite-utils@e7ecb0ff...

$ python scripts/clone_target_at_sha.py \
    --repo hynek/structlog \
    --head-sha f7e9f78dbd31b967eeaebaf9f2e5f424065cdaf2 \
    --manual-egress-ok --install-oida-code \
    --scm-pretend-version structlog=25.5.0.dev0 \
    --import-smoke structlog
target: hynek/structlog@f7e9f78d...
```

(Probes not committed — operator-time evidence captured here
categorically.)

## Second-order gap surfaced (NOT fixed in this block)

While the import-smoke now passes, running the verifier
end-to-end against the cloned venvs still fails for non-pytest
targets:

```
$ <clone>/.venv/Scripts/python.exe -m pytest --version
No module named pytest
```

Cause: `pip install -e .` for sqlite-utils / structlog only
installs runtime deps. Their pytest comes from a `[tests]`
extra (e.g. structlog: `tests = ["pytest-asyncio>=0.17",
"pytest>=6.0"]`) that the clone helper does NOT request. For
seed_008 this works because pytest IS the target package —
installing pytest's source tree puts pytest itself in the venv.

**This is a SECOND class of bootstrap gap.** Per cgpro
QA/A45_step4_outcome verdict_q3 (`minimal_first_then_broader_in_separate_block`),
fixing it in the same block would blur whether the minimal
hypothesis (install-order + import-smoke) closed the observed
failure class. The next-block scope is `--install-extras`
flag (or equivalent) — deferred.

## Hermetic test contract (8 tests)

| Test | What it asserts |
|---|---|
| `test_clone_module_carries_egress_marker` | ADR-53: marker present |
| `test_install_order_oida_code_first` | oida-code installed BEFORE target when --install-oida-code |
| `test_install_order_target_only_when_no_oida_code` | back-compat: 1 install call w/o flag |
| `test_import_smoke_command_construction` | one `python -c "import X"` per --import-smoke X |
| `test_import_smoke_failure_reporting` | failure → SystemExit(2) + `target_bootstrap_gap` banner naming the package |
| `test_main_invokes_import_smoke_after_installs` | smoke runs AFTER all installs |
| `test_no_import_smoke_skips_smoke_step` | back-compat: no flag → no smoke call |
| `test_workflow_non_reference_test_still_passes` | ADR-53 lane-isolation still enforced |

All hermetic via `monkeypatch` + `subprocess.run` stubbing —
no real `git` or `pip` calls, no network, sub-100ms total.

## Holdout discipline state

| Field | Value |
|---|---|
| N_pinned | 5 (3 train + 2 holdout) — unchanged |
| Holdout ratio | 2/5 = 0.40 (still inside [0.20, 0.40] enforcing band) |
| seed_008 status | train, `verification_candidate` (Phase 6.1'e step 3) |
| seed_062 status | train, Tier-3-pinned, never round-tripped |
| seed_142 status | train, Tier-3-pinned, never round-tripped |
| seed_065 status | holdout, `tainted-by-bootstrap-gap` per ADR-59 |
| seed_157 status | holdout, `tainted-by-bootstrap-gap` per ADR-59 |

Per cgpro `next_action`: seed_065 + seed_157 are NOT replaced
in this commit. Replacement happens AFTER the second-order gap
is also fixed (next block), then a fresh freeze-rule pass at
the post-fix SHA.

## Test count

**1111 → 1119 (+8).** All new tests in
`tests/test_phase6_1_f_clone_bootstrap.py`. No existing test
was modified.

## Hard wall preserved

* `total_v_net` / `debt_final` / `corrupt_success` /
  `corrupt_success_ratio` / `verdict` — none emitted.
  ADR-22/24/25/26 hard wall ACTIVE.
* `merge-safe` / `production-safe` / `bug-free` / `verified` /
  `security-verified` — none in any new artifact.
* `enable-tool-gateway` default — unchanged (`false`).
* MCP runtime — none. Phase 4.7+ anti-MCP locks ACTIVE.
* Provider tool-calling in **runtime path** (`src/oida_code/`)
  — none. The change is exclusively to a `scripts/` manual-lane
  file.

## Lane separation preserved

The four-lane structural separation continues to hold. The
manual data acquisition lane is unchanged at 3 scripts:
`build_calibration_seed_index.py`, `llm_author_replays.py`,
`clone_target_at_sha.py` (this commit's edit target). All carry
the `MANUAL_EGRESS_SCRIPT = True` marker.

## What this block does NOT deliver

* The second-order test-deps gap fix (`--install-extras`).
  Deferred to next block.
* Replacement of seed_065 + seed_157. Deferred until both
  bootstrap classes are closed.
* Multi-provider replay panel (DeepSeek + Grok + MiniMax).
  Optional step 5 from the original 6.1'e plan.
* AI-tier cold-reader rerun on the new corpus.

## What's next

**Phase 6.1'g (or 6.1'f-broader)** — second-order bootstrap
gap fix:

1. Add `--install-extras EXTRAS` flag (e.g. `--install-extras
   tests`) that pip-installs the target with `[EXTRAS]`
   syntax: `pip install -e ".[tests]"`.
2. Update the script docstring + tests.
3. Verify on sqlite-utils + structlog: pytest is now in the
   venv after the install.
4. Re-run a fresh freeze-rule holdout pass on either the
   existing seed_065 + seed_157 (taint cleared) OR fresh
   replacements from the 46 inclusions.
5. Expected outcome: `verification_candidate` on at least one
   non-pytest holdout. That would be the first
   non-pytest-shaped target generalisation.

## Cross-references

* QA/A45 (initial pass): `QA/A45.md`
* QA/A45_followup (step 4 strategy): `QA/A45_followup.md`
* QA/A45_step4_outcome (this block's mandate): `QA/A45_step4_outcome.md`
* ADR-58 (Phase 6.1'e steps 1-3): `memory-bank/decisionLog.md`
* ADR-59 (Phase 6.1'e step 4): `memory-bank/decisionLog.md`
* ADR-60 (this block): `memory-bank/decisionLog.md`
* Clone helper: `scripts/clone_target_at_sha.py`
* Tests: `tests/test_phase6_1_f_clone_bootstrap.py`
* Phase 6.1'e step 4 evidence (target_bootstrap_gap):
  `reports/phase6_1_e/round_trip_outputs/seed_065_*` and
  `reports/phase6_1_e/round_trip_outputs/seed_157_*`.

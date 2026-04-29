# Phase 6.1'g — clone helper extras + groups (second-order bootstrap fix)

**Status:** delivered (commit pending).
**Phase block:** 6.1'g (per QA/A46 next_action).
**Predecessor:** Phase 6.1'f (commit `0e0864f` — install-order
flip + import-smoke).
**Cycle verdict (per QA/A46 verdict_q4):** "Phase 6.1'
validated the discipline and produced one real checkout
proof-of-concept, but it must not claim holdout generalisation
until the test-extras bootstrap gap is fixed and a fresh frozen
holdout pass succeeds."

This is the bootstrap-side half of the verdict's prerequisite.
The fresh frozen holdout pass is Phase 6.1'h (next commit).

## What this block delivers

Two parallel CLI flags on `scripts/clone_target_at_sha.py`,
one per Python packaging standard:

1. **`--install-extras EXTRAS`** (repeatable, PEP 621): turns
   the target install into `pip install -e <clone>[EXTRAS]`.
   Use when target declares dev/test deps under
   `[project.optional-dependencies]`.
2. **`--install-group GROUP`** (repeatable, PEP 735): runs
   `pip install --group <pyproject>:GROUP` after the editable
   install. Use when target declares dev/test deps under
   `[dependency-groups]`. Requires pip 25.1+.
3. **Auto pytest-smoke** when ANY extras OR groups are
   requested: `python -m pytest --version` runs after all
   installs; failure produces a `target_bootstrap_gap` banner.

Plus `_pip_install_groups` helper (~30 lines) and
`_pytest_version_smoke` helper (~25 lines).

## Empirical validation (one-off probes, NOT committed)

```
$ python scripts/clone_target_at_sha.py \
    --repo simonw/sqlite-utils \
    --head-sha e7ecb0ffdfcb15a879e0da202a00966623f1e79c \
    --manual-egress-ok --install-oida-code \
    --install-extras test \
    --import-smoke sqlite_utils

pip install -e oida-code (local) into venv ...
pip install -e simonw/sqlite-utils[test] into venv ...
import-smoke: `import sqlite_utils` OK
pytest-smoke: pytest 9.0.3
```

```
$ python scripts/clone_target_at_sha.py \
    --repo hynek/structlog \
    --head-sha f7e9f78dbd31b967eeaebaf9f2e5f424065cdaf2 \
    --manual-egress-ok --install-oida-code \
    --scm-pretend-version structlog=25.5.0.dev0 \
    --install-group tests \
    --import-smoke structlog

pip install -e oida-code (local) into venv ...
pip install -e hynek/structlog into venv ...
pip install --group tests (PEP 735) into venv ...
import-smoke: `import structlog` OK
pytest-smoke: pytest 9.0.3
```

Both targets now have BOTH the package importable AND pytest
in the venv. The 6.1'h freeze-rule pass can now produce
honest verifier outcomes for the holdouts.

**Wrong-extras-name failure mode** (helpful, not silent):

```
$ python scripts/clone_target_at_sha.py \
    --repo simonw/sqlite-utils \
    ... --install-extras tests ...   # plural — wrong name
target_bootstrap_gap: `python -m pytest --version` FAILED
(rc=1); pytest is not in the venv after the editable
install. Did you forget --install-extras with the right
extras name (e.g. tests / dev / test)? stderr tail:
  No module named pytest
```

## Two parallel flags (vs cgpro's literal "narrow --install-extras")

cgpro's QA/A46 next_action said "a narrow `--install-extras`
corrective". The implementation extends to TWO flags
(`--install-extras` for PEP 621, `--install-group` for PEP
735) because the two existing holdout cases use different
packaging standards:

* sqlite-utils declares `[project.optional-dependencies] test
  = [..., "pytest"]` — PEP 621.
* structlog declares `[dependency-groups] tests = [...,
  "pytest>=6.0"]` — PEP 735.

Without both flags, the freeze-rule pass cannot run on both
holdouts. The implementation is still narrow:

* Each flag is a thin pip-passthrough.
* No auto-detection logic.
* No build-backend speculation.
* No project-wide default extras name.

ADR-61 documents this minor scope expansion as accepted; it is
the SAME class of fix (bring pytest into the venv via the
target's metadata declaration) with two mechanical paths.

## Hermetic test contract (9 tests)

| Test | Asserts |
|---|---|
| `test_pip_install_editable_extras_forwarded` | extras tuple → `[a,b]` syntax in path arg |
| `test_pip_install_editable_no_extras_unchanged` | back-compat: bare path without extras |
| `test_pip_install_groups_per_group_invocation` | `pip install --group <pyproject>:<g>` once per group |
| `test_pytest_version_smoke_happy_path` | rc=0 → pytest version line in stderr |
| `test_pytest_version_smoke_failure_banner` | rc!=0 → SystemExit(2) + `target_bootstrap_gap` |
| `test_main_runs_pytest_smoke_when_extras_provided` | extras → smoke fires once |
| `test_main_runs_pytest_smoke_when_groups_provided` | groups → smoke fires once |
| `test_main_no_pytest_smoke_when_neither_provided` | back-compat: no smoke without flags |
| `test_main_passes_extras_through_to_install` | repeatable `--install-extras X Y` → tuple `("X","Y")` |

All hermetic via `monkeypatch` + `subprocess.run` stub. No
real pip/git/network. Sub-100ms total runtime.

The Phase 6.1'f tests received a small signature-compatibility
update: the 4 stubs of `_pip_install_editable` now accept the
new `extras` kwarg. No semantic change.

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

seed_065 + seed_157 are NOT untainted by 6.1'g — the taint
clears only after a fresh freeze-rule pass at the post-6.1'g
SHA. That is Phase 6.1'h's job.

## Test count

**1119 → 1128 (+9).** All new tests in
`tests/test_phase6_1_g_extras_and_groups.py`. The 4 stub
updates in `tests/test_phase6_1_f_clone_bootstrap.py` are
non-counting (signature compatibility only).

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
  file + tests + reports + memory-bank.

## Lane separation preserved

The four-lane structural separation continues to hold. The
manual data acquisition lane is unchanged at 3 scripts:
`build_calibration_seed_index.py`, `llm_author_replays.py`,
`clone_target_at_sha.py` (this commit's edit target). All
carry the `MANUAL_EGRESS_SCRIPT = True` marker.

## What this block does NOT deliver

* The Phase 6.1'h freeze-rule holdout pass. Next commit.
* AI-tier cold-reader rerun. Per cgpro QA/A46: explicitly OFF
  the table until the bootstrap blocker is fully closed.
* Public benchmark exploration. Same.
* MCP runtime. Same — and project-rule 2 keeps it off the
  critical path indefinitely.

## What's next (Phase 6.1'h)

Per QA/A46 next_action + verdict_q4:

1. Frozen manifest at the post-6.1'g SHA. Code + DeepSeek
   model + LLM prompt + replay shapes + generator + verifier
   ALL frozen.
2. Re-run seed_065 + seed_157 round-trips with the new flags
   (`--install-extras test` for sqlite-utils, `--install-group
   tests` for structlog) + `--import-smoke <package>` +
   auto-pytest-smoke.
3. Outcome categories per QA/A45_followup matrix:
   `verification_candidate` → archive + count; honest pytest
   counterexample → archive as honest negative; new
   `target_bootstrap_gap` → record + investigate further.
4. Per-case archive in `reports/phase6_1_h/round_trip_outputs/`.

If 6.1'h produces ≥1 holdout `verification_candidate`, the
6.1' chain has its first generalisation evidence and the
verdict_q4 prerequisite is met. If 6.1'h produces 0 holdout
verification_candidate again, the chain produces another
honest-fail signal; the next iteration would either replace
the holdouts or escalate to a separate broader investigation.

## Cross-references

* QA/A46 (this block's mandate): `QA/A46.md`
* QA/A45 / QA/A45_followup / QA/A45_step4_outcome:
  `QA/A45.md`, `QA/A45_followup.md`, `QA/A45_step4_outcome.md`
* ADR-58 (Phase 6.1'e steps 1-3): `memory-bank/decisionLog.md`
* ADR-59 (Phase 6.1'e step 4): `memory-bank/decisionLog.md`
* ADR-60 (Phase 6.1'f minimal bootstrap): `memory-bank/decisionLog.md`
* ADR-61 (this block): `memory-bank/decisionLog.md`
* Clone helper: `scripts/clone_target_at_sha.py`
* Tests: `tests/test_phase6_1_g_extras_and_groups.py`

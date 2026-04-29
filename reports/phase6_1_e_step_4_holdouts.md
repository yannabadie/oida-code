# Phase 6.1'e step 4 — holdout round-trips under freeze rule

**Status:** delivered (commit pending).
**Phase block:** 6.1'e step 4 (per QA/A45 follow-up).
**Predecessor:** Phase 6.1'e steps 1-3 (commit `f27e40c`).
**Acceptance criterion:** holdout round-trips run end-to-end
under freeze rule; outcomes archived per-case; freeze rule
strictly enforced (no in-pass tooling edits).

## Freeze manifest (frozen BEFORE running)

Per QA/A45 follow-up cgpro verdict_q2 + step_4_recommendation:

* **Code SHA:** `f27e40c` (oida-code main at the start of pass).
* **Provider:** DeepSeek `deepseek-chat` via the existing
  `scripts/llm_author_replays.py` system prompt — no edits.
* **No in-pass edits** to: `src/oida_code/bundle/`,
  `src/oida_code/verifier/`, `scripts/clone_target_at_sha.py`,
  `scripts/llm_author_replays.py`, the LLM system prompt, the
  pass-replay shapes.
* **`--scm-pretend-version` flags allowed** (predeclared env
  bootstrap from target metadata, not tooling edits per
  cgpro verdict_q1).
* **seed_008 NOT re-run** (train control already established).

## Per-case results

### seed_065_simonw_sqlite_utils_680 — `target_bootstrap_gap`

**Outcome:** `status=diagnostic_only`, `tool_calls=1`,
unsupported claim `C.column_type_mapping.repair_needed`.

**Root cause (observed without in-pass fix):** pytest exited
rc=4. Stdout excerpt:

```
ImportError while loading conftest 'tests/conftest.py'.
tests/conftest.py:1: in <module>
    from sqlite_utils import Database
sqlite_utils\_...
```

The `sqlite_utils` package is not importable from the venv at
the time pytest runs the conftest. The clone helper's
`pip install -e <clone>` reported success; nevertheless the
import fails at test time. The freeze rule prohibits
investigating the cause inside this pass.

**Per cgpro outcome matrix:** `install/bootstrap/pytest-config
adapter failure → record target_bootstrap_gap, make no in-pass
fix, then create a non-holdout regression test and replace the
affected holdout before counting`.

**Counts as holdout evidence:** ❌ (pending replacement
post-pass).

**Evidence archived under:**
`reports/phase6_1_e/round_trip_outputs/seed_065_simonw_sqlite_utils_680/`.

### seed_157_hynek_structlog_761 — `target_bootstrap_gap`

**Outcome:** `status=diagnostic_only`, `tool_calls=1`,
unsupported claim `C.callsite_qual_name.capability_sufficient`.

**Root cause (observed without in-pass fix):** pytest exited
rc=4. Stdout excerpt:

```
ImportError while loading conftest 'tests/conftest.py'.
tests/conftest.py:12: in <module>
    import structlog
E   ModuleNotFoundError: No module named 'structlog'
```

Same shape as seed_065: target package `structlog` not
importable from the venv at pytest time, despite the clone
helper's `pip install -e <clone>` reporting success.

**Per cgpro outcome matrix:** same as seed_065 —
`target_bootstrap_gap`. NO in-pass fix.

**Counts as holdout evidence:** ❌ (pending replacement
post-pass).

**Evidence archived under:**
`reports/phase6_1_e/round_trip_outputs/seed_157_hynek_structlog_761/`.

## Freeze rule compliance check

| Rule | Compliance |
|---|---|
| Code SHA frozen (`f27e40c`) before any inspection | ✅ |
| Generator NOT edited in-pass | ✅ |
| Verifier NOT edited in-pass | ✅ |
| Clone helper NOT edited in-pass | ✅ |
| LLM-author script + prompt NOT edited in-pass | ✅ |
| Pass replay shapes NOT edited in-pass | ✅ |
| `--scm-pretend-version` only on `structlog` (predeclared from target metadata) | ✅ |
| seed_008 NOT re-run | ✅ |
| Outcomes archived per-case in separate sections | ✅ |

## Generalisation signal

Holdout pass result: **0/2 holdouts produced
`verification_candidate`.** Both produced
`target_bootstrap_gap` from the same root cause shape (target
package not importable from clone-venv at pytest time).

This is a meaningful generalisation gap. The seed_008 (train)
run worked because pytest IS the target package — there's no
"target imported from venv" step (the test imports from the
pytest source tree directly via the editable install's
`<src>/...` paths). Both holdouts have a different shape: their
`tests/conftest.py` imports the package (`from sqlite_utils
import Database`, `import structlog`), and that import fails.

The clone helper's bootstrap (`pip install -e <clone>`)
generalises poorly: it succeeds for some targets and silently
fails to make the package importable for others. Possible
causes (NOT investigated in-pass):

* Install order: oida-code is pip-installed AFTER the target;
  installing oida-code may re-resolve dependencies and remove
  the target's editable link.
* Build backend differences: pytest uses setuptools_scm with
  static config; sqlite-utils and structlog use different build
  backends (sqlite-utils uses setuptools, structlog uses hatch).
* Editable install mode flags: `pip install -e` defaults vary
  with the build backend.

## Post-pass corrective work (next commit, NOT this one)

Per cgpro verdict_q1 lenient follow-up path:

1. **Investigate the bootstrap gap** in a separate phase block
   (probably 6.1'e-fix or 6.1'f). Reproduce the failure with
   an explicit non-holdout regression test that does NOT use
   any holdout case_id.
2. **Fix the clone helper / bootstrap** based on the
   investigation. Likely candidates:
   * Install oida-code BEFORE the target (so the target's
     editable install is the last word).
   * Use `pip install --no-build-isolation -e .` for targets
     with non-setuptools backends.
   * Verify importability after install (`python -c "import
     <package>"`) before returning success from the clone
     helper.
3. **Replace seed_065 and seed_157 with new holdout candidates**
   from the existing 46 inclusions. Both demoted to
   non-counted-as-holdout. Pin two fresh holdout cases AFTER
   the bootstrap fix is verified on a non-holdout case.
4. **Re-run** the new holdouts under a fresh freeze rule pass.

## What this block does NOT deliver

* No `verification_candidate` outcome on a holdout. The seed_008
  train control is the only `verification_candidate` so far.
* No fix for the bootstrap gap. Freeze rule prohibits in-pass
  fix.
* No multi-provider replay panel. Optional step 5; deferred.
* No AI-tier cold-reader re-run on the corpus. Operator's call.

## Honest summary

Phase 6.1'e step 4 surfaces a real generalisation gap: the
end-to-end pipeline that produced `verification_candidate` on
seed_008 (train) does NOT produce `verification_candidate` on
seed_065 or seed_157 (holdout). The honest classification is
NOT a verifier failure — pytest is correctly invoked and
correctly reports the import error. The gap is in the clone
helper's bootstrap: `pip install -e <clone>` does not
guarantee the target package is importable from the venv at
pytest time.

This is exactly what the holdout discipline is for. The
generator and verifier were unchanged between seed_008 and the
holdouts; the divergent outcome reveals that the broader
pipeline (specifically the clone helper) overfits to
pytest-shaped targets. This is a fixable gap, but the freeze
rule deliberately prevents fixing it during the holdout pass —
that fix belongs to a separate evaluation cycle with a
non-holdout regression test.

## Cross-references

* QA/A45 follow-up (this pass): `QA/A45_followup.md`
* QA/A45 (initial pass): `QA/A45.md`
* ADR-58 (Phase 6.1'e steps 1-3):
  `memory-bank/decisionLog.md`
* Phase 6.1'e steps 1-3 report: `reports/phase6_1_e_steps_1_3.md`
* Round-trip evidence (seed_008 — train control):
  `reports/phase6_1_e/round_trip_outputs/seed_008_pytest_dev_pytest_14407/`
* Round-trip evidence (seed_065 — `target_bootstrap_gap`):
  `reports/phase6_1_e/round_trip_outputs/seed_065_simonw_sqlite_utils_680/`
* Round-trip evidence (seed_157 — `target_bootstrap_gap`):
  `reports/phase6_1_e/round_trip_outputs/seed_157_hynek_structlog_761/`
* Clone helper: `scripts/clone_target_at_sha.py`
* LLM-author script: `scripts/llm_author_replays.py`

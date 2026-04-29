# QA/A45 — Phase 6.1'e step 4 outcome verdict (cgpro phase61-review, second resume)

**Date:** 2026-04-29.
**Cycle reviewed:** Phase 6.1'e step 4 (commit `97f27cc`).
**cgpro session:** `phase61-review` (resumed second time;
conversation `69f1bde2-70c0-8387-9c89-743f8780cb14`).

## What was asked

Three follow-up questions after step 4 surfaced
`target_bootstrap_gap` for both holdouts (0/2
verification_candidate):

1. Methodological status of the 6.1' chain — win, loss, mixed?
2. Which next-step option — 6.1'f-fix vs AI-tier rerun vs pause?
3. If 6.1'f-fix: minimal vs broader scope?

## cgpro verdict (verbatim, JSON)

```json
{
  "verdict_q1": "mixed_with_explicit_qualifier; the 6.1' chain is a methodological win on process integrity and a methodological no-claim on generalisation: the runtime-loader guard, enforced N=5 ratio, frozen holdout pass, and no in-pass edits worked exactly as intended, and ADR-59 explicitly records that 0/2 holdouts exposed target_bootstrap_gap rather than being counted as success. But the empirical result is still 1 train verification_candidate, 0 successful holdouts, so the only honest qualifier is: the discipline is validated; the verification_candidate path is not yet broadly viable.",
  "verdict_q2": "pursue_6_1_f_fix; fix the known bootstrap gap before spending provider budget on AI-tier cold readers, because the current dominant failure is already localized upstream of verifier semantics: target package importability after clone+editable install. Pip documents editable installs as adding the development directory to Python's import path, while also warning that editable-vs-regular behavior can differ by build backend, so an explicit post-install import smoke is the right corrective guard.",
  "verdict_q3": "minimal_first_then_broader_in_separate_block; do the smallest falsifiable corrective first: install oida-code before the target, install the target last, and add a mandatory post-install importability smoke for the target package. Do not add build-backend flag plumbing, pip-upgrade policy, or forensic-archive expansion in the same block; those are useful but would blur whether the minimal bootstrap hypothesis fixed the observed class.",
  "next_action": "Next commit: Phase 6.1'f bootstrap-corrective block. Scope: edit scripts/clone_target_at_sha.py only to (1) install local oida-code first when --install-oida-code is set, (2) install the cloned target editable second, and (3) add an explicit repeatable --import-smoke PACKAGE check that runs the clone venv's Python as python -c \"import PACKAGE\" after all installs; fail fast with a clear target_bootstrap_gap message if any smoke import fails. Add tests/test_phase6_1_f_clone_bootstrap.py with hermetic subprocess/monkeypatch tests for install order, import-smoke command construction, refusal/failure reporting, and preservation of MANUAL_EGRESS_SCRIPT workflow non-reference. Update memory-bank/decisionLog.md, memory-bank/progress.md, and add reports/phase6_1_f_bootstrap_corrective.md. Do not count seed_065 or seed_157; mark them as tainted-by-bootstrap-gap or demote/replace per the existing protocol. After the fix and tests pass, choose fresh holdout replacements from the existing 46 inclusions, predeclare --import-smoke sqlite_utils or --import-smoke structlog as applicable for any future target, then run a new freeze-rule pass at the post-fix SHA. Seed_008 does not need to be rerun in the corrective commit; rerun it only as an optional regression control after the minimal fix is green, not as holdout evidence."
}
```

(`--web` mode citation tokens stripped from the parsed verdict.)

## What this means for Phase 6.1'f

**Honest framing per verdict_q1:** the discipline is validated;
the `verification_candidate` path is not yet broadly viable.
Phase 6.1'f's job is to lift the dominant failure mode (target
package importability) so a future evaluation pass can produce
real holdout-generalisation signal.

### Phase 6.1'f scope (minimal, per verdict_q3)

Edit `scripts/clone_target_at_sha.py` only — three changes:

1. **Install order flip:** when `--install-oida-code` is set,
   install the local oida-code package FIRST. Then install the
   cloned target editable SECOND. The hypothesis: installing
   oida-code after the target may have re-resolved dependencies
   and removed the target's editable link.
2. **`--import-smoke PACKAGE` flag (repeatable):** after all
   installs complete, run `<venv>/python -c "import PACKAGE"`
   for each smoke value. Fail fast with a clear
   `target_bootstrap_gap` message naming the failing package +
   the install order used.
3. **Documentation update inline:** the script's docstring
   notes the install-order rationale and the smoke-check
   contract.

### Out-of-scope for Phase 6.1'f (deferred per verdict_q3)

* Build-backend-specific flag plumbing (hatch-vcs / poetry-core
  config-settings).
* `pip install --upgrade pip` policy.
* Forensic-archive expansion of failed bootstraps.
* AI-tier cold-reader rerun.

These belong to a follow-up block IF Phase 6.1'f's minimal fix
does NOT close the gap.

### Tests for Phase 6.1'f

`tests/test_phase6_1_f_clone_bootstrap.py` with hermetic
subprocess/monkeypatch tests:

* Install order — `_pip_install_editable` for oida-code
  precedes the target call.
* Import-smoke command construction — `python -c "import X"`
  invoked once per `--import-smoke X` entry.
* Refusal / failure reporting — clear `target_bootstrap_gap`
  message includes the failing package + install order.
* MANUAL_EGRESS_SCRIPT workflow non-reference — the existing
  dynamic-discovery test continues to pass.

### Holdout discipline at end of 6.1'f

Per next_action: seed_065 + seed_157 are NOT counted as holdout
evidence. They are marked `tainted-by-bootstrap-gap` (or
demoted to `partition: train`, then replaced with fresh holdout
candidates from the 46 inclusions). The replacement + re-run
pass happens in a SEPARATE commit at the post-6.1'f SHA, NOT in
6.1'f itself. seed_008 stays as the train control, NOT re-run
in 6.1'f.

## Cross-references

* QA/A45 (initial pass): `QA/A45.md`
* QA/A45_followup (step 4 strategy): `QA/A45_followup.md`
* ADR-58 (Phase 6.1'e steps 1-3): `memory-bank/decisionLog.md`
* ADR-59 (Phase 6.1'e step 4): `memory-bank/decisionLog.md`
* Phase 6.1'e step 4 report: `reports/phase6_1_e_step_4_holdouts.md`
* Round-trip evidence (target_bootstrap_gap):
  `reports/phase6_1_e/round_trip_outputs/seed_065_*` and
  `reports/phase6_1_e/round_trip_outputs/seed_157_*`.
* Clone helper: `scripts/clone_target_at_sha.py` (the file to
  edit in 6.1'f).

# QA/A45 follow-up — Phase 6.1'e step 4 strategy (holdouts under freeze rule)

**Date:** 2026-04-29.
**Cycle reviewed:** Phase 6.1'e steps 1-3 (commit `f27e40c`).
**Test count:** 1102 → 1111 (+9).
**cgpro session:** `phase61-review` (resumed; conversation
`69f1bde2-70c0-8387-9c89-743f8780cb14`).

## What was asked

Three follow-up questions after the user said "demande à cgpro"
on the next-step decision (single-pass vs multi-pass, freeze-rule
edge cases, scope creep on the verifier-runtime fix).

## cgpro verdict (verbatim, JSON)

```json
{
  "verdict_q1": "mixed_with_explicit_test; follow strict freeze inside Step 4, but allow a lenient follow-up path only after the pass is sealed: a target-class-general verifier or adapter fix is acceptable only if reproduced by an explicit non-holdout regression test, recorded as an adapter/bootstrap gap, and the affected holdout is demoted or replaced before it is counted as holdout evidence. Predeclared environment bootstrap flags derived from target metadata are not tooling edits; code, prompt, generator, verifier, or replay-shape edits learned from a holdout failure are forbidden in-pass.",
  "verdict_q2": "both_in_parallel_with_doc_split; run seed_065 and seed_157 as one fixed-code evaluation batch at the same oida-code SHA, with commands and provider settings frozen before inspecting either verifier result, but archive and report them in separate per-case sections. This gives the clean single-pass discipline you want while preventing a seed_065 diagnosis from changing the seed_157 procedure; the ratio guard is now enforcing at 2/5 = 0.40 and ADR-58 already isolates Step 4 as the clean holdout pass.",
  "verdict_q3": "scope_creep_acknowledge_but_keep; the pytest adapter change is scope creep in the narrow sense because it touches the established verifier runtime path, but no split phase is required because it was discovered on the train case, is target-class-general, stdlib-only, defensively parsed, and ADR-58 already records it as an ADR-49 sub-decision preserving addopts neutralization rather than changing the verifier contract. Keep it under Phase 6.1'e, but label it explicitly as adapter hardening / ADR-49.x in the Step 4 report.",
  "step_4_recommendation": "Create one freeze manifest before running anything: code SHA f27e40c, exact commands, one DeepSeek replay-author call per case, no prompt edits, no hand-edited replays, no generator/verifier/clone-helper edits. Run seed_065 with --repo simonw/sqlite-utils --head-sha e7ecb0ffdfcb15a879e0da202a00966623f1e79c --manual-egress-ok --install-oida-code and no --scm-pretend-version, because sqlite-utils declares static version 4.0a0. Run seed_157 with --repo hynek/structlog --head-sha f7e9f78dbd31b967eeaebaf9f2e5f424065cdaf2 --manual-egress-ok --install-oida-code --scm-pretend-version structlog=25.5.0.dev0, because structlog uses hatch-vcs dynamic versioning and this PR is in the unreleased-after-25.4.0 section. Do not re-run seed_008 inside this holdout pass; it is already the train control. Outcome handling: verification_candidate means archive and count; diagnostic_only from test-not-found means record a seed/test_scope defect and demote/replace after the pass; install/bootstrap/pytest-config/adapter failures mean record target_bootstrap_gap or tool_adapter_gap, make no in-pass fix, then create a non-holdout regression test and replace the affected holdout before counting; claim-level pytest failure or counterexample means archive as the holdout result, not as a tooling failure."
}
```

(Note: the cgpro response also included web-citation tokens
("GitHub", "+1", "+4") at the ends of each verdict — those are
`--web` mode artifacts and have no semantic content. Stripped from
the parsed verdict above.)

## What this means for Phase 6.1'e step 4

### Freeze manifest (frozen BEFORE running anything)

Per cgpro verdict_q2 (single-batch + per-case archive) +
step_4_recommendation:

* **Code SHA frozen:** `f27e40c` (oida-code main at the start of
  the pass).
* **Provider:** DeepSeek `deepseek-chat` via
  `scripts/llm_author_replays.py` with the existing system
  prompt (no edits).
* **No edits in-pass:** generator (`src/oida_code/bundle/`),
  verifier (`src/oida_code/verifier/`), clone helper
  (`scripts/clone_target_at_sha.py`), LLM-author script
  (`scripts/llm_author_replays.py`), prompts, replay shapes —
  NONE may be modified during the pass.
* **`--scm-pretend-version` flags are environment bootstrap, not
  tooling edits** (per verdict_q1 explicit clarification). They
  are predeclared from target metadata, hence allowed.
* **seed_008 is NOT re-run in this pass.** It is the train
  control, already established.

### Outcome handling matrix

| Outcome | Treatment | Counts as holdout evidence? |
|---|---|---|
| `verification_candidate` | archive + count | ✅ |
| `diagnostic_only` from test-not-found | record seed/test_scope defect; demote/replace AFTER pass | ❌ (until replaced) |
| install/bootstrap/pytest-config/adapter failure | record `target_bootstrap_gap` or `tool_adapter_gap`; NO in-pass fix; create non-holdout regression test AFTER pass; replace affected holdout BEFORE it counts | ❌ |
| claim-level pytest failure / counterexample | archive as the holdout result (NOT as tooling failure) | ✅ (negative result is still a holdout outcome) |

### Frozen commands

```bash
# seed_065 — sqlite-utils REAL/FLOAT migration
python scripts/clone_target_at_sha.py \
    --repo simonw/sqlite-utils \
    --head-sha e7ecb0ffdfcb15a879e0da202a00966623f1e79c \
    --manual-egress-ok \
    --install-oida-code
# (no --scm-pretend-version: sqlite-utils declares static version
# 4.0a0, the shallow clone has it directly)

# seed_157 — structlog QUAL_NAME callsite param
python scripts/clone_target_at_sha.py \
    --repo hynek/structlog \
    --head-sha f7e9f78dbd31b967eeaebaf9f2e5f424065cdaf2 \
    --manual-egress-ok \
    --install-oida-code \
    --scm-pretend-version structlog=25.5.0.dev0
# (structlog uses hatch-vcs dynamic versioning; this PR is in the
# unreleased-after-25.4.0 section)
```

For each case:

```bash
python -m oida_code.cli prepare-gateway-bundle \
    --case-id <case_id> \
    --out .tmp/round_trip_e_step4

DEEPSEEK_API_KEY=$(grep '^DEEPSEEK_API_KEY=' .env | cut -d= -f2- | tr -d '"' | tr -d "'") \
    python scripts/llm_author_replays.py \
        --case-id <case_id> \
        --bundle-dir .tmp/round_trip_e_step4/<case_id> \
        --manual-egress-ok

# verify-grounded with the clone venv on PATH (so its pytest@head_sha is used)
PATH="$(cygpath -w <clone>/.venv/Scripts);$PATH" \
    <clone>/.venv/Scripts/python.exe -m oida_code.cli verify-grounded \
        <bundle>/packet.json \
        --forward-replay-1 <bundle>/pass1_forward.json \
        --backward-replay-1 <bundle>/pass1_backward.json \
        --forward-replay-2 <bundle>/pass2_forward.json \
        --backward-replay-2 <bundle>/pass2_backward.json \
        --tool-policy <bundle>/tool_policy.json \
        --approved-tools <bundle>/approved_tools.json \
        --gateway-definitions <bundle>/gateway_definitions.json \
        --audit-log-dir .tmp/round_trip_e_step4/<case_id>_audit \
        --out .tmp/round_trip_e_step4/<case_id>_report.json \
        --repo-root <clone>
```

Per cgpro verdict_q3, the pytest-adapter `-p plugin` preservation
fix that landed in step 3 stays under "Phase 6.1'e adapter
hardening / ADR-49.x" — labeled explicitly in the step 4 report.

## Cross-references

* QA/A45 (initial pass): `QA/A45.md`
* ADR-58 (Phase 6.1'e steps 1-3): `memory-bank/decisionLog.md`
* Phase 6.1'e steps 1-3 report: `reports/phase6_1_e_steps_1_3.md`
* Round-trip evidence (seed_008):
  `reports/phase6_1_e/round_trip_outputs/seed_008_pytest_dev_pytest_14407/`
* Step 4 round-trip evidence (this commit's target):
  `reports/phase6_1_e/round_trip_outputs/seed_065_*` and
  `reports/phase6_1_e/round_trip_outputs/seed_157_*`.

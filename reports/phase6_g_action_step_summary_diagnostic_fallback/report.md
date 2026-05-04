# Phase 6.g GitHub Action Step Summary diagnostic fallback quarantine

Date: 2026-05-04

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

Phase 6.g rewrites the runtime fallback path that the reusable
GitHub Action writes into `$GITHUB_STEP_SUMMARY` when the polished
diagnostic Markdown (`$DIAGNOSTIC_MD`) is not produced.

The fallback now:

- Uses an explicitly diagnostic header (`## OIDA-code diagnostic
  evidence`) instead of the legacy verdict-flavored title (`## OIDA-code
  audit`).
- Emits a non-claim disclaimer (`Diagnostic only — not a merge decision
  or production-readiness assessment.`) before the audit report
  excerpt.
- Drops the internal-comment phrase `legacy audit report excerpt`.

The change is metadata/text-only on a runtime fallback path. It does
not alter action inputs, defaults, outputs, `runs` shape, shell
commands, SARIF behavior, gateway behavior, provider behavior,
workflows, or source code. It does not change the audit excerpt itself
(`head -n 80 "$OUTPUT_DIR/report.md"`) — that excerpt continues to come
from `audit --format markdown`, which Phase 6.e (ADR-77) already
quarantined.

## What changed

- `action.yml` lines around the Phase 4.9-B step-summary fallback now
  reference Phase 6.g and ADR-79 in their leading comment.
- The fallback header changes from `## OIDA-code audit` to
  `## OIDA-code diagnostic evidence`.
- A new `echo` line publishes the non-claim disclaimer before the
  audit excerpt.
- The internal-comment phrase `legacy audit report excerpt` is removed.
- Tests in `tests/test_phase6_g_action_step_summary_diagnostic_fallback.py`
  pin: the new title, the non-claim line, the absence of the legacy
  title and the legacy comment phrase, the preserved Calibration
  metrics block, the preserved composite step list, the preserved CLI
  command set, the preserved action outputs, the preserved safe
  defaults, and the absence of public product-verdict phrases.

## Non-changes

- No `runs` shape change.
- No action input name, default, or output name change.
- No workflow change.
- No `src/oida_code/**` change.
- No corpus index, partition, pin, schema, or clone-helper change.
- No provider call.
- No MCP runtime change.
- No gateway default change.
- No JSON or SARIF schema migration.
- No SARIF upload behavior change.
- No new CLI alias.
- No `audit --format markdown` rendering change beyond what Phase 6.e
  already shipped.

## Why this block was chosen

cgpro `autonomous-protocol-20260430` (run 2026-05-04) selected this
block over G-6d resume (methodologically blocked: ADR-76 requires
exactly four clean candidates, only two survive) and over G-6c step 1
(blocked: independent human review is not available in the autonomous
loop). Phase 6.g closes the remaining easy front-door verdict-leak
surface the Phase 6.e/6.f pair did not yet cover: the GitHub Action
runtime fallback that runs whenever `render-artifacts` cannot produce
`$DIAGNOSTIC_MD`.

## References

- GitHub Actions docs: workflow commands write to
  `$GITHUB_STEP_SUMMARY` and the result is rendered as Markdown on
  the run's summary page.
- ADR-77 (Phase 6.e) quarantined the same verdict language inside the
  CLI Markdown front door.
- ADR-78 (Phase 6.f) quarantined the same verdict language inside the
  reusable Action's public metadata (`description`, `branding`).
- ADR-79 (this block) quarantines the same verdict language inside the
  Action's runtime Step Summary fallback.

## Verification

- `python -m json.tool reports\phase6_g_action_step_summary_diagnostic_fallback\report.json > $null`
- `python -m pytest tests/test_phase6_g_action_step_summary_diagnostic_fallback.py -q`
- `python -m pytest tests/test_phase6_g_action_step_summary_diagnostic_fallback.py tests/test_phase6_f_action_metadata_diagnostic_quarantine.py tests/test_phase6_e_front_door_diagnostic_cli.py tests/test_product_strategy_reset.py tests/test_reports.py tests/test_self_audit_guard.py -q`
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py src\oida_code .github\workflows`
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m pytest -q`
- `git diff --check`

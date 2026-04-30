# Phase 6.f GitHub Action metadata diagnostic quarantine

Date: 2026-04-30

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

Phase 6.f updates the reusable `action.yml` public metadata so the GitHub
Action front door matches ADR-77 and the active diagnostic-only product
strategy.

The change is metadata-only. It does not alter action inputs, defaults,
outputs, `runs`, shell commands, SARIF behavior, provider behavior, gateway
behavior, workflows, or source code.

## What changed

- `action.yml` no longer starts with `AI code verifier`.
- The public action description no longer says the tool measures what code
  "actually guarantees".
- The description now says the action produces diagnostic evidence for
  AI-authored Python diffs.
- The description explicitly says it is not a merge or production-readiness
  decision.
- Tests pin the diagnostic wording and the safe defaults:
  `enable-tool-gateway=false`, `upload-sarif=false`, `fail-on=none`,
  `llm-provider=replay`, and `gateway-fail-on-contract=false`.

## Non-changes

- No `runs` change.
- No action input name, default, or output name change.
- No workflow change.
- No `src/oida_code/**` change.
- No corpus index or clone-helper change.
- No provider call.
- No MCP runtime.
- No gateway default change.
- No JSON or SARIF schema migration.

## References

- GitHub action metadata docs: `action.yml` defines name, description, inputs,
  outputs, and runs configuration.
- GitHub secure-use docs: least-privilege and script-injection guidance remain
  relevant; this block preserves the existing env-var indirection and safe
  defaults.
- arXiv 2512.11602: GitHub Actions job permissions are a real supply-chain
  risk surface, so the action should avoid overstating what its diagnostics
  prove.

## Verification

- `python -m json.tool reports\phase6_f_action_metadata_diagnostic_quarantine\report.json > $null`
- `python -m pytest tests/test_phase6_f_action_metadata_diagnostic_quarantine.py -q`
- `python -m pytest tests/test_phase6_f_action_metadata_diagnostic_quarantine.py tests/test_phase6_e_front_door_diagnostic_cli.py tests/test_product_strategy_reset.py tests/test_reports.py tests/test_self_audit_guard.py -q`
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py src\oida_code .github\workflows`
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m pytest -q`
- `git diff --check`

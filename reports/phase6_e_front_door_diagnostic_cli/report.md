# Phase 6.e front-door diagnostic CLI UX

Date: 2026-04-30

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

Phase 6.e modifies the existing `audit --format markdown` renderer in place.
No new `review` or `diagnose` alias is added.

The reason is simple: `audit --format markdown` is already the front-door
human path. Adding a new alias while leaving legacy verdict language in the
existing renderer would preserve the unsafe surface.

## What changed

- Markdown output title changes to `# OIDA Code Diagnostic Report`.
- The old `**Verdict:**` row is removed.
- Legacy internal JSON verdict values are mapped to diagnostic reviewer text.
- Official fusion fields are shown only as blocked in human Markdown.
- `## Repair plan` becomes `## Human follow-up checklist`.
- Top-level CLI help now says the tool provides diagnostic evidence for Python
  reviewers, not a merge or production-readiness decision.
- `audit --help` explains that Markdown is diagnostic-only and JSON preserves
  the legacy schema.
- `repair --help` remains visible but is explicitly a compatibility stub, not
  a front-door path and not a code-modification tool.

## Mapping

| Legacy JSON value | Human Markdown text |
|---|---|
| `verified` | No contradiction observed by configured deterministic checks (diagnostic only; not proof of correctness) |
| `counterexample_found` | Contradicted by deterministic evidence (human review required) |
| `insufficient_evidence` | Evidence gap remains (human review required) |
| `corrupt_success` | Success evidence conflicts with critical findings (human review required) |

The JSON and SARIF schemas are unchanged. This is a human-output quarantine,
not a schema migration.

## Non-changes

- No new CLI alias.
- No JSON schema migration.
- No SARIF schema migration.
- No `resolve_verdict` or `fail-on` behavior change.
- No direct provider call.
- No corpus/index/partition change.
- No clone-helper dependency-policy change.
- No MCP/runtime/provider/gateway default change.
- No GitHub Action default change.

## Verification

- `python -m json.tool reports\phase6_e_front_door_diagnostic_cli\report.json > $null`
- `python -m pytest tests/test_phase6_e_front_door_diagnostic_cli.py tests/test_reports.py tests/test_cli_audit.py tests/test_cli_smoke.py tests/test_cli_help_windows_encoding.py -q`
- `python -m pytest tests/test_phase4_9_diagnostic_report.py tests/test_product_strategy_reset.py tests/test_reports.py tests/test_self_audit_guard.py -q`
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py action.yml src\oida_code\verifier src\oida_code\provider src\oida_code\tool_gateway`
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m pytest -q`
- `git diff --check`

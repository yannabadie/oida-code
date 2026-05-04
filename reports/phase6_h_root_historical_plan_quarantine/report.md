# Phase 6.h root historical PLAN.md diagnostic quarantine

Date: 2026-05-04

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

Phase 6.h historicizes `PLAN.md` so the root-level merged blueprint +
roadmap document can no longer be quoted as a current product claim
surface. The block adds an explicit archival banner, per-section
historical markers, an ADR-22 hard-wall reminder after the JSON report
contract snippet, and reframes the §6 verdict-taxonomy table so the
legacy "Proved enough to merge" phrasing for the `verified` token no
longer reads as an active product label.

The change is documentation-only on the root historical plan. It does
not alter `src/oida_code/**`, `action.yml`, `.github/workflows/**`,
`scripts/clone_target_at_sha.py`, the calibration-seed corpus index,
the partition pins, the gateway defaults, the provider runtime, the
MCP runtime, the JSON/SARIF schemas, or the CLI behavior. It also
does not delete historical content; the OIDA scoring formulas, the
verdict-token vocabulary, the GitHub-App / SaaS / repair-planner
references, and the eight-phase roadmap remain in place so the
project's evolution stays auditable.

## What changed

- `PLAN.md` gets a strong "ARCHIVAL — READ THIS FIRST" banner near
  the top that names ADR-80 + Phase 6.h, blocks `total_v_net`,
  `debt_final`, `corrupt_success`, `corrupt_success_ratio`,
  `verdict`, `V_net`, and `Debt` as non-public outputs blocked by
  ADR-22 / ADR-24 / ADR-25 / ADR-26, and explicitly tells readers not
  to quote sentences from this file as current product claims.
- `## 3. Pipeline architecture`, `## 6. Verdict taxonomy`,
  `## 7. OIDA scoring core`, `## 11. CLI contract`,
  `## 12. Report contract`, `## 14. Phased roadmap`,
  `## 15. Honesty rules`, and `## 16. Wedge` each get a leading
  block-quote that marks the section as the 2026-04-24 historical
  snapshot and points to the active surface that supersedes it.
- The §6 verdict-taxonomy human-prose table is reframed so the
  legacy `verified` token is shown as `obsolete: "Proved enough to
  merge" — pre-ADR-74 wording, no longer used`, and a new column
  shows the active 2026-05-04 reviewer text per ADR-77 / Phase 6.e.
- The §12 report contract gets a "Hard-wall reminder
  (post-ADR-22 / ADR-24 / ADR-25 / ADR-26)" block after the JSON
  snippet that explicitly states the official fusion fields are not
  emitted, the schemas pin them with `Literal[False]`, and the
  active diagnostic-only `AuditReport` schema lives in
  `src/oida_code/models/audit_report.py`.
- Tests in `tests/test_phase6_h_root_historical_plan_quarantine.py`
  pin: archival banner + Phase 6.h + ADR-80 references, blocked-field
  enumeration in the banner, "Proved enough to merge" only in
  obsolete context, per-section historical markers,
  pipeline-section historical marker, hard-wall reminder, the
  preserved active-authority pointers, and the absence of
  unframed active product-verdict claims.

## Non-changes

- No `src/oida_code/**` change.
- No `action.yml` change.
- No `.github/workflows/**` change.
- No `scripts/clone_target_at_sha.py` change.
- No `reports/calibration_seed/index.json`, partition, or pin change.
- No JSON or SARIF schema migration.
- No CLI behavior change.
- No provider call.
- No PAT_GITHUB use.
- No MCP runtime change.
- No gateway default change.
- No new CLI alias.
- No deletion of historical PLAN.md content; the OIDA scoring
  formulas, verdict-token vocabulary, GitHub-App / SaaS / repair-
  planner references, and the eight-phase roadmap all remain visible
  so the project's evolution stays auditable.

## Why this block was chosen

cgpro `autonomous-protocol-20260430` (run 2026-05-04, post-Phase-6.g)
selected this block over G-6d resume (still methodologically blocked:
ADR-76 requires four clean candidates, only two survive), over G-6c
step 1 (still blocked: independent human review is not available in
the autonomous loop), and over a broad G-4 audit cleanup (out of
scope for a single autonomous cycle). PLAN.md is a root-level file
with high visibility — closer to a public front door than the older
reports / ADR log — and it still contained the most dangerous active
phrasing the Phase 6.e/6.f/6.g triple did not yet cover (notably the
`verified = "Proved enough to merge"` row in the §6 verdict-taxonomy
table, the §12 report-contract JSON snippet showing official fusion
fields, and the §14 roadmap "useful verdict inside a PR" exit
criterion).

## References

- ADR-77 (Phase 6.e) quarantined the same verdict language inside the
  CLI Markdown front door.
- ADR-78 (Phase 6.f) quarantined the same verdict language inside the
  reusable Action's public metadata.
- ADR-79 (Phase 6.g) quarantined the same verdict language inside the
  Action's runtime Step Summary fallback.
- ADR-80 (this block) quarantines the same verdict language inside the
  root historical `PLAN.md` document.

## Verification

- `python -m json.tool reports\phase6_h_root_historical_plan_quarantine\report.json > $null`
- `python -m pytest tests/test_phase6_h_root_historical_plan_quarantine.py -q`
- `python -m pytest tests/test_phase6_h_root_historical_plan_quarantine.py tests/test_phase6_g_action_step_summary_diagnostic_fallback.py tests/test_phase6_f_action_metadata_diagnostic_quarantine.py tests/test_phase6_e_front_door_diagnostic_cli.py tests/test_product_strategy_reset.py tests/test_reports.py tests/test_self_audit_guard.py -q`
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py src\oida_code action.yml .github\workflows`
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m pytest -q`
- `git diff --check`

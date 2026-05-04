# Phase 6.i root MVP blueprint diagnostic quarantine

Date: 2026-05-04

cgpro thread: `autonomous-protocol-20260430`

cgpro conversation: `69f3ba6f-60f0-838b-8028-a8af734b2d72`

## Decision

Phase 6.i historicizes `oida-code-mvp-blueprint.md` so the root-level
2026-04-23 MVP blueprint can no longer be quoted as a current product
spec. The block adds an explicit archival banner, per-section
historical markers, an ADR-22 hard-wall reminder after the §9 JSON
report-contract snippet, and inline obsolete tags on the most
dangerous active phrasing (notably "AI code verifier", "actually
guarantees", "Final verdict buckets", "proved enough for merge",
"repair planner", "GitHub App later", and "forward/backward verdict
merge").

The change is documentation-only on the root historical blueprint.
It does not alter `src/oida_code/**`, `action.yml`,
`.github/workflows/**`, `scripts/clone_target_at_sha.py`, the
calibration-seed corpus index, the partition pins, the gateway
defaults, the provider runtime, the MCP runtime, the JSON/SARIF
schemas, or the CLI behavior. It also does not delete historical
content; the OIDA scoring vocabulary (`v_net`, `debt`, `grounding`,
`double_loop_repair`, `Q_obs`), the four-bucket verdict labels, the
GitHub-App / SaaS / repair-planner trajectory, the 10-day
implementation plan, and the wedge framing all remain visible so the
project's evolution stays auditable.

## What changed

- `oida-code-mvp-blueprint.md` gets a strong "ARCHIVAL — READ THIS
  FIRST" banner near the top that names ADR-81 + Phase 6.i, blocks
  `total_v_net`, `debt_final`, `corrupt_success`,
  `corrupt_success_ratio`, `verdict`, `V_net`, and `Debt` as
  non-public outputs blocked by ADR-22 / ADR-24 / ADR-25 / ADR-26 +
  `Literal[False]`, and explicitly tells readers not to quote
  sentences from this file as current product claims.
- Eight section headers each get a leading historical block-quote:
  `## 1. Positioning`, `### Pass 3 — Agentic verification`,
  `### Deployment modes`, `## 9. Report contract`,
  `## 10. LLM choice for the MVP`,
  `## 11. First 10 implementation days`,
  `## 12. Hard rules for honesty`, and `## 13. Best wedge`.
- The dangerous phrases — `AI code verifier`, `actually guarantees`,
  `Final verdict buckets`, `proved enough for merge`, `repair
  planner`, `GitHub App later`, `verdict merge` — each get an inline
  `*(historical 2026-04-23 — obsolete; …)*` tag right next to the
  phrase, reinforcing the section-level historical marker.
- A "Hard-wall reminder
  (post-ADR-22 / ADR-24 / ADR-25 / ADR-26)" block follows the §9
  JSON snippet and explicitly states the official fusion fields are
  not emitted, the schemas pin them with `Literal[False]`, and the
  active diagnostic-only `AuditReport` schema lives in
  `src/oida_code/models/audit_report.py`.
- Tests in `tests/test_phase6_i_root_mvp_blueprint_quarantine.py`
  pin: archival banner + Phase 6.i + ADR-81 references, blocked-field
  enumeration in the banner, every dangerous phrase only in
  historical context (within a 30-line window), per-section
  historical markers, hard-wall reminder, the absence of unframed
  active product-verdict claims, and the preservation of the
  historical OIDA vocabulary tokens.

## Non-changes

- No `src/oida_code/**` change.
- No `action.yml` change.
- No `.github/workflows/**` change.
- No `scripts/clone_target_at_sha.py` change.
- No `reports/calibration_seed/index.json`, partition, or pin change.
- No `PLAN.md` change.
- No JSON or SARIF schema migration.
- No CLI behavior change.
- No provider call.
- No PAT_GITHUB use.
- No MCP runtime change.
- No gateway default change.
- No new CLI alias.
- No deletion of historical blueprint content; the OIDA scoring
  vocabulary, four-bucket verdict labels, GitHub-App / SaaS /
  repair-planner trajectory, 10-day implementation plan, and wedge
  framing all remain visible.

## Why this block was chosen

cgpro `autonomous-protocol-20260430` (run 2026-05-04, post-Phase-6.h
6/6 CI green on `8111de9`) selected this surface over README
historicization (already partially aligned by ADR-74/77/78), over
`docs/concepts/` quarantine (the plain-language doc is already
explicitly diagnostic-only), over G-6d resume (still
methodologically blocked: ADR-76 requires four clean candidates,
only two survive), over G-6c step 1 (still blocked: independent
human review is not available in the autonomous loop), and over a
broad G-4 audit cleanup (out of scope for one autonomous cycle).
The blueprint is a small root-level file densely concentrated in
dangerous phrasing — the highest-yield remaining quarantine target
after the Phase 6.e/6.f/6.g/6.h quadruple closed the runtime
front-door surfaces.

## References

- ADR-77 (Phase 6.e) quarantined the same verdict language inside the
  CLI Markdown front door.
- ADR-78 (Phase 6.f) quarantined the same verdict language inside the
  reusable Action's public metadata.
- ADR-79 (Phase 6.g) quarantined the same verdict language inside the
  Action's runtime Step Summary fallback.
- ADR-80 (Phase 6.h) quarantined the same verdict language inside the
  root historical `PLAN.md` document.
- ADR-81 (this block) quarantines the same verdict language inside
  the root historical `oida-code-mvp-blueprint.md` document.

## Verification

- `python -m json.tool reports\phase6_i_root_mvp_blueprint_quarantine\report.json > $null`
- `python -m pytest tests/test_phase6_i_root_mvp_blueprint_quarantine.py -q`
- `python -m pytest tests/test_phase6_i_root_mvp_blueprint_quarantine.py tests/test_phase6_h_root_historical_plan_quarantine.py tests/test_phase6_g_action_step_summary_diagnostic_fallback.py tests/test_phase6_f_action_metadata_diagnostic_quarantine.py tests/test_phase6_e_front_door_diagnostic_cli.py tests/test_product_strategy_reset.py tests/test_reports.py tests/test_self_audit_guard.py -q`
- `git diff --exit-code -- reports\calibration_seed\index.json scripts\clone_target_at_sha.py src\oida_code action.yml .github\workflows PLAN.md`
- `python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py`
- `python -m pytest -q`
- `git diff --check`

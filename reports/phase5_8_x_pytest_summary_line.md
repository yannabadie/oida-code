# Phase 5.8.x — pytest_summary_line + Tier 5 operator soak gate cleared

**Status: complete (commit bc11711).** ADR-47 + ADR-48 logged.

## What shipped

Two related deliverables landed across this phase:

1. **Phase 5.8.x adapter follow-up (ADR-47, commits 93c7581 + c7734b3).** A
   `pytest_summary_line: str | None = None` field on
   `VerifierToolResult` (frozen Pydantic, max_length=400), populated by a
   generic `extract_summary_line(stdout) -> str | None` hook on the base
   `ToolAdapter` (`PytestAdapter` overrides with a regex parser that
   scans stdout bottom-up and the LAST summary-shaped line wins). The
   line is also folded into the synthesised `[E.tool.pytest.0]`
   `EvidenceItem.summary` parenthetical so the operator-facing surface
   (which only reads `evidence_items[*].summary`) exposes the counts. A
   follow-up fix (commit c7734b3) strips ANSI SGR escapes before the
   regex match because targets that pin `addopts = "--color=yes"` in
   their pyproject.toml emit colored output through subprocess pipes
   (discovered while preparing case_004).

2. **Tier 5 operator soak gate cleared (ADR-48, commits 0282c40 →
   bc11711).** case_003 re-dispatched (run 25047711777) so cgpro could
   relabel UX 2/1/2/2 → 2/2/2/2 with the new evidence shape; case_004
   (un33k/python-slugify@7edf477, claim_type=precondition_supported,
   run 25050370380) and case_005 (alecthomas/voluptuous@4cef6ce,
   claim_type=capability_sufficient, run 25051323517) authored as real
   audit packets and dispatched. cgpro labelled both
   useful_true_positive UX 2/2/2/2 on first pass. Aggregate flips
   from `continue_soak` to `document_opt_in_path` per aggregator rule 5
   (cases_completed>=5 AND usefulness_rate>=0.6). `enable-tool-gateway`
   remains default false in the composite Action regardless.

## Acceptance evidence

### Quality gates on commit bc11711

```
ruff:   All checks passed!
mypy:   Success: no issues found in 98 source files
pytest: 960 passed, 4 skipped in 144s
```

Test count delta over the phase:
- Before Phase 5.8.x: 943 passed / 4 skipped
- After ADR-47 schema + parser tests: 958 passed / 4 skipped (+15)
- After ANSI-strip regression tests: 960 passed / 4 skipped (+2)
- After case_004 + case_005 sidecars + Tier 5 rename: 960 passed / 4 skipped (no
  net delta — case_004/005 are integration cases not unit tests; the
  Tier 3/4/5 promotion test was renamed in place)

### CI on bc11711

All 6 GitHub-hosted workflows green:

| Workflow | Run ID |
|---|---|
| ci | 25051850793 |
| action-smoke | 25051850817 |
| provider-baseline-node24-smoke | 25051850781 |
| gateway-grounded-smoke | 25051850768 |
| gateway-calibration | 25051850763 |
| action-gateway-smoke | 25051850782 |

### Operator-soak runs

| Run | Case | Target | Outcome |
|---|---|---|---|
| 25047711777 | case_003 re-dispatch | pallets/markupsafe@7856c3d | success — pytest_summary_line="29 passed in 0.03s"; UX 2/1/2/2 → 2/2/2/2 |
| 25050370380 | case_004 first dispatch | un33k/python-slugify@7edf477 | success — pytest_summary_line="83 passed in 0.07s"; useful_true_positive UX 2/2/2/2 |
| 25051323517 | case_005 first dispatch | alecthomas/voluptuous@4cef6ce | success — pytest_summary_line="167 passed in 0.17s"; useful_true_positive UX 2/2/2/2 |

All three runs: `gateway-status=diagnostic_only`,
`gateway-official-field-leak-count=0`, ADR-22 hard wall preserved.

### Aggregate snapshot (reports/operator_soak/aggregate.md)

```
cases_total: 5
cases_completed: 5
useful_true_positive_count: 5
useful_true_negative_count: 0
false_positive_count: 0
false_negative_count: 0
unclear_count: 0
insufficient_fixture_count: 0
contract_violation_count: 0
official_field_leak_count: 0

operator_usefulness_rate: 1.000
summary_readability_avg: 2.000
evidence_traceability_avg: 2.000
actionability_avg: 2.000
no_false_verdict_avg: 2.000

Recommendation: document_opt_in_path
```

### Five-case shape diversity

| Case | Repo | Claim type | Strategy |
|---|---|---|---|
| 001 | yannabadie/oida-code (self-audit) | negative_path_covered | docstring change with no behavior delta |
| 002 | python-semver/python-semver | negative_path_covered | cross-repo no-install (pure-Python single file) |
| 003 | pallets/markupsafe | observability_sufficient | cross-repo C-extension install (target_install=true) |
| 004 | un33k/python-slugify | precondition_supported | cross-repo CLI-precondition install (target_install=true) |
| 005 | alecthomas/voluptuous | capability_sufficient | cross-repo capability install (target_install=true) |

## Honesty statement

Phase 5.8.x adds a structured pytest summary field plus an ANSI-strip
fix to the gateway adapter; it does not implement MCP; it does not
enable provider tool-calling; it does not allow write tools or network
egress; it does not validate production predictive performance; it
does not tune production thresholds; it does not emit official
`total_v_net` / `debt_final` / `corrupt_success`; it does not modify
the vendored OIDA core. The Tier 5 promotion gate clears the
diagnostic recommendation from `continue_soak` to
`document_opt_in_path` — the action default `enable-tool-gateway`
stays `"false"` regardless. The Phase 4.7 + Phase 5.0 + Phase 5.1 +
Phase 5.2 + Phase 5.3 + Phase 5.4 + Phase 5.5 + Phase 5.6 + Phase 5.7
+ Phase 5.8 anti-MCP locks remain ACTIVE.

## Pre-existing operator-soak warning

Each operator-soak.yml run emits a benign warning on the outer
upload step:

```
##[warning]No files were found with the provided path: oida-main/.oida/**.
No artifacts will be uploaded.
```

This warning is **pre-existing across all soak runs** (25045245609,
25047711777, 25050370380, 25051323517 — and the earlier case_001 +
case_002 runs). The actual gateway artefact comes from the composite
action's inner `oida-code-gateway` upload step, which works correctly
on every run. The outer upload step's `oida-main/.oida/**` glob
returns no matches because the composite action writes to a
different path that the outer step does not resolve. Not a fix-now;
documented here so future Claude does not re-investigate.

## Next phase decision

Per the QA cadence the next phase is gated on operator decision.
`document_opt_in_path` is a diagnostic recommendation — it does NOT
flip the action default. Phase 5.9 would document the opt-in
gateway-grounded path with the operator-facing audit
methodology written up; Phase 6.0+ remains MCP-deferred until further
operator soak data lands.

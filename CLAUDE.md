# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install (dev): `python -m pip install -e ".[dev]"`

Quality gates (run all three before claiming a block complete — the QA review checks all of them):

```bash
python -m ruff check src/ tests/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py
python -m mypy src/ scripts/evaluate_shadow_formula.py scripts/real_repo_shadow_smoke.py
python -m pytest -q
```

Run one test file or a single test:

```bash
python -m pytest tests/test_phase4_1_verifier_contract.py -v
python -m pytest tests/test_phase4_1_verifier_contract.py::test_forward_only_is_not_enough -v
```

CLI subcommands (defined in `src/oida_code/cli.py`):

| Command | Purpose |
|---|---|
| `oida-code inspect <repo> --base <rev> --out request.json` | Pass-1 deterministic facts collector |
| `oida-code audit <repo> --base <rev> --intent ticket.md --format markdown --out report.md` | Full deterministic audit (Phase 1 path) |
| `oida-code normalize <request.json> --surface impact\|changed` | Build NormalizedScenario from request |
| `oida-code score-trace <trace.jsonl> --request <r> --surface impact [--experimental-shadow-fusion]` | Trajectory scorer + opt-in shadow fusion |
| `oida-code estimate-llm <packet.json> --llm-provider replay --llm-response-fixture <reply.json>` | Phase 4.0 LLM estimator dry-run |
| `oida-code verify-claims <packet.json> --forward-replay <r> --backward-replay <r>` | Phase 4.1 forward/backward verifier |

Standalone evaluation scripts:

```bash
python scripts/evaluate_shadow_formula.py        # E2 sensitivity sweep + graph ablation; writes .oida/e2/
python scripts/real_repo_shadow_smoke.py         # E2 shadow smoke on oida-code self + attrs
python scripts/real_repo_smoke.py                # D3 structural smoke
python scripts/paper_sanity_check.py             # D1 paper-conformance checks
```

`oida-code audit` shells out to `ruff` / `mypy` / `pytest` / `semgrep` / `codeql` via `shutil.which`. Run it from inside the **target** repo's venv so `pytest` and `mypy` see the target's installed packages. Missing tools become `status="tool_missing"` in the report — never a crash.

**Windows note**: `pytest` invocations must run in the foreground. There is a per-repo memory feedback (`feedback_windows_fork_pressure.md`) that running pytest with `run_in_background` triggers exponential Cygwin fork costs through self-audit tests that re-invoke the CLI.

## Architecture

### The hard wall: official fusion fields stay null

**ADR-22, ADR-24, ADR-25, ADR-26 are non-negotiable.** No code path may emit `total_v_net`, `debt_final`, `corrupt_success`, `corrupt_success_ratio`, or `verdict` in a Pydantic model dump. Enforcement is layered:

1. The schemas don't expose those fields (e.g. `ShadowFusionReport`, `EstimatorReport`, `VerifierAggregationReport`).
2. `authoritative` is pinned to `Literal[False]` on shadow + verifier reports — not just defaulted, **pinned**, so any attempt to set `True` fails Pydantic validation.
3. Runners check raw response bodies for forbidden phrases (V_net / debt_final / corrupt_success / verdict / merge_safe / production_safe / bug_free / security_verified / official_*) and reject the entire response if any appears.
4. Tests (`test_*_no_official_fields`, `test_official_summary_fields_still_null_in_e3`, `test_official_ready_candidate_is_unreachable_at_v0_4_x`) parametrize over every fixture and assert no leakage.

When adding a new schema or runner, add it to the forbidden-phrase chain — never just trust the default.

### The three architecture rules (PLAN.md §4)

1. **Truth does not come from the LLM.** Evidence flows from tools, tests, counter-examples, proven properties, static alerts. The LLM plans / explains / proposes — it never replaces a passing test, and `is_authoritative=True` is rejected for `source="llm"` at the model level.
2. LongCoT and Simula are Phase 7 research moat — off the critical path.
3. No "mathematical proof of arbitrary code" claim, ever.

### Vendored OIDA core (ADR-02)

`src/oida_code/_vendor/oida_framework/` is a frozen copy of the OIDA v4.2 reference implementation. SHA256-pinned in `VENDORED_FROM.txt`. Reuse, do not rewrite. ruff and mypy explicitly **exclude** `_vendor/` (see `pyproject.toml`); modifying it would diverge from upstream. Refresh = re-copy + recompute SHA + bump `VENDORED_FROM.txt`.

The translator between Pydantic public surface and the vendored dataclass core lives in `src/oida_code/score/mapper.py` (`pydantic_to_vendored`, `vendored_to_pydantic`).

### Module layout

```
src/oida_code/
├── _vendor/oida_framework/    OIDA v4.2 core (verbatim; do not edit)
├── models/                    Pydantic v2 public surface (extra="forbid")
├── extract/                   Obligation extractor + dependency graph + audit-surface derivation
├── verify/                    Deterministic runners (ruff, mypy, pytest, semgrep, codeql, hypothesis, mutmut)
├── score/                     Trajectory scorer, fusion readiness, shadow fusion, mapper, event_evidence
├── estimators/                Phase 4.0 — frozen estimate contracts + deterministic baselines + LLM dry-run
├── verifier/                  Phase 4.1 — forward/backward verifier contracts + aggregator + replay providers
├── report/                    Markdown / JSON report rendering
├── github/                    GitHub Action + Checks API integration (Phase 6)
├── ingest/                    Trace parsers (Claude Code transcripts, etc.)
└── cli.py                     Typer entry point
```

### Block / phase cadence

The project ships in named blocks driven by external review files in `QA/A*.md`. Each block:

1. Receives a directive in `QA/A<n>.md` listing acceptance criteria, forbidden actions, expected tests, and the report filename.
2. Lands as one commit with `feat(phase<n>-<block>):` or `feat(phase<n>):`, an ADR appended to `memory-bank/decisionLog.md` (timestamped), a report under `reports/<block>.md`, and tests covering every listed criterion.
3. Updates README + `memory-bank/progress.md` with the new test count and status line.
4. Validates via the next `QA/A<n+1>.md` review file before the next block starts.

Current blocks: **Phase 3.5** (A→D structural pipeline) → **E0–E3** (fusion readiness, shadow fusion, formula decision, estimator contracts) → **Phase 4.0** (LLM estimator dry-run) → **4.0.1** (fence hardening) → **Phase 4.1** (forward/backward verifier contract). Reports for each block under `reports/`.

### ADR discipline

Every architectural decision lives in `memory-bank/decisionLog.md` as a timestamped block:

```
[YYYY-MM-DD HH:MM:SS] - **ADR-NN: <one-line decision>.**
**Why:** ...
**Decision:** ...
**Accepted:** ...
**Rejected:** ...
**Outcome:** ...
```

Append, never overwrite. When code references an ADR (e.g. `# ADR-22 §5 Option B`), search `decisionLog.md` for the full text — code comments only carry the pointer, not the rationale.

### Forbidden in any commit

- Modifying `src/oida_code/_vendor/**` (ADR-02).
- Calling an external LLM API by default. The opt-in providers (`OptionalExternalLLMProvider`, `OptionalExternalVerifierProvider`) are stubs that raise `*ProviderUnavailable` whether the env var is set or not — Phase 4.2 will introduce real bindings under a follow-up ADR.
- Echoing env-var values in logs, exceptions, reports, or commits. There are explicit `test_*_does_not_leak_secrets` guards.
- Bumping the PyPI version to a non-alpha tag while official fields are still blocked.
- Adding tests that claim predictive validation (Spearman, commits>0 correlation, etc.). Phase 3 already tripped on a length-confound proxy; Phase 3.5+ enforces "structural validation only".

### Pydantic patterns specific to this repo

- `ConfigDict(extra="forbid", frozen=True, validate_assignment=True)` on every report-shaped model. Frozen prevents post-construction mutation; `validate_assignment` rejects re-validation attempts.
- `Literal[False]` pin (instead of `bool = False`) for any field that must never become `True` in production.
- Public collections are `tuple[...]`, not `list[...]` — list mutators (`append`, `extend`, slice assignment) are unavailable on the public surface.
- Model-level `@model_validator(mode="after")` for cross-field invariants (e.g. `source="default"` ⇒ `confidence=0.0` ⇒ `is_default=True`).

### Prompt-injection defence (4.0.1 hardening)

User-supplied evidence text in `LLMEvidencePacket.evidence_items[*].summary` is wrapped in named per-item fences:

```
<<<OIDA_EVIDENCE id="[E.event.1]" kind="event">>>
...untrusted data...
<<<END_OIDA_EVIDENCE id="[E.event.1]">>>
```

`_neutralise_fence_close` inserts a zero-width space inside any literal `<<<END_OIDA_EVIDENCE` or `<<<OIDA_EVIDENCE` in user content so a forged inner close cannot truncate the block. The fence is one defence layer — runners additionally enforce forbidden-phrase rejection, schema validation, and citation rules independently. Don't rely on the fence alone.

### Memory bank protocol (.github/*.chatmode.md)

`memory-bank/` carries the long-running project context: `productContext.md`, `activeContext.md`, `systemPatterns.md`, `decisionLog.md`, `progress.md`, `architect.md`. Append timestamped entries; never overwrite. The "UMB" / "Update Memory Bank" command in chatmode files refreshes all five at once.

## Important docs to read before non-trivial changes

- `oida-code-mvp-blueprint.md` — authoritative spec.
- `PLAN.md` — phase decomposition (§14 Phase 0-7).
- `memory-bank/systemPatterns.md` — 3-pass pipeline, 4-bucket verdict, OIDA scoring formulas, vendoring discipline.
- `memory-bank/decisionLog.md` — full ADR history (ADR-01 … ADR-26).
- The relevant `reports/<block>.md` for whichever block you're touching.
- The latest `QA/A<n>.md` directive (currently QA/A16.md — Phase 4.1 validation + Phase 4.2 plan).

# Progress

**Active plan: `PLAN.md`** (merged blueprint + roadmap, 2026-04-24).
The schedule below uses `PLAN.md` §14 Phase 0-7 numbering, not the original `prompt.md` Phase-1/2/3/4 wording.

## Done

- [x] Initialize project (workspace scaffolding, brainstorm docs).
- [x] **Phase 0 — cadrage + bootstrap** (2026-04-23 → 2026-04-24). Commits `15138f3..1733f98` on `main`. See `PHASE1_REPORT.md` (titled for historical reasons; describes Phase 0 output).
  - Context digest (10 mandatory docs read).
  - Public repo `yannabadie/oida-code` created (MIT, `main` tracked).
  - Blueprint §7 tree scaffolded under `src/oida_code/`.
  - Pydantic I/O models v1 (`AuditRequest`, `NormalizedScenario`, `AuditReport`).
  - Vendored OIDA core (SHA256-pinned in `VENDORED_FROM.txt`).
  - Typer CLI with `inspect` implemented; 4 other subcommands `NotImplementedError` with phase pointers.
  - 4 quality gates green: ruff ✓, mypy --strict ✓ (41 files), pytest 10/10 ✓, `oida-code inspect` deserializes. Coverage 74%.
  - memory-bank populated with real content (6 files + 12 ADRs).
- [x] **Merge blueprint + roadmap into `PLAN.md`** (2026-04-24). ADR-10/11/12 logged.

## Doing

- [ ] Nothing. Waiting for user "go Phase 1" before starting the deterministic-audit layer.

## Next — Phase 1 (deterministic audit · 2-3 weeks, per `PLAN.md` §14)

**Entry gate:** Phase 0 shipped (met).

**Scope:**
- [ ] `verify/lint.py` — wrap `ruff check --output-format=json` (Python-only v0).
- [ ] `verify/typing.py` — wrap `mypy --output-format=... ` (JSON or strict-mode stdout parse).
- [ ] `verify/pytest_runner.py` — invoke `pytest --json-report` (or JUnit-XML), parse pass/fail/errors, feed the `regression` term of `tests_pass`.
- [ ] `verify/semgrep_scan.py` — `semgrep --json` with a starter ruleset.
- [ ] `verify/codeql_scan.py` — `codeql database analyze` CLI wrapper (Python pack first). Degraded-OK if CodeQL CLI missing.
- [ ] `extract/blast_radius.py` — minimal heuristic (changed-modules × fan-out) to populate `AuditRequest.policy`-relative `blast_radius`.
- [ ] `ingest/manifest.detect_commands` — pyproject / setup.py / requirements.txt / Pipfile auto-detection.
- [ ] `report/json_report.py` — write a v1 `AuditReport`.
- [ ] `report/markdown_report.py` — human-readable summary for PR comment body.
- [ ] `report/sarif_export.py` — SARIF 2.1.0 for GitHub code-scanning.
- [ ] `score/verdict.py` — deterministic-path verdict resolver (no LLM yet): `verified` if all evidence present + grounding ≥ threshold; `counterexample_found` on any failing test / surviving mutant / high-severity Semgrep; `insufficient_evidence` otherwise. `corrupt_success` stays dark until Phase 5.
- [ ] `cli.py` — wire `oida-code normalize`, `verify`, and `audit` (deterministic path); add `--intent PATH`, `--format {json,sarif,markdown}`, `--fail-on {any_critical,corrupt,none}`.

**Exit criterion:** Stable report on **10 Python repos without human intervention**. JSON + SARIF + Markdown outputs all validate against their schemas. No crashes. CodeQL may be optional (gated on CLI availability).

## Phase 2 — observation model + obligation graph (2 weeks)

**Entry gate:** Phase 1 shipped.

Deliverables: `models/trace.py`, `models/obligation.py`, `models/progress_event.py`, `extract/obligation_graph.py`, `extract/{claims,preconditions,dependencies}.py`, `score/mapper.py`, `verify/hypothesis_runner.py`, `verify/mutmut_runner.py`, **50-100 hand-annotated PR traces** in `datasets/traces_v1/`.

Exit criterion: can describe action-by-action where an agent explores / exploits / stagnates / loops on a real PR. Obligation-extraction recall ≥ 60% on the annotated set.

## Phase 3 — Explore/Exploit adapter (2 weeks)

Deliverables: `score/trajectory.py`, correlation dashboard (Jupyter or Streamlit in `notebooks/`).

Exit criterion: scorer distinguishes "didn't find" (exploration error) vs "found but didn't use" (exploitation error). Spearman ρ > 0.5 against human labels on Phase 2 dataset.

## Phase 4 — agentic verifier (2 weeks, blocked on M.2 2TB upgrade)

Deliverables: `llm/{client,schemas,forward_verifier,backward_verifier}.py`, extended `score/verdict.py`, CLI `--llm-endpoint --offline`.

Exit criterion: multi-turn verifier beats single-pass LLM judge on Phase 2 annotated set.

## Phase 5 — OIDA fusion + repair (2 weeks)

Deliverables: `score/{fusion,repair}.py`, `llm/repair_prompts.py`, CLI `repair` wired.

Exit criterion: can explain every red/yellow verdict on a PR with evidence, not vibes.

## Phase 6 — product surface (2 weeks)

Deliverables: `.github/workflows/oida-code.yml`, `github/{checks,annotations}.py`.

Exit criterion: dev installs tool in <15 min and sees useful verdict inside a PR. Demo on 10 intentionally sloppy PRs with false-positive / false-negative table recorded before any threshold tuning.

## Phase 7 — research moat (months 4-6, off critical path)

LongCoT-Mini → full benchmark harness; Simula-driven synthetic dataset v1; Dafny proof modules for 2-3 critical invariants; TypeScript start.

Exit criterion: measurable moat (corrupt-success F1 on adversarial dataset + long-horizon critic robustness plot).

---
[2026-04-23 21:57:00] - Phase 1 bootstrap kicked off from `prompt.md`.
[2026-04-24 07:04:50] - Phase 1 Steps 0-4 complete. All quality gates green. Moving to Step 5 (report + stop).
[2026-04-24 07:45:00] - Merge: `prompt.md` "phase 1 bootstrap" retroactively relabeled **Phase 0** to match `PLAN.md` §14. `PHASE1_REPORT.md` kept as historical artifact (describes Phase 0 output). Next = Phase 1 deterministic audit, awaiting user "go".
